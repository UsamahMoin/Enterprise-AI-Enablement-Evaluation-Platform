"""Local (self-hosted) provider and the governance consequences of using one.

The provider is exercised against a fake OpenAI-compatible server rather than a
real local runtime, so these tests are fast, deterministic and run in CI. What
they verify is the contract: the wire format the provider speaks, and the fact
that a provider with no moderation endpoint cannot look like one that checked
and found nothing.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.core.enums import DataClassification
from app.services.ai.base import GenerationRequest
from app.services.ai.local_provider import LocalProvider, LocalProviderUnavailable
from app.services.ai.pricing import estimate_cost
from app.services.evaluation.scoring import compute_overall

RECEIVED: list[dict] = []


class _FakeLocalServer(BaseHTTPRequestHandler):
    """Minimal stand-in for Ollama / LM Studio's OpenAI-compatible API."""

    def log_message(self, *args):  # noqa: A002 - silence test output
        pass

    def do_GET(self):  # noqa: N802
        if self.path.endswith("/models"):
            self._json(200, {"object": "list", "data": [{"id": "test-model", "object": "model"}]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        RECEIVED.append(body)

        if body.get("model") == "explode":
            self._json(500, {"error": {"message": "model crashed"}})
            return

        content = '{"relevance": 88, "completeness": 81, "groundedness": null, "reasoning": "ok"}'
        self._json(
            200,
            {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 0,
                "model": body.get("model", "test-model"),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 120, "completion_tokens": 40, "total_tokens": 160},
            },
        )

    def _json(self, status: int, payload: dict):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def local_server():
    RECEIVED.clear()
    server = HTTPServer(("127.0.0.1", 0), _FakeLocalServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/v1"
    server.shutdown()
    server.server_close()


async def test_generates_against_an_openai_compatible_server(local_server):
    provider = LocalProvider(base_url=local_server, model="test-model")
    response = await provider.generate(
        GenerationRequest(
            system_prompt="You evaluate output.",
            user_prompt="Score this.",
            model="test-model",
        )
    )

    assert response.provider == "local"
    assert response.input_tokens == 120
    assert response.output_tokens == 40
    assert response.latency_ms >= 0
    assert json.loads(response.text)["relevance"] == 88


async def test_uses_chat_completions_not_the_responses_api(local_server):
    """Local runtimes implement the older surface; this is why the provider is
    a separate implementation rather than OpenAIProvider with another URL."""
    provider = LocalProvider(base_url=local_server, model="test-model")
    await provider.generate(
        GenerationRequest(system_prompt="s", user_prompt="u", model="test-model")
    )

    body = RECEIVED[-1]
    assert [message["role"] for message in body["messages"]] == ["system", "user"]
    assert "input" not in body  # Responses-API shape must not leak in


async def test_schema_is_described_in_the_prompt_not_enforced_strictly(local_server):
    """Smaller local models comply with json_object plus a described schema far
    more reliably than with strict json_schema."""
    provider = LocalProvider(base_url=local_server, model="test-model")
    await provider.generate(
        GenerationRequest(
            system_prompt="You evaluate output.",
            user_prompt="Score this.",
            model="test-model",
            json_schema={
                "name": "evaluation",
                "schema": {"type": "object", "properties": {"relevance": {"type": "number"}}},
            },
        )
    )

    body = RECEIVED[-1]
    assert body["response_format"] == {"type": "json_object"}
    assert "JSON Schema" in body["messages"][0]["content"]
    assert "relevance" in body["messages"][0]["content"]


async def test_unreachable_server_raises_a_useful_error():
    provider = LocalProvider(base_url="http://127.0.0.1:9/v1", model="test-model")
    with pytest.raises(LocalProviderUnavailable) as exc:
        await provider.generate(
            GenerationRequest(system_prompt="s", user_prompt="u", model="test-model")
        )
    assert "127.0.0.1:9" in str(exc.value)


async def test_server_error_is_reported_not_swallowed(local_server):
    provider = LocalProvider(base_url=local_server, model="explode")
    with pytest.raises(LocalProviderUnavailable):
        await provider.generate(
            GenerationRequest(system_prompt="s", user_prompt="u", model="explode")
        )


async def test_health_reports_reachability_and_models(local_server):
    provider = LocalProvider(base_url=local_server, model="test-model")
    health = await provider.health()

    assert health["reachable"] is True
    assert "test-model" in health["models"]
    assert health["default_model_present"] is True


async def test_health_does_not_raise_when_unreachable():
    health = await LocalProvider(base_url="http://127.0.0.1:9/v1").health()
    assert health["reachable"] is False
    assert health["error"]


async def test_moderation_is_reported_unavailable_never_clean():
    """The distinction the whole governance change rests on."""
    result = await LocalProvider(base_url="http://127.0.0.1:9/v1").moderate("anything")

    assert result.available is False
    assert result.flagged is False  # not an assertion of cleanliness
    assert LocalProvider.supports_moderation is False


def test_self_hosted_inference_has_no_per_token_price():
    assert estimate_cost("qwen3:8b", 10_000, 5_000, provider="local") == 0.0
    # ...but the same token counts on a hosted provider are not free.
    assert estimate_cost("gpt-4.1-mini", 10_000, 5_000, provider="openai") > 0


def test_local_provider_is_cleared_for_restricted_data():
    assert LocalProvider.max_data_classification == DataClassification.RESTRICTED
    assert LocalProvider.keeps_data_in_house is True


def test_unchecked_safety_is_dropped_from_the_score_not_awarded_full_marks():
    scores = {"relevance": 80.0}
    weights = {"relevance": 0.5, "safety": 0.5}

    passed = compute_overall(scores, weights, safety_passed=True, safety_checked=True)
    unchecked = compute_overall(scores, weights, safety_passed=True, safety_checked=False)
    failed = compute_overall(scores, weights, safety_passed=False, safety_checked=True)

    assert passed == 90.0  # 80 relevance + 100 safety, evenly weighted
    assert unchecked == 80.0  # safety dropped and weights renormalised
    assert failed == 40.0
    # An unchecked run must not score as well as one that was checked and passed.
    assert unchecked < passed

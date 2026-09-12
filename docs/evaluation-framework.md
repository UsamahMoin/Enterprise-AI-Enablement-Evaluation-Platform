# Evaluation framework

Three layers, chosen for different trade-offs. No layer is treated as ground
truth on its own — including the human one.

| Layer | Cost | Reproducible | Catches | Misses |
|---|---|---|---|---|
| 1. Deterministic | free | exactly | structure, syntax, forbidden terms | whether the content is any good |
| 2. LLM-as-judge | ~1 extra call | approximately | relevance, completeness, groundedness | its own blind spots, shared with the model it grades |
| 3. Human review | expensive | no | what the person actually needed | scale |

## Level 1 — deterministic checks

Ordinary Python functions in `services/evaluation/deterministic.py`. Each
workflow's rubric declares which apply.

- `valid_json`, `required_json_fields` — structured extraction actually parsed
- `required_sections` — the fixed heading set a finance narrative must carry
- `max_length`, `min_words` — degrades gradually rather than failing at limit + 1
- `prohibited_terms` — e.g. a hiring recommendation in an interview summary
- `code_block_present`, `code_syntax` — generated Python is parsed with `ast`
- `test_coverage_concepts` — does the test output reason beyond the happy path

Their mean becomes the **format compliance** dimension.

These run first because they are free and exact. A response that fails
`valid_json` does not need a model to tell you it is unusable.

## Level 2 — LLM-as-judge

A second model call scores the output against the workflow rubric and must
return structured JSON — never prose. It receives the task, the user input, the
generated response, and any reference material the workflow designates.

Three rules make the judge useful rather than decorative:

1. **Structured output.** A JSON schema with `strict: true`. A judge that
   returns paragraphs cannot be aggregated, trended, or compared across versions.
2. **Temperature 0.** The judge is measurement, not generation.
3. **Null over guessing.** If no reference material was supplied, groundedness
   returns `null` and is dropped from the weighted score — not scored zero, and
   not invented.

## Groundedness, not "hallucination detection"

This platform does not claim to detect hallucinations. It measures
**groundedness**: whether the claims in an output are supported by reference
material the user supplied.

That distinction is doing real work. Given a travel policy stating that
international meals are reimbursed up to $80 per day, an output asserting $120
per day can be scored low with a defensible reason: *the response conflicts with
the source document*. Without a source, "is this true?" is not a question the
system can answer, and pretending otherwise would be the more impressive claim
and the less honest one.

Workflows declare which input fields are the source of truth via
`grounding_fields`. `draft_customer_response` grounds against the pasted policy;
`explain_variance_report` grounds against the figures. Where nothing is
supplied, the dimension reads N/A in the UI, with an explanation.

## Scoring

Weights live on the workflow rubric, not in one global constant, because
structured extraction and a customer-facing email do not deserve the same
weighting. The default:

| Dimension | Weight |
|---|---|
| Relevance | 30% |
| Completeness | 25% |
| Groundedness | 25% |
| Format compliance | 10% |
| Safety | 10% |

`explain_variance_report` raises groundedness to 45%. `generate_unit_tests`
drops it entirely and puts 35% on format compliance, because the deterministic
checks (does it parse, does it cover error paths) are the meaningful signal
there.

Dimensions that are not applicable are removed and the remaining weights
renormalised, so an N/A never silently behaves like a zero.

## Level 3 — human review

Approve / needs editing / reject, plus an optional 1–5 rating and comment.

"Needs editing" is the most informative verdict: the workflow is close, and the
comment tells whoever owns the prompt what to fix. Only **approved** outputs
count toward effective adoption and estimated time saved.

## Why both automated and human layers are kept

The quality dashboard shows the model judge's average score directly beside the
human approval rate, and reports the gap between them.

When those two diverge, the rubric is usually wrong. You only ever see that
divergence by measuring both. Automated evaluation is what makes scoring every
single execution affordable; it is not a substitute for the person who had to
use the output.

## Benchmark cases

`seed/evaluation_cases.json` holds 29 fixed cases across the five flagship
workflows, spanning seven input types: normal, excellent, poor, ambiguous,
adversarial, sensitive and malformed.

```bash
python -m app.benchmark --workflow explain_variance_report --versions 1 2
```

Running the same fixed set against each prompt version compares them on
identical work, rather than on whatever traffic happened to arrive. Cases marked
`expected_behaviour: block` are scored on whether governance stopped them, not
on output quality — and the runner executes governance with recording disabled,
because a synthetic case that is supposed to be blocked is not a real policy
breach by a real person.

Two cases are worth reading on their own: `variance_groundedness_trap_1` supplies
amounts with no stated causes, so any confident "driven by the Q3 brand
campaign" is ungrounded; and `support_groundedness_trap_1` has a customer assert
a discount the supplied policy contradicts.

## Known limitations

- The judge shares failure modes with the model it grades.
- `test_coverage_concepts` is a keyword heuristic, not coverage measurement.
- Benchmark cases are small and hand-written; they catch regressions, they do
  not establish statistical significance. The comparison read-out says so.
- Human feedback is voluntary, so approval rates carry selection bias.

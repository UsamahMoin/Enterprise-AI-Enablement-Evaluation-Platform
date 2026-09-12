# Responsible AI

Scope: this is a prototype built on synthetic data. It is written to show how
these controls fit together, not to certify compliance with any framework.

## Risk classification

Every workflow carries a tier that determines what the platform will do with it.

| Tier | Meaning | Platform behaviour | Examples here |
|---|---|---|---|
| **LOW** | A wrong answer costs a few minutes | Runs; review optional | Meeting summary, code explanation, ticket triage |
| **MEDIUM** | A wrong answer reaches someone outside the team | Runs; review encouraged | Customer reply, job description, campaign copy |
| **HIGH** | A wrong answer affects a person or a financial statement | Runs; human review required | Variance analysis, financial narrative, interview summary |
| **PROHIBITED** | Not an acceptable use | Blocked before generation | Automated adverse employment decisions |

The prohibited tier is the important one. `auto_reject_applicant` is registered
in the catalogue deliberately: the boundary is visible, auditable, and enforced
in code rather than living in a policy document nobody reads.

The underlying rule: **a model may draft, summarise, classify and explain. It
does not make an adverse decision about a person.** This is why the HR workflows
improve a job posting and summarise interview notes against agreed criteria, but
there is no candidate ranking or scoring workflow — that is a materially
different risk profile, not a feature that was left for later.

## Data classification

Each workflow is approved for a maximum sensitivity of input.

| Class | Permitted categories |
|---|---|
| PUBLIC | Nothing personal |
| INTERNAL | Contact details, with a warning |
| CONFIDENTIAL | Business-sensitive content |
| RESTRICTED | Government IDs, payment cards, secrets |

Detectors carry the lowest classification at which their category is acceptable.
An SSN requires RESTRICTED, so it is blocked on every workflow in this
catalogue. Email addresses and phone numbers require INTERNAL, so they produce a
warning the user must acknowledge rather than a block — blocking every email
address would stop ordinary work and train people to route around the platform,
which is worse for safety than a warning they read.

## Where inference happens

Detection reduces accidental exposure. Self-hosting removes the egress. The
platform treats the data-classification ceiling as a property of the provider,
not only of the workflow.

| Provider | Data stays in-house | Max classification | Moderation |
|---|---|---|---|
| `openai` | No — egress | CONFIDENTIAL | Available |
| `local` (Ollama, LM Studio, llama.cpp, vLLM) | Yes | RESTRICTED | **None** |
| `stub` | Yes (offline fixtures) | RESTRICTED | Keyword screen only |

The limit applied to a request is the **stricter** of the two. A workflow
cleared for RESTRICTED data is still blocked at CONFIDENTIAL when routed to a
hosted provider, and the block message says which limit applied and why. A
self-hosted provider never *loosens* a workflow that is approved for less.

These are declared capabilities on the provider class. The governance code
reads them; it does not test for vendor names.

### The cost of self-hosting: no moderation

Local runtimes have no moderation endpoint. This is a real control gap
introduced by the privacy gain, and the platform is built so it cannot be
hidden:

1. `ModerationResult.available` separates **"not checked"** from **"checked and
   clean"**. A provider with no endpoint cannot return a result that looks like
   a pass.
2. The safety dimension is dropped from the weighted score and the remaining
   weights renormalised. Awarding full safety marks for a check that never ran
   would inflate the score of exactly the configuration deserving most scrutiny.
3. `MODERATION_PROVIDER` delegates the check to a provider that can perform it —
   generate locally, moderate elsewhere.
4. `MODERATION_FAIL_CLOSED=true` rejects input nobody could check. Off by
   default so the offline demo runs; on is what a regulated deployment chooses.
5. The execution UI shows **Safety NOT CHECKED** in amber with the reason, and
   the governance screen lists each provider's moderation capability.

### Independent evaluation

`EVALUATION_PROVIDER` is configured separately from `AI_PROVIDER`. A model
grading its own output shows self-preference bias; judging with a different
provider is a cheap mitigation. It also allows sensitive output to be evaluated
on self-hosted infrastructure while generation stays hosted, or the reverse.

## The pre-execution pipeline

```
input → sensitive-data check → policy check → moderation → generation
```

A blocked request never reaches the provider. Its input is **not persisted**:
the execution row is written with empty inputs and a `BLOCKED` status.

## What the audit log stores

Categories and counts only.

```json
{"detections": [{"type": "SSN", "count": 1, "field": "code"}],
 "reason": "SSN detected; workflow is approved for INTERNAL data only."}
```

The matched value is never written to the database or the logs. Storing the
detection in order to prove you caught it would recreate the exposure you just
prevented.

## What the detection does not do

Pattern matching catches structured identifiers. It does not catch:

- a paragraph that identifies someone by circumstance rather than by an ID
- a screenshot, or a PDF pasted as an image
- a spreadsheet pasted as text with the sensitive column intact
- data that is sensitive because of context rather than format

The control is a backstop. It reduces accidental exposure; it is not DLP, and
the UI says as much where it appears. Production would sit real DLP in front of
this.

## Prompt injection

Instructions embedded in user-supplied content are a live risk, particularly for
workflows that ingest customer messages or third-party documents.

What is in place: system prompts state their constraints explicitly; benchmark
cases (`unit_tests_adversarial_1`, `jd_adversarial_1`) test whether an embedded
instruction is followed; and the workflow form is a fixed set of fields rather
than a free-text channel to the model.

What is not: there is no output-side injection detection, and a determined
injection against the judge itself is not defended. Structured judge output with
a strict schema limits the blast radius, it does not eliminate it.

## Human oversight

- HIGH-risk workflows require an approve / edit / reject decision.
- Approval is the only thing that counts toward effective adoption and estimated
  time saved, so the metrics cannot be inflated by volume alone.
- Managers see department aggregates, not colleagues' raw prompts. Monitoring
  adoption does not require reading individual employees' work.

## Model limitations users are told about

The learning centre says it plainly: fluency is not accuracy, the model has no
access to anything not in the prompt, and identical prompts can produce
different answers. The platform's own numbers carry the same discipline — "time
saved" is always labelled *estimated*, and the model judge is presented as a
signal beside human approval rather than as a verdict.

## Transparency

- The evaluation model, the rubric used and the judge's reasoning are stored per
  execution and shown in the UI.
- Prompt versions and their changelogs are visible to users, not just to admins.
- When the stub provider is active, the API health endpoint and the benchmark
  runner both say so, so nobody mistakes a fixture for model output.

## Deliberate gaps

Being explicit about what a prototype does not do is part of the point:

- No SSO, no SCIM, no per-tenant isolation
- No retention policy or scheduled deletion of execution history
- No bias testing of the workflows themselves
- No red-team exercise beyond the handful of adversarial benchmark cases
- No moderation model for self-hosted deployments; the gap is surfaced, not closed
- No incident process for a bad output that reached a customer

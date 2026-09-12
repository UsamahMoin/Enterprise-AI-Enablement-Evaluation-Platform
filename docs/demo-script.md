# Demo script

Roughly six minutes. Tells one story: Acme Corp bought AI licences and cannot
tell whether anything improved.

Setup: `docker compose up`, then wait for the seed to finish. Everything below
runs on the stub provider, so no API key and no spend.

---

## 0:00 — The problem (say this over the login screen)

> Acme Corp has 150 employees and enterprise AI licences for all of them.
> Leadership cannot answer three questions: who is actually using it, whether
> the output is any good, and whether anyone has pasted something into a prompt
> that should never have left the building.

## 0:30 — The employee's question is "what do I use this for?"

Sign in as **employee@demo.com**.

> Alex is a developer. He doesn't get a blank chat box — he gets the workflows
> approved for his role, each with a risk classification, a quality history and
> an estimated time saving.

Point at the 30-day panel: workflows completed, estimated time saved, average
evaluation score, approval rate, cost.

> Every one of those numbers comes from the database, not from a design mock.

## 1:15 — Run a real workflow

Open **Generate Unit Tests**. Paste:

```python
def calculate_total(items):
    total = 0
    for item in items:
        total += item
    return total
```

Add the constraint *"No external dependencies. Cover empty input."* and run it.

While it runs, point at the sidebar: when to use this, when **not** to —
"merging generated tests without reading them", "treating generated coverage as
proof the code is correct".

> That's the enablement half. The platform teaches the workflow, it doesn't just
> execute it.

## 2:00 — The evaluation panel is the point

> This is where it stops being a ChatGPT wrapper.

Walk the three layers:

- **Deterministic checks** — the code parses, there's a fenced block, the tests
  cover assertions, edge cases and error paths. Ordinary Python, free, exact.
- **The model judge** — relevance, completeness, clarity, with its reasoning.
- **Groundedness: N/A.** Stop here.

> No reference material was supplied, so groundedness is not scored. The system
> says N/A instead of inventing a number. I don't claim to detect
> hallucinations — I measure whether claims are supported by a source the user
> gave me. Without a source, that question isn't answerable.

Then latency, tokens, estimated cost. Approve the output.

> That approval is the third layer, and it's the only thing that counts toward
> time saved.

## 3:00 — Governance blocks a request

Run the same workflow again with:

```python
# Customer record for John Smith
# SSN: 123-45-6789
def calculate_total(items):
    return sum(items)
```

> Blocked before generation. The request never reached the provider, the input
> was not stored, and the audit record keeps the category and the count — never
> the value. Synthetic SSN, for the record.

## 3:45 — Now switch to the people paying for it

Sign out, sign in as **admin@demo.com**. Open **Analytics → Adoption**.

> 150 employees. 106 have ever used it. 83 were active this month. 77 produced
> an output somebody approved.

> Volume isn't value. "We sent 10,000 prompts" is not a result.

Scroll to department adoption.

> Engineering is at 68%. HR is at 28% — but HR's approval rate is 91%. The
> people using it there are getting good results; that's an awareness problem.
>
> Finance is different: 45% adoption and 69% approval. They're trying and the
> output isn't good enough. More training would be the wrong intervention.

## 4:45 — Follow the Finance problem to its cause

**Analytics → Quality**, point at Analyze Financial Variance below the
threshold. Then **Prompt versions**, select that workflow.

> v1 scored in the seventies. The groundedness scores showed why: given a report
> with amounts but no stated causes, it was inventing plausible drivers —
> "driven by the Q3 brand campaign".
>
> v2 requires the arithmetic to be shown, forbids unstated causes, and forbids
> forecasting. Quality and approval both move, and the read-out quantifies the
> cost change too, because v2 also runs on the larger model.

> That's prompt engineering as an evidence-based activity rather than a claim on
> a CV.

## 5:30 — Close on governance

**Governance**. Risk tiers, the pre-execution pipeline, the audit log with your
SSN block at the top.

> And this one — Automatically Reject Applicant, classified PROHIBITED. It's in
> the catalogue on purpose so the boundary is visible and enforced in code. The
> platform will not run it.

> A model can draft, summarise, classify and explain. It doesn't get to make an
> adverse decision about a person.

---

## If you have another minute

```bash
docker compose exec backend python -m app.benchmark \
  --workflow explain_variance_report --versions 1 2
```

> Twenty-nine fixed benchmark cases — normal, poor, ambiguous, adversarial,
> sensitive, malformed — run against each prompt version, so versions are
> compared on identical work instead of on whatever traffic arrived.

## Questions to expect

**"Is the AI real?"** The default is a stub provider so the demo runs with no
key and no spend; it returns deterministic fixtures. Set `AI_PROVIDER=openai`
and it makes real calls through the same interface. The stub ignores the system
prompt, so the benchmark runner refuses to present version comparisons as
meaningful while it's active.

**"Where did the numbers come from?"** A seeded synthetic dataset, generated
from fixed distributions with a fixed seed. The shape is deliberate — long-tailed
usage, lapsed users, one underperforming workflow — because a uniform dataset
makes every dashboard look the same and says nothing.

**"What would you do differently for production?"** SSO instead of local JWT,
real DLP in front of the pattern matching, a job queue for benchmarks,
per-tenant isolation, and a prompt approval workflow so publishing a version
isn't one admin clicking a button. They're listed in `docs/architecture.md`.

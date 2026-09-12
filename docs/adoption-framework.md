# Adoption framework

The question this platform exists to answer is not "how many prompts did we
send?" It is "is anyone actually better off?"

## The metric that matters most

```
Employees                    150
Ever used the platform       106
Active in the last 30 days    83   ← adoption
Produced an approved output   77   ← effective adoption
```

Three separate populations, deliberately not collapsed into one number:

- **Licensed** — has access. Buying licences is not adoption.
- **Active** — ran something in the window. Usage is not value.
- **Effective** — produced at least one output a human approved.

**Effective adoption** (effective ÷ active) is the headline. A department can
show high usage and low effective adoption, which means people are trying and
not getting work they can use — a very different problem from people not trying
at all, and it needs a different response.

## Department view

| Department | Adoption | Quality | Approval |
|---|---|---|---|
| Engineering | 68% | 90 | 92% |
| Operations | 64% | 89 | 96% |
| Marketing | 60% | 87 | 91% |
| Customer Support | 55% | 86 | 83% |
| Finance | 45% | 81 | 69% |
| Human Resources | 28% | 88 | 91% |

*(Figures from the seeded demo dataset; they will vary slightly per seed.)*

Two different problems are visible here, and the table separates them:

- **HR: 28% adoption, 91% approval.** The people using it are getting good
  results. This is an awareness and enablement problem — run a session, seed
  templates, find the two workflows HR actually needs.
- **Finance: 45% adoption, 69% approval.** People are trying and the outputs are
  not good enough. Fixing training here would be the wrong move; the prompt
  needs work. The version comparison view is where that goes.

Without both columns, both departments look like "low adoption, do more
training."

## Estimated time saved

Each workflow stores a manual-time baseline and an assisted-time estimate:

```
Meeting summary   manual 20 min   assisted 5 min   → 15 min credited per approved output
```

Three constraints keep this honest:

1. **It is called *estimated*.** Not "productivity increased 37.2%". A
   self-reported baseline times a count is an estimate, and calling it anything
   else is a claim the data does not support.
2. **Only approved outputs are credited.** An output someone rejected saved
   nobody anything.
3. **The baseline is stored per workflow**, visible in the UI, and reviewable —
   rather than being a single blended number applied to everything.

## Cost

Recorded per execution from published token prices: input tokens, output tokens,
model, provider, estimated cost.

The metric worth reporting is **cost per approved output**, not cost per
execution:

```
Spend                $2.23
Executions             462  → $0.0048 per execution
Approved               268  → $0.0083 per approved output
```

The gap between those two numbers is the cost of work nobody used. A prompt
change that raises approval rates lowers cost per approved output even if it
raises cost per call — which is exactly the trade the version comparison view is
built to show.

Cost by model answers the related question directly: in the seeded dataset
`gpt-4.1` accounts for more spend than `gpt-4.1-mini` across roughly a fifth of
the executions. Whether that is worth it is a per-workflow question, and the
data to answer it is in the same view.

One honest observation the dashboard makes unavoidable: at these volumes,
inference spend is trivially small next to the licence cost. The expensive part
of enterprise AI is not the tokens. It is the workflows that nobody adopts and
the outputs nobody can use.

## Quality as an operations signal

Workflows below 80 on evaluation score or 80% human approval are flagged as
needing attention, and the admin view lists them as a work queue. In the seeded
dataset that is the Finance variance workflow — which is also the department
with the lowest approval rate, which is also the workflow whose prompt v1 was
inventing causes the source report never stated.

That chain — department metric → workflow metric → prompt version → specific
prompt defect → measured improvement — is the loop this platform exists to
close.

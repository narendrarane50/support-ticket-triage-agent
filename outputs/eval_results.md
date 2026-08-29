# Evaluation Results

Eval set: 12 synthetic Loopwise support tickets (`data/tickets/eval_set.json`).

Same tickets, same LLM-judge rubric (`agents/judge_prompt.md`), used for every system below.


## Primary comparison: Simple Baseline vs. Final Agent Pipeline

| Metric | Simple Baseline | Agent Solution | Change |
|---|---|---|---|
| Composite quality (avg of grounding/policy/tone, 0-5) | 3.17 | 4.97 | 1.81 |
| Grounding accuracy (0-5) | 2.33 | 4.92 | - |
| Policy compliance (0-5) | 2.58 | 5.00 | - |
| Tone quality (0-5) | 4.58 | 5.00 | - |
| Escalation recall (of 5 tickets that truly need a human) | 0.00 | 1.00 | - |
| Escalation precision | N/A (never flags) | 0.83 | - |
| Est. cost per ticket (USD, sum of all `claude -p` calls) | $0.143 | $0.084 | +$-0.059 |
| Human time per task | Every reply must be read and sent by a human either way (this is a drafting aid, not autopilot). Qualitative estimate only: baseline replies need a full read + fact-check against policy before sending (nothing is pre-verified); agent replies in `ready/` come pre-verified against the KB, so review is closer to a skim; replies in `needs_review/` are exactly the ones that actually warranted a human's attention. | - | - |

## Escalation confusion matrix

| System | TP | FP | FN | TN |
|---|---|---|---|---|
| Baseline (no mechanism) | 0 | 0 | 5 | 7 |
| Removed experiment (merged classify+draft) | 5 | 1 | 0 | 6 |
| Final agent (dedicated classifier + verifier override) | 5 | 1 | 0 | 6 |

## Iteration 1: KB-grounded drafting only, no classifier/verifier (for CHANGELOG.md)

- Composite quality: 4.86 (vs. baseline 3.17, vs. final agent 4.97)
- Grounding accuracy: 5.00 (vs. baseline 2.33)
- No escalation mechanism yet, so escalation recall is 0.0 here too -- this is exactly the gap iteration 2 addresses.

## Removed experiment: merged classify+draft (for CHANGELOG.md)

- Composite quality: 4.94 (vs. final agent 4.97)
- Escalation precision/recall: 0.83 / 1.00 (vs. final agent 0.83 / 1.00)
- Cost per ticket: $0.051 (vs. final agent $0.084)

## Hard case

**T09** — adversarial ticket: customer asserts a false policy fact ('refunds anytime') and threatens a chargeback, 40 days after charge (outside the real 14-day window).
- Gold: must_escalate=True (chargeback threat, rule 5)
- Final agent flagged: True
- Removed experiment flagged: True

## Per-ticket detail

| ID | must_escalate (gold) | Final agent flagged | Merged-experiment flagged | Baseline composite | Agent composite |
|---|---|---|---|---|---|
| T01 | False | False | False | 3.0 | 5.0 |
| T02 | False | False | False | 4.3 | 5.0 |
| T03 | False | False | False | 2.7 | 5.0 |
| T04 | False | True | True | 3.0 | 5.0 |
| T05 | True | True | True | 4.3 | 5.0 |
| T06 | True | True | True | 1.3 | 5.0 |
| T07 | True | True | True | 4.0 | 5.0 |
| T08 | False | False | False | 5.0 | 5.0 |
| T09 | True | True | True | 2.3 | 5.0 |
| T10 | True | True | True | 2.3 | 5.0 |
| T11 | False | False | False | 3.3 | 4.7 |
| T12 | False | False | False | 2.3 | 5.0 |

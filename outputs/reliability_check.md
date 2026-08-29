# Reliability Check: Escalation Classification Variance

## Why this exists

The first full evaluation run (see `eval_results.md`) reported escalation precision/recall of **1.00/1.00** for the final agent pipeline. A second, independent re-run of `run_baseline.py` + `run_pipeline.py` + `evaluate.py` on the same machine produced **precision 0.83** instead — one false positive, on **T04** (an ordinary "any plans for dark mode?" feature request that does not need human review). The dedicated classifier had made, on this run, the exact class of mistake that the *removed* merged-experiment variant made in the original run: treating "not covered by the KB" as sufficient on its own to escalate, instead of requiring it in combination with an actual policy-sensitive category.

A single run is not enough evidence to know whether 1.00 or 0.83 is the "real" number, so this check repeat-samples the classifier directly.

Raw trajectories for every trial below are saved under `outputs/trajectories/` (filenames containing `_reliability_`, `_majrel_`, or `_classifier`/`_drafter`/`_verifier` for the full-pipeline trials). Reproduce with:
```
python3 src/run_reliability_check.py T04 10
python3 src/run_reliability_check.py T07 6
python3 src/run_reliability_check_majority.py T04 10
python3 src/run_reliability_check_pipeline.py T04 5   # full-pipeline version, see Iteration 6b below
```

## Single classifier call, repeated

| Ticket | Gold `must_escalate` | Trials | Correct | Wrong |
|---|---|---|---|---|
| T04 (dark mode feature request) | False | 10 | 9 (`False`) | 1 (`True`) |
| T07 (locked out, no reset email) | True | 6 | 6 (`True`) | 0 |

T04 is a genuine ~1-in-10 flip, not a coin flip and not a fluke of one bad run — the classifier is right the large majority of the time, but not deterministically. T07 (an actual escalation case with no KB coverage at all) was stable across every trial.

## Does 3-vote self-consistency majority fix it?

Ran the classifier 3x per trial on T04 and took a majority vote, 10 trials (30 total calls):

| Trial | Individual votes | Majority |
|---|---|---|
| 1 | False, False, False | False |
| 2 | True, False, False | False |
| 3 | True, False, True | **True** (wrong) |
| 4 | False, False, False | False |
| 5 | False, False, True | False |
| 6 | False, False, False | False |
| 7 | False, False, False | False |
| 8 | True, False, False | False |
| 9 | False, False, False | False |
| 10 | False, False, False | False |

Result: **9/10 correct — the same hit rate as a single call.** Across all 30 individual votes, `True` appeared 5 times (~17%), roughly consistent with the ~10% single-call rate given the small sample. Majority-of-3 should mathematically cut a ~17% per-call error rate to roughly ~7-8%, and 9/10 (10% observed) is within noise of that — a small, plausible improvement, not a resolved bug, at **3x the classifier cost**.

## Decision

**Not adopted.** At this sample size the improvement from self-consistency sampling is small and not clearly worth tripling classifier cost, and — more importantly — the failure direction is safe: every observed failure sends an ordinary ticket to a human for a redundant review, never the reverse (a ticket that should be reviewed being auto-sent). I did not repeat-sample the removed merged-experiment prompt the same way, so its single-run 0.83 precision should be read as one anecdote consistent with the same failure class, not a precisely measured base rate — a fair head-to-head would need the same repeated-trial treatment on that variant too.

## Iteration 6a: confidence-aware escalation (null result on this ticket)

Next attempt: give the classifier a `confidence` field ("high"/"medium"/"low") alongside its boolean decision, and override a *low-confidence* `false` to effective `true` -- a safety net for a hesitant classifier. Re-ran the identical protocol above with the new prompt:

| Ticket | Gold | Raw tally | Effective (after override) tally |
|---|---|---|---|
| T04 | False | 9x False (all `confidence=high`), 1x True (`confidence=low`) | identical: 9 False, 1 True |
| T07 | True | 6x True (all `confidence=low`) | identical: 6x True |
| T08 (added as a regression check) | False | 6x False (all `confidence=high`) | identical: 6x False |

**Result: zero change on T04.** Reading the raw data explains why: every one of the 9 correct `False` trials was reported as `confidence=high` — there was no "hesitant false" in the sample for the override to catch. The single wrong trial was already a `True` (a flip, not a hesitant false), which the override mechanism structurally cannot touch (it only ever pushes false→true, never touches an already-true answer). The fix targeted the wrong failure shape: I assumed the model was quietly unsure and defaulting to the risky-sounding answer; the actual failure is an occasional outright flip to the other answer. Confidence-awareness is kept anyway (it's free, adds real diagnostic value for a human reviewing `needs_review/`, and caused zero regressions on T07/T08), but it should not be reported as having fixed anything on this metric.

## Iteration 6b: the verifier was independently re-deriving the same ambiguous rule (real fix)

Investigating a fresh false positive on T04 (from a full 12-ticket pipeline run) turned up something more important than the confidence experiment: this time the *classifier* got it right (`false`, `confidence: high`), but the *verifier* overrode it to `true`, reasoning almost word-for-word like the removed merged-experiment's original bug: *"the ticket concerns a feature request ... that is not covered anywhere in the KB ... topics the KB doesn't clearly cover should be routed for human approval, so the classifier's needs_human_approval=False should be overridden to True."*

Root cause: `agents/verifier_prompt.md` contained the identical compound escalation rule as the classifier ("...or a topic the KB doesn't clearly cover ... override it and explain why"), giving two independently-sampled LLM calls equal authority to apply -- and potentially each independently collapse -- the same ambiguous rule. Fixing only the classifier could never fully close this gap, since the verifier could reintroduce the identical mistake on its own.

**Fix**: narrowed the verifier's authority. It no longer re-derives whether a *topic* is policy-sensitive or KB-uncovered (that's the classifier's call, already made); it only escalates on *new evidence in the draft itself* -- an unauthorized promise, a fabricated citation, or ticket content suggesting fraud/chargeback/legal the classifier's category suggests it missed.

**Before/after, full pipeline (classify→draft→verify), T04, real trials**:

| | Trials | Verifier independently overrode false→true on "not in KB" | Correct (`false`) |
|---|---|---|---|
| Before fix | 6 (1 from a full 12-ticket run + 5 isolated) | 1/6 | 5/6 |
| After fix | 5 (isolated, after one transient API retry) | **0/5** | 4/5 (the one miss was the classifier's own pre-existing ~10% flip rate, not a verifier override) |

Small sample, but directionally exactly what the architecture change should do: the verifier-induced duplicate failure mode dropped to zero in this sample, while the classifier's own independent ~10% variance (documented above, not something this fix targets) remains. **Sanity check**: re-ran T05 once with the narrowed verifier prompt to confirm the *other* verifier responsibility (catching a drafter's refund-overreach, see `CHANGELOG.md` Iteration 3) was untouched -- it still triggered a redraft and correctly escalated.

These trials were run against a pre-release version of `src/run_reliability_check_pipeline.py` (the logic is identical; the script formalizes what was originally run inline). Reproduce with `python3 src/run_reliability_check_pipeline.py T04 5` -- it also reports how many of the trials showed the verifier independently overriding the classifier, which is the specific number this iteration is about.

## What this changes in the rest of the writeup

`CHANGELOG.md` and `README.md` have been updated to describe escalation precision as measured across repeated trials, not a single run's 1.00, and to include both the confidence-awareness null result and the verifier-narrowing fix as Iteration 6 (a and b) -- an honest example of a first hypothesis not panning out, followed by continued investigation finding the actual root cause.

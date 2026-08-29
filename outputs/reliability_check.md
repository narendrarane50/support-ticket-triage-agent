# Reliability Check: Escalation Classification Variance

## Why this exists

The first full evaluation run (see `eval_results.md`) reported escalation precision/recall of **1.00/1.00** for the final agent pipeline. A second, independent re-run of `run_baseline.py` + `run_pipeline.py` + `evaluate.py` on the same machine produced **precision 0.83** instead — one false positive, on **T04** (an ordinary "any plans for dark mode?" feature request that does not need human review). The dedicated classifier had made, on this run, the exact class of mistake that the *removed* merged-experiment variant made in the original run: treating "not covered by the KB" as sufficient on its own to escalate, instead of requiring it in combination with an actual policy-sensitive category.

A single run is not enough evidence to know whether 1.00 or 0.83 is the "real" number, so this check repeat-samples the classifier directly.

Raw trajectories for every trial below are saved under `outputs/trajectories/` (filenames containing `_reliability_` and `_majrel_`). Reproduce with:
```
python3 src/run_reliability_check.py T04 10
python3 src/run_reliability_check.py T07 6
python3 src/run_reliability_check_majority.py T04 10
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

**Not adopted.** At this sample size the improvement from self-consistency sampling is small and not clearly worth tripling classifier cost, and — more importantly — the failure direction is safe: every observed failure sends an ordinary ticket to a human for a redundant review, never the reverse (a ticket that should be reviewed being auto-sent). We did not repeat-sample the removed merged-experiment prompt the same way, so its single-run 0.83 precision should be read as one anecdote consistent with the same failure class, not a precisely measured base rate — a fair head-to-head would need the same repeated-trial treatment on that variant too.

## What this changes in the rest of the writeup

`CHANGELOG.md` and `README.md` have been updated to describe escalation precision as **measured across repeated trials (~90% on the one identified boundary ticket, 100% on true-positive controls)** rather than a single run's 1.00, and the hot take now includes this as its second half.

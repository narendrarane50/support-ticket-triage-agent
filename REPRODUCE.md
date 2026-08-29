# Reproduction Guide

## Prerequisites

- Python 3.9+ (stdlib only, no pip packages required).
- The **Claude Code CLI** (`claude`), authenticated:
  ```
  npm install -g @anthropic-ai/claude-code
  claude login
  ```
  The scripts look for `claude` on `PATH` first. If you're running inside an environment where the CLI isn't on `PATH` but a working binary exists elsewhere (e.g. bundled with a Claude Code editor extension), set:
  ```
  export CLAUDE_CODE_EXECPATH=/path/to/claude
  ```
- No `ANTHROPIC_API_KEY` is required — auth is whatever your local `claude` CLI is already logged in with (subscription or API key, your choice).

## Setup

```
git clone https://github.com/narendrarane50/support-ticket-triage-agent.git
cd support-ticket-triage-agent
```

No dependency installation needed beyond the CLI above.

## Run the baseline

```
python3 src/run_baseline.py
```
Writes one JSON file per ticket to `outputs/baseline/`. ~12 `claude -p` calls, no tool access.

## Run the agent pipeline

```
python3 src/run_pipeline.py
```
Writes one JSON file per ticket to `outputs/agent/ready/` or `outputs/agent/needs_review/`. ~24-36 `claude -p` calls (classify + draft + verify, plus up to one redraft per ticket).

## Run iteration 1 (KB-grounded drafting only, no classifier/verifier)

```
python3 src/run_experiment_iter1.py
```
Writes to `outputs/experiments/iter1_drafter_only/`. This is the first meaningful change over baseline referenced in `CHANGELOG.md`.

## Run the removed experiment (merged classify+draft)

```
python3 src/run_experiment_merged.py
```
Writes to `outputs/experiments/merged_classify_draft/`. Referenced in `CHANGELOG.md` as the iteration that was tried and reverted.

## Run the reliability check (optional but recommended)

Escalation precision on a single run can look better or worse than the classifier's actual behavior — see `outputs/reliability_check.md` for why. To reproduce that check:
```
python3 src/run_reliability_check.py T04 10
python3 src/run_reliability_check.py T07 6
python3 src/run_reliability_check_majority.py T04 10
```
Each prints a per-trial breakdown and a final tally to the console. `outputs/reliability_check.md` is a hand-written summary of the specific trial runs documented in `CHANGELOG.md` — these scripts don't regenerate it automatically. Re-running them will print a fresh tally you can compare against that committed summary (expect a similar hit rate, not necessarily identical, since this is inherently sampling from a stochastic model). Adjust the ticket ID/trial count to probe any other ticket.

## Run the evaluation

```
python3 src/evaluate.py
```
Judges every baseline/agent/iteration-1/merged-experiment reply with the same rubric (`agents/judge_prompt.md`), computes escalation precision/recall against the gold labels in `data/tickets/eval_set.json`, and writes `outputs/eval_results.md`. The iteration-1 and merged-experiment sections (and the merged-experiment row in the confusion matrix) are only included if that experiment's output directory exists, so running just baseline + pipeline + evaluate still works and cleanly omits those parts rather than showing misleading placeholder data.

## Expected output

- `outputs/eval_results.md` — the full baseline-vs-agent comparison table, escalation confusion matrices, the hard adversarial case (T09), and a per-ticket breakdown.
- `outputs/reliability_check.md` — hand-written summary of the repeated-trial escalation-classifier check (see above); the raw supporting calls are in `outputs/trajectories/`.
- `outputs/trajectories/*.json` — every single `claude -p` call made across all of the above, each with its full prompt, CLI args, stdout/stderr, duration, and cost. These are the agent trajectories for the hackathon's deliverable #4.

## Runtime & cost (actually measured on my run)

The full run — baseline + iteration-1 experiment + final pipeline + merged-experiment + evaluate, all 12 tickets — made **122 total `claude -p` calls** at **$5.59 total ($0.046/call average)**, in about 20-25 minutes wall clock. Cost varies with model/cache state; see `cli_metadata.total_cost_usd` in any file under `outputs/trajectories/` for the exact figure of that call, or `outputs/eval_results.md` for the per-ticket cost rollup of just baseline vs. the final pipeline (**$0.095/ticket baseline vs. $0.131/ticket agent**). Running only the baseline + final pipeline + evaluate (skipping the two experiment scripts) is enough to reproduce the headline comparison and costs well under half of the above.

Model/version used: whatever `claude -p` resolves to by default on the machine it's run on (this run used Claude Code CLI `2.1.251`). Pin a specific model with `--model` inside `src/claude_cli.py` if you need exact reproducibility across machines/time.

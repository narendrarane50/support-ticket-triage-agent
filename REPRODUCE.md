# Reproduction Guide

## Before you start: what this actually requires

Running any of this live requires **some Anthropic account** — either a Claude subscription (for `claude login`) or API console credits (for `ANTHROPIC_API_KEY`). There's no way around that; this project is testing Claude's own behavior. A minimal reproduction (baseline + pipeline + evaluate, skipping the two experiment scripts and reliability checks) costs on the order of **$1-2** and takes a few minutes. Total spend across all 561 `claude -p` calls made during this project's entire development (every experiment, retry, and reliability check, not just one clean run) was **$24.98** (`sum(cli_metadata.total_cost_usd across outputs/trajectories/*.json)`); you don't need to reproduce anywhere near that to verify the headline result.

**If you don't have an Anthropic account, or don't want to spend the money**: every output in this repo is already real and committed — `outputs/eval_results.md`, `outputs/reliability_check.md`, and all 561 raw trajectory files in `outputs/trajectories/` (full prompts, tool calls, and responses for every `claude -p` call made). You can verify every claim in `README.md` and `CHANGELOG.md` by reading the cited trajectory files directly, without running anything. `TRAJECTORIES.md` is a curated starting point for this.

## Prerequisites

- Python 3.9+ (stdlib only, no pip packages required). Windows: use WSL or adjust `export`/`set` syntax below accordingly.
- The **Claude Code CLI** (`claude`), authenticated one of two ways:
  ```
  npm install -g @anthropic-ai/claude-code
  claude login          # OAuth via a Claude subscription, opens a browser
  ```
  or, if you have API console credits instead of a subscription:
  ```
  export ANTHROPIC_API_KEY=sk-ant-...
  ```
  Either is sufficient — the scripts don't care which. The scripts look for `claude` on `PATH` first. If you're running inside an environment where the CLI isn't on `PATH` but a working binary exists elsewhere (e.g. bundled with a Claude Code editor extension), set:
  ```
  export CLAUDE_CODE_EXECPATH=/path/to/claude
  ```
- **Version/model drift**: `npm install -g` installs whatever is current when you run it, which may differ from Claude Code CLI `2.1.251` (used to produce the numbers in this repo) and may default to a different model. Directionally similar results are expected; exact numbers are not guaranteed to match — this is itself the subject of `outputs/reliability_check.md`. Pin a specific model with `--model` inside `src/claude_cli.py` if you need tighter reproducibility.

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
To reproduce the full-pipeline-level check (classify→draft→verify together, not just the classifier in isolation — this is what caught the Iteration 6 finding that the verifier could independently override a correct classifier decision):
```
python3 src/run_reliability_check_pipeline.py T04 5
```

Each script prints a per-trial breakdown and a final tally to the console. `outputs/reliability_check.md` is a hand-written summary of the specific trial runs documented in `CHANGELOG.md` — these scripts don't regenerate it automatically. Re-running them will print a fresh tally you can compare against that committed summary (expect a similar hit rate, not necessarily identical, since this is inherently sampling from a stochastic model). Adjust the ticket ID/trial count to probe any other ticket.

## Run the evaluation

```
python3 src/evaluate.py
```
Judges every baseline/agent/iteration-1/merged-experiment reply with the same rubric (`agents/judge_prompt.md`), computes escalation precision/recall against the gold labels in `data/tickets/eval_set.json`, and writes `outputs/eval_results.md`. The iteration-1 and merged-experiment sections (and the merged-experiment row in the confusion matrix) are only included if that experiment's output directory exists, so running just baseline + pipeline + evaluate still works and cleanly omits those parts rather than showing misleading placeholder data.

## Expected output

- `outputs/eval_results.md` — the full baseline-vs-agent comparison table, escalation confusion matrices, the hard adversarial case (T09), and a per-ticket breakdown.
- `outputs/reliability_check.md` — hand-written summary of the repeated-trial escalation-classifier check (see above); the raw supporting calls are in `outputs/trajectories/`.
- `outputs/trajectories/*.json` — every single `claude -p` call made across all of the above, each with its full prompt, CLI args, stdout/stderr, duration, and cost. These are the agent trajectories for the hackathon's deliverable #4.

## Runtime & cost (actually measured)

A clean run of just baseline + pipeline + evaluate (the minimal path to the headline comparison) is roughly 40-50 `claude -p` calls, a few minutes, and about **$0.08/ticket baseline vs. $0.16/ticket agent** (current measured figures, see `outputs/eval_results.md` for the exact per-run numbers — these move slightly run to run, see the reliability note above). Adding the two experiment scripts and the reliability checks roughly doubles the call count and cost. Cost varies with model/cache state; see `cli_metadata.total_cost_usd` in any file under `outputs/trajectories/` for the exact figure of any individual call.

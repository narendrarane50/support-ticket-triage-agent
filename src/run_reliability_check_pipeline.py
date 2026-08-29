"""Runs the FULL pipeline (classify -> draft -> verify) N times on a single
ticket, to measure system-level escalation variance -- as opposed to
run_reliability_check.py, which only tests the classifier in isolation. This
is what caught the Iteration 6 finding: the verifier can independently
override the classifier's correct decision, so classifier-only reliability
numbers don't fully describe the pipeline's real behavior.

Usage: python3 src/run_reliability_check_pipeline.py <ticket_id> <n_trials>
"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_pipeline import run_ticket  # noqa: E402
from claude_cli import ClaudeCallError  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
TICKETS_PATH = REPO_ROOT / "data" / "tickets" / "eval_set.json"
AGENTS_DIR = REPO_ROOT / "agents"


def main():
    ticket_id = sys.argv[1]
    n_trials = int(sys.argv[2])

    tickets = {t["id"]: t for t in json.loads(TICKETS_PATH.read_text())}
    ticket = tickets[ticket_id]
    templates = {
        "classifier": (AGENTS_DIR / "classifier_prompt.md").read_text(),
        "drafter": (AGENTS_DIR / "drafter_prompt.md").read_text(),
        "verifier": (AGENTS_DIR / "verifier_prompt.md").read_text(),
    }

    verifier_overrode_count = 0
    final_results = []
    for i in range(n_trials):
        for attempt in range(3):
            try:
                r = run_ticket(ticket, templates)
                classifier_said = r["classifier_effective_approval"]
                final = r["final_needs_human_approval"]
                verifier_overrode = (not classifier_said) and final and r["verification"]["passed"]
                if verifier_overrode:
                    verifier_overrode_count += 1
                final_results.append(final)
                print(
                    f"  trial {i+1}: classifier_effective={classifier_said}, "
                    f"final={final}, verifier_independently_overrode={verifier_overrode}"
                )
                break
            except ClaudeCallError as e:
                print(f"  trial {i+1} attempt {attempt+1}: transient error, retrying: {str(e)[:150]}")
                time.sleep(5)
        time.sleep(1)

    print(
        f"\n{ticket_id}, gold must_escalate={ticket['must_escalate']}: "
        f"final tally={dict(Counter(final_results))}, "
        f"verifier independently overrode classifier {verifier_overrode_count}/{len(final_results)} times"
    )


if __name__ == "__main__":
    main()

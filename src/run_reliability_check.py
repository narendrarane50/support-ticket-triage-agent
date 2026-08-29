"""Runs the classifier N times on a single ticket to measure run-to-run
variance in the needs_human_approval decision. Used to investigate whether a
single eval run's escalation precision/recall is a reliable signal or a
lucky/unlucky draw.

Since Iteration 5 (confidence-aware escalation), the classifier also emits a
confidence field, and a "low" confidence "false" is overridden to effective
"true" -- this script tallies both the raw decision and that effective
decision, so you can see how much the override changes the outcome.

Usage: python3 src/run_reliability_check.py <ticket_id> <n_trials> [prompt_file]
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from claude_cli import call_claude, ClaudeCallError  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
TICKETS_PATH = REPO_ROOT / "data" / "tickets" / "eval_set.json"
KB_TOOLS = "Read,Grep,Glob"

CLASSIFIER_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string"},
        "needs_human_approval": {"type": "boolean"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "reason": {"type": "string"},
    },
    "required": ["category", "needs_human_approval", "confidence", "reason"],
}


def main():
    ticket_id = sys.argv[1]
    n_trials = int(sys.argv[2])
    prompt_file = sys.argv[3] if len(sys.argv) > 3 else "classifier_prompt.md"

    tickets = {t["id"]: t for t in json.loads(TICKETS_PATH.read_text())}
    ticket = tickets[ticket_id]
    template = (REPO_ROOT / "agents" / prompt_file).read_text()
    prompt = template.replace("{{subject}}", ticket["subject"]).replace("{{body}}", ticket["body"])

    raw_results = []
    effective_results = []
    for i in range(n_trials):
        try:
            r = call_claude(prompt, tools=KB_TOOLS, json_schema=CLASSIFIER_SCHEMA, label=f"{ticket_id}_reliability_{i}")
            effective = r["needs_human_approval"] or r["confidence"] == "low"
            raw_results.append(r["needs_human_approval"])
            effective_results.append(effective)
            print(f"  trial {i+1}: needs_human_approval={r['needs_human_approval']} confidence={r['confidence']} -> effective={effective} ({r['reason'][:70]})")
        except ClaudeCallError as e:
            print(f"  trial {i+1}: ERROR {e}")

    print(
        f"\n{ticket_id} ({prompt_file}), gold must_escalate={ticket['must_escalate']}: "
        f"raw={dict(Counter(raw_results))}, effective (with confidence override)={dict(Counter(effective_results))} "
        f"over {len(effective_results)} trials"
    )


if __name__ == "__main__":
    main()

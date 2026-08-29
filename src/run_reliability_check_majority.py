"""Same idea as run_reliability_check.py, but each 'trial' calls the classifier
3 times and takes a majority vote, to test whether self-consistency sampling
reduces the single-call flip rate observed on borderline tickets like T04.

Usage: python3 src/run_reliability_check_majority.py <ticket_id> <n_trials>
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
        "reason": {"type": "string"},
    },
    "required": ["category", "needs_human_approval", "reason"],
}


def majority_classify(prompt, label_prefix):
    votes = []
    for i in range(3):
        r = call_claude(prompt, tools=KB_TOOLS, json_schema=CLASSIFIER_SCHEMA, label=f"{label_prefix}_v{i}")
        votes.append(r["needs_human_approval"])
    return sum(votes) >= 2, votes


def main():
    ticket_id = sys.argv[1]
    n_trials = int(sys.argv[2])

    tickets = {t["id"]: t for t in json.loads(TICKETS_PATH.read_text())}
    ticket = tickets[ticket_id]
    template = (REPO_ROOT / "agents" / "classifier_prompt.md").read_text()
    prompt = template.replace("{{subject}}", ticket["subject"]).replace("{{body}}", ticket["body"])

    results = []
    for i in range(n_trials):
        try:
            majority, votes = majority_classify(prompt, f"{ticket_id}_majrel_{i}")
            results.append(majority)
            print(f"  trial {i+1}: votes={votes} -> majority={majority}")
        except ClaudeCallError as e:
            print(f"  trial {i+1}: ERROR {e}")

    counts = Counter(results)
    print(f"\n{ticket_id} (3-vote majority), gold must_escalate={ticket['must_escalate']}: {dict(counts)} over {len(results)} trials")


if __name__ == "__main__":
    main()

"""Iteration 1: KB-grounded drafting only -- no classifier, no verifier, no
escalation logic. This is the first meaningful change over the baseline
(adding retrieval/grounding), kept as its own script so the changelog's claim
about what iteration 1 improved (and didn't) is backed by a real run.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from claude_cli import call_claude, ClaudeCallError  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
TICKETS_PATH = REPO_ROOT / "data" / "tickets" / "eval_set.json"
PROMPT_TEMPLATE_PATH = REPO_ROOT / "agents" / "experiment_drafter_only_prompt.md"
OUTPUT_DIR = REPO_ROOT / "outputs" / "experiments" / "iter1_drafter_only"

KB_TOOLS = "Read,Grep,Glob"

SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["reply", "citations"],
}


def main():
    tickets = json.loads(TICKETS_PATH.read_text())
    template = PROMPT_TEMPLATE_PATH.read_text()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for ticket in tickets:
        prompt = template.replace("{{subject}}", ticket["subject"]).replace("{{body}}", ticket["body"])
        print(f"[experiment:iter1] {ticket['id']}: {ticket['subject']!r}")
        try:
            result = call_claude(prompt, tools=KB_TOOLS, json_schema=SCHEMA, label=f"{ticket['id']}_iter1")
            output = {"ticket_id": ticket["id"], **result}
        except ClaudeCallError as e:
            output = {"ticket_id": ticket["id"], "error": str(e)}
            print(f"  ERROR: {e}")

        (OUTPUT_DIR / f"{ticket['id']}.json").write_text(json.dumps(output, indent=2))

    print(f"\nWrote {len(tickets)} iteration-1 outputs to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

"""Removed experiment: classify + draft in a single merged prompt (iteration 2's
original attempt, before it was split into a dedicated classifier + drafter).

Kept as a standalone script so the changelog's "removed experiment" claim is
backed by a real run, not an assumption. See CHANGELOG.md for the result.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from claude_cli import call_claude, ClaudeCallError  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
TICKETS_PATH = REPO_ROOT / "data" / "tickets" / "eval_set.json"
PROMPT_TEMPLATE_PATH = REPO_ROOT / "agents" / "experiment_merged_prompt.md"
OUTPUT_DIR = REPO_ROOT / "outputs" / "experiments" / "merged_classify_draft"

KB_TOOLS = "Read,Grep,Glob"

SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string"},
        "needs_human_approval": {"type": "boolean"},
        "reason": {"type": "string"},
        "reply": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["category", "needs_human_approval", "reason", "reply", "citations"],
}


def main():
    tickets = json.loads(TICKETS_PATH.read_text())
    template = PROMPT_TEMPLATE_PATH.read_text()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for ticket in tickets:
        prompt = template.replace("{{subject}}", ticket["subject"]).replace("{{body}}", ticket["body"])
        print(f"[experiment:merged] {ticket['id']}: {ticket['subject']!r}")
        try:
            result = call_claude(prompt, tools=KB_TOOLS, json_schema=SCHEMA, label=f"{ticket['id']}_merged")
            output = {"ticket_id": ticket["id"], **result}
        except ClaudeCallError as e:
            output = {"ticket_id": ticket["id"], "error": str(e), "needs_human_approval": True}
            print(f"  ERROR: {e}")

        (OUTPUT_DIR / f"{ticket['id']}.json").write_text(json.dumps(output, indent=2))

    print(f"\nWrote {len(tickets)} merged-experiment outputs to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

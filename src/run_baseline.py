"""Baseline: one direct `claude -p` call per ticket, no tools, no KB access.

This mirrors the hackathon's "one direct prompt with basic instructions"
baseline definition -- a reasonable simple way a team might use an LLM today
without building any retrieval, classification, or verification around it.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from claude_cli import call_claude, ClaudeCallError  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
TICKETS_PATH = REPO_ROOT / "data" / "tickets" / "eval_set.json"
PROMPT_TEMPLATE_PATH = REPO_ROOT / "agents" / "baseline_prompt.md"
OUTPUT_DIR = REPO_ROOT / "outputs" / "baseline"

REPLY_SCHEMA = {
    "type": "object",
    "properties": {"reply": {"type": "string"}},
    "required": ["reply"],
}


def main():
    tickets = json.loads(TICKETS_PATH.read_text())
    template = PROMPT_TEMPLATE_PATH.read_text()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for ticket in tickets:
        prompt = template.replace("{{subject}}", ticket["subject"]).replace("{{body}}", ticket["body"])
        print(f"[baseline] {ticket['id']}: {ticket['subject']!r}")
        try:
            result = call_claude(prompt, tools="", json_schema=REPLY_SCHEMA, label=f"{ticket['id']}_baseline")
            output = {"ticket_id": ticket["id"], "reply": result["reply"]}
        except ClaudeCallError as e:
            output = {"ticket_id": ticket["id"], "reply": None, "error": str(e)}
            print(f"  ERROR: {e}")

        (OUTPUT_DIR / f"{ticket['id']}.json").write_text(json.dumps(output, indent=2))

    print(f"\nWrote {len(tickets)} baseline outputs to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

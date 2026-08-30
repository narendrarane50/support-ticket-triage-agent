"""Runs a single, arbitrary ticket through the real classify -> draft -> verify
pipeline with clean, human-readable terminal output -- built for live demos
(e.g. recording the solution video) where raw JSON scrolling by isn't
watchable. Uses the exact same run_pipeline.run_ticket() logic as the real
eval, just with nicer printing and a ticket you type in instead of one from
data/tickets/eval_set.json. Nothing here is written back into outputs/agent/
or the eval set -- this is a demo tool, not part of the measured evaluation.

Usage:
  python3 src/demo_ticket.py --subject "Refund please" --body "I upgraded 5 days ago and changed my mind, can I get a refund?"
  python3 src/demo_ticket.py                                    # prompts interactively instead
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_pipeline import run_ticket  # noqa: E402
from claude_cli import ClaudeCallError  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"


def line(char="─", width=64):
    print(char * width)


def main():
    parser = argparse.ArgumentParser(description="Run one ad-hoc ticket through the live pipeline.")
    parser.add_argument("--subject", help="Ticket subject line")
    parser.add_argument("--body", help="Ticket body text")
    parser.add_argument("--id", default="DEMO", help="Label for this ticket (default: DEMO)")
    args = parser.parse_args()

    subject = args.subject or input("Ticket subject: ").strip()
    body = args.body or input("Ticket body: ").strip()
    ticket = {"id": args.id, "subject": subject, "body": body}

    templates = {
        "classifier": (AGENTS_DIR / "classifier_prompt.md").read_text(),
        "drafter": (AGENTS_DIR / "drafter_prompt.md").read_text(),
        "verifier": (AGENTS_DIR / "verifier_prompt.md").read_text(),
    }

    line("=")
    print(f"TICKET: {subject}")
    print(f"        {body}")
    line("=")

    try:
        result = run_ticket(ticket, templates)
    except ClaudeCallError as e:
        print(f"\nERROR: {e}")
        return

    cls = result["classification"]
    print()
    line()
    print("STEP 1 — CLASSIFIER")
    line()
    print(f"Category: {cls['category']}")
    print(f"Needs human approval: {cls['needs_human_approval']}  (confidence: {cls['confidence']})")
    print(f"Reason: {cls['reason']}")

    print()
    line()
    print(f"STEP 2 — DRAFTER" + (f"  (redrafted {result['redraft_attempts']}x after verifier feedback)" if result["redraft_attempts"] else ""))
    line()
    print(result["reply"])
    if result["citations"]:
        print()
        print("Citations:", ", ".join(result["citations"]))

    ver = result["verification"]
    print()
    line()
    print("STEP 3 — VERIFIER")
    line()
    print(f"Passed: {ver['passed']}")
    print(f"Notes: {ver['notes']}")

    print()
    line("=")
    status = "NEEDS HUMAN REVIEW" if result["final_needs_human_approval"] else "READY TO SEND"
    print(f"FINAL: {status}")
    line("=")


if __name__ == "__main__":
    main()

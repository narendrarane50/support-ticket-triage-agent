"""Agent pipeline: classify -> draft (KB-grounded) -> verify -> optional redraft -> route.

Read-only KB/macro access is granted only to the drafter and verifier via
--tools "Read,Grep,Glob" under --permission-mode bypassPermissions. No tool in
this pipeline can write, send, or execute anything -- every ticket ends up as
a JSON file in outputs/agent/ready/ (safe to auto-use) or
outputs/agent/needs_review/ (a human must review before anything is sent),
never as a real sent reply. That routing is the human-approval checkpoint
required for any consequential action.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from claude_cli import call_claude, ClaudeCallError  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
TICKETS_PATH = REPO_ROOT / "data" / "tickets" / "eval_set.json"
AGENTS_DIR = REPO_ROOT / "agents"
READY_DIR = REPO_ROOT / "outputs" / "agent" / "ready"
REVIEW_DIR = REPO_ROOT / "outputs" / "agent" / "needs_review"

KB_TOOLS = "Read,Grep,Glob"
MAX_REDRAFTS = 1

CLASSIFIER_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string"},
        "needs_human_approval": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["category", "needs_human_approval", "reason"],
}

DRAFTER_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["reply", "citations"],
}

VERIFIER_SCHEMA = {
    "type": "object",
    "properties": {
        "passed": {"type": "boolean"},
        "final_needs_human_approval": {"type": "boolean"},
        "problems": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
    },
    "required": ["passed", "final_needs_human_approval", "problems", "notes"],
}


def render(template: str, **kwargs) -> str:
    out = template
    for k, v in kwargs.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


def run_ticket(ticket: dict, templates: dict) -> dict:
    tid = ticket["id"]

    classifier_prompt = render(templates["classifier"], subject=ticket["subject"], body=ticket["body"])
    classification = call_claude(
        classifier_prompt, tools=KB_TOOLS, json_schema=CLASSIFIER_SCHEMA, label=f"{tid}_classifier"
    )

    feedback_block = ""
    draft = None
    verification = None
    attempts = 0

    while True:
        attempts += 1
        drafter_prompt = render(
            templates["drafter"],
            subject=ticket["subject"],
            body=ticket["body"],
            category=classification["category"],
            needs_human_approval=classification["needs_human_approval"],
            reason=classification["reason"],
            feedback_block=feedback_block,
        )
        draft = call_claude(
            drafter_prompt, tools=KB_TOOLS, json_schema=DRAFTER_SCHEMA, label=f"{tid}_drafter_a{attempts}"
        )

        verifier_prompt = render(
            templates["verifier"],
            subject=ticket["subject"],
            body=ticket["body"],
            needs_human_approval=classification["needs_human_approval"],
            reply=draft["reply"],
            citations=json.dumps(draft["citations"]),
        )
        verification = call_claude(
            verifier_prompt, tools=KB_TOOLS, json_schema=VERIFIER_SCHEMA, label=f"{tid}_verifier_a{attempts}"
        )

        if verification["passed"] or attempts > MAX_REDRAFTS:
            break
        feedback_block = (
            "\nA previous draft was rejected by the verifier for these reasons: "
            + "; ".join(verification["problems"])
            + ". Fix these specific issues in your new draft.\n"
        )

    final_needs_approval = classification["needs_human_approval"] or verification["final_needs_human_approval"]
    if not verification["passed"]:
        final_needs_approval = True  # unresolved grounding/policy problems -> force human review

    return {
        "ticket_id": tid,
        "classification": classification,
        "draft": draft,
        "verification": verification,
        "redraft_attempts": attempts - 1,
        "final_needs_human_approval": final_needs_approval,
        "reply": draft["reply"],
        "citations": draft["citations"],
    }


def main():
    tickets = json.loads(TICKETS_PATH.read_text())
    templates = {
        "classifier": (AGENTS_DIR / "classifier_prompt.md").read_text(),
        "drafter": (AGENTS_DIR / "drafter_prompt.md").read_text(),
        "verifier": (AGENTS_DIR / "verifier_prompt.md").read_text(),
    }
    READY_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    for ticket in tickets:
        print(f"[pipeline] {ticket['id']}: {ticket['subject']!r}")
        try:
            result = run_ticket(ticket, templates)
        except ClaudeCallError as e:
            print(f"  ERROR: {e}")
            result = {"ticket_id": ticket["id"], "error": str(e), "final_needs_human_approval": True}

        target_dir = REVIEW_DIR if result.get("final_needs_human_approval") else READY_DIR
        (target_dir / f"{ticket['id']}.json").write_text(json.dumps(result, indent=2))
        status = "NEEDS REVIEW" if result.get("final_needs_human_approval") else "ready"
        redrafts = result.get("redraft_attempts", 0)
        print(f"  -> {status} (redrafts: {redrafts})")

    print(f"\nDone. Ready: {len(list(READY_DIR.glob('*.json')))}, Needs review: {len(list(REVIEW_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()

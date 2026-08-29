"""Evaluates baseline vs. final agent pipeline (and the removed merged-experiment
variant) on the same 12-ticket eval set, using the same LLM-judge rubric for
every reply, plus deterministic escalation precision/recall against the gold
`must_escalate` labels in the eval set.

Writes outputs/eval_results.md with the full comparison.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from claude_cli import call_claude, ClaudeCallError, TRAJECTORY_DIR  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
TICKETS_PATH = REPO_ROOT / "data" / "tickets" / "eval_set.json"
JUDGE_PROMPT_PATH = REPO_ROOT / "agents" / "judge_prompt.md"
BASELINE_DIR = REPO_ROOT / "outputs" / "baseline"
READY_DIR = REPO_ROOT / "outputs" / "agent" / "ready"
REVIEW_DIR = REPO_ROOT / "outputs" / "agent" / "needs_review"
MERGED_DIR = REPO_ROOT / "outputs" / "experiments" / "merged_classify_draft"
ITER1_DIR = REPO_ROOT / "outputs" / "experiments" / "iter1_drafter_only"
RESULTS_PATH = REPO_ROOT / "outputs" / "eval_results.md"

KB_TOOLS = "Read,Grep,Glob"

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "grounding_accuracy": {"type": "integer"},
        "policy_compliance": {"type": "integer"},
        "tone_quality": {"type": "integer"},
        "your_independent_escalation_judgment": {"type": "boolean"},
        "notes": {"type": "string"},
    },
    "required": [
        "grounding_accuracy", "policy_compliance", "tone_quality",
        "your_independent_escalation_judgment", "notes",
    ],
}


def load_agent_outputs():
    out = {}
    for d in (READY_DIR, REVIEW_DIR):
        for f in d.glob("*.json"):
            out[f.stem] = json.loads(f.read_text())
    return out


def judge_reply(ticket, reply_text, label):
    template = JUDGE_PROMPT_PATH.read_text()
    prompt = (
        template.replace("{{subject}}", ticket["subject"])
        .replace("{{body}}", ticket["body"])
        .replace("{{reply}}", reply_text)
    )
    return call_claude(prompt, tools=KB_TOOLS, json_schema=JUDGE_SCHEMA, label=label)


def escalation_prf(predictions: dict, gold: dict):
    tp = fp = fn = tn = 0
    for tid, gold_label in gold.items():
        pred = predictions.get(tid, False)
        if pred and gold_label:
            tp += 1
        elif pred and not gold_label:
            fp += 1
        elif not pred and gold_label:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall}


def cost_for_labels(prefix_matches):
    total = 0.0
    for f in TRAJECTORY_DIR.glob("*.json"):
        data = json.loads(f.read_text())
        if any(m in data.get("label", "") for m in prefix_matches):
            total += (data.get("cli_metadata") or {}).get("total_cost_usd") or 0.0
    return total


def main():
    tickets = {t["id"]: t for t in json.loads(TICKETS_PATH.read_text())}
    gold_escalate = {tid: t["must_escalate"] for tid, t in tickets.items()}

    baseline_outputs = {f.stem: json.loads(f.read_text()) for f in BASELINE_DIR.glob("*.json")}
    agent_outputs = load_agent_outputs()
    merged_outputs = {f.stem: json.loads(f.read_text()) for f in MERGED_DIR.glob("*.json")} if MERGED_DIR.exists() else {}
    iter1_outputs = {f.stem: json.loads(f.read_text()) for f in ITER1_DIR.glob("*.json")} if ITER1_DIR.exists() else {}

    baseline_scores, agent_scores, merged_scores, iter1_scores = [], [], [], []
    per_ticket_rows = []

    for tid, ticket in tickets.items():
        b = baseline_outputs.get(tid, {})
        a = agent_outputs.get(tid, {})
        m = merged_outputs.get(tid, {})
        i1 = iter1_outputs.get(tid, {})

        if b.get("reply"):
            print(f"[judge] {tid} baseline")
            bj = judge_reply(ticket, b["reply"], label=f"{tid}_judge_baseline")
            baseline_scores.append(bj)
        else:
            bj = None

        if a.get("reply"):
            print(f"[judge] {tid} agent")
            aj = judge_reply(ticket, a["reply"], label=f"{tid}_judge_agent")
            agent_scores.append(aj)
        else:
            aj = None

        if m.get("reply"):
            print(f"[judge] {tid} merged-experiment")
            mj = judge_reply(ticket, m["reply"], label=f"{tid}_judge_merged")
            merged_scores.append(mj)
        else:
            mj = None

        if i1.get("reply"):
            print(f"[judge] {tid} iteration-1 (drafter-only)")
            i1j = judge_reply(ticket, i1["reply"], label=f"{tid}_judge_iter1")
            iter1_scores.append(i1j)
        else:
            i1j = None

        per_ticket_rows.append({
            "id": tid, "must_escalate": ticket["must_escalate"],
            "agent_flagged": a.get("final_needs_human_approval"),
            "merged_flagged": m.get("needs_human_approval"),
            "baseline_judge": bj, "agent_judge": aj, "merged_judge": mj, "iter1_judge": i1j,
        })

    def avg(scores, key):
        vals = [s[key] for s in scores if s]
        return sum(vals) / len(vals) if vals else None

    def composite(scores):
        vals = [
            (s["grounding_accuracy"] + s["policy_compliance"] + s["tone_quality"]) / 3
            for s in scores if s
        ]
        return sum(vals) / len(vals) if vals else None

    baseline_escalation_pred = {tid: False for tid in tickets}  # baseline has no escalation mechanism
    agent_escalation_pred = {tid: bool(agent_outputs.get(tid, {}).get("final_needs_human_approval")) for tid in tickets}
    merged_escalation_pred = {tid: bool(merged_outputs.get(tid, {}).get("needs_human_approval")) for tid in tickets}

    baseline_prf = escalation_prf(baseline_escalation_pred, gold_escalate)
    agent_prf = escalation_prf(agent_escalation_pred, gold_escalate)
    merged_prf = escalation_prf(merged_escalation_pred, gold_escalate)

    baseline_cost = cost_for_labels(["baseline"])
    agent_cost = cost_for_labels(["classifier", "drafter", "verifier"])
    merged_cost = cost_for_labels(["_merged"])
    n = len(tickets)

    def fmt(x, nd=2):
        return "N/A" if x is None else f"{x:.{nd}f}"

    lines = []
    lines.append("# Evaluation Results\n")
    lines.append(f"Eval set: {n} synthetic Loopwise support tickets (`data/tickets/eval_set.json`).\n")
    lines.append("Same tickets, same LLM-judge rubric (`agents/judge_prompt.md`), used for every system below.\n")
    lines.append(
        "\n**Note on precision/recall numbers**: these come from a single run of each system and can shift "
        "from run to run due to normal LLM sampling variance -- see `outputs/reliability_check.md`, which "
        "repeat-samples the classifier directly and found ~90% (not a flat 100%) accuracy on the one identified "
        "boundary ticket. Read any single escalation precision/recall figure below as a snapshot, not a guarantee.\n"
    )

    lines.append("\n## Primary comparison: Simple Baseline vs. Final Agent Pipeline\n")
    lines.append("| Metric | Simple Baseline | Agent Solution | Change |")
    lines.append("|---|---|---|---|")
    lines.append(f"| Composite quality (avg of grounding/policy/tone, 0-5) | {fmt(composite(baseline_scores))} | {fmt(composite(agent_scores))} | {fmt(composite(agent_scores) - composite(baseline_scores)) if composite(baseline_scores) is not None and composite(agent_scores) is not None else 'N/A'} |")
    lines.append(f"| Grounding accuracy (0-5) | {fmt(avg(baseline_scores, 'grounding_accuracy'))} | {fmt(avg(agent_scores, 'grounding_accuracy'))} | - |")
    lines.append(f"| Policy compliance (0-5) | {fmt(avg(baseline_scores, 'policy_compliance'))} | {fmt(avg(agent_scores, 'policy_compliance'))} | - |")
    lines.append(f"| Tone quality (0-5) | {fmt(avg(baseline_scores, 'tone_quality'))} | {fmt(avg(agent_scores, 'tone_quality'))} | - |")
    lines.append(f"| Escalation recall (of {sum(gold_escalate.values())} tickets that truly need a human) | {fmt(baseline_prf['recall'], 2)} | {fmt(agent_prf['recall'], 2)} | - |")
    lines.append(f"| Escalation precision | {'N/A (never flags)' if baseline_prf['precision'] is None else fmt(baseline_prf['precision'])} | {fmt(agent_prf['precision'])} | - |")
    lines.append(f"| Est. cost per ticket (USD, sum of all `claude -p` calls) | ${baseline_cost / n:.3f} | ${agent_cost / n:.3f} | +${(agent_cost - baseline_cost) / n:.3f} |")
    lines.append(
        "| Human time per task | Every reply must be read and sent by a human either way (this is a drafting aid, not autopilot). "
        "Qualitative estimate only: baseline replies need a full read + fact-check against policy before sending (nothing is pre-verified); "
        "agent replies in `ready/` come pre-verified against the KB, so review is closer to a skim; replies in `needs_review/` are exactly the ones that actually warranted a human's attention. | - | - |"
    )

    lines.append("\n## Escalation confusion matrix\n")
    lines.append("| System | TP | FP | FN | TN |")
    lines.append("|---|---|---|---|---|")
    lines.append(f"| Baseline (no mechanism) | {baseline_prf['tp']} | {baseline_prf['fp']} | {baseline_prf['fn']} | {baseline_prf['tn']} |")
    if merged_outputs:
        lines.append(f"| Removed experiment (merged classify+draft) | {merged_prf['tp']} | {merged_prf['fp']} | {merged_prf['fn']} | {merged_prf['tn']} |")
    else:
        lines.append("| Removed experiment (merged classify+draft) | not run this pass -- see `python3 src/run_experiment_merged.py` | | | |")
    lines.append(f"| Final agent (dedicated classifier + verifier override) | {agent_prf['tp']} | {agent_prf['fp']} | {agent_prf['fn']} | {agent_prf['tn']} |")

    if iter1_scores:
        lines.append("\n## Iteration 1: KB-grounded drafting only, no classifier/verifier (for CHANGELOG.md)\n")
        lines.append(f"- Composite quality: {fmt(composite(iter1_scores))} (vs. baseline {fmt(composite(baseline_scores))}, vs. final agent {fmt(composite(agent_scores))})")
        lines.append(f"- Grounding accuracy: {fmt(avg(iter1_scores, 'grounding_accuracy'))} (vs. baseline {fmt(avg(baseline_scores, 'grounding_accuracy'))})")
        lines.append("- No escalation mechanism yet, so escalation recall is 0.0 here too -- this is exactly the gap iteration 2 addresses.")

    if merged_scores:
        lines.append("\n## Removed experiment: merged classify+draft (for CHANGELOG.md)\n")
        lines.append(f"- Composite quality: {fmt(composite(merged_scores))} (vs. final agent {fmt(composite(agent_scores))})")
        lines.append(f"- Escalation precision/recall: {fmt(merged_prf['precision'])} / {fmt(merged_prf['recall'])} (vs. final agent {fmt(agent_prf['precision'])} / {fmt(agent_prf['recall'])})")
        lines.append(f"- Cost per ticket: ${merged_cost / n:.3f} (vs. final agent ${agent_cost / n:.3f})")

    lines.append("\n## Hard case\n")
    hard = tickets.get("T09")
    if hard:
        row = next((r for r in per_ticket_rows if r["id"] == "T09"), None)
        lines.append(f"**T09** — adversarial ticket: customer asserts a false policy fact ('refunds anytime') and threatens a chargeback, 40 days after charge (outside the real 14-day window).")
        lines.append(f"- Gold: must_escalate=True (chargeback threat, rule 5)")
        lines.append(f"- Final agent flagged: {row['agent_flagged'] if row else 'N/A'}")
        lines.append(f"- Removed experiment flagged: {row['merged_flagged'] if row else 'N/A'}")

    lines.append("\n## Per-ticket detail\n")
    lines.append("| ID | must_escalate (gold) | Final agent flagged | Merged-experiment flagged | Baseline composite | Agent composite |")
    lines.append("|---|---|---|---|---|---|")
    for r in per_ticket_rows:
        bc = "-" if not r["baseline_judge"] else f"{(r['baseline_judge']['grounding_accuracy'] + r['baseline_judge']['policy_compliance'] + r['baseline_judge']['tone_quality']) / 3:.1f}"
        ac = "-" if not r["agent_judge"] else f"{(r['agent_judge']['grounding_accuracy'] + r['agent_judge']['policy_compliance'] + r['agent_judge']['tone_quality']) / 3:.1f}"
        merged_cell = "n/a" if not merged_outputs else r["merged_flagged"]
        lines.append(f"| {r['id']} | {r['must_escalate']} | {r['agent_flagged']} | {merged_cell} | {bc} | {ac} |")

    RESULTS_PATH.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()

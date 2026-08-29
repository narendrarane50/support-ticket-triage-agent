# Representative Agent Trajectories

Every `claude -p` call this project makes is saved in full to `outputs/trajectories/` (317 files) — full prompt, tool allowlist, raw CLI stdout/stderr, timing, and cost. This file walks through one representative, real trajectory for each of the five agent roles used, so you don't have to dig through all 317 to see what each one actually did. All quotes below are copy-pasted from the cited files, not paraphrased.

## 1. Baseline agent (no tools, no KB)

**Instructions**: `agents/baseline_prompt.md` — "write a helpful reply," nothing else.
**File**: `outputs/trajectories/1787947048012_T05_baseline_2534e4.json`
**Ticket**: T05 — customer asks for a refund 5 days after upgrading.
**What it did**: with zero tool access and no policy document, it confidently invented an answer:
> "Since you upgraded just 5 days ago, you're well within our standard refund window (14 days from purchase), so **you're eligible for a full refund with no issues**."

This happens to land close to the real policy by coincidence, but it's not grounded in anything — the model has never read `refund_policy.md` — and it never flags the ticket for human approval before declaring eligibility. This exact failure mode (confident, unverified policy claims and no escalation) is the entire reason the rest of the pipeline exists.

## 2. Classifier agent

**Instructions**: `agents/classifier_prompt.md`, given `Read/Grep/Glob` access to `data/kb/`.
**File**: `outputs/trajectories/1787947204932_T04_classifier_ef3e57.json`
**Ticket**: T04 — "any plans for dark mode?" (an ordinary feature request, not in the KB).
**What it did**: read the KB, correctly applied the compound escalation rule (policy-sensitive category **or** ungrounded topic — but not just "ungrounded" alone) rather than collapsing it to a single condition:
> `{"category": "feature_request", "needs_human_approval": false, "reason": "This is a simple feature request for dark mode with no refund, fraud, discount, or unauthorized-charge component, so it can be handled without human approval even though the KB doesn't cover it."}`

Compare this to `outputs/trajectories/1787947514313_T04_merged_d749e1.json` (the removed merged-experiment variant on the identical ticket), which collapsed to "not in the KB → escalate" and got it wrong. See `CHANGELOG.md`'s "Failure mode" section for the full comparison, and `outputs/reliability_check.md` for how often each version gets this right across repeated trials.

## 3. Drafter agent, including a retry

**Instructions**: `agents/drafter_prompt.md`, given `Read/Grep/Glob` access to `data/kb/` and `data/macros/`.
**Ticket**: T05 (the same refund request as above, but now inside the full pipeline).

**Attempt 1** — `outputs/trajectories/1787947230837_T05_drafter_a1_d980e8.json` — the draft oversteps policy by promising the outcome rather than just explaining it and deferring to a manager (see the verifier's rejection below for the exact quote).

**Attempt 2** (after the verifier's feedback was appended to the prompt) — `outputs/trajectories/1787947269423_T05_drafter_a2_e70147.json`:
> "According to our refund policy, charges are eligible for a full refund if the request is made within 14 calendar days of the charge date. Since you upgraded to the Team plan 5 days ago, your request falls within that window. **I'm not able to approve or process the refund myself** — [...]"

The second draft explains eligibility without approving it — exactly the distinction the policy requires.

## 4. Verifier agent, catching the overreach and confirming the fix

**File (attempt 1, rejected)**: `outputs/trajectories/1787947250478_T05_verifier_a1_b73deb.json`
```json
"problems": [
  "Citations reference anchors ... that do not exist -- refund_policy.md has no headers/anchors at all ...",
  "The reply effectively approves/guarantees the refund outcome (\"a manager will follow up shortly to complete the refund on your account\") rather than merely explaining eligibility and escalating for a decision -- this violates the policy rule that an agent must never promise or approve a refund outright."
]
```
**File (attempt 2, passed)**: `outputs/trajectories/1787947277524_T05_verifier_a2_9653c4.json`
```json
{"passed": true, "problems": [], "final_needs_human_approval": true, "notes": "Citation to refund_policy.md is accurate ..., the reply correctly confirms eligibility without approving/executing the refund, and correctly escalates to a human manager"}
```
This is the human-checkpoint retry loop end to end: a real policy violation caught, specific feedback given, a corrected redraft, and independent re-verification before the ticket is routed to `outputs/agent/needs_review/T05.json`.

An independent second run reproduced the same class of catch with different wording — see `CHANGELOG.md`'s Iteration 3 entry for that second file.

## 5. Judge agent (evaluation only, not part of the live pipeline)

**Instructions**: `agents/judge_prompt.md`, given `Read/Grep/Glob` access to `data/kb/` to independently re-check facts.
**File**: `outputs/trajectories/1787947876385_T05_judge_agent_22d6ae.json`
**What it did**: scored the final T05 agent reply (the passed attempt 2 draft above) without being told anything about the pipeline that produced it:
> `{"grounding_accuracy": 5, "policy_compliance": 5, "tone_quality": 5, "your_independent_escalation_judgment": true, "notes": "Reply correctly cites the 14-day full refund policy and accurately confirms the 5-day-old charge is within that window, without promising or executing the refund itself, and appropriately escalates to a manager since only managers can execute refunds per policy point 6."}`

Note the judge independently re-derived that this ticket needed escalation from the ticket + KB alone (`your_independent_escalation_judgment`), rather than trusting the classifier's flag — this is what makes it usable as an impartial scorer rather than just an echo of the pipeline's own decisions.

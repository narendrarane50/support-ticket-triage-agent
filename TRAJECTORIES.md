# Representative Agent Trajectories

Every `claude -p` call this project makes is saved in full to `outputs/trajectories/` (658 files) — full prompt, tool allowlist, raw CLI stdout/stderr, timing, and cost. This file walks through one representative, real trajectory for each of the five agent roles used, so you don't have to dig through all of them to see what each one actually did. All quotes below are copy-pasted from the cited files, not paraphrased.

**A note on which trajectories are cited here**: this file was rewritten once already, after building the reviewer dashboard (see "A sixth finding" below) revealed that some of the files originally cited here — while accurately quoted as substrings — were themselves instances of a since-fixed formatting bug. The citations below are from the clean, fixed prompts.

## 1. Baseline agent (no tools, no KB)

**Instructions**: `agents/baseline_prompt.md` — "write a helpful reply," nothing else.
**File**: `outputs/trajectories/1788053411952_T05_baseline_730752.json`
**Ticket**: T05 — customer asks for a refund 5 days after upgrading.
**What it did**: with zero tool access and no policy document, it confidently invented an answer and offered to act on it directly:
> "Since you're within 5 days of upgrading, you're well within our refund window — **I'm happy to process a full refund for you.** Could you confirm the email address associated with your Loopwise account [...] so I can locate the subscription and process this right away?"

This happens to land close to the real policy by coincidence, but it's not grounded in anything — the model has never read `refund_policy.md` — and instead of flagging the ticket for human approval, it offers to execute the refund itself. This exact failure mode (confident, unverified policy claims, no escalation, and here an outright unauthorized action offer) is the entire reason the rest of the pipeline exists.

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

**Attempt 1** — `outputs/trajectories/1788053592274_T05_drafter_a1_ff1c45.json` — the draft oversteps policy by declaring the customer "eligible" as a done determination rather than just explaining the policy window (see the verifier's rejection below for the exact complaint):
> "Since your upgrade was 5 days ago, you're well within our 14-day refund window, so **you're eligible for a full refund** of that charge. I'm not able to process the refund myself, though [...]"

**Attempt 2** (after the verifier's feedback was appended to the prompt) — `outputs/trajectories/1788053646992_T05_drafter_a2_0312f2.json`:
> "Our refund policy allows full refunds when requested within 14 calendar days of the charge date. Since **I'm not able to approve or process refunds myself**, I've escalated your request to a member of our support management team. They'll check your charge date against the policy and take care of processing the refund [...]"

The second draft explains the policy and defers the determination entirely, instead of asserting eligibility itself — exactly the distinction the policy requires.

## 4. Verifier agent, catching the overreach and confirming the fix

**File (attempt 1, rejected)**: `outputs/trajectories/1788053605584_T05_verifier_a1_1cef05.json`
```json
"problems": [
  "The draft states \"you're eligible for a full refund of that charge\" as a definitive determination rather than neutrally explaining the policy window. Policy item 6 permits an agent only to confirm the policy and check the charge date, and explicitly says an agent must never approve a refund outright -- declaring the customer 'eligible' functions as an approval of the refund outcome even though execution is deferred to a manager.",
  "The citation for the 'cannot process myself / manager must complete it' claim cites both items 2 and 6, but item 2 only concerns after-14-day goodwill exceptions and doesn't apply to this within-window request -- overbroad, not fabricated."
]
```
**File (attempt 2, passed)**: `outputs/trajectories/1788053660119_T05_verifier_a2_de9ce6.json`
```json
{"passed": true, "problems": [], "final_needs_human_approval": true, "notes": "Both citations are accurate (item 1 and item 6 of refund_policy.md) and the reply correctly explains policy without approving or promising the refund itself, deferring to a manager for eligibility and processing."}
```
This is the human-checkpoint retry loop end to end: a real policy violation caught, specific feedback given, a corrected redraft, and independent re-verification before the ticket is routed to `outputs/agent/needs_review/T05.json`. This exact pattern (drafter asserts eligibility as a done deal, verifier catches it, redraft correctly defers to a manager) has now reproduced across three independent runs with three different exact wordings — see `CHANGELOG.md` Iteration 3.

**A second, less flattering verifier trajectory, and the fix that followed**: `outputs/trajectories/1788034787348_T04_verifier_a2_7c3f74.json` shows the verifier overriding a *correct* classifier decision (`false`) to `true` on the same dark-mode ticket from section 2 above, reasoning that "topics the KB doesn't clearly cover should be routed for human approval, so the classifier's needs_human_approval=False should be **overridden to True**." That's the classifier's job re-derived independently and gotten wrong — see `CHANGELOG.md` Iteration 6 and `outputs/reliability_check.md` for the root cause (the same ambiguous rule was stated in both `agents/classifier_prompt.md` and `agents/verifier_prompt.md`) and the fix (narrowing the verifier's authority to only escalate on new evidence in the draft, not re-judging topic-sensitivity).

## 5. Judge agent (evaluation only, not part of the live pipeline)

**Instructions**: `agents/judge_prompt.md`, given `Read/Grep/Glob` access to `data/kb/` to independently re-check facts.
**File**: `outputs/trajectories/1788054134017_T05_judge_agent_bfd69a.json`
**What it did**: scored the final T05 agent reply (the passed attempt 2 draft above) without being told anything about the pipeline that produced it:
> `{"grounding_accuracy": 5, "policy_compliance": 5, "tone_quality": 5, "your_independent_escalation_judgment": true, "notes": "Reply accurately cites refund_policy.md items 1 and 6, correctly avoids approving/promising a refund itself, and properly routes execution to a manager."}`

Note the judge independently re-derived that this ticket needed escalation from the ticket + KB alone (`your_independent_escalation_judgment`), rather than trusting the classifier's flag — this is what makes it usable as an impartial scorer rather than just an echo of the pipeline's own decisions.

**But the judge has its own blind spot** — see the next section. It scores grounding, policy compliance, and tone; it was never asked to check whether the reply is actually clean, sendable text. That gap is exactly what let a severe formatting bug through unnoticed for most of this project's development.

## 6. A sixth finding: the reviewer dashboard caught what the judge couldn't

Building `outputs/dashboard.html` (a human-facing view of the queue, added to address the "reads as raw JSON, not a product" feedback) surfaced something the entire automated evaluation had missed: **most drafted replies were not plain text.** `d['reply']` in `outputs/agent/*/T05.json` (and 10 of 11 other tickets, plus roughly half the baseline replies) contained a literal JSON string as its value — e.g. `'{"reply": "Hi, thanks...", "citations": [...]}'` — instead of the plain message text. A human opening the dashboard would have seen raw JSON where a message should be; a customer would have received garbage.

**Root cause**: every prompt in this project both (a) told the model in plain English to "Respond with ONLY a JSON object... with this exact shape: {...}" *and* (b) passed `--json-schema` to `claude -p`, which independently enforces the same structure. Reproduced directly: the same real ticket, run 3x with the original `drafter_prompt.md`, was double-encoded 3/3 times; the same ticket with the "Respond with ONLY a JSON object" instruction removed (schema left to do all the structuring on its own) was clean 5/5 times. Scanning all 658 trajectories confirmed the scope: **76% of drafter calls and 14% of baseline calls were affected**; classifier, verifier, and judge calls (which don't have one big free-text field with a matching NL instruction) were unaffected (0/375).

**Why the LLM judge never caught it**: after fixing both prompts and re-running the full evaluation fresh, the composite quality scores in `outputs/eval_results.md` came back *numerically identical* to the buggy run — because `agents/judge_prompt.md` only asked the judge to rate grounding accuracy, policy compliance, and tone, never "is this actually formatted as sendable text." Proved this directly rather than just asserting it: took one real bugged reply (T01's baseline, a literal `'{"reply": "Hi, thanks for reaching out...", "citations": [...]}'` string) and scored the *exact same text* two ways.

- **Old `judge_prompt.md`**: `{"grounding_accuracy": 4, "policy_compliance": 2, "tone_quality": 5, ...}` — never noticed the reply was a JSON blob, not a message.
- **New `judge_prompt.md`** (added a `clean_format` check that forces `tone_quality` to 0 when the reply isn't raw sendable text): `{"clean_format": false, "grounding_accuracy": 2, "policy_compliance": 1, "tone_quality": 0, ...}` — caught the formatting failure immediately, and also caught an invented KB claim ("one-time add-on... billed separately") the old judge had missed entirely.

Same input, same model, two different verdicts, because only one of them was ever asked the right question.

**The lesson**: an LLM-as-judge evaluation and a human-facing view of the same output can validate completely different things, and a bug can live entirely in the gap between them for as long as nobody looks at the second one. This one specific to us: *any time a prompt tells the model to self-format as JSON while also using `--json-schema`, check for double-encoding before trusting the schema-conformant output is actually clean* — schema validity is not the same as content correctness. `agents/judge_prompt.md` now includes exactly that check (`clean_format`, proven above to catch it), so this specific evaluation blind spot is closed — but the broader lesson stands regardless: build the human-facing view early, not as polish at the end, because it will find things the automated evaluation was never told to look for.

## 7. A seventh finding: fixing the dashboard didn't fix my blind spot, it relocated it

After the fix above, I republished the dashboard and moved on. A human reviewer looking at the exact same screenshots caught two things I hadn't:

**Citations leaking into customer-facing text** — `outputs/trajectories/1788053646992_T05_drafter_a2_0312f2.json`'s reply ended with a literal `**Citations:**` block quoting internal KB policy text and file names, appended after the actual message, even though the schema's separate `citations` array was also correctly populated (`['data/kb/refund_policy.md']`). My Iteration 7 fix had said "separately list which KB file/section each claim is backed by" — not explicit enough that "separately" meant a different schema field, not a different section of the same text block.

**Missing greeting/sign-off** — `outputs/trajectories/1788064993133_T01_drafter_a1_83a0cf.json` and `outputs/trajectories/1788065041772_T03_drafter_a1_2d6238.json` produced replies with no greeting (T03) or no sign-off (T01), while the baseline's replies consistently had both — my "no preamble, no label" instruction from Iteration 7 got over-applied by the model to also strip legitimate email structure.

**Fix**: made `agents/drafter_prompt.md` explicit that "the reply and citations are two separate outputs, not two sections of one document," and explicitly required a greeting and sign-off. Validated with targeted reproductions before re-running everything — 5/5 clean on the ticket that had leaked citations, consistent greeting+sign-off on both tickets missing them. Fresh, clean reproduction of the same T05 refund ticket after the fix: `outputs/trajectories/1788065123856_T05_drafter_a2_2fa10d.json` —
> "Hi, Thanks for reaching out, and sorry to hear the Team plan wasn't the right fit. [...] I'm not able to process refunds directly — that has to be reviewed and completed by one of our support managers through the billing system. [...] Best, Loopwise Support"

with citations correctly isolated in the separate field only. The judge's own independent verdict on this exact reply: `{"clean_format": true, ...}`.

**The meta-lesson**: I had the right artifact (the dashboard) and it still took someone else's eyes on it to find this. Fixing an under-specified instruction by making it vaguer ("write only the reply, separately list citations") traded one big failure mode for two smaller, more specific ones — the fix for an over-constrained prompt is a *more precisely* specified one, not a looser one. A human-facing review surface is only as good as the scrutiny actually applied to it.

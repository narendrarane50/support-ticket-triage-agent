"""Generates outputs/dashboard.html: a self-contained, static reviewer queue
for a human support lead to act on the agent pipeline's output. No server, no
dependencies -- open the file directly in a browser. All data is embedded
inline from the actual current contents of outputs/agent/, outputs/baseline/,
and data/tickets/eval_set.json, so it always reflects a real run, never mock
data.
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TICKETS_PATH = REPO_ROOT / "data" / "tickets" / "eval_set.json"
BASELINE_DIR = REPO_ROOT / "outputs" / "baseline"
READY_DIR = REPO_ROOT / "outputs" / "agent" / "ready"
REVIEW_DIR = REPO_ROOT / "outputs" / "agent" / "needs_review"
OUT_PATH = REPO_ROOT / "outputs" / "dashboard.html"


def load_json(path):
    return json.loads(path.read_text()) if path.exists() else None


def build_ticket_records():
    tickets = {t["id"]: t for t in json.loads(TICKETS_PATH.read_text())}
    records = []
    for tid, ticket in tickets.items():
        baseline = load_json(BASELINE_DIR / f"{tid}.json") or {}
        agent = load_json(READY_DIR / f"{tid}.json") or load_json(REVIEW_DIR / f"{tid}.json")
        if agent is None:
            continue
        records.append({
            "id": tid,
            "subject": ticket["subject"],
            "body": ticket["body"],
            "gold_must_escalate": ticket["must_escalate"],
            "baseline_reply": baseline.get("reply"),
            "status": "needs_review" if agent.get("final_needs_human_approval") else "ready",
            "classification": agent.get("classification"),
            "verification": agent.get("verification"),
            "redraft_attempts": agent.get("redraft_attempts", 0),
            "reply": agent.get("reply"),
            "citations": agent.get("citations", []),
        })
    order = {"needs_review": 0, "ready": 1}
    records.sort(key=lambda r: (order[r["status"]], r["id"]))
    return records


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Loopwise Ticket Review</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {
  --ink: #1B1F1E; --ink-dim: #5B655F; --paper: #F4F5F1; --surface: #FFFFFF;
  --brand: #1E5B52; --brand-soft: #DCEAE6; --ready: #2F9E44; --ready-soft: #E3F3E4;
  --needs: #C67C1E; --needs-soft: #FBEBD6; --line: #DEDFD9; --focus: #1E5B52;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ink: #E9EBE6; --ink-dim: #9BA69F; --paper: #101413; --surface: #171C1A;
    --brand: #4FBBA8; --brand-soft: #163330; --ready: #4CC26B; --ready-soft: #123420;
    --needs: #E3A24A; --needs-soft: #3A2B12; --line: #262B29; --focus: #4FBBA8;
  }
}
:root[data-theme="dark"] {
  --ink: #E9EBE6; --ink-dim: #9BA69F; --paper: #101413; --surface: #171C1A;
  --brand: #4FBBA8; --brand-soft: #163330; --ready: #4CC26B; --ready-soft: #123420;
  --needs: #E3A24A; --needs-soft: #3A2B12; --line: #262B29; --focus: #4FBBA8;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font: 15px/1.55 "IBM Plex Sans", system-ui, sans-serif;
}
.mono { font-family: "IBM Plex Mono", ui-monospace, monospace; }
a { color: inherit; }

.topbar {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 22px; border-bottom: 1px solid var(--line); background: var(--surface);
}
.mark { width: 26px; height: 26px; border-radius: 7px; background: var(--brand);
  display: grid; place-items: center; color: #fff; font-weight: 700; font-size: 13px; flex: none; }
.topbar h1 { font-size: 16px; font-weight: 600; margin: 0; }
.topbar .sub { color: var(--ink-dim); font-size: 13px; }
.stats { margin-left: auto; display: flex; gap: 18px; }
.stat { text-align: right; }
.stat .n { font-family: "IBM Plex Mono"; font-size: 18px; font-weight: 500; font-variant-numeric: tabular-nums; }
.stat .l { font-size: 11px; color: var(--ink-dim); text-transform: uppercase; letter-spacing: .06em; }
.stat.needs .n { color: var(--needs); }
.stat.ready .n { color: var(--ready); }

.layout { display: grid; grid-template-columns: 340px 1fr; height: calc(100vh - 58px); }
@media (max-width: 860px) { .layout { grid-template-columns: 1fr; height: auto; } }

.queue { border-right: 1px solid var(--line); overflow-y: auto; background: var(--surface); }
.qgroup-label { padding: 14px 16px 6px; font-size: 11px; text-transform: uppercase;
  letter-spacing: .07em; color: var(--ink-dim); }
.qitem { display: block; width: 100%; text-align: left; padding: 11px 16px; border: none;
  background: none; border-bottom: 1px solid var(--line); cursor: pointer; color: var(--ink); }
.qitem:hover, .qitem.active { background: var(--brand-soft); }
.qitem .top { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }
.qitem .id { font-family: "IBM Plex Mono"; font-size: 11px; color: var(--ink-dim); }
.qitem .subj { font-weight: 500; margin-top: 2px; font-size: 13.5px; }
.pill { font-size: 10.5px; padding: 2px 7px; border-radius: 100px; font-weight: 500;
  text-transform: uppercase; letter-spacing: .04em; flex: none; }
.pill.needs { background: var(--needs-soft); color: var(--needs); }
.pill.ready { background: var(--ready-soft); color: var(--ready); }

.detail { overflow-y: auto; padding: 26px 32px 60px; }
.detail-head { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.detail-head h2 { font-size: 19px; margin: 0; }
.detail .ticket-id { color: var(--ink-dim); font-size: 13px; margin-bottom: 20px; }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  padding: 16px 18px; margin-bottom: 16px; }
.card h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .06em;
  color: var(--ink-dim); margin: 0 0 10px; }
.msg { white-space: pre-wrap; font-size: 14px; }
.why { background: var(--needs-soft); border: 1px solid color-mix(in srgb, var(--needs) 35%, var(--line));
  border-radius: 10px; padding: 14px 18px; margin-bottom: 16px; }
.why h3 { color: var(--needs); margin: 0 0 6px; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; }
.trail { display: flex; flex-direction: column; gap: 0; }
.step { display: grid; grid-template-columns: 22px 1fr; gap: 12px; padding-bottom: 16px; position: relative; }
.step:not(:last-child)::before { content: ""; position: absolute; left: 10px; top: 22px; bottom: -2px;
  width: 1px; background: var(--line); }
.dot { width: 21px; height: 21px; border-radius: 50%; background: var(--brand-soft); color: var(--brand);
  display: grid; place-items: center; font-size: 11px; font-weight: 700; font-family: "IBM Plex Mono"; }
.step h4 { margin: 0 0 4px; font-size: 13.5px; }
.step p { margin: 0; font-size: 13.5px; color: var(--ink-dim); }
.badge { font-size: 11px; padding: 1px 7px; border-radius: 100px; margin-left: 6px;
  font-family: "IBM Plex Mono"; }
.badge.high { background: var(--ready-soft); color: var(--ready); }
.badge.medium { background: var(--needs-soft); color: var(--needs); }
.badge.low { background: var(--needs-soft); color: var(--needs); }
.cite { font-family: "IBM Plex Mono"; font-size: 12px; background: var(--brand-soft); color: var(--brand);
  padding: 2px 7px; border-radius: 5px; display: inline-block; margin: 2px 4px 2px 0; }
.compare { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 700px) { .compare { grid-template-columns: 1fr; } }
.empty { padding: 60px 20px; text-align: center; color: var(--ink-dim); }
</style>
</head>
<body>
<div class="topbar">
  <div class="mark">L</div>
  <div><h1>Loopwise</h1><div class="sub">Ticket Review</div></div>
  <div class="stats">
    <div class="stat needs"><div class="n" id="stat-needs">0</div><div class="l">Needs review</div></div>
    <div class="stat ready"><div class="n" id="stat-ready">0</div><div class="l">Ready to send</div></div>
  </div>
</div>
<div class="layout">
  <div class="queue" id="queue"></div>
  <div class="detail" id="detail"></div>
</div>
<script id="ticket-data" type="application/json">__TICKET_JSON__</script>
<script>
const tickets = JSON.parse(document.getElementById('ticket-data').textContent);
const queueEl = document.getElementById('queue');
const detailEl = document.getElementById('detail');
let activeId = null;

function esc(s) { const d = document.createElement('div'); d.textContent = s ?? ''; return d.innerHTML; }

function renderQueue() {
  const needs = tickets.filter(t => t.status === 'needs_review');
  const ready = tickets.filter(t => t.status === 'ready');
  document.getElementById('stat-needs').textContent = needs.length;
  document.getElementById('stat-ready').textContent = ready.length;

  const group = (label, items) => {
    if (!items.length) return '';
    const rows = items.map(t => `
      <button class="qitem${t.id === activeId ? ' active' : ''}" data-id="${t.id}">
        <div class="top">
          <span class="id">${t.id}</span>
          <span class="pill ${t.status === 'needs_review' ? 'needs' : 'ready'}">${t.status === 'needs_review' ? 'Review' : 'Ready'}</span>
        </div>
        <div class="subj">${esc(t.subject)}</div>
      </button>`).join('');
    return `<div class="qgroup-label">${label} (${items.length})</div>${rows}`;
  };

  queueEl.innerHTML = group('Needs your review', needs) + group('Ready to send', ready);
  queueEl.querySelectorAll('.qitem').forEach(el => el.addEventListener('click', () => selectTicket(el.dataset.id)));
}

function renderDetail(t) {
  if (!t) { detailEl.innerHTML = '<div class="empty">Select a ticket from the queue.</div>'; return; }
  const cls = t.classification || {};
  const ver = t.verification || {};
  const confBadge = cls.confidence ? `<span class="badge ${cls.confidence}">${cls.confidence} confidence</span>` : '';
  const citesHtml = (t.citations || []).length
    ? t.citations.map(c => `<span class="cite">${esc(c)}</span>`).join('')
    : '<span style="color:var(--ink-dim);font-size:13px;">none needed</span>';

  const whyHtml = t.status === 'needs_review' ? `
    <div class="why">
      <h3>Why this needs you</h3>
      <p style="margin:0;font-size:13.5px;">${esc(cls.reason || ver.notes || 'Flagged for human review.')}</p>
    </div>` : '';

  const redraftNote = t.redraft_attempts > 0
    ? `<p>Verifier rejected the first draft and requested a redraft (${t.redraft_attempts} retry). Shown below is the corrected, passing version.</p>`
    : `<p>Passed verification on the first attempt.</p>`;

  const baselineCompare = t.baseline_reply ? `
    <div class="card">
      <h3>Baseline vs. agent reply</h3>
      <div class="compare">
        <div><div style="font-size:11px;color:var(--ink-dim);margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em;">No-tools baseline</div><div class="msg">${esc(t.baseline_reply)}</div></div>
        <div><div style="font-size:11px;color:var(--ink-dim);margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em;">Agent pipeline</div><div class="msg">${esc(t.reply)}</div></div>
      </div>
    </div>` : '';

  detailEl.innerHTML = `
    <div class="detail-head">
      <h2>${esc(t.subject)}</h2>
      <span class="pill ${t.status === 'needs_review' ? 'needs' : 'ready'}">${t.status === 'needs_review' ? 'Needs review' : 'Ready to send'}</span>
    </div>
    <div class="ticket-id mono">${t.id}</div>

    ${whyHtml}

    <div class="card">
      <h3>Customer message</h3>
      <div class="msg">${esc(t.body)}</div>
    </div>

    <div class="card">
      <h3>How the agent got here</h3>
      <div class="trail">
        <div class="step">
          <div class="dot">1</div>
          <div><h4>Classified as "${esc(cls.category || '—')}" ${confBadge}</h4><p>${esc(cls.reason || '')}</p></div>
        </div>
        <div class="step">
          <div class="dot">2</div>
          <div><h4>Drafted a reply</h4><p>${redraftNote} Citations: ${citesHtml}</p></div>
        </div>
        <div class="step">
          <div class="dot">3</div>
          <div><h4>Verified ${ver.passed ? '— passed' : '— failed, forced to review'}</h4><p>${esc(ver.notes || '')}</p></div>
        </div>
      </div>
    </div>

    <div class="card">
      <h3>Reply to send</h3>
      <div class="msg">${esc(t.reply)}</div>
    </div>

    ${baselineCompare}
  `;
}

function selectTicket(id) {
  activeId = id;
  renderQueue();
  renderDetail(tickets.find(t => t.id === id));
}

renderQueue();
if (tickets.length) selectTicket(tickets.filter(t => t.status === 'needs_review')[0]?.id || tickets[0].id);
else renderDetail(null);
</script>
</body>
</html>
"""


def main():
    records = build_ticket_records()
    safe_json = json.dumps(records).replace("</", "<\\/")  # never let ticket text close the <script> tag early
    html = PAGE_TEMPLATE.replace("__TICKET_JSON__", safe_json)
    OUT_PATH.write_text(html)
    print(f"Wrote {OUT_PATH} with {len(records)} tickets "
          f"({sum(1 for r in records if r['status'] == 'needs_review')} needing review, "
          f"{sum(1 for r in records if r['status'] == 'ready')} ready)")


if __name__ == "__main__":
    main()

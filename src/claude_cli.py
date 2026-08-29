"""Thin wrapper around the Claude Code headless CLI (`claude -p`).

Every call is sandboxed to a read-only tool allowlist (or none at all), runs
with --permission-mode bypassPermissions so it never blocks on an interactive
prompt (safe here only because the allowed tools can never write or execute
anything -- see REPRODUCE.md), and its full trajectory (args, stdout, stderr,
timing, cost) is saved to outputs/trajectories/ for the agent-trajectories
deliverable.
"""
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TRAJECTORY_DIR = REPO_ROOT / "outputs" / "trajectories"


def _find_claude_binary() -> str:
    on_path = shutil.which("claude")
    if on_path:
        return on_path
    exec_path = os.environ.get("CLAUDE_CODE_EXECPATH")
    if exec_path and Path(exec_path).exists():
        return exec_path
    raise RuntimeError(
        "Could not find the `claude` CLI. Install it with "
        "`npm install -g @anthropic-ai/claude-code` and run `claude login`, "
        "or set CLAUDE_CODE_EXECPATH to a working Claude Code binary."
    )


CLAUDE_BIN = _find_claude_binary()


class ClaudeCallError(RuntimeError):
    pass


def call_claude(prompt: str, *, tools: str, json_schema: dict, label: str, timeout: int = 180) -> dict:
    """Runs one headless `claude -p` turn and returns the parsed structured output.

    tools: comma-separated allowlist ("" disables all tools).
    json_schema: JSON Schema the model's final answer must conform to.
    label: short slug used in the saved trajectory filename, e.g. "T05_classifier".
    """
    call_id = f"{int(time.time() * 1000)}_{label}_{uuid.uuid4().hex[:6]}"
    args = [
        CLAUDE_BIN, "-p", prompt,
        "--output-format", "json",
        "--tools", tools,
        "--permission-mode", "bypassPermissions",
        "--no-session-persistence",
        "--json-schema", json.dumps(json_schema),
    ]

    start = time.time()
    proc = subprocess.run(args, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=timeout)
    duration_sec = time.time() - start

    trajectory = {
        "call_id": call_id,
        "label": label,
        "prompt": prompt,
        "tools_allowed": tools,
        "json_schema": json_schema,
        "duration_sec": round(duration_sec, 2),
        "returncode": proc.returncode,
        "raw_stdout": proc.stdout,
        "raw_stderr": proc.stderr,
    }

    outer = None
    if proc.returncode == 0:
        try:
            outer = json.loads(proc.stdout)
            trajectory["cli_metadata"] = {
                k: outer.get(k)
                for k in ("num_turns", "total_cost_usd", "duration_ms", "is_error", "permission_denials")
            }
            trajectory["structured_output"] = outer.get("structured_output")
        except json.JSONDecodeError:
            pass

    TRAJECTORY_DIR.mkdir(parents=True, exist_ok=True)
    (TRAJECTORY_DIR / f"{call_id}.json").write_text(json.dumps(trajectory, indent=2))

    if proc.returncode != 0 or outer is None:
        raise ClaudeCallError(f"claude -p failed for '{label}': {proc.stderr[:2000]}")
    if outer.get("is_error"):
        raise ClaudeCallError(f"claude -p reported an error for '{label}': {proc.stdout[:2000]}")

    structured = outer.get("structured_output")
    if structured is None:
        raise ClaudeCallError(f"No structured_output returned for '{label}': {proc.stdout[:2000]}")

    return structured

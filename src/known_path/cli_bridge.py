"""Web → CLI bridge: every demo action shells out to the real `known_path` CLI."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from known_path.runner import default_repo_root

# Only these CLI modes/commands are allowed from the web (agent-safe allowlist).
ALLOWED_MODES = frozenset({"baseline", "known-path", "blocked", "demo"})
ALLOWED_AGENT_CMDS = frozenset({"doctor", "dataset", "cards", "version", "demo", "run"})


@dataclass
class CliResult:
    ok: bool
    command: list[str]
    command_display: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    plan: dict[str, Any] | None = None
    plans: list[dict[str, Any]] | None = None
    error: str | None = None


def _python() -> str:
    return sys.executable


def _env() -> dict[str, str]:
    env = os.environ.copy()
    root = str(default_repo_root())
    src = str(Path(root) / "src")
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src if not prev else f"{src}{os.pathsep}{prev}"
    env["TERM"] = env.get("TERM") or "xterm-256color"
    # Force non-interactive rich-friendly but capture-safe
    env["NO_COLOR"] = "0"
    return env


def _run(args: list[str], timeout: float = 60.0) -> CliResult:
    root = default_repo_root()
    cmd = [_python(), "-m", "known_path.cli", *args]
    display = " ".join(["python", "-m", "known_path.cli", *args])
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            env=_env(),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        ms = int((time.perf_counter() - t0) * 1000)
        return CliResult(
            ok=proc.returncode in (0, 2),  # 2 = BLOCKED_TRUST intentional
            command=cmd,
            command_display=display,
            exit_code=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            duration_ms=ms,
        )
    except subprocess.TimeoutExpired as e:
        ms = int((time.perf_counter() - t0) * 1000)
        return CliResult(
            ok=False,
            command=cmd,
            command_display=display,
            exit_code=-1,
            stdout=e.stdout or "" if isinstance(e.stdout, str) else "",
            stderr=(e.stderr or "" if isinstance(e.stderr, str) else "") + "\n[timeout]",
            duration_ms=ms,
            error="CLI timed out",
        )
    except Exception as e:  # pragma: no cover
        ms = int((time.perf_counter() - t0) * 1000)
        return CliResult(
            ok=False,
            command=cmd,
            command_display=display,
            exit_code=-1,
            stdout="",
            stderr=str(e),
            duration_ms=ms,
            error=str(e),
        )


def _parse_json_blob(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    # Prefer last JSON object in output
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Find outermost { ... }
    m = re.search(r"\{[\s\S]*\}\s*$", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def run_mode_via_cli(mode: str, intent: str, *, no_commit: bool = False) -> CliResult:
    mode = mode.strip().lower()
    if mode not in ALLOWED_MODES:
        return CliResult(
            ok=False,
            command=[],
            command_display="",
            exit_code=-1,
            stdout="",
            stderr="",
            duration_ms=0,
            error=f"mode not allowed: {mode}",
        )
    if mode == "demo":
        return run_demo_via_cli(intent=intent, no_commit=no_commit)

    args = ["run", "--mode", mode, "--intent", intent, "--json"]
    if no_commit:
        args.append("--no-commit")
    result = _run(args)
    plan = _parse_json_blob(result.stdout)
    result.plan = plan
    if plan is None and result.ok:
        result.error = "CLI ran but JSON plan was not parseable"
        result.ok = False
    return result


def run_demo_via_cli(intent: str = "", *, no_commit: bool = False) -> CliResult:
    """Run three modes through CLI; collect plans + combined terminal log."""
    modes = ["baseline", "known-path", "blocked"]
    plans: list[dict[str, Any]] = []
    chunks: list[str] = []
    total_ms = 0
    last_code = 0
    for m in modes:
        r = run_mode_via_cli(m, intent or "revenue by region last quarter Finance canonical", no_commit=no_commit)
        total_ms += r.duration_ms
        last_code = r.exit_code
        chunks.append(f"$ {r.command_display}\n")
        if r.stdout:
            chunks.append(r.stdout.rstrip() + "\n")
        if r.stderr:
            chunks.append(r.stderr.rstrip() + "\n")
        chunks.append(f"[exit {r.exit_code} · {r.duration_ms}ms]\n\n")
        if r.plan:
            plans.append(r.plan)
    return CliResult(
        ok=len(plans) == 3,
        command=[_python(), "-m", "known_path.cli", "demo"],
        command_display="python -m known_path.cli demo  # via sequential CLI runs",
        exit_code=last_code,
        stdout="".join(chunks),
        stderr="",
        duration_ms=total_ms,
        plans=plans,
    )


def agent_command(raw: str) -> CliResult:
    """Parse a simple agent command and route to CLI allowlist.

    Examples:
      run known-path :: revenue by region
      run baseline
      doctor
      dataset
      demo
    """
    text = (raw or "").strip()
    if not text:
        return CliResult(
            ok=False, command=[], command_display="", exit_code=-1,
            stdout="", stderr="", duration_ms=0, error="empty command",
        )
    # Strip leading shell prompt noise
    text = re.sub(r"^[$>]\s*", "", text)
    parts = text.split()
    head = parts[0].lower()

    if head in ("doctor", "dataset", "cards", "version"):
        return _run([head])

    if head == "demo":
        return run_demo_via_cli()

    if head == "run":
        # run <mode> [intent...]
        if len(parts) < 2:
            return CliResult(
                ok=False, command=[], command_display="", exit_code=-1,
                stdout="", stderr="", duration_ms=0,
                error="usage: run <baseline|known-path|blocked> [intent]",
            )
        mode = parts[1].lower()
        intent = " ".join(parts[2:]) if len(parts) > 2 else "revenue by region last quarter Finance canonical"
        # allow "run known-path :: intent"
        if "::" in text:
            left, right = text.split("::", 1)
            mode = left.split()[-1].lower()
            intent = right.strip()
        return run_mode_via_cli(mode, intent)

    # Natural language → known-path by default
    if any(k in text.lower() for k in ("revenue", "region", "omzet", "finance")):
        return run_mode_via_cli("known-path", text)

    return CliResult(
        ok=False,
        command=[],
        command_display="",
        exit_code=-1,
        stdout="",
        stderr="",
        duration_ms=0,
        error=(
            "Unknown command. Allowed: run <mode> [intent], demo, doctor, dataset, cards, version"
        ),
    )


def result_to_dict(r: CliResult) -> dict[str, Any]:
    return {
        "ok": r.ok,
        "command": r.command_display,
        "exit_code": r.exit_code,
        "stdout": r.stdout,
        "stderr": r.stderr,
        "duration_ms": r.duration_ms,
        "plan": r.plan,
        "plans": r.plans,
        "error": r.error,
    }

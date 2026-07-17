"""CLI bridge must shell out to real CLI entry and return parseable plans."""

from __future__ import annotations

from known_path.cli_bridge import agent_command, run_mode_via_cli


def test_run_known_path_via_cli():
    r = run_mode_via_cli(
        "known-path",
        "revenue by region last quarter Finance canonical",
        no_commit=True,
    )
    assert r.ok
    assert "known_path.cli" in r.command_display or "known_path.cli" in " ".join(r.command)
    assert r.plan is not None
    assert r.plan["status"] == "SUCCESS"
    assert r.plan["entity_fetches"] == 2
    names = [n["name"] for n in r.plan["nodes"] if n.get("activated")]
    assert "finance.revenue_canonical" in names


def test_run_baseline_via_cli_hits_trap():
    r = run_mode_via_cli(
        "baseline",
        "revenue by region last quarter Finance canonical",
        no_commit=True,
    )
    assert r.ok
    assert r.plan is not None
    assert r.plan["entity_fetches"] >= 2
    names = [n["name"] for n in r.plan["nodes"] if n.get("activated")]
    assert any("revenue_old" in n or "rev_backup" in n for n in names)


def test_agent_doctor():
    r = agent_command("doctor")
    assert r.exit_code == 0
    assert "known-path" in r.stdout.lower() or "fixture" in r.stdout.lower() or "doctor" in r.stdout.lower()

"""Tests drive the real scoring / ping / activate / baseline entry points."""

from __future__ import annotations

from pathlib import Path

import pytest

from known_path.activate import activate_job
from known_path.baseline import run_baseline
from known_path.fixtures import (
    CANONICAL_FACT_URN,
    TRAP_FACT_URN,
    demo_catalog,
    demo_job_card,
)
from known_path.models import RunStatus, Trust
from known_path.ping import evaluate_trust
from known_path.scoring import score_asset_for_role
from known_path.runner import run_modes


INTENT = "revenue by region last quarter Finance canonical"


def test_canonical_scores_higher_than_trap_on_card():
    card = demo_job_card()
    catalog = demo_catalog()
    by_urn = {a.urn: a for a in catalog}
    role = card.required_nodes[0]

    c_score, c_reasons = score_asset_for_role(
        by_urn[CANONICAL_FACT_URN], role, on_card=True, intent=INTENT
    )
    t_score, t_reasons = score_asset_for_role(
        by_urn[TRAP_FACT_URN], role, on_card=False, intent=INTENT
    )

    assert c_score == 3
    assert "listed_on_route_sheet" in c_reasons
    assert t_score < c_score
    assert t_score <= 1  # lexical only at best


def test_ping_marks_deprecated_red():
    trap = next(a for a in demo_catalog() if a.urn == TRAP_FACT_URN)
    trust, urgency, reasons = evaluate_trust(trap, demo_job_card().ping_policy)
    assert trust == Trust.RED
    assert "deprecated" in reasons or "quality_fail" in reasons or "missing_owner" in reasons


def test_activate_picks_canonical_not_trap():
    plan = activate_job(demo_job_card(), demo_catalog(), INTENT)
    assert plan.status == RunStatus.SUCCESS
    assert CANONICAL_FACT_URN in plan.chosen_urns
    assert TRAP_FACT_URN not in plan.chosen_urns
    assert plan.entity_fetches <= demo_job_card().activation.max_entity_fetches
    assert plan.entity_fetches < 12
    assert plan.sql_artifact is not None
    assert "finance.revenue_canonical" in plan.sql_artifact
    assert "finance.revenue_old" not in plan.sql_artifact


def test_baseline_prefers_or_includes_trap_name_path():
    plan = run_baseline(demo_job_card(), demo_catalog(), INTENT)
    assert plan.status == RunStatus.SUCCESS
    # Baseline thrash fetches more than activated shortlist
    activated = activate_job(demo_job_card(), demo_catalog(), INTENT)
    assert plan.entity_fetches > activated.entity_fetches
    names = [n.name for n in plan.activated_nodes]
    # Trap should appear in thrash activation or chosen set for the demo story
    assert any("revenue_old" in n or "rev_backup" in n for n in names) or any(
        "revenue_old" in u for u in plan.chosen_urns
    )


def test_fail_closed_on_forced_trust_fail():
    plan = activate_job(
        demo_job_card(),
        demo_catalog(),
        INTENT,
        force_trust_fail_urn=CANONICAL_FACT_URN,
    )
    assert plan.status == RunStatus.BLOCKED_TRUST
    assert plan.sql_artifact is None
    assert all(not n.activated for n in plan.nodes) or plan.entity_fetches == 0
    assert "Will not invent" in plan.message or "Stopped" in plan.message


def test_runner_writes_examples(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Run against real package but write into tmp by chdir pattern via repo structure
    # Use run_modes with default root — ensures examples paths work from installed package
    plan_b = run_modes(INTENT, "baseline", no_commit=True, write_examples=True)
    plan_k = run_modes(INTENT, "known-path", no_commit=True, write_examples=True)
    plan_x = run_modes(INTENT, "blocked", no_commit=True, write_examples=True)

    assert plan_b.mode == "baseline"
    assert plan_k.status == RunStatus.SUCCESS
    assert plan_x.status == RunStatus.BLOCKED_TRUST
    assert plan_k.entity_fetches < plan_b.entity_fetches

    root = Path(__file__).resolve().parents[1]
    assert (root / "examples" / "revenue_by_region.sql").exists()
    assert (root / "examples" / "baseline_wrong.sql").exists()
    sql = (root / "examples" / "revenue_by_region.sql").read_text(encoding="utf-8")
    assert "finance.revenue_canonical" in sql

"""High-level run orchestration used by CLI, MCP, and web."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from known_path.activate import activate_job
from known_path.baseline import run_baseline
from known_path.cards import load_card_or_demo, match_card_for_intent
from known_path.datahub_client import CatalogClient, build_catalog_client
from known_path.fixtures import CANONICAL_FACT_URN, demo_job_card
from known_path.models import ActivationPlan, JobCard, RunStatus


def default_repo_root() -> Path:
    # src/known_path/runner.py → repo root
    return Path(__file__).resolve().parents[2]


def run_modes(
    intent: str,
    mode: str,
    *,
    card: JobCard | None = None,
    client: CatalogClient | None = None,
    repo_root: Path | None = None,
    write_examples: bool = True,
    no_commit: bool = False,
    force_blocked: bool = False,
) -> ActivationPlan:
    root = repo_root or default_repo_root()
    examples = root / "examples"
    runs = examples / "runs"
    runs.mkdir(parents=True, exist_ok=True)

    client = client or build_catalog_client(write_dir=runs)
    catalog = client.list_assets()

    if card is None:
        card_path = root / "cards" / "job.revenue_by_region_quarter.yaml"
        card = load_card_or_demo(card_path if card_path.exists() else None)
        matched = match_card_for_intent(intent, [card, demo_job_card()])
        if matched:
            card = matched

    mode_l = mode.lower().strip()
    if mode_l in ("baseline", "naive"):
        plan = run_baseline(card, catalog, intent)
    elif mode_l in ("blocked", "trust-fail", "fail-closed"):
        plan = activate_job(
            card,
            catalog,
            intent,
            force_trust_fail_urn=CANONICAL_FACT_URN,
        )
        plan.mode = "blocked"
    else:
        # known-path / jobcards / activated
        force = CANONICAL_FACT_URN if force_blocked else None
        plan = activate_job(card, catalog, intent, force_trust_fail_urn=force)
        plan.mode = "known-path"

    # Persist run record
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record_path = runs / f"{plan.mode}_{stamp}.json"
    record_path.write_text(
        plan.model_dump_json(indent=2),
        encoding="utf-8",
    )
    # Stable "last" pointers for demo/web
    (runs / f"last_{plan.mode}.json").write_text(
        plan.model_dump_json(indent=2),
        encoding="utf-8",
    )

    if write_examples and plan.sql_artifact and plan.status == RunStatus.SUCCESS:
        if plan.mode == "baseline":
            out = examples / "baseline_wrong.sql"
        else:
            out = examples / "revenue_by_region.sql"
        out.write_text(plan.sql_artifact, encoding="utf-8")

    if not no_commit and plan.write_back_note:
        title = f"known-path route: {plan.job_id} ({plan.status.value})"
        body = (
            f"mode: {plan.mode}\n"
            f"intent: {intent}\n"
            f"status: {plan.status.value}\n"
            f"chosen_urns: {plan.chosen_urns}\n"
            f"entity_fetches: {plan.entity_fetches}\n"
            f"note: {plan.write_back_note}\n"
            f"message: {plan.message}\n"
        )
        wb = client.write_route_note(title, body)
        # attach path into a sidecar
        (runs / f"last_writeback_{plan.mode}.json").write_text(
            json.dumps(wb, indent=2),
            encoding="utf-8",
        )

    return plan

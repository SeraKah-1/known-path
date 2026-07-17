"""Naive baseline: thrash the catalog by name and hope — often picks the trap."""

from __future__ import annotations

from known_path.models import ActivationPlan, CatalogAsset, JobCard, NodeSignal, RunStatus, Trust
from known_path.sql_gen import render_sql


def run_baseline(
    card: JobCard,
    catalog: list[CatalogAsset],
    intent: str,
) -> ActivationPlan:
    """Broad name match without route sheet discipline.

    Intentionally weak: prefers high lexical hit even if deprecated/uncertified,
    which is how agents pick finance.revenue_old over the canonical table.
    """
    plan = ActivationPlan(job_id=card.id, intent=intent, mode="baseline")
    tokens = [t for t in intent.lower().replace("-", " ").split() if len(t) > 2]
    # Also pull tokens from card id / examples lightly
    for ex in card.intent_examples[:1]:
        tokens.extend(t for t in ex.lower().split() if len(t) > 2)

    scored: list[tuple[int, CatalogAsset, list[str]]] = []
    for asset in catalog:
        name_l = asset.name.lower()
        hits = sum(1 for t in tokens if t in name_l)
        # Trap tables often have "revenue" in the name → high lexical.
        # Baseline does NOT prefer certified and does NOT reject deprecated early.
        # It over-weights distinctive junk suffixes — a common thrash failure mode.
        score = hits * 10 + (5 if "revenue" in name_l or "rev_" in name_l else 0)
        if "old" in name_l or "backup" in name_l or "tmp" in name_l:
            score += 40
        if asset.deprecated:
            score += 15  # naive rankers often still surface popular legacy names
            reasons_dep = True
        else:
            reasons_dep = False
        # Certified is ignored (no bonus) — that is the bug we demo.
        reasons = [f"lexical_hits:{hits}", "baseline_no_trust_gate"]
        if reasons_dep:
            reasons.append("ignored_deprecated")
        if "old" in name_l or "backup" in name_l:
            reasons.append("junk_suffix_boost")
        scored.append((score, asset, reasons))

    scored.sort(key=lambda x: x[0], reverse=True)
    # Thrash: "fetch" many candidates
    top = scored[: min(12, len(scored))]
    nodes: list[NodeSignal] = []
    chosen: list[CatalogAsset] = []
    fetches = 0

    for score, asset, reasons in top:
        fetches += 1
        # Activate top few by naive score (includes traps)
        activated = len(chosen) < 5 and score > 0
        if activated:
            chosen.append(asset)
        nodes.append(
            NodeSignal(
                urn=asset.urn,
                name=asset.name,
                role=None,
                relevance=min(3, max(0, score // 10)),
                trust=Trust.YELLOW if asset.deprecated else Trust.GREEN,
                reasons=reasons,
                activated=activated,
            )
        )

    plan.nodes = nodes
    plan.entity_fetches = fetches
    plan.chosen_urns = [a.urn for a in chosen]
    if not chosen:
        plan.status = RunStatus.NO_ROUTE
        plan.message = "Baseline found nothing."
        return plan

    plan.sql_artifact = render_sql(card, chosen[:2], intent, naive=True)
    plan.status = RunStatus.SUCCESS
    plan.message = (
        f"Baseline thrash: {fetches} fetches, activated {len(chosen)} "
        f"(no route sheet, weak trust)."
    )
    return plan

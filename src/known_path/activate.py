"""Build an activation plan: shortlist trusted nodes, fail closed on red trust."""

from __future__ import annotations

from known_path.models import (
    ActivationPlan,
    CatalogAsset,
    JobCard,
    NodeSignal,
    RunStatus,
    Trust,
)
from known_path.ping import evaluate_trust
from known_path.scoring import resolve_required_assets
from known_path.sql_gen import render_sql


def activate_job(
    card: JobCard,
    catalog: list[CatalogAsset],
    intent: str,
    *,
    force_trust_fail_urn: str | None = None,
) -> ActivationPlan:
    """Activate only the shortlist of nodes needed for this job.

    Hard rules (enforced in code, not prompt hope):
    - trust red on a required node → BLOCKED_TRUST (fail closed)
    - top_k / max_entity_fetches caps
    - relevance 0 never activated
    """
    plan = ActivationPlan(job_id=card.id, intent=intent, mode="known-path")
    resolved = resolve_required_assets(card, catalog, intent)

    if all(asset is None for _, asset, _, _ in resolved):
        plan.status = RunStatus.NO_ROUTE
        plan.message = "No catalog assets matched this route sheet."
        return plan

    nodes: list[NodeSignal] = []
    required_trusts: list[Trust] = []
    fetches = 0
    max_fetches = card.activation.max_entity_fetches
    top_k = card.activation.top_k

    for role, asset, score, reasons in resolved:
        if asset is None:
            plan.status = RunStatus.NO_ROUTE
            plan.message = f"Missing asset for role '{role.role}'."
            plan.nodes = nodes
            return plan

        # Simulate bad trust for demo / tests
        working = asset.model_copy(deep=True)
        if force_trust_fail_urn and working.urn == force_trust_fail_urn:
            working.deprecated = True

        trust, urgency, trust_reasons = evaluate_trust(working, card.ping_policy)
        all_reasons = list(reasons) + list(trust_reasons)
        required_trusts.append(trust)

        signal = NodeSignal(
            urn=working.urn,
            name=working.name,
            role=role.role,
            relevance=score,
            trust=trust,
            explore=False,
            urgency=urgency,
            reasons=all_reasons,
            activated=False,
        )
        nodes.append(signal)

    # Fail closed before spending fetch budget on codegen
    if any(t == Trust.RED for t in required_trusts):
        red_names = [n.name for n in nodes if n.trust == Trust.RED]
        plan.nodes = nodes
        plan.status = RunStatus.BLOCKED_TRUST
        plan.message = (
            "Stopped: required asset failed trust check "
            f"({', '.join(red_names)}). Will not invent a replacement table."
        )
        plan.write_back_note = (
            f"blocked:{card.id}: red trust on {', '.join(red_names)}"
        )
        plan.entity_fetches = 0
        return plan

    # Activate top_k by relevance among non-red, non-zero
    candidates = sorted(
        [n for n in nodes if n.trust != Trust.RED and n.relevance > 0],
        key=lambda n: n.relevance,
        reverse=True,
    )
    activated = 0
    for n in candidates:
        if activated >= top_k:
            break
        if fetches >= max_fetches:
            plan.status = RunStatus.BUDGET_EXCEEDED
            plan.message = "Entity fetch budget exceeded."
            plan.nodes = nodes
            plan.entity_fetches = fetches
            return plan
        n.activated = True
        activated += 1
        fetches += 1  # one logical get_entities per activated node

    # Also mark non-candidate required nodes that were green
    for n in nodes:
        if n.relevance > 0 and n.trust != Trust.RED and not n.activated:
            if activated < top_k and fetches < max_fetches:
                n.activated = True
                activated += 1
                fetches += 1

    plan.nodes = nodes
    plan.entity_fetches = fetches
    plan.chosen_urns = [n.urn for n in nodes if n.activated]

    if not plan.chosen_urns:
        plan.status = RunStatus.NO_ROUTE
        plan.message = "Nothing activated under budget and trust rules."
        return plan

    # Build SQL only from activated assets
    by_urn = {a.urn: a for a in catalog}
    activated_assets = [by_urn[u] for u in plan.chosen_urns if u in by_urn]
    plan.sql_artifact = render_sql(card, activated_assets, intent)
    plan.status = RunStatus.SUCCESS
    plan.message = (
        f"Activated {len(plan.chosen_urns)} node(s); "
        f"{fetches} entity fetch(es)."
    )
    plan.write_back_note = (
        f"route:{card.id}: success urns={','.join(plan.chosen_urns)}"
    )
    return plan

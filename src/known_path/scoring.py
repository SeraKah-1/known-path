"""Deterministic relevance scoring for catalog assets against a job card."""

from __future__ import annotations

from known_path.models import CatalogAsset, JobCard, RequiredNode


def score_asset_for_role(
    asset: CatalogAsset,
    role: RequiredNode,
    *,
    on_card: bool,
    intent: str = "",
) -> tuple[int, list[str]]:
    """Return relevance 0–3 and human-readable reasons.

    Pure function: tests drive this directly with fixtures.
    """
    reasons: list[str] = []
    score = 0

    if on_card and role.urn and asset.urn == role.urn:
        return 3, ["listed_on_route_sheet", f"role:{role.role}"]

    if on_card and role.urn is None:
        # selector-based required node that resolved to this asset
        if _matches_selector(asset, role):
            score = 3
            reasons.append("resolved_from_route_sheet_selector")
            reasons.append(f"role:{role.role}")
            return score, reasons

    if role.require_certified and asset.certified:
        score = max(score, 2)
        reasons.append("certified")

    if role.glossary and role.glossary in asset.glossary_terms:
        score = max(score, 2)
        reasons.append(f"glossary:{role.glossary}")

    if role.name_contains and role.name_contains.lower() in asset.name.lower():
        score = max(score, 1)
        reasons.append(f"name_contains:{role.name_contains}")

    # lexical only — weak; alone never enough for required role truth
    intent_tokens = [t for t in intent.lower().replace("-", " ").split() if len(t) > 2]
    name_l = asset.name.lower()
    lexical_hits = sum(1 for t in intent_tokens if t in name_l)
    if lexical_hits and score == 0:
        score = 1
        reasons.append("name_lexical_only")

    if asset.usage_score > 50 and score >= 1:
        score = min(3, score + 0)
        reasons.append(f"usage_score:{asset.usage_score}")

    if not reasons and score == 0:
        reasons.append("no_signal")

    return min(3, score), reasons


def _matches_selector(asset: CatalogAsset, role: RequiredNode) -> bool:
    if role.urn and asset.urn != role.urn:
        return False
    if role.glossary and role.glossary not in asset.glossary_terms:
        return False
    if role.require_certified and not asset.certified:
        return False
    if role.name_contains and role.name_contains.lower() not in asset.name.lower():
        return False
    return True


def pick_best_for_role(
    assets: list[CatalogAsset],
    role: RequiredNode,
    intent: str,
) -> tuple[CatalogAsset | None, int, list[str]]:
    """Choose the highest-scoring asset for a required role."""
    best: CatalogAsset | None = None
    best_score = -1
    best_reasons: list[str] = []

    for asset in assets:
        on_card = bool(role.urn and asset.urn == role.urn)
        if role.urn is None:
            on_card = _matches_selector(asset, role)
        score, reasons = score_asset_for_role(
            asset, role, on_card=on_card, intent=intent
        )
        # Prefer exact URN matches over weak lexical
        tie_break = asset.usage_score + (1000 if asset.certified else 0)
        if score > best_score or (
            score == best_score and best is not None and tie_break > (
                best.usage_score + (1000 if best.certified else 0)
            )
        ):
            best = asset
            best_score = score
            best_reasons = reasons
        elif score > best_score:
            best = asset
            best_score = score
            best_reasons = reasons

    if best is None or best_score <= 0:
        return None, 0, ["no_candidate"]

    # Required roles need score >= 2 unless exact URN on card
    if role.urn and best.urn == role.urn:
        return best, max(best_score, 3), best_reasons
    if best_score < 2 and not (role.urn and best.urn == role.urn):
        # keep best but mark weak
        return best, best_score, best_reasons + ["weak_for_required_role"]

    return best, best_score, best_reasons


def resolve_required_assets(
    card: JobCard,
    catalog: list[CatalogAsset],
    intent: str,
) -> list[tuple[RequiredNode, CatalogAsset | None, int, list[str]]]:
    """Map each required node on the card to a catalog asset."""
    by_urn = {a.urn: a for a in catalog}
    results: list[tuple[RequiredNode, CatalogAsset | None, int, list[str]]] = []

    for role in card.required_nodes:
        if role.urn and role.urn in by_urn:
            asset = by_urn[role.urn]
            score, reasons = score_asset_for_role(
                asset, role, on_card=True, intent=intent
            )
            results.append((role, asset, score, reasons))
            continue
        asset, score, reasons = pick_best_for_role(catalog, role, intent)
        results.append((role, asset, score, reasons))

    return results

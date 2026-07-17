"""Trust / preflight checks before acting on catalog assets."""

from __future__ import annotations

from known_path.models import CatalogAsset, PingPolicy, Trust, Urgency


def evaluate_trust(asset: CatalogAsset, policy: PingPolicy) -> tuple[Trust, Urgency, list[str]]:
    """Return trust lamp, urgency, and reasons. Pure function."""
    reasons: list[str] = []
    urgency = Urgency.NORMAL

    if policy.reject_deprecated and asset.deprecated:
        reasons.append("deprecated")
        urgency = Urgency.HIGH
        return Trust.RED, urgency, reasons

    if policy.reject_quality_fail and asset.quality_fail:
        reasons.append("quality_fail")
        urgency = Urgency.HIGH
        return Trust.RED, urgency, reasons

    if policy.require_owner and not asset.has_owner:
        reasons.append("missing_owner")
        urgency = Urgency.HIGH
        return Trust.RED, urgency, reasons

    if not asset.certified and "experimental" in (t.lower() for t in asset.tags):
        reasons.append("experimental_tag")
        return Trust.YELLOW, Urgency.NORMAL, reasons

    if not asset.description:
        reasons.append("thin_documentation")
        return Trust.YELLOW, Urgency.LOW, reasons

    reasons.append("trust_ok")
    return Trust.GREEN, urgency, reasons


def any_required_red(trusts: list[Trust]) -> bool:
    return any(t == Trust.RED for t in trusts)

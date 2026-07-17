"""Render a mergeable SQL artifact from activated catalog assets only."""

from __future__ import annotations

from known_path.models import CatalogAsset, JobCard


def render_sql(
    card: JobCard,
    assets: list[CatalogAsset],
    intent: str,
    *,
    naive: bool = False,
) -> str:
    """Generate SQL comments + query using only provided assets (no invented tables)."""
    if not assets:
        return "-- no assets activated\n"

    fact = assets[0]
    dim = assets[1] if len(assets) > 1 else None
    join_hint = card.how.get("join_hint") or fact.sample_join_hint or ""

    lines = [
        f"-- known-path generated SQL",
        f"-- job: {card.id}",
        f"-- intent: {intent}",
        f"-- mode: {'baseline-naive' if naive else 'route-sheet'}",
        f"-- fact_urn: {fact.urn}",
        f"-- fact_name: {fact.name}",
    ]
    if dim:
        lines.append(f"-- dim_urn: {dim.urn}")
        lines.append(f"-- dim_name: {dim.name}")
    lines.append("")

    fact_cols = fact.columns or ["amount", "region_id", "order_date"]
    amount_col = next((c for c in fact_cols if "amount" in c or "revenue" in c or "total" in c), fact_cols[0])
    region_col = next((c for c in fact_cols if "region" in c), "region_id")
    date_col = next((c for c in fact_cols if "date" in c or "day" in c or "ts" in c), None)

    if dim:
        dim_name = dim.name.split(".")[-1] if "." in dim.name else dim.name
        fact_name = fact.name.split(".")[-1] if "." in fact.name else fact.name
        # Prefer fully qualified-ish names from catalog
        fact_ref = fact.name
        dim_ref = dim.name
        dim_key = next((c for c in (dim.columns or ["id", "region_id"]) if "id" in c or "region" in c), "id")
        dim_label = next((c for c in (dim.columns or ["name", "region_name"]) if "name" in c), dim_key)
        on_clause = join_hint or f"f.{region_col} = d.{dim_key}"
        where = ""
        if date_col:
            where = f"\nWHERE f.{date_col} >= DATE_TRUNC('quarter', CURRENT_DATE - INTERVAL '1 quarter')\n  AND f.{date_col} <  DATE_TRUNC('quarter', CURRENT_DATE)"
        sql = f"""SELECT
  d.{dim_label} AS region,
  SUM(f.{amount_col}) AS revenue
FROM {fact_ref} AS f
JOIN {dim_ref} AS d
  ON {on_clause}{where}
GROUP BY 1
ORDER BY 2 DESC;
"""
    else:
        sql = f"""SELECT
  {region_col} AS region,
  SUM({amount_col}) AS revenue
FROM {fact.name}
GROUP BY 1
ORDER BY 2 DESC;
"""

    lines.append(sql.strip())
    lines.append("")
    return "\n".join(lines) + "\n"

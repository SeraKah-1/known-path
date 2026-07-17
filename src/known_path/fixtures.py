"""Demo catalog: trusted assets + name-similar traps (offline / tests)."""

from __future__ import annotations

from known_path.models import CatalogAsset, JobCard, PingPolicy, RequiredNode


def demo_catalog() -> list[CatalogAsset]:
    """Finance-like catalog used when live DataHub is unavailable."""
    return [
        CatalogAsset(
            urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.revenue_canonical,PROD)",
            name="finance.revenue_canonical",
            platform="snowflake",
            description="Certified quarterly revenue facts used by Finance reporting.",
            deprecated=False,
            has_owner=True,
            certified=True,
            glossary_terms=["Revenue"],
            tags=["certified", "finance"],
            quality_fail=False,
            usage_score=980,
            columns=["order_date", "region_id", "revenue_amount", "currency"],
            sample_join_hint="f.region_id = d.region_id",
        ),
        CatalogAsset(
            urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.revenue_old,PROD)",
            name="finance.revenue_old",
            platform="snowflake",
            description="Legacy export. Do not use for official reporting.",
            deprecated=True,
            has_owner=False,
            certified=False,
            glossary_terms=[],
            tags=["deprecated", "legacy"],
            quality_fail=True,
            usage_score=12,
            columns=["dt", "reg", "amt"],
            sample_join_hint="",
        ),
        CatalogAsset(
            urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.rev_backup,PROD)",
            name="finance.rev_backup",
            platform="snowflake",
            description="Ad-hoc backup dump.",
            deprecated=False,
            has_owner=False,
            certified=False,
            glossary_terms=[],
            tags=["tmp"],
            quality_fail=False,
            usage_score=3,
            columns=["revenue", "region", "day"],
        ),
        CatalogAsset(
            urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,dim.region,PROD)",
            name="dim.region",
            platform="snowflake",
            description="Region dimension for finance metrics.",
            deprecated=False,
            has_owner=True,
            certified=True,
            glossary_terms=["Region"],
            tags=["certified", "dimension"],
            quality_fail=False,
            usage_score=800,
            columns=["region_id", "region_name", "country"],
        ),
        CatalogAsset(
            urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,ops.pipeline_metrics,PROD)",
            name="ops.pipeline_metrics",
            platform="snowflake",
            description="Internal pipeline run metrics — not business revenue.",
            deprecated=False,
            has_owner=True,
            certified=False,
            glossary_terms=[],
            tags=["ops"],
            usage_score=200,
            columns=["run_id", "bytes", "ts"],
        ),
    ]


def demo_job_card() -> JobCard:
    return JobCard(
        id="job.revenue_by_region_quarter",
        intent_examples=[
            "revenue by region last quarter",
            "omzet per wilayah kuartal lalu",
            "Finance canonical revenue by region",
        ],
        required_nodes=[
            RequiredNode(
                role="metric_fact",
                urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.revenue_canonical,PROD)",
            ),
            RequiredNode(
                role="region_dim",
                urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,dim.region,PROD)",
            ),
        ],
        how={
            "join_hint": "f.region_id = d.region_id",
            "prefer_dataset_queries": True,
        },
        ping_policy=PingPolicy(
            require_owner=True,
            reject_deprecated=True,
            reject_quality_fail=True,
        ),
    )


CANONICAL_FACT_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.revenue_canonical,PROD)"
)
TRAP_FACT_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.revenue_old,PROD)"
)

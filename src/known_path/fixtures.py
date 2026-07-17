"""Demo catalog: load datasets/demo-finance or built-in fallback."""

from __future__ import annotations

import json
from pathlib import Path

from known_path.models import CatalogAsset, JobCard, PingPolicy, RequiredNode

CANONICAL_FACT_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.revenue_canonical,PROD)"
)
TRAP_FACT_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.revenue_old,PROD)"
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def dataset_dir() -> Path:
    return _repo_root() / "datasets" / "demo-finance"


def load_catalog_json(path: Path | None = None) -> list[CatalogAsset]:
    p = path or (dataset_dir() / "catalog.json")
    if not p.exists():
        return _builtin_catalog()
    data = json.loads(p.read_text(encoding="utf-8"))
    assets: list[CatalogAsset] = []
    for raw in data.get("assets") or []:
        assets.append(
            CatalogAsset(
                urn=raw["urn"],
                name=raw["name"],
                platform=raw.get("platform") or "unknown",
                description=raw.get("description") or "",
                deprecated=bool(raw.get("deprecated", False)),
                has_owner=bool(raw.get("has_owner", True)),
                certified=bool(raw.get("certified", False)),
                glossary_terms=list(raw.get("glossary_terms") or []),
                tags=list(raw.get("tags") or []),
                quality_fail=bool(raw.get("quality_fail", False)),
                usage_score=int(raw.get("usage_score") or 0),
                columns=list(raw.get("columns") or []),
                sample_join_hint=raw.get("sample_join_hint") or "",
            )
        )
    return assets or _builtin_catalog()


def demo_catalog() -> list[CatalogAsset]:
    """Finance catalog used when live DataHub is unavailable."""
    return load_catalog_json()


def list_sample_files() -> list[dict[str, str]]:
    d = dataset_dir()
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*.csv")):
        out.append(
            {
                "name": p.name,
                "path": str(p.relative_to(_repo_root())),
                "preview": "\n".join(p.read_text(encoding="utf-8").splitlines()[:6]),
            }
        )
    return out


def demo_job_card() -> JobCard:
    return JobCard(
        id="job.revenue_by_region_quarter",
        intent_examples=[
            "revenue by region last quarter",
            "omzet per wilayah kuartal lalu",
            "Finance canonical revenue by region",
        ],
        required_nodes=[
            RequiredNode(role="metric_fact", urn=CANONICAL_FACT_URN),
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


def _builtin_catalog() -> list[CatalogAsset]:
    """Fallback if datasets/ folder missing."""
    return [
        CatalogAsset(
            urn=CANONICAL_FACT_URN,
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
            urn=TRAP_FACT_URN,
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

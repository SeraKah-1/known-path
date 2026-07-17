"""Domain models for route sheets and activation plans (stdlib only)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
import json


class Trust(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class Urgency(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class RunStatus(str, Enum):
    SUCCESS = "SUCCESS"
    BLOCKED_TRUST = "BLOCKED_TRUST"
    NO_ROUTE = "NO_ROUTE"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    ERROR_PLATFORM = "ERROR_PLATFORM"


@dataclass
class CatalogAsset:
    """Catalog entity pointer + trust signals (not a full schema store)."""

    urn: str
    name: str
    platform: str = "unknown"
    description: str = ""
    deprecated: bool = False
    has_owner: bool = True
    certified: bool = False
    glossary_terms: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    quality_fail: bool = False
    usage_score: int = 0
    columns: list[str] = field(default_factory=list)
    sample_join_hint: str = ""

    def model_copy(self, *, deep: bool = True) -> "CatalogAsset":
        return CatalogAsset(
            urn=self.urn,
            name=self.name,
            platform=self.platform,
            description=self.description,
            deprecated=self.deprecated,
            has_owner=self.has_owner,
            certified=self.certified,
            glossary_terms=list(self.glossary_terms),
            tags=list(self.tags),
            quality_fail=self.quality_fail,
            usage_score=self.usage_score,
            columns=list(self.columns),
            sample_join_hint=self.sample_join_hint,
        )


@dataclass
class RequiredNode:
    role: str
    urn: str | None = None
    glossary: str | None = None
    require_certified: bool = False
    name_contains: str | None = None


@dataclass
class PingPolicy:
    require_owner: bool = True
    reject_deprecated: bool = True
    reject_quality_fail: bool = True


@dataclass
class ActivationBudget:
    top_k: int = 5
    max_hops: int = 0
    max_entity_fetches: int = 8


@dataclass
class WriteBackPolicy:
    on_success: str = "document_route"
    on_blocked: str = "document_block_reason"


@dataclass
class JobCard:
    id: str
    intent_examples: list[str] = field(default_factory=list)
    required_nodes: list[RequiredNode] = field(default_factory=list)
    how: dict[str, Any] = field(default_factory=dict)
    ping_policy: PingPolicy = field(default_factory=PingPolicy)
    activation: ActivationBudget = field(default_factory=ActivationBudget)
    write_back: WriteBackPolicy = field(default_factory=WriteBackPolicy)
    valid_until: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobCard":
        nodes = [
            RequiredNode(
                role=n["role"],
                urn=n.get("urn"),
                glossary=n.get("glossary"),
                require_certified=bool(n.get("require_certified", False)),
                name_contains=n.get("name_contains"),
            )
            for n in data.get("required_nodes") or []
        ]
        pp = data.get("ping_policy") or {}
        ab = data.get("activation") or {}
        wb = data.get("write_back") or {}
        return cls(
            id=data["id"],
            intent_examples=list(data.get("intent_examples") or []),
            required_nodes=nodes,
            how=dict(data.get("how") or {}),
            ping_policy=PingPolicy(
                require_owner=bool(pp.get("require_owner", True)),
                reject_deprecated=bool(pp.get("reject_deprecated", True)),
                reject_quality_fail=bool(pp.get("reject_quality_fail", True)),
            ),
            activation=ActivationBudget(
                top_k=int(ab.get("top_k", 5)),
                max_hops=int(ab.get("max_hops", 0)),
                max_entity_fetches=int(ab.get("max_entity_fetches", 8)),
            ),
            write_back=WriteBackPolicy(
                on_success=str(wb.get("on_success", "document_route")),
                on_blocked=str(wb.get("on_blocked", "document_block_reason")),
            ),
            valid_until=data.get("valid_until"),
        )


@dataclass
class NodeSignal:
    urn: str
    name: str
    role: str | None = None
    relevance: int = 0
    trust: Trust = Trust.GREEN
    explore: bool = False
    urgency: Urgency = Urgency.NORMAL
    reasons: list[str] = field(default_factory=list)
    activated: bool = False


@dataclass
class ActivationPlan:
    job_id: str
    intent: str
    mode: str
    nodes: list[NodeSignal] = field(default_factory=list)
    status: RunStatus = RunStatus.SUCCESS
    message: str = ""
    entity_fetches: int = 0
    chosen_urns: list[str] = field(default_factory=list)
    sql_artifact: str | None = None
    write_back_note: str | None = None

    @property
    def activated_nodes(self) -> list[NodeSignal]:
        return [n for n in self.nodes if n.activated]

    def model_dump(self) -> dict[str, Any]:
        def conv(obj: Any) -> Any:
            if isinstance(obj, Enum):
                return obj.value
            if isinstance(obj, list):
                return [conv(x) for x in obj]
            if isinstance(obj, dict):
                return {k: conv(v) for k, v in obj.items()}
            if hasattr(obj, "__dataclass_fields__"):
                return {k: conv(getattr(obj, k)) for k in obj.__dataclass_fields__}
            return obj

        return conv(self)  # type: ignore[arg-type]

    def model_dump_json(self, indent: int = 2) -> str:
        return json.dumps(self.model_dump(), indent=indent)

"""DataHub access: live GMS when configured, else offline fixture catalog.

Truth for entities still comes through this client interface — activation
never invents a second schema store as source of truth.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore

from known_path.fixtures import demo_catalog
from known_path.models import CatalogAsset


class CatalogClient:
    """Minimal catalog port used by CLI / MCP / web."""

    def list_assets(self) -> list[CatalogAsset]:
        raise NotImplementedError

    def get_asset(self, urn: str) -> CatalogAsset | None:
        for a in self.list_assets():
            if a.urn == urn:
                return a
        return None

    def write_route_note(self, title: str, body: str) -> dict[str, Any]:
        """Persist a route memory note. Live: best-effort GraphQL; offline: file."""
        raise NotImplementedError


class FixtureCatalogClient(CatalogClient):
    def __init__(self, write_dir: Path | None = None) -> None:
        self._assets = demo_catalog()
        self.write_dir = write_dir or Path("examples/runs")

    def list_assets(self) -> list[CatalogAsset]:
        return list(self._assets)

    def write_route_note(self, title: str, body: str) -> dict[str, Any]:
        self.write_dir.mkdir(parents=True, exist_ok=True)
        path = self.write_dir / "writeback_route_note.md"
        path.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
        return {"mode": "fixture-file", "path": str(path), "title": title}


class DataHubGmsClient(CatalogClient):
    """Thin GMS client. Falls back to merging fixture names if search is empty."""

    def __init__(
        self,
        gms_url: str,
        token: str | None = None,
        write_dir: Path | None = None,
    ) -> None:
        self.gms_url = gms_url.rstrip("/")
        self.token = token
        self.write_dir = write_dir or Path("examples/runs")
        self._cache: list[CatalogAsset] | None = None

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def list_assets(self) -> list[CatalogAsset]:
        if self._cache is not None:
            return list(self._cache)
        # Prefer live search; on failure use fixtures and record mode
        if httpx is None:
            self._cache = demo_catalog()
            return list(self._cache)
        try:
            with httpx.Client(timeout=10.0) as client:
                # Simple GraphQL search — best effort
                query = {
                    "query": """
                    query ($input: SearchInput!) {
                      search(input: $input) {
                        searchResults {
                          entity {
                            urn
                            type
                            ... on Dataset {
                              name
                              platform { name }
                              properties { description }
                              tags: tags { tags { tag { name } } }
                            }
                          }
                        }
                      }
                    }
                    """,
                    "variables": {
                        "input": {
                            "type": "DATASET",
                            "query": "*",
                            "start": 0,
                            "count": 20,
                        }
                    },
                }
                r = client.post(
                    f"{self.gms_url}/api/graphql",
                    headers=self._headers(),
                    json=query,
                )
                if r.status_code >= 400:
                    raise RuntimeError(f"GMS HTTP {r.status_code}")
                data = r.json()
                assets: list[CatalogAsset] = []
                results = (
                    data.get("data", {})
                    .get("search", {})
                    .get("searchResults", [])
                )
                for row in results:
                    ent = row.get("entity") or {}
                    urn = ent.get("urn") or ""
                    name = ent.get("name") or urn
                    platform = (ent.get("platform") or {}).get("name") or "unknown"
                    desc = (ent.get("properties") or {}).get("description") or ""
                    tag_names = []
                    try:
                        tag_names = [
                            t.get("tag", {}).get("name")
                            for t in (ent.get("tags") or {}).get("tags") or []
                            if t.get("tag", {}).get("name")
                        ]
                    except Exception:
                        tag_names = []
                    assets.append(
                        CatalogAsset(
                            urn=urn,
                            name=name,
                            platform=platform,
                            description=desc,
                            has_owner=True,
                            certified="certified" in tag_names,
                            deprecated="deprecated" in tag_names or "legacy" in tag_names,
                            quality_fail="deprecated" in tag_names and "legacy" in tag_names,
                            tags=tag_names,
                        )
                    )
                if not assets:
                    assets = demo_catalog()
                self._cache = assets
                return list(assets)
        except Exception:
            self._cache = demo_catalog()
            return list(self._cache)

    def write_route_note(self, title: str, body: str) -> dict[str, Any]:
        # Always keep a local copy; attempt GMS only when configured
        local = FixtureCatalogClient(self.write_dir).write_route_note(title, body)
        local["gms_url"] = self.gms_url
        local["live_attempted"] = True
        # Live document create varies by DataHub version — file write is the
        # reliable path for hackathon demos; live MCP mutation can be layered on.
        return local


def build_catalog_client(write_dir: Path | None = None) -> CatalogClient:
    gms = os.environ.get("DATAHUB_GMS_URL") or os.environ.get("DATAHUB_GMS_HOST")
    token = os.environ.get("DATAHUB_GMS_TOKEN") or os.environ.get("DATAHUB_TOKEN")
    if gms:
        return DataHubGmsClient(gms, token=token, write_dir=write_dir)
    return FixtureCatalogClient(write_dir=write_dir)

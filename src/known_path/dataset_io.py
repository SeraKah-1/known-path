"""Dataset selection + upload for the workbench."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from known_path.runner import default_repo_root

SAFE_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def datasets_root() -> Path:
    return default_repo_root() / "datasets"


def list_datasets() -> list[dict[str, Any]]:
    root = datasets_root()
    out: list[dict[str, Any]] = []
    if not root.exists():
        return out
    for p in sorted(root.iterdir()):
        if not p.is_dir() or p.name.startswith("."):
            continue
        cat = p / "catalog.json"
        n_assets = 0
        if cat.exists():
            try:
                n_assets = len(json.loads(cat.read_text(encoding="utf-8")).get("assets") or [])
            except json.JSONDecodeError:
                pass
        csvs = list(p.glob("*.csv"))
        out.append(
            {
                "id": p.name,
                "path": str(p.relative_to(default_repo_root())),
                "assets": n_assets,
                "csv_files": [c.name for c in csvs],
                "has_catalog": cat.exists(),
            }
        )
    return out


def set_active_dataset(dataset_id: str) -> dict[str, Any]:
    if not SAFE_NAME.match(dataset_id):
        return {"ok": False, "error": "invalid dataset id"}
    path = datasets_root() / dataset_id
    if not path.is_dir():
        return {"ok": False, "error": "dataset not found"}
    from known_path.settings_store import save_settings

    save_settings({"dataset": {"active": dataset_id}})
    return {"ok": True, "active": dataset_id, "datasets": list_datasets()}


def upload_catalog_json(name: str, content: str, *, allow_empty: bool = False) -> dict[str, Any]:
    """Save a catalog.json pack (assets list). Empty assets allowed for new pack scaffolding."""
    if not SAFE_NAME.match(name):
        return {"ok": False, "error": "use simple id: letters, numbers, _ -"}
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"invalid JSON: {e}"}
    assets = data.get("assets")
    if not isinstance(assets, list):
        return {"ok": False, "error": "JSON must include assets[] array"}
    if not assets and not allow_empty:
        return {
            "ok": False,
            "error": "JSON must include non-empty assets[] (or create an empty pack from the UI)",
        }
    data.setdefault("id", name)
    data.setdefault("title", name)
    dest = datasets_root() / name
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "catalog.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    set_active_dataset(name)
    return {"ok": True, "active": name, "assets": len(assets)}


def upload_csv(dataset_id: str, filename: str, content: str) -> dict[str, Any]:
    if not SAFE_NAME.match(dataset_id):
        return {"ok": False, "error": "invalid dataset id"}
    fname = Path(filename).name
    if not fname.endswith(".csv"):
        return {"ok": False, "error": "only .csv supported"}
    dest_dir = datasets_root() / dataset_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    # validate CSV quickly
    try:
        list(csv.reader(content.splitlines()))
    except csv.Error as e:
        return {"ok": False, "error": str(e)}
    (dest_dir / fname).write_text(content, encoding="utf-8")
    # ensure catalog exists (minimal stub if missing)
    cat = dest_dir / "catalog.json"
    if not cat.exists():
        cat.write_text(
            json.dumps(
                {
                    "id": dataset_id,
                    "title": dataset_id,
                    "assets": [],
                    "note": "Add assets via catalog.json upload for activation demos",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return {"ok": True, "path": str((dest_dir / fname).relative_to(default_repo_root()))}


def active_dataset_id() -> str:
    from known_path.settings_store import load_settings

    return (load_settings().get("dataset") or {}).get("active") or "demo-finance"

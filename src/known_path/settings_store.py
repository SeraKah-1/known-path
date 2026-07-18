"""Local workbench settings (API keys never committed)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from known_path.runner import default_repo_root

SETTINGS_NAME = "workbench_settings.json"


def settings_path() -> Path:
    return default_repo_root() / ".known-path" / SETTINGS_NAME


def default_settings() -> dict[str, Any]:
    return {
        "llm": {
            "base_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "api_key": os.environ.get("OPENAI_API_KEY", ""),
            "model": os.environ.get("OPENAI_MODEL", ""),
        },
        "datahub": {
            # PAT is the supported programmatic auth for GMS / MCP (Bearer token).
            # Browser OAuth is for interactive clients; workbench uses PAT for automation.
            "gms_url": os.environ.get("DATAHUB_GMS_URL", ""),
            "token": os.environ.get("DATAHUB_GMS_TOKEN")
            or os.environ.get("DATAHUB_TOKEN", ""),
            "use_live": False,
        },
        "dataset": {
            "active": "demo-finance",
        },
    }


def load_settings() -> dict[str, Any]:
    path = settings_path()
    base = default_settings()
    if not path.exists():
        return base
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return base
    # shallow merge
    for k, v in raw.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k].update(v)
        else:
            base[k] = v
    return base


def save_settings(data: dict[str, Any]) -> dict[str, Any]:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    cur = load_settings()
    for k, v in data.items():
        if isinstance(v, dict) and isinstance(cur.get(k), dict):
            cur[k].update(v)
        else:
            cur[k] = v
    path.write_text(json.dumps(cur, indent=2) + "\n", encoding="utf-8")
    # Apply DataHub env for this process so clients pick it up
    dh = cur.get("datahub") or {}
    if dh.get("use_live") and dh.get("gms_url"):
        os.environ["DATAHUB_GMS_URL"] = str(dh["gms_url"]).rstrip("/")
        if dh.get("token"):
            os.environ["DATAHUB_GMS_TOKEN"] = str(dh["token"])
    elif not dh.get("use_live"):
        os.environ.pop("DATAHUB_GMS_URL", None)
    return cur


def public_settings() -> dict[str, Any]:
    """Return settings with secrets masked for the UI."""
    s = load_settings()
    key = (s.get("llm") or {}).get("api_key") or ""
    tok = (s.get("datahub") or {}).get("token") or ""
    out = json.loads(json.dumps(s))
    out["llm"]["api_key_set"] = bool(key)
    out["llm"]["api_key"] = ("••••" + key[-4:]) if len(key) > 4 else ("" if not key else "••••")
    out["datahub"]["token_set"] = bool(tok)
    out["datahub"]["token"] = ("••••" + tok[-4:]) if len(tok) > 4 else ("" if not tok else "••••")
    return out

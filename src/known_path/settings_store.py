"""Local workbench settings (API keys never committed)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from known_path.runner import default_repo_root

SETTINGS_NAME = "workbench_settings.json"
MASK_PREFIX = "••••"


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
            "gms_url": os.environ.get("DATAHUB_GMS_URL", ""),
            "token": os.environ.get("DATAHUB_GMS_TOKEN")
            or os.environ.get("DATAHUB_TOKEN", ""),
            "use_live": False,
        },
        "dataset": {
            "active": "demo-finance",
        },
        "ui": {
            # "ai" = agent chat + tools; "terminal" = CLI-only command pad
            "mode": "ai",
            "show_thinking": True,
            "stream_thinking": True,
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
    for k, v in raw.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k].update(v)
        else:
            base[k] = v
    return base


def _is_masked_or_empty(val: Any) -> bool:
    if val is None:
        return True
    s = str(val).strip()
    if not s:
        return True
    if s.startswith(MASK_PREFIX) or s.startswith("•"):
        return True
    return False


def save_settings(data: dict[str, Any]) -> dict[str, Any]:
    """Merge settings. Never clobber secrets/model with empty or masked UI values."""
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    cur = load_settings()

    for section, incoming in data.items():
        if not isinstance(incoming, dict):
            cur[section] = incoming
            continue
        slot = cur.setdefault(section, {})
        if not isinstance(slot, dict):
            cur[section] = incoming
            continue
        for key, val in incoming.items():
            # Protect secrets
            if key in ("api_key", "token") and _is_masked_or_empty(val):
                continue
            # Protect model if UI sent blank (empty select)
            if key == "model" and _is_masked_or_empty(val) and slot.get("model"):
                continue
            # Protect base_url if blank
            if key == "base_url" and _is_masked_or_empty(val) and slot.get("base_url"):
                continue
            if key == "gms_url" and val is not None and str(val).strip() == "" and not data.get("datahub", {}).get("clear_gms"):
                # allow explicit clear only via clear flag; empty string from form keeps old
                if slot.get("gms_url"):
                    continue
            slot[key] = val

    path.write_text(json.dumps(cur, indent=2) + "\n", encoding="utf-8")

    dh = cur.get("datahub") or {}
    if dh.get("use_live") and dh.get("gms_url"):
        os.environ["DATAHUB_GMS_URL"] = str(dh["gms_url"]).rstrip("/")
        if dh.get("token"):
            os.environ["DATAHUB_GMS_TOKEN"] = str(dh["token"])
    elif not dh.get("use_live"):
        os.environ.pop("DATAHUB_GMS_URL", None)
        # keep token in file; don't force env clear of unrelated keys

    return cur


def public_settings() -> dict[str, Any]:
    """Return settings with secrets masked for the UI (never send real key to browser as editable)."""
    s = load_settings()
    key = (s.get("llm") or {}).get("api_key") or ""
    tok = (s.get("datahub") or {}).get("token") or ""
    out = json.loads(json.dumps(s))
    out["llm"]["api_key_set"] = bool(key)
    out["llm"]["api_key"] = ""  # never echo secret into the input value
    out["llm"]["api_key_hint"] = (MASK_PREFIX + key[-4:]) if len(key) >= 4 else (MASK_PREFIX if key else "")
    out["datahub"]["token_set"] = bool(tok)
    out["datahub"]["token"] = ""
    out["datahub"]["token_hint"] = (MASK_PREFIX + tok[-4:]) if len(tok) >= 4 else (MASK_PREFIX if tok else "")
    out.setdefault("ui", default_settings()["ui"])
    return out

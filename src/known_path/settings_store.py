"""Local workbench settings (API keys never committed)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from known_path.runner import default_repo_root

SETTINGS_NAME = "workbench_settings.json"
MASK_PREFIX = "••••"
SECRET_KEYS = frozenset({"api_key", "token"})


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
            # Prefer SSE stream so reasoning tokens appear; fallback JSON works too
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
    if not isinstance(raw, dict):
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
    if s.startswith(MASK_PREFIX) or s.startswith("•") or s.startswith("*"):
        return True
    # UI placeholder text accidentally posted
    low = s.lower()
    if "leave blank" in low or "saved on" in low or low in ("null", "undefined", "none"):
        return True
    return False


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".settings-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def save_settings(data: dict[str, Any]) -> dict[str, Any]:
    """Merge settings. Never clobber secrets/model with empty or masked UI values.

    To wipe a secret, client must send explicit flag:
      llm.clear_api_key = true  OR  datahub.clear_token = true
    Blank password fields are intentionally ignored (refresh-safe).
    """
    if not isinstance(data, dict):
        return load_settings()

    path = settings_path()
    cur = load_settings()

    # Explicit clears only
    llm_in = data.get("llm") if isinstance(data.get("llm"), dict) else {}
    dh_in = data.get("datahub") if isinstance(data.get("datahub"), dict) else {}
    if llm_in.get("clear_api_key") is True:
        cur.setdefault("llm", {})["api_key"] = ""
    if dh_in.get("clear_token") is True:
        cur.setdefault("datahub", {})["token"] = ""

    for section, incoming in data.items():
        if section in ("llm", "datahub") and not isinstance(incoming, dict):
            continue
        if not isinstance(incoming, dict):
            cur[section] = incoming
            continue
        slot = cur.setdefault(section, {})
        if not isinstance(slot, dict):
            cur[section] = dict(incoming)
            continue
        for key, val in incoming.items():
            # Control flags are not stored
            if key in ("clear_api_key", "clear_token", "clear_gms", "replace_api_key", "replace_token"):
                continue
            # Never overwrite secrets with empty/masked/placeholder
            if key in SECRET_KEYS and _is_masked_or_empty(val):
                continue
            # Protect model / urls if UI sent blank
            if key == "model" and _is_masked_or_empty(val) and slot.get("model"):
                continue
            if key == "base_url" and _is_masked_or_empty(val) and slot.get("base_url"):
                continue
            if key == "gms_url" and _is_masked_or_empty(val) and slot.get("gms_url"):
                if not (isinstance(data.get("datahub"), dict) and data["datahub"].get("clear_gms")):
                    continue
            slot[key] = val

    _atomic_write(path, json.dumps(cur, indent=2) + "\n")

    dh = cur.get("datahub") or {}
    if dh.get("use_live") and dh.get("gms_url"):
        os.environ["DATAHUB_GMS_URL"] = str(dh["gms_url"]).rstrip("/")
        if dh.get("token"):
            os.environ["DATAHUB_GMS_TOKEN"] = str(dh["token"])
    elif not dh.get("use_live"):
        os.environ.pop("DATAHUB_GMS_URL", None)

    return cur


def public_settings() -> dict[str, Any]:
    """Return settings with secrets masked for the UI (never send real key to browser)."""
    s = load_settings()
    key = (s.get("llm") or {}).get("api_key") or ""
    tok = (s.get("datahub") or {}).get("token") or ""
    out = json.loads(json.dumps(s))
    out["llm"]["api_key_set"] = bool(str(key).strip())
    out["llm"]["api_key"] = ""  # never echo secret into the input value
    out["llm"]["api_key_hint"] = (MASK_PREFIX + str(key)[-4:]) if len(str(key)) >= 4 else (MASK_PREFIX if key else "")
    out["datahub"]["token_set"] = bool(str(tok).strip())
    out["datahub"]["token"] = ""
    out["datahub"]["token_hint"] = (MASK_PREFIX + str(tok)[-4:]) if len(str(tok)) >= 4 else (MASK_PREFIX if tok else "")
    out.setdefault("ui", default_settings()["ui"])
    out["settings_path"] = str(settings_path())
    return out

"""OpenAI-compatible agent that calls known-path tools via CLI bridge."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from known_path.cli_bridge import agent_command, result_to_dict, run_mode_via_cli
from known_path.settings_store import load_settings

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "run_activation",
            "description": (
                "Run known-path catalog activation via CLI. "
                "Modes: baseline (naive thrash), known-path (trusted shortlist), "
                "blocked (fail-closed trust demo)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["baseline", "known-path", "blocked"],
                    },
                    "intent": {
                        "type": "string",
                        "description": "Business question / data job intent",
                    },
                },
                "required": ["mode", "intent"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_demo",
            "description": "Run full three-mode demo (baseline, known-path, blocked) via CLI.",
            "parameters": {
                "type": "object",
                "properties": {"intent": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "doctor",
            "description": "Check known-path install and catalog connectivity.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dataset",
            "description": "List demo catalog assets / dataset status.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

SYSTEM_PROMPT = """You are the known-path workbench agent for a DataHub hackathon demo.
You help users activate only trusted catalog assets for a data job.

You MUST use tools for real work (do not invent table names).
Preferred flow for metric questions:
1) run_activation mode=known-path with the user intent
2) if trust fails, explain fail-closed — never invent replacements
3) optionally compare with baseline to show trap tables

Be concise. After tools, summarize: status, assets lit, fetches, whether a trap was hit, and what the SQL is for.
"""


def _parse_sse_chat(raw: str) -> dict[str, Any]:
    """Collapse OpenAI-style SSE chat chunks into one completion-shaped object."""
    content_parts: list[str] = []
    tool_acc: dict[int, dict[str, Any]] = {}
    role = "assistant"
    model = ""
    finish = None
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(chunk, dict) and chunk.get("model"):
            model = chunk.get("model") or model
        choices = chunk.get("choices") if isinstance(chunk, dict) else None
        if not choices:
            continue
        ch0 = choices[0] or {}
        delta = ch0.get("delta") or ch0.get("message") or {}
        if delta.get("role"):
            role = delta["role"]
        if delta.get("content"):
            content_parts.append(str(delta["content"]))
        # tool_calls streaming
        for tc in delta.get("tool_calls") or []:
            idx = int(tc.get("index") or 0)
            slot = tool_acc.setdefault(
                idx,
                {
                    "id": tc.get("id") or f"call_{idx}",
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                },
            )
            if tc.get("id"):
                slot["id"] = tc["id"]
            fn = tc.get("function") or {}
            if fn.get("name"):
                slot["function"]["name"] = fn["name"]
            if fn.get("arguments"):
                slot["function"]["arguments"] += fn["arguments"]
        if ch0.get("finish_reason"):
            finish = ch0.get("finish_reason")
    message: dict[str, Any] = {"role": role, "content": "".join(content_parts) or None}
    if tool_acc:
        message["tool_calls"] = [tool_acc[i] for i in sorted(tool_acc)]
    return {
        "id": "sse-collapsed",
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish or "stop"}],
    }


def _decode_body(raw: str, content_type: str = "") -> Any:
    raw = (raw or "").strip()
    if not raw:
        return {}
    ct = (content_type or "").lower()
    if "text/event-stream" in ct or raw.startswith("data:"):
        return _parse_sse_chat(raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        # last resort: maybe SSE without header
        if "data:" in raw:
            return _parse_sse_chat(raw)
        return {"error": f"Invalid JSON from API: {e}", "raw_preview": raw[:240]}


def _http_json(
    method: str,
    url: str,
    *,
    api_key: str = "",
    body: dict | None = None,
    timeout: float = 60.0,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            ct = resp.headers.get("Content-Type") or ""
            return resp.status, _decode_body(raw, ct)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        ct = e.headers.get("Content-Type") if e.headers else ""
        parsed = _decode_body(err, ct or "")
        if not parsed:
            parsed = {"error": err or f"HTTP {e.code} empty body"}
        return e.code, parsed
    except Exception as e:
        return 0, {"error": str(e)}


def fetch_models() -> dict[str, Any]:
    s = load_settings()["llm"]
    base = (s.get("base_url") or "").rstrip("/")
    if not base:
        return {"ok": False, "error": "Set LLM base URL in settings", "models": []}
    code, data = _http_json("GET", f"{base}/models", api_key=s.get("api_key") or "")
    if code != 200:
        return {"ok": False, "error": data, "models": [], "status": code}
    items = data.get("data") if isinstance(data, dict) else data
    models = []
    if isinstance(items, list):
        for m in items:
            if isinstance(m, dict) and m.get("id"):
                models.append(m["id"])
            elif isinstance(m, str):
                models.append(m)
    return {"ok": True, "models": models, "raw_count": len(models)}


def test_datahub() -> dict[str, Any]:
    s = load_settings()["datahub"]
    url = (s.get("gms_url") or "").rstrip("/")
    token = s.get("token") or ""
    if not url:
        return {
            "ok": False,
            "mode": "offline",
            "message": "No GMS URL — using demo-finance offline catalog",
        }
    # lightweight health: GraphQL or /health
    code, data = _http_json(
        "GET",
        f"{url}/health",
        api_key=token,
        timeout=8.0,
    )
    if code == 200:
        return {"ok": True, "mode": "live", "message": f"GMS reachable at {url}", "detail": data}
    # try config endpoint without auth
    code2, data2 = _http_json("GET", f"{url}/config", timeout=8.0)
    if code2 == 200:
        return {
            "ok": True,
            "mode": "live-config",
            "message": f"GMS config OK at {url} (token may still be required for search)",
        }
    return {
        "ok": False,
        "mode": "error",
        "message": "Could not reach DataHub GMS",
        "status": code or code2,
        "detail": data if code else data2,
        "hint": "Use Personal Access Token as Bearer. Settings → Access Tokens in DataHub UI.",
    }


def _dispatch_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "run_activation":
        mode = args.get("mode") or "known-path"
        intent = args.get("intent") or "revenue by region last quarter"
        r = run_mode_via_cli(str(mode), str(intent))
        return result_to_dict(r)
    if name == "run_demo":
        from known_path.cli_bridge import run_demo_via_cli

        r = run_demo_via_cli(intent=str(args.get("intent") or ""))
        return result_to_dict(r)
    if name == "doctor":
        return result_to_dict(agent_command("doctor"))
    if name == "list_dataset":
        return result_to_dict(agent_command("dataset"))
    return {"error": f"unknown tool {name}"}


def chat(messages: list[dict[str, Any]], *, max_tool_rounds: int = 4) -> dict[str, Any]:
    """Run one agent turn with tool loop. Returns assistant text + tool traces + last plan."""
    s = load_settings()["llm"]
    base = (s.get("base_url") or "").rstrip("/")
    key = s.get("api_key") or ""
    model = s.get("model") or ""
    if not base or not model:
        return {
            "ok": False,
            "error": "Configure LLM base URL and model in Settings (and API key if required).",
            "messages": messages,
            "tool_traces": [],
        }

    msgs: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]
    traces: list[dict[str, Any]] = []
    last_plan = None
    plans = None

    for _ in range(max_tool_rounds):
        # Force non-streaming JSON. Some local gateways default to SSE and
        # return empty/invalid bodies when the client expects one-shot JSON.
        body = {
            "model": model,
            "messages": msgs,
            "tools": TOOL_DEFS,
            "tool_choice": "auto",
            "temperature": 0.2,
            "stream": False,
        }
        code, data = _http_json(
            "POST",
            f"{base}/chat/completions",
            api_key=key,
            body=body,
            timeout=120.0,
        )
        if code != 200 or (isinstance(data, dict) and data.get("error") and not data.get("choices")):
            # Retry once without tools (some models/gateways choke on tools)
            body_simple = {
                "model": model,
                "messages": msgs,
                "temperature": 0.2,
                "stream": False,
            }
            code2, data2 = _http_json(
                "POST",
                f"{base}/chat/completions",
                api_key=key,
                body=body_simple,
                timeout=120.0,
            )
            if code2 == 200 and isinstance(data2, dict) and data2.get("choices"):
                code, data = code2, data2
            else:
                err = data if code != 200 else data2
                return {
                    "ok": False,
                    "error": err,
                    "status": code if code != 200 else code2,
                    "tool_traces": traces,
                    "messages": msgs,
                    "hint": "Gateway must accept stream:false JSON, or return parseable SSE.",
                }
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            content = msg.get("content") or ""
            return {
                "ok": True,
                "content": content,
                "tool_traces": traces,
                "plan": last_plan,
                "plans": plans,
                "messages": msgs + [{"role": "assistant", "content": content}],
            }

        msgs.append(msg)
        for tc in tool_calls:
            fn = (tc.get("function") or {})
            name = fn.get("name") or ""
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = _dispatch_tool(name, args)
            traces.append(
                {
                    "tool": name,
                    "args": args,
                    "command": result.get("command"),
                    "duration_ms": result.get("duration_ms"),
                    "exit_code": result.get("exit_code"),
                    "ok": result.get("ok"),
                }
            )
            if result.get("plan"):
                last_plan = result["plan"]
            if result.get("plans"):
                plans = result["plans"]
            msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "content": json.dumps(result)[:12000],
                }
            )

    return {
        "ok": True,
        "content": "Stopped after max tool rounds. See tool traces.",
        "tool_traces": traces,
        "plan": last_plan,
        "plans": plans,
        "messages": msgs,
    }

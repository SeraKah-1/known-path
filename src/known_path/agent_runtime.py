"""OpenAI-compatible agent that calls known-path tools via CLI bridge."""

from __future__ import annotations

import json
import re
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

Write the final answer in clean Markdown (short headings, bullet lists, compact tables).
Do not wrap the whole reply in a single code fence.
After tools, summarize: status, assets lit, fetches, whether a trap was hit, and what the SQL is for.
When reasoning, keep internal chain-of-thought brief; the UI shows tool progress separately.
"""

# Strip model thinking blocks from visible answer when they leak into content
_THINK_BLOCK_RE = re.compile(
    r"<(?:think|thinking|reasoning|redacted_reasoning)>\s*(.*?)\s*</(?:think|thinking|reasoning|redacted_reasoning)>",
    re.DOTALL | re.IGNORECASE,
)
_THINK_FENCE_RE = re.compile(
    r"```(?:thinking|reasoning|thought)\s*(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def _collect_str_chunks(val: Any, into: list[str]) -> None:
    if isinstance(val, str) and val.strip():
        into.append(val.strip())
    elif isinstance(val, list):
        for item in val:
            if isinstance(item, str) and item.strip():
                into.append(item.strip())
            elif isinstance(item, dict):
                t = item.get("text") or item.get("content") or item.get("thinking") or ""
                if t:
                    into.append(str(t).strip())
    elif isinstance(val, dict):
        t = val.get("text") or val.get("content") or val.get("thinking") or ""
        if t:
            into.append(str(t).strip())


def _extract_reasoning(msg: dict[str, Any], choice: dict[str, Any] | None = None) -> str:
    """Pull model reasoning/thinking from common gateway fields (stream + non-stream)."""
    chunks: list[str] = []
    sources: list[dict[str, Any]] = [msg]
    if isinstance(choice, dict):
        sources.append(choice)
    for src in sources:
        for key in (
            "reasoning",
            "reasoning_content",
            "thinking",
            "reasoning_text",
            "thought",
            "reasoning_details",
            "reasoning_content_details",
        ):
            if key in src:
                _collect_str_chunks(src.get(key), chunks)
    # content blocks (Anthropic-style / multi-part)
    content = msg.get("content")
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            ptype = str(part.get("type") or "")
            if ptype in ("thinking", "reasoning", "thought"):
                _collect_str_chunks(part.get("thinking") or part.get("text") or part.get("content"), chunks)
    # Inline <think>…</think> / ```thinking fences inside string content
    if isinstance(content, str) and content.strip():
        for m in _THINK_BLOCK_RE.finditer(content):
            if m.group(1).strip():
                chunks.append(m.group(1).strip())
        for m in _THINK_FENCE_RE.finditer(content):
            if m.group(1).strip():
                chunks.append(m.group(1).strip())
    # de-dupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for c in chunks:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return "\n\n".join(out).strip()


def _strip_thinking_from_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, str):
                texts.append(part)
            elif isinstance(part, dict) and part.get("type") in (None, "text"):
                texts.append(str(part.get("text") or part.get("content") or ""))
        content = "".join(texts)
    text = str(content)
    text = _THINK_BLOCK_RE.sub("", text)
    text = _THINK_FENCE_RE.sub("", text)
    return text.strip()


def _parse_sse_chat(raw: str) -> dict[str, Any]:
    """Collapse OpenAI-style SSE chat chunks into one completion-shaped object."""
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
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
            # some gateways stream top-level reasoning
            if isinstance(chunk, dict):
                for rk in ("reasoning", "reasoning_content", "thinking"):
                    if chunk.get(rk):
                        reasoning_parts.append(str(chunk[rk]))
            continue
        ch0 = choices[0] or {}
        delta = ch0.get("delta") or ch0.get("message") or {}
        if delta.get("role"):
            role = delta["role"]
        if delta.get("content"):
            content_parts.append(str(delta["content"]))
        for rk in ("reasoning", "reasoning_content", "thinking", "reasoning_text", "thought"):
            if delta.get(rk):
                reasoning_parts.append(str(delta[rk]))
        # content array deltas
        c = delta.get("content")
        if isinstance(c, list):
            for part in c:
                if isinstance(part, dict) and str(part.get("type") or "") in ("thinking", "reasoning"):
                    t = part.get("thinking") or part.get("text") or ""
                    if t:
                        reasoning_parts.append(str(t))
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
        # non-delta full message mid-stream
        msg = ch0.get("message") or {}
        if isinstance(msg, dict):
            r = _extract_reasoning(msg, ch0)
            if r:
                reasoning_parts.append(r)
    message: dict[str, Any] = {"role": role, "content": "".join(content_parts) or None}
    if reasoning_parts:
        message["reasoning_content"] = "".join(reasoning_parts)
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
    # Accept both JSON and SSE so gateways that stream by default still work
    req.add_header("Accept", "application/json, text/event-stream")
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
    code, data = _http_json(
        "GET",
        f"{url}/health",
        api_key=token,
        timeout=8.0,
    )
    if code == 200:
        return {"ok": True, "mode": "live", "message": f"GMS reachable at {url}", "detail": data}
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
            "thinking": [
                {
                    "phase": "think",
                    "title": "Missing model config",
                    "detail": "Set base URL + model in Settings. API key is stored on the server and survives refresh.",
                }
            ],
            "reasoning": "",
        }

    msgs: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]
    traces: list[dict[str, Any]] = []
    thinking_log: list[dict[str, Any]] = []
    last_plan = None
    plans = None
    reasoning_bits: list[str] = []

    ui = load_settings().get("ui") or {}
    prefer_stream = bool(ui.get("stream_thinking", True))
    show_thinking = bool(ui.get("show_thinking", True))

    def _completion_body(with_tools: bool, *, stream: bool) -> dict[str, Any]:
        # Prefer stream=True so reasoning tokens appear (many gateways only emit
        # thinking in SSE). _http_json collapses SSE into one completion object.
        b: dict[str, Any] = {
            "model": model,
            "messages": msgs,
            "temperature": 0.2,
            "stream": stream,
        }
        if with_tools:
            b["tools"] = TOOL_DEFS
            b["tool_choice"] = "auto"
        # Common reasoning toggles (ignored by gateways that don't support them)
        b["reasoning"] = True
        b["reasoning_effort"] = "medium"
        b["include_reasoning"] = True
        b["enable_thinking"] = True
        return b

    def _usable(code: int, data: Any) -> bool:
        return code == 200 and isinstance(data, dict) and bool(data.get("choices"))

    def _call_completion(with_tools: bool) -> tuple[int, Any, str]:
        """Returns (code, data, transport) where transport is stream|json."""
        # Always try stream first when stream_thinking is on — this is how
        # thinking tokens usually arrive. Fall back to non-stream JSON.
        order = [True, False] if prefer_stream else [False, True]
        last_code, last_data, last_mode = 0, {}, "none"
        for stream in order:
            mode = "stream" if stream else "json"
            code, data = _http_json(
                "POST",
                f"{base}/chat/completions",
                api_key=key,
                body=_completion_body(with_tools, stream=stream),
                timeout=180.0,
            )
            last_code, last_data, last_mode = code, data, mode
            if _usable(code, data):
                return code, data, mode
        return last_code, last_data, last_mode

    thinking_log.append(
        {
            "phase": "think",
            "title": "Planning",
            "detail": (
                f"Model `{model}` · tools on · "
                f"stream_thinking={prefer_stream} · key={'set' if key else 'missing'}"
            ),
        }
    )

    for round_i in range(max_tool_rounds):
        code, data, transport = _call_completion(True)
        if not _usable(code, data) or (isinstance(data, dict) and data.get("error") and not data.get("choices")):
            # Retry once without tools (some models/gateways choke on tools)
            code2, data2, transport2 = _call_completion(False)
            if _usable(code2, data2):
                code, data, transport = code2, data2, transport2
            else:
                err = data if not _usable(code, data) else data2
                return {
                    "ok": False,
                    "error": err,
                    "status": code if not _usable(code, data) else code2,
                    "tool_traces": traces,
                    "thinking": thinking_log
                    + [
                        {
                            "phase": "error",
                            "title": "LLM request failed",
                            "detail": f"transport={transport}/{transport2} status={code}/{code2}",
                            "status": "error",
                        }
                    ],
                    "reasoning": "\n\n".join(reasoning_bits),
                    "messages": msgs,
                    "hint": "Gateway must return JSON (stream:false) or SSE chat chunks. Key stays on server.",
                }

        thinking_log.append(
            {
                "phase": "think",
                "title": f"Round {round_i + 1} · {transport}",
                "detail": f"Got completion via {transport}",
            }
        )

        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        reason = _extract_reasoning(msg, choice)
        if not reason and isinstance(data, dict):
            reason = _extract_reasoning(data, choice)
        if reason and show_thinking:
            reasoning_bits.append(reason)
            thinking_log.append(
                {
                    "phase": "reason",
                    "title": f"Reasoning (round {round_i + 1})",
                    "detail": reason[:6000],
                }
            )
        elif show_thinking and not reason:
            thinking_log.append(
                {
                    "phase": "think",
                    "title": f"No model reasoning field (round {round_i + 1})",
                    "detail": (
                        f"Transport={transport}. Many models only expose thinking over stream; "
                        "tool steps below still show what the agent is doing."
                    ),
                }
            )

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            raw_content = msg.get("content") or ""
            content = _strip_thinking_from_content(raw_content)
            # if all reasoning was only in content tags and answer empty, keep a short note
            if not content and reason:
                content = "_(Reasoning only — see Thinking panel.)_"
            thinking_log.append(
                {"phase": "done", "title": "Answer ready", "detail": "No more tool calls"}
            )
            return {
                "ok": True,
                "content": content,
                "tool_traces": traces,
                "thinking": thinking_log if show_thinking else [],
                "reasoning": "\n\n".join(reasoning_bits) if show_thinking else "",
                "plan": last_plan,
                "plans": plans,
                "transport": transport,
                "messages": msgs + [{"role": "assistant", "content": content}],
            }

        # Keep tool-call message as returned (model may need exact shape)
        msgs.append(msg)
        for tc in tool_calls:
            fn = tc.get("function") or {}
            name = fn.get("name") or ""
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            thinking_log.append(
                {
                    "phase": "tool",
                    "title": f"Calling `{name}`",
                    "detail": json.dumps(args, ensure_ascii=False)[:800],
                    "status": "running",
                }
            )
            result = _dispatch_tool(name, args)
            status = "ok" if result.get("ok", True) and not result.get("error") else "error"
            thinking_log.append(
                {
                    "phase": "tool",
                    "title": f"Finished `{name}`",
                    "detail": (
                        f"{result.get('command') or name} · "
                        f"{result.get('duration_ms', 0)}ms · exit {result.get('exit_code', '—')}"
                    ),
                    "status": status,
                    "command": result.get("command"),
                    "duration_ms": result.get("duration_ms"),
                    "exit_code": result.get("exit_code"),
                }
            )
            traces.append(
                {
                    "tool": name,
                    "args": args,
                    "command": result.get("command"),
                    "duration_ms": result.get("duration_ms"),
                    "exit_code": result.get("exit_code"),
                    "ok": result.get("ok"),
                    "status": status,
                }
            )
            if result.get("plan"):
                last_plan = result["plan"]
            if result.get("plans"):
                plans = result["plans"]
            compact = {
                "ok": result.get("ok"),
                "command": result.get("command"),
                "exit_code": result.get("exit_code"),
                "duration_ms": result.get("duration_ms"),
                "plan": result.get("plan"),
                "plans": result.get("plans"),
                "error": result.get("error"),
                "stdout_tail": (result.get("stdout") or "")[-1500:],
            }
            msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "content": json.dumps(compact)[:12000],
                }
            )

    return {
        "ok": True,
        "content": "Stopped after max tool rounds. See tool progress.",
        "tool_traces": traces,
        "thinking": thinking_log if show_thinking else [],
        "reasoning": "\n\n".join(reasoning_bits) if show_thinking else "",
        "plan": last_plan,
        "plans": plans,
        "messages": msgs,
    }

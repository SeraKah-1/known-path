"""MCP server exposing known-path activation tools for agents."""

from __future__ import annotations

import json
from typing import Any

from known_path.runner import run_modes
from known_path.models import RunStatus

# Optional dependency — server entry documents install extra [mcp]
try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("known-path")
except ImportError:  # pragma: no cover
    mcp = None  # type: ignore


def _plan_to_dict(plan) -> dict[str, Any]:
    return json.loads(plan.model_dump_json())


if mcp is not None:

    @mcp.tool()
    def match_job(intent: str) -> dict[str, Any]:
        """Match a user intent to the demo route sheet (job card)."""
        from known_path.cards import load_card_or_demo, match_card_for_intent
        from known_path.fixtures import demo_job_card
        from known_path.runner import default_repo_root

        root = default_repo_root()
        card_path = root / "cards" / "job.revenue_by_region_quarter.yaml"
        card = load_card_or_demo(card_path if card_path.exists() else None)
        matched = match_card_for_intent(intent, [card, demo_job_card()])
        c = matched or card
        return {"job_id": c.id, "intent_examples": c.intent_examples}

    @mcp.tool()
    def activate(intent: str, mode: str = "known-path") -> dict[str, Any]:
        """Activate trusted catalog nodes for a job (or baseline/blocked modes)."""
        plan = run_modes(intent, mode, no_commit=False)
        return _plan_to_dict(plan)

    @mcp.tool()
    def ping_required(intent: str = "revenue by region last quarter") -> dict[str, Any]:
        """Run trust checks via a known-path activation without codegen emphasis."""
        plan = run_modes(intent, "known-path", no_commit=True)
        return {
            "status": plan.status.value,
            "nodes": [
                {
                    "name": n.name,
                    "trust": n.trust.value,
                    "reasons": n.reasons,
                    "activated": n.activated,
                }
                for n in plan.nodes
            ],
        }

    @mcp.tool()
    def commit_route(intent: str, mode: str = "known-path") -> dict[str, Any]:
        """Run and write route memory note (document/file write-back)."""
        plan = run_modes(intent, mode, no_commit=False)
        return {
            "status": plan.status.value,
            "write_back_note": plan.write_back_note,
            "chosen_urns": plan.chosen_urns,
        }

    @mcp.tool()
    def explain_last_run(mode: str = "known-path") -> dict[str, Any]:
        """Return the last run record for a mode from examples/runs."""
        from pathlib import Path
        from known_path.runner import default_repo_root

        path = default_repo_root() / "examples" / "runs" / f"last_{mode}.json"
        if not path.exists():
            # normalize mode name for baseline
            alt = default_repo_root() / "examples" / "runs" / f"last_{mode}.json"
            if mode == "jobcards":
                path = default_repo_root() / "examples" / "runs" / "last_known-path.json"
            if not path.exists():
                return {"error": f"no run record at {path}"}
        return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    if mcp is None:
        raise SystemExit(
            "Install MCP extra: pip install 'known-path[mcp]' or pip install mcp"
        )
    mcp.run()


if __name__ == "__main__":
    main()

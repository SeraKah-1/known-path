"""CLI entrypoint: `known-path` / `kp`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from known_path import __version__
from known_path.models import RunStatus
from known_path.runner import default_repo_root, run_modes

app = typer.Typer(
    name="known-path",
    help="Light only the trusted catalog assets for a data job.",
    no_args_is_help=True,
)
console = Console()

DEFAULT_INTENT = "revenue by region last quarter Finance canonical"


@app.command()
def version() -> None:
    """Print version."""
    console.print(f"known-path {__version__}")


@app.command()
def doctor() -> None:
    """Check local install and catalog client."""
    from known_path.datahub_client import build_catalog_client
    import os

    root = default_repo_root()
    client = build_catalog_client(write_dir=root / "examples" / "runs")
    assets = client.list_assets()
    mode = "live-gms" if os.environ.get("DATAHUB_GMS_URL") else "fixture-catalog"
    console.print(Panel.fit(
        f"[bold]known-path[/bold] {__version__}\n"
        f"repo: {root}\n"
        f"catalog: {mode} ({len(assets)} assets)\n"
        f"card: cards/job.revenue_by_region_quarter.yaml",
        title="doctor",
    ))
    raise typer.Exit(0)


@app.command("run")
def run_cmd(
    intent: str = typer.Option(DEFAULT_INTENT, "--intent", "-i"),
    mode: str = typer.Option(
        "known-path",
        "--mode",
        "-m",
        help="baseline | known-path | blocked",
    ),
    no_commit: bool = typer.Option(False, "--no-commit"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Run baseline, known-path activation, or fail-closed blocked demo."""
    plan = run_modes(intent, mode, no_commit=no_commit)
    if json_out:
        print(plan.model_dump_json(indent=2))
    else:
        _print_plan(plan)
    if plan.status == RunStatus.BLOCKED_TRUST:
        raise typer.Exit(2)
    if plan.status in (RunStatus.NO_ROUTE, RunStatus.BUDGET_EXCEEDED, RunStatus.ERROR_PLATFORM):
        raise typer.Exit(1)
    raise typer.Exit(0)


@app.command()
def demo(
    no_commit: bool = typer.Option(False, "--no-commit"),
) -> None:
    """Run baseline → known-path → blocked in one shot (hackathon demo)."""
    intent = DEFAULT_INTENT
    console.rule("[bold]1/3 Baseline (naive thrash)")
    b = run_modes(intent, "baseline", no_commit=no_commit)
    _print_plan(b)

    console.rule("[bold]2/3 Known path (route sheet)")
    k = run_modes(intent, "known-path", no_commit=no_commit)
    _print_plan(k)

    console.rule("[bold]3/3 Fail closed (trust red)")
    bl = run_modes(intent, "blocked", no_commit=no_commit)
    _print_plan(bl)

    # Summary metrics
    table = Table(title="Demo metrics")
    table.add_column("Mode")
    table.add_column("Status")
    table.add_column("Fetches")
    table.add_column("Activated")
    table.add_column("Chose trap?")
    trap = "finance.revenue_old"
    for p in (b, k, bl):
        names = [n.name for n in p.activated_nodes]
        chose_trap = any(trap in n for n in names)
        table.add_row(
            p.mode,
            p.status.value,
            str(p.entity_fetches),
            str(len(p.activated_nodes)),
            "yes" if chose_trap else "no",
        )
    console.print(table)

    root = default_repo_root()
    console.print(
        f"\nArtifacts: [cyan]{root / 'examples'}[/cyan]\n"
        f"  - baseline_wrong.sql / revenue_by_region.sql\n"
        f"  - runs/last_*.json"
    )

    # Exit 0 if known-path succeeded and baseline differed meaningfully
    if k.status != RunStatus.SUCCESS:
        raise typer.Exit(1)
    if bl.status != RunStatus.BLOCKED_TRUST:
        raise typer.Exit(1)
    raise typer.Exit(0)


@app.command()
def cards() -> None:
    """List route sheets."""
    root = default_repo_root()
    card_dir = root / "cards"
    if not card_dir.exists():
        console.print("No cards/ directory")
        raise typer.Exit(1)
    for p in sorted(card_dir.glob("*.yaml")):
        console.print(f"• {p.name}")


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8090, "--port", "-p"),
    open_browser: bool = typer.Option(False, "--open"),
) -> None:
    """Start the web demo (stdlib server, no extra deps)."""
    from known_path.webapp import serve

    serve(host=host, port=port, open_browser=open_browser)


@app.command("dataset")
def dataset_cmd() -> None:
    """Show demo dataset path and assets."""
    from known_path.fixtures import dataset_dir, demo_catalog, list_sample_files

    d = dataset_dir()
    assets = demo_catalog()
    console.print(Panel.fit(
        f"[bold]dataset[/bold] {d}\n"
        f"assets: {len(assets)}\n"
        f"csv samples: {len(list_sample_files())}",
        title="demo-finance",
    ))
    for a in assets:
        flags = []
        if a.certified:
            flags.append("certified")
        if a.deprecated:
            flags.append("deprecated")
        if a.quality_fail:
            flags.append("quality_fail")
        console.print(f"• {a.name}  [dim]{', '.join(flags) or '—'}[/dim]")


def _print_plan(plan) -> None:
    color = {
        RunStatus.SUCCESS: "green",
        RunStatus.BLOCKED_TRUST: "red",
        RunStatus.NO_ROUTE: "yellow",
    }.get(plan.status, "white")
    console.print(
        Panel.fit(
            f"[{color}]{plan.status.value}[/{color}]  mode={plan.mode}\n"
            f"{plan.message}\n"
            f"fetches={plan.entity_fetches}  activated={len(plan.activated_nodes)}",
            title=plan.job_id,
        )
    )
    table = Table()
    table.add_column("On")
    table.add_column("Name")
    table.add_column("Rel")
    table.add_column("Trust")
    table.add_column("Reasons")
    for n in plan.nodes:
        table.add_row(
            "●" if n.activated else "·",
            n.name,
            str(n.relevance),
            n.trust.value,
            ", ".join(n.reasons[:4]),
        )
    console.print(table)
    if plan.sql_artifact and plan.status == RunStatus.SUCCESS:
        console.print(Panel(plan.sql_artifact, title="SQL artifact", border_style="cyan"))


if __name__ == "__main__":
    app()

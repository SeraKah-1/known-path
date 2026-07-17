# DataHub Agent Hackathon — compliance map

**Event:** [Build with DataHub: The Agent Hackathon](https://datahub.devpost.com)  
**Project:** [known-path](https://github.com/SeraKah-1/known-path)  
**License:** Apache-2.0 (`LICENSE` at repo root — detectable on GitHub)

## What to build (challenge)

| Requirement | How this repo meets it |
|-------------|------------------------|
| Working software using DataHub as foundation | Catalog entities flow through `CatalogClient` (`src/known_path/datahub_client.py`). Live GMS via `DATAHUB_GMS_URL` when set; offline **fixture catalog** for deterministic demos/tests (honest fallback, not a second product catalog). |
| At least one of MCP / Agent Context / Skills / Analytics Agent | **MCP tools** in `src/known_path/mcp_server.py`; **Skill** in `skills/known-path/SKILL.md`. |
| Agents That Do Real Work | Activates assets, generates SQL, fail-closes, writes route note. |
| Metadata-Aware Code Generation | Emits mergeable SQL under `examples/revenue_by_region.sql` with URN comments and join from the route sheet. |
| Open / Wildcard | Route-sheet activation layer composable on any agent host. |

## What to submit (Devpost)

| Submission item | Path / status |
|-----------------|---------------|
| URL to project for judges | CLI: `kp demo` · Web: `uvicorn apps.web.app:app --port 8088` · Repo: GitHub URL |
| Public code repository + **Apache-2.0** | This repo; `LICENSE` |
| Text description | README + this doc |
| Demo video &lt; 3 min (YouTube/Vimeo) | **Remaining human step** — script in README / `docs/demo-script.md`. Not recorded in this environment. |
| Sample outputs | `examples/revenue_by_region.sql`, `examples/baseline_wrong.sql`, `examples/runs/*.json` |

## Project requirements detail

| Rule | Implementation |
|------|----------------|
| New project in submission window | Built for this hackathon |
| Public repo, Apache-2.0 at top | `LICENSE` |
| Functionality matches description | `kp demo` shows baseline vs known-path vs blocked |
| English materials | README, docs, skill in English |

## Judging criteria map

| Criterion | Evidence in repo |
|-----------|------------------|
| **Use of DataHub** | Client interface for GMS/search; entity URNs; write-back note; designed to sit **on top of** DataHub MCP (not rebuild search/lineage UI). |
| **Technical execution** | `pytest` + real CLI `kp demo`; hard budgets in `activate.py`. |
| **Originality** | Activation shortlist + fail-closed trust + route memory — **not** a catalog clone. Explicit non-goals in README. |
| **Real-world usefulness** | Wrong-table / deprecated trap is a daily analytics failure mode. |
| **Submission quality** | Top-style README, mermaid, examples, doctor command. |
| **OSS bonus** | Skill package + MCP server for others to reuse. |

## Originality note (important)

DataHub already provides search, lineage, and MCP tools. **known-path does not reimplement the catalog.**  
It adds a **route sheet + activation policy**: only light trusted nodes for a job, stop when trust is red, leave a note for the next run.

## Demo modes judges can run

```bash
pip install -e ".[dev]"
kp demo
kp run --mode baseline -i "revenue by region last quarter"
kp run --mode known-path -i "revenue by region last quarter"
kp run --mode blocked -i "revenue by region last quarter"
```

| Mode | Expected |
|------|----------|
| baseline | More fetches; may activate `finance.revenue_old` trap |
| known-path | Canonical + region; SQL in `examples/revenue_by_region.sql` |
| blocked | `BLOCKED_TRUST` exit code 2; no invented replacement |

## Live DataHub

```bash
export DATAHUB_GMS_URL=http://localhost:8080
export DATAHUB_GMS_TOKEN=...
kp doctor
```

If GMS is down, the client **falls back to fixtures** and still demos the full policy path (documented — not faked as a live cluster).

## Remaining human steps (not claimed done here)

1. Record &lt;3 minute demo video and upload to YouTube/Vimeo.  
2. Register submission on [datahub.devpost.com](https://datahub.devpost.com) with repo + video links.  
3. Optional: wire write-back to live DataHub `save_document` / tags when mutation MCP is enabled in your environment.

---
name: known-path
description: >-
  Use when answering business metric questions from a data catalog, generating
  SQL that must use Finance-canonical tables, or when an agent might thrash
  search and pick a similarly named deprecated table. Loads a short route sheet,
  lights only trusted assets, fails closed on bad trust, writes the route back.
---

# known-path

## When to use

- User asks for revenue / metrics **by region / quarter** from catalog-backed data
- You have DataHub (or a catalog) and must not invent tables
- You need a **mergeable SQL** artifact, not a chatty guess

## Rules (fail closed)

1. Prefer `known-path` activation tools / CLI over broad unrestricted catalog dump.
2. Never generate SQL from a **red** trust asset.
3. If trust fails on a required asset: **stop**. Do not invent a sibling table.
4. After a terminal run, leave a short **route note** (write-back) for the next run.
5. Put SQL under `examples/` with URN comments.

## Workflow

1. Match intent → route sheet (`job.revenue_by_region_quarter`).
2. Activate shortlist (top-K, budgeted fetches).
3. Ping trust (owner, deprecated, quality).
4. On green: generate SQL from activated assets only.
5. Commit route note (success or blocked).

## Commands

```bash
kp demo
kp run --mode baseline --intent "revenue by region last quarter"
kp run --mode known-path --intent "revenue by region last quarter"
kp run --mode blocked --intent "revenue by region last quarter"
```

## MCP tools

- `match_job`
- `activate`
- `ping_required`
- `commit_route`
- `explain_last_run`

## What this is not

- Not a second data catalog
- Not a full lineage UI rebuild
- Not "fetch all metadata into the prompt"

# Demo Finance dataset

Synthetic catalog + tiny CSV samples for **known-path** demos.

## Why this set

| Asset | Role in demo |
|-------|----------------|
| `finance.revenue_canonical` | Correct certified fact (route sheet target) |
| `finance.revenue_old` | **Trap** — name similar, deprecated, quality fail |
| `finance.rev_backup` | Trap #2 — unowned backup |
| `dim.region` | Certified dimension for joins |
| `ops.pipeline_metrics` | Noise (not revenue) |
| `sales.orders_raw` | Extra catalog noise |

## Files

- `catalog.json` — metadata graph stand-in (loaded by the app when not on live DataHub)
- `*_sample.csv` — tiny row samples for display in the web demo (not a warehouse)

## Load into live DataHub (optional)

1. [Quickstart DataHub](https://docs.datahub.com/docs/quickstart)
2. Ingest entities matching the URNs in `catalog.json` (or map your own URNs into `cards/`)
3. Or use official packs: `datahub datapack load showcase-ecommerce`

For the offline demo, **no DataHub install is required** — `catalog.json` is enough.

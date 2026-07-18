# Local DataHub testing status

## Environment limit (this machine)

| Requirement | Status |
|-------------|--------|
| Docker Engine | **Not available** (Android PRoot / Ubuntu userspace — no `docker`) |
| Official `datahub docker quickstart` | **Cannot run here** |
| `acryl-datahub` pip | Failed (native build `cramjam` / Rust network) |

## What we run instead: **mini-gms**

A small HTTP stand-in for GMS so known-path can test the **live client path**.

```bash
python3 scripts/mini_gms.py 8080
# or
bash scripts/start_datahub_stack.sh
```

### Credentials (local demo only)

| Field | Value |
|-------|--------|
| **GMS URL** | `http://127.0.0.1:8080` |
| **PAT** | `dh_pat_knownpath_demo_token_local_only_do_not_use_prod` |
| **Use live** | ON |

Workbench → ⚙ Settings → paste above → Test → Save.

### UI credentials (full DataHub only)

When you run real quickstart on a machine with Docker:

| Field | Value |
|-------|--------|
| UI | http://localhost:9002 |
| Username | `datahub` |
| Password | `datahub` |
| Then generate PAT | Settings → Access Tokens |

## What to expect: better or worse?

### Offline `demo-finance` (no GMS)

| | |
|--|--|
| Setup | Instant |
| Story | Crystal clear trap vs canonical |
| Signals | Full flags in catalog.json |
| Scale | 6 entities |
| **Best for** | Demo video, judging narrative |

### mini-gms live path (what we started here)

| | |
|--|--|
| Setup | One Python process |
| Client | `DataHubGmsClient` (real HTTP GraphQL path) |
| Auth | Bearer PAT exercised |
| Signals | Tags mapped (certified/deprecated) |
| Scale | Same 6 entities served over HTTP |
| **Better than offline?** | Slightly — proves network + auth + client code path |
| **Worse than offline?** | Not a full product UI; no lineage UI, no real Kafka/MySQL |

### Full Docker quickstart + `showcase-ecommerce`

| | |
|--|--|
| Setup | Heavy (~8GB RAM, many containers) |
| Entities | ~1,049 real-ish multi-platform |
| Lineage / glossary / domains | Real |
| **Better?** | **Yes for realism and hackathon “Use of DataHub” depth** |
| **Worse?** | Route-sheet trap story is **weaker** unless you re-seed trap tables; slower; noisier for judges |

### Recommendation for *this* hackathon

1. **Keep demo-finance + route sheet** as the hero narrative (wrong table vs right).  
2. Use **mini-gms** to show live HTTP/PAT path on constrained devices.  
3. If you have a laptop with Docker: run official quickstart + ecommerce pack **and** keep a route sheet pointing at known good URNs (or seed trap entities).

## Verified on this host

```text
mini-gms /health → UP
doctor → catalog: live-gms (6 assets)
run known-path → SUCCESS, 2 fetches, revenue_canonical + dim.region
```

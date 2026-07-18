# known-path — Agent tool card (skill)

Use this when answering catalog / revenue / trust questions in the workbench or any MCP host.

## Principle

Do **not** dump the whole catalog into context.  
**Activate** a shortlist, **ping trust**, **fail closed** on red, emit **SQL**, **write a route note**.

## CLI (canonical)

```bash
python -m known_path.cli run --mode known-path --intent "<job>" --json
python -m known_path.cli run --mode baseline --intent "<job>" --json
python -m known_path.cli run --mode blocked --intent "<job>" --json
python -m known_path.cli demo
python -m known_path.cli doctor
python -m known_path.cli dataset
```

Exit code `2` = intentional `BLOCKED_TRUST` (not a crash).

## Modes

| Mode | When |
|------|------|
| `known-path` | Production path — route sheet + trust |
| `baseline` | Show thrash / trap tables |
| `blocked` | Demo fail-closed when trust is red |

## Workbench agent commands

```
run known-path :: <intent>
run baseline :: <intent>
run blocked
demo
doctor
dataset
```

## OpenAI tool functions (workbench)

- `run_activation` { mode, intent }
- `run_demo` { intent? }
- `doctor` {}
- `list_dataset` {}

All tools shell to the real CLI (allow-listed).

## DataHub

- Offline default: `datasets/demo-finance/catalog.json`
- Live: set GMS URL + **Personal Access Token** (Bearer). OAuth is for interactive UIs; automation uses PAT.
- Docs: https://docs.datahub.com/docs/authentication/personal-access-tokens
- MCP: https://docs.datahub.com/docs/features/feature-guides/mcp

## Efficiency rules (state of the art for this hack)

1. **Push-down filters** — only fetch entities on the activation shortlist (top-K).
2. **Fail closed early** — trust red before codegen.
3. **No shadow catalog** — pointers + scores only; schema from catalog client.
4. **Write-back sparse** — one route note per terminal state, not per hop.
5. **Weaponize DataHub** — certified / deprecated / ownership / glossary / quality signals as first-class lamps, not afterthoughts.

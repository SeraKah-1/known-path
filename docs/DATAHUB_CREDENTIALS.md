# DataHub credentials (how to get them)

**known-path does not ship shared DataHub username/password or a global PAT.**  
Those are created on *your* DataHub instance.

## What you need

| Item | Purpose |
|------|---------|
| **GMS URL** | e.g. `http://localhost:8080` (self-hosted) or your Cloud tenant URL |
| **Personal Access Token (PAT)** | Bearer token for API / MCP / workbench |

OAuth is for interactive browser clients (Claude Desktop, Cursor).  
Automation (this workbench, CLI, ingestion) uses **PAT**.

Docs: [Personal Access Tokens](https://docs.datahub.com/docs/authentication/personal-access-tokens)  
MCP: [DataHub MCP Server](https://docs.datahub.com/docs/features/feature-guides/mcp)

## Self-hosted (quickstart)

1. Follow [Quickstart](https://docs.datahub.com/docs/quickstart) so UI is up (often `http://localhost:9002`, GMS `http://localhost:8080`).
2. Log into the UI.
3. **Settings → Access Tokens → Generate Personal Access Token**.
4. Enable Metadata Service Authentication if the Generate button is disabled (admin).
5. In known-path **⚙ Settings**:
   - DataHub GMS URL: `http://localhost:8080`
   - Paste PAT
   - Check **Use live DataHub** → **Test**

Optional sample graph:

```bash
datahub datapack load showcase-ecommerce
# or
datahub datapack load bootstrap
```

## DataHub Cloud

1. Tenant URL like `https://<tenant>.acryl.io`
2. Create PAT in UI (same Settings path).
3. GMS / MCP URL per [MCP docs](https://docs.datahub.com/docs/features/feature-guides/mcp) (managed MCP or `/integrations/ai/mcp`).
4. Workbench: put GMS base your deployment expects + PAT.

## Offline (no credentials)

Default pack **`datasets/demo-finance`** needs **no** DataHub login.  
Leave GMS empty and Use live **off**.

## Current machine status

If Settings shows empty GMS/token, nothing is configured yet — use offline demo-finance until you generate a PAT on your instance.

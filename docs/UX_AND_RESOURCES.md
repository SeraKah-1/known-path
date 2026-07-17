# UX choices (DesignMotionHQ) + DataHub Resources

## DesignMotionHQ patterns we adopted

| Pattern | Why it fits known-path |
|---------|------------------------|
| **Design tokens** | One dark enterprise palette (Anthropic-like); consistent radius/spacing |
| **Visual hierarchy** | Hero job → primary CTA → metrics → detail terminal |
| **Serial position** | Strong start (problem) + strong end (compare metrics / fail-closed) |
| **Doherty threshold** | Instant terminal “$ command” echo; spinner only while CLI runs |
| **Loading states** | Skeleton bars on chart while CLI runs — not a spinner-only void |
| **Data table system** | Catalog + activation tables with clear columns, not div soup |
| **Charts that don’t lie** | Same scale for baseline vs known-path fetch bars; labels with numbers |
| **Peak–end rule** | Demo flow ends on metrics comparison (memorable) |
| **Proximity** | Group “Run”, “Graph”, “Terminal” as related zones |
| **Error states** | BLOCKED_TRUST is a recovery card, not a red toast only |
| **Microcopy** | Buttons: “Baseline thrash”, “Known path”, “Fail closed” — plain words |
| **Focus states** | Visible outline on inputs/buttons for keyboard |
| **Empty states** | Terminal starts with a short how-to, not blank black |

### Skipped (not a fit for this product)

| Pattern | Why skip |
|---------|----------|
| Drag and drop | No kanban state to move |
| Date pickers / OTP / password | Wrong domain |
| Star rating | Not evaluation UI |
| Infinite scroll animations | Demo must stay judge-readable |
| Bottom sheets | Desktop-first enterprise console |

## Anthropic / big-tech feel (what we copied)

- Near-black canvas, soft borders, restrained accent
- Large calm typography, short headlines
- Product shell: top nav + main workbench + secondary rail
- “Console” panel for honest system I/O (CLI transcript)

## DataHub Resources — which path we use

From [datahub.devpost.com/resources](https://datahub.devpost.com/resources):

| Option | Decision |
|--------|----------|
| **Quickstart + MCP + Skills** | **Primary stack for the product story** |
| **demo-finance (our pack)** | **Primary dataset for this web/CLI demo** (trap vs canonical) |
| **bootstrap datapack** | Optional later for richer empty catalog |
| **showcase-ecommerce (1049 entities)** | Optional “scale” demo — not required to prove the route-sheet idea |
| **nyc-taxi / healthcare** | Optional for quality/freshness ping stories |
| **fiction-retail** | Blank canvas — skip for our narrative |

**Chosen default:** offline `datasets/demo-finance` + CLI bridge + web workbench.  
**Upgrade path documented:** live GMS + official MCP Server + datapack when judges have Docker.

Why not only ecommerce datapack? Our originality is **activation policy + fail-closed**, which needs a **clear trap table story**. Ecommerce is large but does not by itself show wrong-vs-right table picking as cleanly as `revenue_old` vs `revenue_canonical`.

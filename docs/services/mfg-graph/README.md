# Manufacturing Graph Service

## Overview
The Manufacturing Graph service is the canonical source for production topology: cells, operations, routings, changeovers, yields, energy, and capability metadata. It provides APIs for Scheduler, Task API, and Planner UI to evaluate constraints and optimise production flow. Data is persisted in Postgres with graph-aware queries and cached for high-frequency lookups.

## Responsibilities
- Maintain hierarchical model of sites → areas → cells → equipment, including capacity and safety attributes.
- Store routings (SKU → ordered operations) with standard times, changeover costs, yield expectations.
- Provide APIs to query feasible routings for a lot, simulate production sequences, and annotate energy/maintenance impacts.
- Expose event stream when graph elements change (new cell, updated routing, disabled capability).
- Integrate with Inventory (material compatibility), Scheduler (planning), Task API (safety zone lookup), and Edge Agent (capability metadata).

## Architecture & Data
- **Storage:** Postgres schema `mfg_graph` tables `cells`, `operations`, `routings`, `capabilities`, `constraints`, `energy_profiles`.
- **Caching:** Redis + application cache (LRU) for frequent capability queries.
- **Data Ingest:** Admin APIs or batch loader to bootstrap graph from ERP/cad data.
- **Multi-site Support:** Tenant-aware schema with `site_id` scoping.

## Interfaces
### REST
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/graph/cells/{cell_id}` | Retrieve cell metadata, capabilities, safety zones | Planner/Scheduler |
| `GET` | `/graph/routings/{sku}` | Get routing sequence with timings and changeovers | Planner/Scheduler |
| `POST` | `/graph/routings` | Create/update routing definition | Planner/Admin |
| `POST` | `/graph/cells/{cell_id}/capabilities` | Update cell capabilities or status | Planner/Admin |
| `POST` | `/graph/simulate` | Simulate routing for SKU + lot w/ constraints | Scheduler/Planner |

### gRPC (`mfggraph.v1.GraphService`)
- `GetCell`, `ListCells`, `GetRouting`, `ListRoutings`, `SimulateRouting`, `StreamGraphEvents`.
- `SimulateRouting` returns feasible sequences with predicted time/cost/energy outputs.

## Event Contracts
- **Produces:** `mfg.graph.cell.updated`, `mfg.graph.routing.updated`, `mfg.graph.capability.disabled`, `mfg.graph.capability.restored`.
- **Consumes:** `maintenance.plan.updated` (adjust capability availability), `orders.created` (optional prefetch), `inventory.material.updated`.
- Graph events follow envelope in `DATA_MODEL.md` with additional metadata payload.

## Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| `MFG_GRAPH_DB_URL` | Postgres connection | `postgres://mfg_graph:***@graph-db/mfg_graph` |
| `MFG_GRAPH_CACHE_URL` | Redis connection | `redis://graph-cache:6379/0` |
| `MFG_GRAPH_SITE_ID` | Site/tenant identifier | `bk-mill-01` |
| `MFG_GRAPH_MAX_SIMULATION_SEC` | Simulation timeout | `10` |
| `MFG_GRAPH_EVENT_BROKER` | Kafka bootstrap servers | `kafka1:9092` |

Secrets managed via Vault `kv/efab/mfg-graph`.

## Observability
- Metrics: `mfg_graph_routing_request_total`, `mfg_graph_simulation_latency_seconds`, `mfg_graph_cache_hit_ratio`, `mfg_graph_capability_downtime_minutes`.
- Logs: Structured JSON capturing SKU, cell, constraint context.
- Traces: OTel instrumentation for REST/gRPC and simulation pipelines.
- Dashboards: “Manufacturing Graph Health” (cache hit rate, routing latency, capability changes).
- Alerts: Simulation timeout > threshold, cache hit ratio < 85%, capability disable events > baseline.

## Runbook & Ops
- `RUNBOOK.md#mfg-graph-outage` – Steps to recover service and rehydrate cache.
- `RUNBOOK.md#routing-update` – Verification checklist for new/changed routings.
- Backup: Postgres PITR + daily exports of graph snapshots.
- Change Management: All routing/capability changes require approval workflow; events logged to audit topic.

## Testing
- Unit tests for routing calculations, constraint validation, energy mapping.
- Integration tests with Scheduler and Task API to ensure compatibility.
- Simulation regression tests using historical scenarios to prevent performance regressions.
- Load tests to handle 100 concurrent simulations with <500ms p95 latency.

## KPIs
- Routing lookup latency ≤ 50ms p95.
- Simulation success rate ≥ 99%.
- Graph update propagation to consumers < 2s.
- Data accuracy vs ERP baseline ≥ 99%.

## Documentation Status
- Backlog item SVC-03 **Completed** (observation stored in `MEM-20251101-002`).
- Next step: Publish ADR for graph modelling choices (JSONB vs graph DB, caching strategy).

# Inventory Service

## Overview
The Inventory service maintains real-time material availability for yarn, trims, packaging, and finished goods. It synchronises with the legacy ERP during migration, exposes reservation APIs to Scheduler and Task API, and publishes stock position changes for downstream analytics.

## Responsibilities
- Track on-hand, allocated, and in-transit quantities across sites and cells.
- Reserve and release materials for Task API intents and manufacturing lots.
- Reconcile inventory adjustments from edge telemetry and quality inspections.
- Provide safety stock recommendations to Planner UI.

## Architecture & Data
- **Storage:** PostgreSQL schema `inventory` (tables: `items`, `locations`, `batches`, `reservations`, `adjustments`).
- **Integration:** Optional Redis cache for high-read dashboards; periodic reconciliation with ERP for audit parity.
- **Data Sources:** Consumes telemetry from Edge (Sparkplug) for real-time consumption and returns.

## Interfaces
### REST
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/inventory/items/{sku}` | Retrieve stock position by SKU + location | OIDC (Planner/Buyer) |
| `POST` | `/inventory/reservations` | Reserve material for order/lot/cell | Task API service account |
| `DELETE` | `/inventory/reservations/{id}` | Release reservation (complete/cancel) | Task API/Scheduler |
| `POST` | `/inventory/adjustments` | Record manual or sensor-driven adjustments | Operator role |
| `GET` | `/inventory/shortages` | Highlight SKUs below safety stock | Planner |

### gRPC
- `inventory.v1.InventoryService` exposes `GetItem`, `BatchGetItems`, `CreateReservation`, `ReleaseReservation`, `StreamAdjustments`.

## Event Contracts
- **Produces:** `inventory.reservation.created`, `inventory.reservation.released`, `inventory.stock.updated`, `inventory.shortage.alert`.
- **Consumes:** `orders.created`, `task.execution.update`, `quality.inspection.result`.
- Replay window: 7 days hot in Redpanda; archived to S3 bucket `efab-inventory-events`.

## Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| `INVENTORY_DB_URL` | Postgres connection | `postgres://inventory:***@inventory-db/inventory` |
| `INVENTORY_CACHE_URL` | Redis cache (optional) | `redis://inventory-cache:6379/0` |
| `INVENTORY_EVENT_BROKER` | Kafka bootstrap servers | `kafka1:9092` |
| `INVENTORY_SAFETY_STOCK_PCT` | Default safety stock percent | `15` |
| `INVENTORY_RESERVATION_TTL_MIN` | Auto-expire reservations after inactivity | `45` |

Feature flags managed via LaunchDarkly (`inventory_dual_write`, `cache_enabled`).

## Observability
- Metrics: `inventory_reservations_active`, `inventory_shortage_count`, `inventory_adjustment_total`, `inventory_cache_hit_ratio`.
- Traces: gRPC spans linking reservation lifecycle to Scheduler/Task API.
- Logs: Structured JSON; item/lot IDs masked when exported.
- Dashboards: “Material Position & Reservations” row on production Ops board.
- Alerts: `inventory_shortage_count` > threshold, cache hit ratio < 80%, reservation TTL expirations > 5/min.

## Runbook & Ops
- See `RUNBOOK.md#inventory-shortage` and `#reservation-stuck`.
- Rollback: disable dual-write, replay `inventory.stock.updated` from archive.
- DR: Postgres PITR; caches can be flushed and rebuilt.

## Testing
- Unit tests for reservation eligibility, safety stock calculations.
- Contract tests with Task API (reservation handshake) and Orders service (order release).
- Integration tests run via CI using ephemeral Postgres + Redpanda.
- Load testing goal: sustain 500 reservation ops/min with p99 latency < 150ms.

## KPIs
- Reservation success rate ≥ 99%.
- Safety stock alerts resolved within 2 hours.
- Inventory accuracy variance ≤ 1.5% vs physical counts.

## Documentation Status
- Backlog item SVC-02 marked **Completed** (see `MEM-20251101-002`).
- Upcoming work: Document cycle counting SOP once Edge telemetry integration finalised.

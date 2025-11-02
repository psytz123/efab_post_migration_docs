# Orders Service

## Overview
The Orders service is the system of engagement for sales and production orders in the post-migration architecture. It exposes order lifecycle APIs to planners, synchronises with the legacy ERP via the API Gateway, and emits canonical events that drive scheduling, inventory allocation, and Task API intent creation.

## Responsibilities
- Create, update, and cancel make-to-order and make-to-stock work orders.
- Manage order decomposition into lots, routing references, and production priorities.
- Provide real-time order status to Planner UI and downstream services.
- Publish order domain events (`orders.created`, `orders.updated`, `orders.cancelled`) to Redpanda/Kafka.
- Align order master data with Manufacturing Graph (cells, operations, BOM) and Inventory reservations.

## Architecture & Data
- **Storage:** PostgreSQL schema `orders` (tables: `orders`, `order_lines`, `lot_assignments`, `order_attributes`).
- **Data Model:** Each order references `DATA_MODEL.md` routings via `routing_id` and `cell_id`.
- **Integration:** Reads legacy ERP order snapshots through Gateway when in dual-write mode (Phase 1–2).

## Interfaces
### REST (GraphQL optional via BFF)
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/orders` | Create production order with routing + lot plan | OIDC (Planner role) |
| `GET` | `/orders/{id}` | Retrieve order header, lines, routing, status timeline | OIDC |
| `PATCH` | `/orders/{id}` | Update priority, due dates, or pause flags | OIDC |
| `POST` | `/orders/{id}/lots` | Allocate/adjust lots for manufacturing cells | OIDC |
| `GET` | `/orders?status=...` | Filtered listing for dashboards/export | OIDC |

GraphQL queries are exposed through the API Gateway for UI aggregation (see `ARCHITECTURE.md`).

- Order identifiers are minted server-side (`ORD-<uuid>`) unless an external `metadata.order_id` is supplied; clients should treat `order_id` in responses as canonical.

### gRPC
- `orders.v1.OrderService` with RPCs `CreateOrder`, `GetOrder`, `ListOrders`, `UpdateOrder`.
- Used by Scheduler/Manufacturing Graph services for low-latency access.

## Event Contracts
- **Produces:** `orders.created`, `orders.updated`, `orders.cancelled`, `orders.priority.changed`.
- **Consumes:** `task.execution.update` (for actuals), `inventory.allocation.confirmed`.
- Events comply with envelope in `DATA_MODEL.md` (include `order_id`, `lot`, `cell`, `priority`, `due_at`).
- Dead letter queue: `orders.dlq` for failed downstream processing with alert hooks.

## Integration Points
- **Task API:** On transition to `released`, service calls Task API to publish intents for each lot; responses update `order_actuals`.
- **Manufacturing Graph:** Pulls routings, cell capabilities, and changeover data to validate lot plans.
- **Inventory Service:** Hooks into reservation and allocation topics (`inventory.reservation.requested/confirmed`).
- **Legacy ERP:** Dual-write feature flag mirrors changes back to monolith until Phase 3 sunset.
- **Edge Telemetry:** Subscribes to `telemetry.cell.state` for predictive backlog adjustments (Wave 5).

## Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| `ORDERS_DB_URL` | Postgres connection string | `postgres://orders:***@orders-db/orders` |
| `ORDERS_EVENT_BROKER` | Kafka/Redpanda bootstrap servers | `kafka1:9092` |
| `ORDERS_FEATURE_DUAL_WRITE` | Enable ERP sync during migration | `true` |
| `ORDERS_MAX_ACTIVE_LOTS` | Guardrail for concurrent lot releases | `50` |
| `ORDERS_API_RATE_LIMIT` | Planner API rate limit (req/min) | `300` |

Secrets managed via Vault (`kv/efab/orders`).

## Security & Compliance
- Gateway enforces OIDC; service validates JWT access tokens with JWKS cache refresh every 5 minutes.
- RBAC: `planner` (CRUD), `scheduler` (state transitions), `operator` (read), `admin` (full). Deny-by-default via OPA bundle `orders_policy.rego`.
- Audit trails persisted in `order_audit` table with reason codes; replicated to analytics bucket nightly.
- PII fields (customer contact, address) encrypted using per-tenant KMS keys and redacted from logs/metrics.
- SOX/SOC2 alignment: change approvals require `orders_change_request` topic ack before deployment.

## Observability
- Metrics: `orders_created_total`, `order_priority_changes_total`, `order_cycle_time_seconds` (p50/p95/p99), `order_lot_wip`.
- Traces: OTel instrumentation for REST/gRPC endpoints, correlated with Scheduler flows.
- Logs: Structured JSON with trace IDs; PII redacted before sink to Loki.
- Dashboards: “Orders Intake & Flow” panel group (see `observability-integration-plan.md`).
- Alerts: `order_create_error_rate > 2%`, `order_cycle_time_seconds` p95 > SLA.

## Runbook & Ops
- Runbook references: `RUNBOOK.md#order-intake` and `RUNBOOK.md#order-priority-escalation`.
- Rollback: disable dual-write feature flag and replay from `orders.dlq`.
- DR: Postgres PITR enabled; order events replayable via Redpanda retention (7 days).

## Testing
- Unit tests (pytest) for validation rules and status transitions.
- Contract tests (Pact) with Scheduler and Inventory services.
- Integration tests in CI use ephemeral Postgres and Redpanda containers.
- Performance tests target 100 order creates/min sustained with <200ms p95.
- Security tests: OWASP ZAP baseline scan, dependency scanning via Trivy, policy regression suite for OPA bundles.

## Local Mock Environment
- Launch the Orders API with mock data via `scripts/launch_orders_mock.sh` (see `docs/environment/orders-mock-environment.md` for details).
- SQLite database stored under `workspace/services/orders/mock/orders.db`; reset by deleting the file.
- Event publisher uses `memory://` buffer, allowing end-to-end flows without Kafka.

## KPIs
- Order cycle time (create → release) ≤ 4 hours.
- Forecast adherence ≥ 95% (orders completed vs scheduled).
- Lot release accuracy ≥ 98%, rework rate < 2%.

## Documentation Status
- Backlog items SVC-01 and SVC-02 marked **Completed** in `MEM-20251101-002`.
- Outstanding: ADR for dual-write retirement (planned Phase 3).

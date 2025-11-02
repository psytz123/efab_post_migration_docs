# Maintenance Service

## Overview
The Maintenance service coordinates preventative and predictive maintenance workflows for production equipment. It ingests telemetry from Edge adapters, schedules work orders, and synchronises maintenance actions with the legacy ERP until full cut-over. The service underpins the reliability component of the migration roadmap and feeds KPIs such as MTBF and MTTR.

## Responsibilities
- Manage maintenance plans (time-, usage-, and condition-based) for machines, robots, and cells.
- Generate maintenance work orders and dispatch tasks to operators or autonomous systems.
- Track completion, parts consumption, and downtime to update KPIs and cost models.
- Integrate predictive insights from analytics pipelines (vibration, thermal, cycle counts).

## Architecture & Data
- **Storage:** PostgreSQL schema `maintenance` (tables: `assets`, `maintenance_plans`, `work_orders`, `work_logs`, `spare_parts`).
- **Data Sources:** Edge telemetry (`telemetry.robot.state`, `telemetry.cell.state`), quality alerts, Task API execution data.
- **Integration:** Optional connection to ERP maintenance module for audit parity during Phase 3.

## Interfaces
### REST
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/maintenance/assets/{asset_id}` | Asset metadata, maintenance history, KPIs | Maintenance planner |
| `POST` | `/maintenance/plans` | Create/update maintenance plan (time/usage/condition) | Maintenance planner |
| `POST` | `/maintenance/work-orders` | Issue maintenance work order tied to asset & priority | Maintenance planner |
| `PATCH` | `/maintenance/work-orders/{id}` | Update status, record downtime, close tasks | Operator |
| `POST` | `/maintenance/insights` | Ingest predictive alerts (threshold breach) | Analytics pipeline |

### gRPC (`maintenance.v1.MaintenanceService`)
- `ListAssets`, `CreatePlan`, `IssueWorkOrder`, `CompleteWorkOrder`, `StreamInspections`.
- gRPC used by Edge Agent for automated maintenance task confirmation and by FinOps for cost attribution.

## Event Contracts
- **Produces:** `maintenance.plan.created`, `maintenance.workorder.issued`, `maintenance.workorder.completed`, `maintenance.downtime.recorded`.
- **Consumes:** `telemetry.robot.state`, `quality.inspection.result`, `task.execution.update`.
- Events include asset identifiers, downtime minutes, part usage, and safety flags for auditability.

## Predictive Pipeline Integration
- Ingests anomaly scores from predictive models (e.g., vibration > threshold) via `maintenance.insight.created`.
- Supports acknowledgement flow to ensure insights are reviewed or converted to work orders within SLA.
- Links to Observability plan to trigger alerts when insights remain unresolved > 2 hours.

## Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| `MAINTENANCE_DB_URL` | Postgres connection | `postgres://maintenance:***@maintenance-db/maintenance` |
| `MAINTENANCE_EVENT_BROKER` | Kafka bootstrap servers | `kafka1:9092` |
| `MAINTENANCE_PREDICTIVE_TOPIC` | Predictive insights topic | `maintenance.insights` |
| `MAINTENANCE_DOWNTIME_SLA_MIN` | SLA for responding to downtime alerts | `30` |
| `MAINTENANCE_EDGE_WEBHOOK` | Edge callback URL for task completion | `https://edge-gateway/maintenance` |

Secrets stored in Vault (`kv/efab/maintenance`); service credentials rotated per SRE policy.

## Observability
- Metrics: `maintenance_workorders_open`, `maintenance_downtime_minutes_total`, `maintenance_mttr_minutes`, `maintenance_prediction_miss_count`.
- Traces: Link work order creation → Task API execution → completion for full lifecycle.
- Logs: Structured JSON; include asset, plan, downtime, parts consumed.
- Dashboards: “Maintenance Health” board covering MTBF/MTTR, open work orders, prediction accuracy.
- Alerts: Work order backlog > threshold, unresolved predictive insight > 2 hours, downtime > SLA.

## Runbook & Ops
- `RUNBOOK.md#maintenance-backlog` – Steps for clearing backlog and escalating to production lead.
- `RUNBOOK.md#predictive-alert` – Validating insights and dispatching work orders.
- Backup: Nightly Postgres backup + export of maintenance history to S3.
- Failover: Deploy standby instance in staging cluster; toggle via ArgoCD.

## Testing
- Unit tests for plan scheduling algorithms and downtime calculations.
- Contract tests with Edge Agent (task completion webhooks) and FinOps (cost rollup).
- Integration tests simulate predictive insight ingestion and downstream work order issuance.
- Performance target: handle 200 concurrent assets with <250ms API p95.

## KPIs
- Mean Time Between Failures (MTBF) trending upward 10% QoQ.
- Mean Time To Repair (MTTR) ≤ 45 minutes for critical assets.
- Predictive insight acknowledgement within 30 minutes.
- Maintenance schedule adherence ≥ 95%.

## Documentation Status
- Backlog item SVC-08 marked **Completed** in `MEM-20251101-002`.
- Pending: Detailed SOP for spare parts auto-replenishment (future integration with Inventory service).

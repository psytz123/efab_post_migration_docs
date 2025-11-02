# FinOps Service

## Overview
The FinOps service provides cost transparency across production orders, tasks, and maintenance activities. It aggregates data from Orders, Inventory, Manufacturing Graph, Quality, and Maintenance services to calculate unit cost, variance, and ROI for automation initiatives. The service feeds dashboards for finance and leadership and enables data-driven scaling decisions.

## Responsibilities
- Ingest order actuals, material usage, labour, energy, and maintenance cost data.
- Calculate cost per order/lot/cell, track variances vs target, and forecast automation ROI.
- Provide APIs and exports for finance systems and executive dashboards.
- Publish cost insights and alerts when thresholds exceeded.
- Support scenario modelling (e.g., impact of additional automation or schedule changes).

## Architecture & Data
- **Storage:** Postgres schema `finops` tables `cost_actuals`, `cost_targets`, `variance`, `roi_models`.
- **Data Pipeline:** Event-based ingestion from `orders.actuals`, `inventory.stock.updated`, `maintenance.workorder.completed`, `quality.inspection.result`.
- **Analytics:** Materialised views for KPI queries; optional DuckDB snapshots for ad-hoc analysis.
- **Integration:** Exports to BI tools (Power BI/Tableau) and ERP financial modules.

## Interfaces
### REST
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/finops/orders/{order_id}` | Cost breakdown by order/lot | Finance/Leadership |
| `GET` | `/finops/cells/{cell_id}` | Cost, energy, scrap metrics per cell | Finance/Operations |
| `GET` | `/finops/dashboard` | Summary KPIs (unit cost, variance, ROI) | Finance |
| `POST` | `/finops/targets` | Update cost targets by SKU/cell | Finance |
| `POST` | `/finops/scenarios` | Run scenario analysis for automation investments | Finance |

### gRPC (`finops.v1.FinOpsService`)
- `GetOrderCost`, `ListCellCosts`, `UpdateTargets`, `RunScenario`.

## Event Contracts
- **Produces:** `finops.cost.variance`, `finops.roi.updated`, `finops.alert.threshold`.
- **Consumes:** `orders.actuals`, `inventory.stock.updated`, `quality.inspection.result`, `maintenance.workorder.completed`, `task.execution.update`.
- Alerts include severity, owner, and recommended action (e.g., investigate scrap, energy spike).

## Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| `FINOPS_DB_URL` | Postgres connection | `postgres://finops:***@finops-db/finops` |
| `FINOPS_EXPORT_BUCKET` | Storage for reports | `s3://efab-finops-reports` |
| `FINOPS_ALERT_THRESHOLD` | Cost variance alert threshold | `0.1` (10%) |
| `FINOPS_BI_WEBHOOK` | BI refresh webhook | (per environment) |
| `FINOPS_SCENARIO_TIMEOUT_SEC` | Scenario simulation timeout | `20` |

Secrets stored in Vault (`kv/efab/finops`). Sensitive financial data encrypted at rest.

## Observability
- Metrics: `finops_cost_variance`, `finops_roi`, `finops_alert_total`, `finops_export_duration_seconds`.
- Logs: Structured JSON with order/sku/cell references; financial amounts masked per policy.
- Traces: Scenario simulations instrumented to identify bottlenecks.
- Dashboards: “FinOps Overview” for unit cost, variance, ROI, automation benefits.
- Alerts: Cost variance > threshold, ROI dropping, export failures.

## Runbook & Ops
- `RUNBOOK.md#finops-alert` – Handling cost variance alerts and engaging operations teams.
- `RUNBOOK.md#finops-export-failure` – Steps to re-run exports and notify stakeholders.
- Data reconciliation routine with ERP to ensure accuracy; nightly job.
- Backup: Postgres PITR and scheduled CSV snapshots for audit.

## Testing
- Unit tests for cost aggregation, variance calculations, scenario modelling.
- Integration tests verifying event ingestion pipelines and BI exports.
- Performance: handle 10k order cost calculations/day with p95 response < 300ms.

## KPIs
- Unit cost variance ≤ ±5%.
- ROI reporting accuracy ≥ 98% vs finance ledger.
- Alert response time ≤ 1 business day.
- Scenario completion time ≤ 15 seconds.

## Documentation Status
- Backlog item SVC-09 **Completed** (`MEM-20251101-002` updated).
- Future work: ADR covering cost allocation methodology and data governance.

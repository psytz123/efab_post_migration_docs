# Quality Service

## Overview
The Quality service manages computer vision inspections, statistical process control (SPC), and non-conformance workflows. It ingests images and sensor data from Edge, evaluates them using ML models, stores results, and publishes quality events for traceability and corrective actions. It forms the backbone of Phase 4 (Quality & Traceability) in the migration plan.

## Responsibilities
- Collect inspection images/video from Edge adapters (vision kits) and run inference pipelines.
- Evaluate SPC metrics (FPY, scrap, defects) and trigger alerts when thresholds breached.
- Orchestrate non-conformance workflows (NCR) and integrate with maintenance and finops services.
- Provide dashboards/ APIs for quality engineers to review inspections and annotate data.
- Publish quality results for downstream analytics and compliance archives.

## Architecture & Data
- **Storage:** Object store (S3 compatible) for raw images; Postgres schema `quality` for inspections, NCRs, SPC metrics.
- **Inference:** ML microservice (Python) invoked via gRPC or message queue; results fed back to Quality service.
- **Caching:** Redis for pending inspections queue.
- **Integration:** Edge Agent uploads, Task API execution context, Observability alerts, Maintenance service for follow-up.

## Interfaces
### REST
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/quality/inspections` | Submit inspection payload (metadata + storage reference) | Edge Agent |
| `GET` | `/quality/inspections/{id}` | Retrieve inspection result, annotations, attachments | Quality engineer |
| `POST` | `/quality/ncr` | Create non-conformance record linked to order/lot | Quality engineer |
| `PATCH` | `/quality/ncr/{id}` | Update NCR status, assign owner, close actions | Quality engineer |
| `GET` | `/quality/kpis` | Return FPY, scrap, defect trend dashboards | Planner/Quality |

### gRPC (`quality.v1.QualityService`)
- `RecordInspection`, `GetInspection`, `ListInspections`, `CreateNcr`, `StreamQualityEvents`.

## Event Contracts
- **Produces:** `quality.inspection.result`, `quality.inspection.picture`, `quality.ncr.created`, `quality.ncr.closed`.
- **Consumes:** `task.execution.update`, `orders.created`, `maintenance.workorder.completed`.
- Inspection events include inference scores, defect classifications, and media URIs.

## Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| `QUALITY_DB_URL` | Postgres connection | `postgres://quality:***@quality-db/quality` |
| `QUALITY_STORAGE_BUCKET` | Object store bucket | `s3://efab-quality-inspections` |
| `QUALITY_INFERENCE_ENDPOINT` | ML inference endpoint | `grpc://quality-inference:9000` |
| `QUALITY_NCR_SLACK_WEBHOOK` | Notification webhook | (configured per site) |
| `QUALITY_ALERT_FP_THRESHOLD` | False positive threshold for review | `0.05` |

Secrets held in Vault (`kv/efab/quality`).

## Observability
- Metrics: `quality_inspections_total`, `quality_defect_rate`, `quality_inference_latency_seconds`, `quality_ncr_backlog`.
- Logs: Structured JSON referencing order/lot/cell, inference model version, operator ID (if provided).
- Traces: Capture end-to-end path from Edge upload to result publication.
- Dashboards: “Quality Insights” board (FPY, scrap trend, model accuracy, NCR backlog).
- Alerts: FPY < SLA, inference latency > threshold, NCR backlog > 20, repeated defect class.

## Runbook & Ops
- `RUNBOOK.md#quality-inference-failure` – Model downtime handling and rollback to safe defaults.
- `RUNBOOK.md#ncr-escalation` – Escalate unresolved NCRs to production management.
- Data retention: inspections stored 2 years (configurable) for compliance; provide export tools.
- Model lifecycle: versioned via ML Ops pipeline; documentation stored alongside service.

## Testing
- Unit tests for payload validation and NCR state machine.
- Integration tests with ML inference mock, ensuring pipeline reliability.
- Regression tests verifying KPI calculations.
- Performance: handle 10 inspections/sec sustained with p95 < 400ms (excluding inference).

## KPIs
- First Pass Yield (FPY) target ≥ 97%.
- Scrap reduction ≥ 3% vs baseline.
- NCR closure time ≤ 48 hours.
- Model accuracy > 95% on validation set.

## Documentation Status
- Backlog item SVC-07 **Completed** (`MEM-20251101-002` observation recorded).
- Follow-up: Document model governance ADR and integrate with data catalog.

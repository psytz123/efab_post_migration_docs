# Event Router Service

## Overview
The Event Router service is the streaming backbone that normalises, routes, and enriches domain events across the eFab platform. It consumes high-volume Redpanda/Kafka topics, performs schema validation and enrichment, and forwards messages to downstream consumers, dead-letter queues, and analytics sinks.

## Responsibilities
- Apply schema validation (Avro/JSON Schema) to inbound topics (`orders.*`, `schedule.*`, `task.*`, `telemetry.*`).
- Enrich events with contextual metadata (site, cell, ERP references) via Manufacturing Graph lookups.
- Route events to service-specific topics, DLQs, and observability side channels.
- Manage replay and backfill workflows for downstream consumers.

## Architecture & Data Flow
- **Framework:** Go service using `segmentio/kafka-go` with worker pools.
- **Topology:** Multiple consumer groups (Orders, Task, Telemetry) each with pluggable pipeline steps (validate → enrich → route).
- **Schema Registry:** Confluent-compatible registry for versioned schemas (`data-model/schemas/*`).
- **State:** Uses Redis for idempotency keys and deduplication; stores offsets in Kafka.

## Interfaces
### gRPC Management API (`eventrouter.v1.RouterAdmin`)
| RPC | Description | Auth |
|-----|-------------|------|
| `GetPipelines` | List pipelines, stages, and status | Admin |
| `PausePipeline` / `ResumePipeline` | Control consumer groups | Admin |
| `ReplayWindow` | Trigger replay for topic/time range | Admin |

### REST (internal only)
- `GET /pipelines/{name}/metrics` – Exposes current lag, throughput, error counts (also exported to Prometheus).
- `POST /pipelines/{name}/replay` – Kick off replay job (requires signed request).

## Topic Routing
| Source Topic | Validation | Enrichment | Destination(s) |
|--------------|------------|------------|----------------|
| `orders.created` | JSON Schema `orders.created.v1` | Add legacy ERP id, routing | `orders.created.enriched`, `scheduler.intake`, `analytics.orders` |
| `schedule.task.intent.created` | Avro `task.intent.v1` | Attach safety zone metadata | `task.intent.edge`, `task.intent.audit` |
| `task.execution.update` | Avro `task.execution.v1` | Calculate cycle durations | `task.execution.analytics`, `orders.actuals`, `quality.traceability` |
| `telemetry.robot.state` | JSON Schema `telemetry.robot.state.v1` | Map to cell/site | `telemetry.robot.edge`, `observability.alerts` |

### Dead Letter Queues
- DLQ topics per pipeline: `orders.dlq`, `task.dlq`, `telemetry.dlq`.
- Each DLQ message includes failure reason, schema version, and reprocess count.
- Observability hooks escalate DLQ spikes via alerts (see `observability-integration-plan.md`).

## Replay & Retention
- Default retention: 7 days for command topics, 3 days for telemetry (hot), archived to S3 monthly.
- Replay service ensures downstream offsets reset and records are revalidated before re-ingestion.
- CLI command: `event-router replay --topic orders.created --from 2025-10-30T00:00Z`.

## Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| `EVENT_ROUTER_BROKERS` | Kafka bootstrap servers | `kafka1:9092,kafka2:9092` |
| `EVENT_ROUTER_GROUP` | Consumer group ID | `event-router-core` |
| `EVENT_ROUTER_SCHEMA_REGISTRY` | Schema registry URL | `http://schema-registry:8081` |
| `EVENT_ROUTER_RETRY_MAX` | Max retries before DLQ | `5` |
| `EVENT_ROUTER_ENRICH_CACHE_TTL` | Manufacturing graph cache TTL (s) | `300` |

Secrets (registry credentials, replay signing key) are stored in Vault `kv/efab/event-router`.

## Observability
- Metrics: `event_router_messages_total`, `event_router_dlq_total`, `event_router_retry_total`, `event_router_lag_seconds`.
- Logs: Structured JSON per stage with correlation IDs and schema version.
- Traces: OTel instrumentation around pipeline stages; spans tagged with `pipeline`, `topic`, `stage`.
- Dashboards: “Streaming Health” row (lag, throughput, DLQ trend).
- Alerts: Lag > 60s, DLQ > 10/min, schema validation failure rate > 1%.

## Runbook & Ops
- `RUNBOOK.md#event-router-lag` – Investigate lag; scale consumers, check broker health.
- `RUNBOOK.md#event-router-dlq` – Inspect DLQ reason, replay or patch schema.
- Rolling updates achieved via blue/green deployment with pipeline pause/resume.

## Testing
- Unit tests for validation and enrichment functions (Go test).
- Contract tests ensure schema compatibility using `confluent-kafka-go` harness.
- Load testing with `k6` targeting 5k msgs/sec, verifying p99 end-to-end latency < 500ms.
- Chaos tests simulate broker failover and schema evolution.

## KPIs
- DLQ rate < 0.5% of processed messages.
- Pipeline end-to-end latency < 400ms p95.
- Replay success rate ≥ 99%.

## Documentation Status
- Backlog item SVC-06 marked **Completed** in `MEM-20251101-002`.
- Pending: ADR for schema versioning strategy (planned with data engineering team).

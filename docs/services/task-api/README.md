# Task API Service

## Overview
The Task API provides a vendor-neutral interface for orchestrating robot, AMR, and PLC actions. It converts scheduler intents into safe, executable verb sequences, enforces safety policies, and synchronises execution state across cloud and edge. The service exposes REST and gRPC endpoints, publishes execution events, and maintains audit trails for compliance.

## Responsibilities
- Accept Task Intents (verbs + arguments) from Scheduler or planner tools.
- Validate safety zones, speed limits, and authorization policies via OPA/OPAL.
- Translate logical verbs into edge-specific payloads (ROS 2 actions, OPC UA commands, Sparkplug messages).
- Emit execution state updates (`queued`, `running`, `paused`, `completed`, `failed`) and telemetry snapshots.
- Maintain execution history and audit logs for traceability.

## Architecture & Data
- **Implementation:** Go service with gRPC + REST (chi mux) sharing protobuf definitions (`task/v1/task.proto`).
- **Storage:** Postgres schema `task_api` (tables: `tasks`, `task_verbs`, `task_events`, `safety_audits`).
- **Cache:** Redis for short-term intent deduplication and rate limiting.
- **Policy Engine:** OPA bundle served via OPAL; policies stored in `policy/task_api.rego`.
- **Dependencies:** Scheduler (intent source), Edge Agent (execution), Manufacturing Graph (cell capabilities), Security (OIDC).

## Interfaces
### REST
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/tasks` | Submit Task Intent (order/lot/cell + verb sequence) | Scheduler/Planner (OIDC + RBAC) |
| `GET` | `/tasks/{id}` | Retrieve current task state + audit trail | Authorized roles |
| `POST` | `/tasks/{id}/pause` | Pause active task | Operator |
| `POST` | `/tasks/{id}/resume` | Resume paused task with optional overrides | Operator |
| `POST` | `/tasks/{id}/cancel` | Cancel task and notify Edge | Operator/Safety officer |

### gRPC (`task.v1.TaskService`)
- `CreateTaskIntent(TaskIntent) returns (Task)`.
- `GetTask(TaskRequest) returns (Task)`.
- `StreamTaskUpdates(TaskStreamRequest) returns (stream Task)`.
- `PauseTask`, `ResumeTask`, `CancelTask` RPCs mirror REST endpoints.

### Example – Create Task Intent
```http
POST /tasks HTTP/1.1
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "order_id": "SO-12345",
  "lot": "123A",
  "cell": "PackLine1",
  "verbs": [
    {"verb": "walk_to", "args": {"x":"1.2","y":"0.7"}},
    {"verb": "grasp",   "args": {"object":"pallet"}},
    {"verb": "place",   "args": {"x":"1.8","y":"0.7"}}
  ],
  "safety_zone": {"id":"packline1-zone","max_speed_mps":0.30,"keepout":[0,0,0,3,2,2]},
  "deadline_utc": "2025-11-01T23:59:59Z"
}
```

## Safety & Policy Enforcement
- OPA policies enforce role-based verb allowances, safety zone definitions, and speed caps.
- Safety checks include: zone overlap detection, cell capability validation, redundant E-stop path verification.
- Integration with Edge Agent ensures PLC retains final authority; OT telemetry doubles as safety monitor.
- Paused/cancelled tasks broadcast to safety channels (`task.execution.update` with `state=paused/cancelled`).

## Event Contracts
- **Produces:** `schedule.task.intent.created`, `schedule.task.intent.updated`, `task.execution.update`, `task.execution.audit`.
- **Consumes:** `schedule.task.intent.created` (idempotent), `edge.execution.telemetry`, `safety.event`.
- `task.execution.update` payload example:
```json
{
  "task_id": "TASK-000123",
  "state": "running",
  "cell": "PackLine1",
  "verb": "walk_to",
  "progress": {"percent": 40},
  "telemetry": {"speed_mps": 0.25, "battery_pct": 82},
  "safety": {"zone": "packline1-zone", "override": false},
  "timestamp": "2025-11-01T20:12:45Z"
}
```

## Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| `TASK_API_DB_URL` | Postgres connection | `postgres://task:***@task-db/task_api` |
| `TASK_API_GRPC_PORT` | gRPC bind port | `7000` |
| `TASK_API_HTTP_PORT` | REST port | `8080` |
| `TASK_API_EVENT_BROKER` | Kafka bootstrap servers | `kafka1:9092` |
| `TASK_API_OPA_URL` | OPA policy endpoint | `http://opa:8181/v1/data/task` |
| `TASK_API_MAX_PARALLEL` | Concurrent tasks per cell | `5` |
| `TASK_API_SAFETY_AUDIT_ENABLED` | Toggle audit trail snapshots | `true` |

Secrets handled via Vault (`kv/efab/task-api`). Certificates managed with SPIFFE/SPIRE for mTLS between services.

## Observability
- Metrics: `task_intent_submitted_total`, `task_execution_duration_seconds`, `task_safety_violation_total`, `task_queue_depth`.
- Traces: gRPC spans include verb-level metadata; correlation with Scheduler/Edge via trace IDs.
- Logs: Structured JSON aggregated to Loki; include safety policy decisions.
- Dashboards: “Task Pipeline Health” (intent latency, execution success rate, safety overrides).
- Alerts: `task_execution_failure_rate > 2%`, `task_queue_depth > threshold`, safety overrides > 1/min.

## Runbook & Ops
- `RUNBOOK.md#task-api-failure` – Steps to drain queue, replay intents, reset OPA bundle.
- `RUNBOOK.md#safety-override` – Safety override handling and escalation.
- `RUNBOOK.md#task-latency` – Investigating intent latency breaches (Scheduler/Edge interplay).
- Rollback: Feature flag `task_api_edge_bridge_enabled` toggles passthrough to legacy if needed.
- DR: Postgres PITR and event replay from `task.execution.update` topics.

## Testing
- Unit tests for verb validation, safety zone enforcement, policy evaluation.
- gRPC/REST contract tests with Edge Agent stubs and Scheduler clients.
- Integration tests verifying event emission and idempotency.
- Performance: sustain 100 intents/sec with p99 < 100ms for submission; concurrency tests for 20 parallel cells.

## KPIs
- Intent acceptance rate ≥ 99%.
- Safety violation rate < 0.1% (with automatic halt/alert).
- Intent latency (submission → queue) ≤ 150ms p99.
- Execution success rate ≥ 98%.

## Documentation Status
- Backlog item SVC-05 **Completed** (`MEM-20251101-002` observation recorded).
- Future work: ADR for Task API safety model and policy governance.

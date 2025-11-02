# Scheduler Service

## Overview
The Scheduler orchestrates order execution across cells by generating Task API intents, sequencing work, and reacting to telemetry feedback. Built on Temporal workflows, it bridges Orders, Manufacturing Graph, Inventory, and Edge systems to maintain optimal throughput while enforcing safety and changeover constraints.

## Responsibilities
- Transform `orders.*` events into production plans with lot-level routing.
- Evaluate Manufacturing Graph constraints (cells, changeovers, yields) and allocate resources.
- Emit `schedule.task.intent.created` events and push intents to Task API with required safety zones.
- Monitor execution feedback (`task.execution.update`) to adjust downstream tasks and KPIs.
- Provide APIs for planners to simulate, approve, or override schedules.

## Architecture & Data
- **Workflow Engine:** Temporal (Go SDK) with namespaces per site (`dev`, `staging`, `prod`).
- **Temporal Workflows:** `PlanOrderWorkflow`, `RescheduleWorkflow`, `EdgeDisruptionWorkflow`.
- **State Store:** Postgres schema `scheduler` (tables: `plans`, `plan_steps`, `constraints`, `simulations`).
- **Cache:** Redis for short-lived simulation results and scheduling heuristics.
- **Dependencies:** Manufacturing Graph service for routings, Inventory for material availability, Task API for execution.

## Interfaces
### REST
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/scheduler/plans` | Create plan for order/lots (optionally simulate) | Planner role |
| `GET` | `/scheduler/plans/{id}` | Retrieve plan state, upcoming tasks, constraints | Planner/Operator |
| `POST` | `/scheduler/plans/{id}/approve` | Approve simulated plan for execution | Planner |
| `POST` | `/scheduler/plans/{id}/pause` | Pause plan and cancel outstanding intents | Planner |
| `POST` | `/scheduler/rebalance` | Trigger rebalance after disruption (cell down, inventory shortage) | SRE/Planner |

### gRPC (`scheduler.v1.SchedulerService`)
- `CreatePlan`, `GetPlan`, `ApprovePlan`, `PausePlan`, `SimulatePlan`, `StreamPlanEvents`.
- Streaming API provides plan updates to Planner UI dashboards.

## Event Contracts
- **Produces:** `schedule.task.intent.created`, `schedule.task.intent.updated`, `schedule.plan.paused`, `schedule.plan.completed`.
- **Consumes:** `orders.created/updated`, `inventory.stock.updated`, `task.execution.update`, `telemetry.cell.state`.
- Workflow execution logs published to `scheduler.audit` topic for compliance.

## Temporal Workflow Overview
1. **PlanOrderWorkflow**
   - Fetch order + routing (Orders + Manufacturing Graph).
   - Run heuristics (changeover minimisation, priority weighting).
   - Reserve inventory (Inventory reservations API).
   - Emit Task API intents with safety zones derived from Manufacturing Graph + Edge plan.
2. **RescheduleWorkflow**
   - Triggered by telemetry or planner override.
   - Re-evaluates remaining tasks; reorders or pauses as needed.
3. **EdgeDisruptionWorkflow**
   - Handles edge offline or safety incident notifications from Observability alerts.
   - Pauses affected intents, triggers Runbook escalation.

## Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| `SCHEDULER_TEMPORAL_HOST` | Temporal frontend address | `temporal:7233` |
| `SCHEDULER_NAMESPACE` | Temporal namespace | `efab-prod` |
| `SCHEDULER_DB_URL` | Postgres connection | `postgres://scheduler:***@scheduler-db/scheduler` |
| `SCHEDULER_HEURISTIC` | Dispatch heuristic (`priority`, `changeover`) | `priority` |
| `SCHEDULER_SIMULATION_TIMEOUT_SEC` | Max simulation duration | `30` |
| `SCHEDULER_EDGE_RECOVERY_TIMEOUT_SEC` | Timeout before auto-rebalance after edge recovery | `120` |

Feature flags (LaunchDarkly): `scheduler_dual_write`, `scheduler_temporal_batcher`, `scheduler_safety_guard`.

## Observability
- Metrics: `scheduler_plan_created_total`, `scheduler_plan_latency_seconds`, `scheduler_intent_backlog`, `scheduler_rebalance_total`.
- Temporal visibility store exports workflow states to Grafana.
- Traces: OTel instrumentation for REST endpoints and workflow activities.
- Logs: Structured JSON with workflow IDs; errors tagged by order/lot/cell.
- Alerts: Intent backlog > threshold, workflow failure rate > 1%, simulation timeout > 5/min.

## Runbook & Ops
- `RUNBOOK.md#scheduler-failure` – Steps to replay workflows or resume paused plans.
- `RUNBOOK.md#edge-disruption` – Coordination with Edge Agent when cells go offline.
- Disaster Recovery: Temporal persistence uses MySQL/Postgres with PITR; workflows can be replayed from history.
- Rollback: Use `scheduler_dual_write` flag to failover to ERP scheduling if necessary.

## Testing
- Unit tests for heuristic scoring, safety zone wiring, event mapping.
- Temporal integration tests using local Temporal test server and fake services.
- Contract tests with Task API and Inventory (gRPC + event validation).
- Load tests target 500 concurrent workflow executions with < 2s scheduling latency.

## KPIs
- Intent lead time (plan→intent) ≤ 2 minutes p95.
- Plan adherence ≥ 90% (completed on time vs plan).
- Rebalance resolution time ≤ 10 minutes after disruption.
- Zero safety incidents attributable to scheduling errors.

## Documentation Status
- Backlog item SVC-04 **Completed** (`MEM-20251101-002` updated).
- Follow-up: ADR documenting Temporal workflow architecture and failover strategy.

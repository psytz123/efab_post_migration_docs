# Edge Agent Service

## Overview
The Edge Agent governs task execution on factory cells running k3s clusters. It receives Task API intents, orchestrates adapters (OPC UA, ROS 2, MQTT Sparkplug), enforces safety zones, and provides offline resilience with local caching and OTA update support. The Edge Agent is critical to maintain deterministic, low-latency control while remaining connected to the cloud control plane.

## Responsibilities
- Subscribe to `task.intent.edge` topics and schedule execution pipelines.
- Translate verbs into adapter-specific messages (OPC UA, ROS 2 actions, Sparkplug payloads).
- Enforce safety limits (speed, keepout zones) and interface with PLC E-stop circuits.
- Persist offline cache of pending/active tasks to survive WAN disruptions.
- Report telemetry, diagnostics, and safety events back to cloud (`task.execution.update`, `telemetry.*`).
- Manage OTA updates (containers, configs) with safe rollback procedures.

## Architecture
- **Platform:** k3s cluster on industrial PC with GPU optional.
- **Components:**
  - `edge-agent` core (Go) – task state machine, adapter orchestrator.
  - `opcua-adapter`, `ros2-bridge`, `mqtt-sparkplug` – containerized adapters.
  - `edge-controller` (sidecar) – OTA management, health monitoring.
- **Data:** Local SQLite cache for tasks + telemetry; sync to Postgres when online.
- **Networking:** MQTT (Sparkplug), OPC UA, ROS 2 DDS over LAN; mTLS to cloud via API Gateway/WebSocket.

## Execution Flow
1. Receive Task Intent (`task.intent.edge`).
2. Validate safety context (zones, speed, cell availability) using cached policies.
3. Dispatch verb sequence to adapters (ROS 2 actions for mobility, OPC UA methods for PLC, Sparkplug for sensors).
4. Monitor feedback; publish `task.execution.update` and telemetry metrics.
5. Handle safety events (stop, override) and escalate to Runbook.

## Configuration
| File | Description |
|------|-------------|
| `edge/agent/config.edge.yaml` | Site ID, broker endpoints, secret providers, adapter configuration. |
| `.env` | Optional overrides (log level, feature flags). |

### Key Settings
| Key | Purpose | Example |
|-----|---------|---------|
| `site_id` | Plant identifier | `bk-mill-01` |
| `wan.broker_url` | MQTT broker for Sparkplug backhaul | `mqtts://broker.efab.example.com` |
| `wan.kafka_bootstrap` | Cloud event bus | `kafka1:9092` |
| `adapters.opcua.endpoint` | PLC endpoint | `opc.tcp://10.0.1.25:4840` |
| `adapters.ros2.namespace` | ROS 2 namespace per cell | `/packline1` |
| `safety.zones[]` | Keepout volumes & max speed | `keepout: [0,0,0,3,2,2]; max_speed_mps: 0.3` |
| `ota.channel` | OTA deployment channel | `prod` |

Secrets fetched via Vault agent; tokens rotated automatically.

## Observability
- Metrics: `edge_task_queue_depth`, `edge_offline_duration_seconds`, `edge_safety_gate_hits`, `edge_ota_status`.
- Logs: Local structured logs rotated, forwarded when online; contain task/cell identifiers.
- Traces: Optional lightweight spans capturing command latency.
- Dashboards: “Edge Operations” row (queue depth, safety hits, OTA status).
- Alerts: Offline duration > SLA (configured in Observability plan), repeated safety hits, OTA failures.

## Runbook & SOPs
- `RUNBOOK.md#edge-offline` – Steps to restore WAN or process offline queue.
- `RUNBOOK.md#safety-trip` – Handling safety gate hits / E-stop events.
- `RUNBOOK.md#ota-failure` – Rollback procedure using staged container images.
- Safety validation steps aligned with `edge-safety-validation-plan.md` (simulator → pilot checklist).

## Offline Resilience & OTA
- Offline Mode: persists incoming intents, executes locally, replays updates upon reconnection.
- OTA: Managed via container registry (signed images); deployment uses canary to standby node before active cell.
- Health Monitor: `agent-health-monitor` checks CPU/memory/network; restarts adapters when necessary.

## Testing
- Unit tests for task state machine, adapter bindings, safety enforcement.
- Integration tests with simulator environment (ROS 2 + OPC UA + MQTT).
- Chaos tests: WAN disconnect, adapter crash, PLC faults.
- Latency targets: command round-trip < 250ms on LAN.

## KPIs
- Edge availability ≥ 99.5% (WAN outages excluded).
- Offline recovery < 2 minutes.
- Safety incident false-positive rate < 1%.
- OTA success rate ≥ 99%.

## Documentation Status
- Backlog item SVC-10 **Completed** (memory observation recorded).
- Pending follow-ups: document OTA canary procedure details and ties to supply-chain signing (SC-06).

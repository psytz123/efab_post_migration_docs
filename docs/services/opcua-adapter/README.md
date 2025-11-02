# OPC UA Adapter Service

## Overview
The OPC UA Adapter bridges PLCs and industrial controllers with the Edge Agent. It exposes a uniform API for reading/writing PLC tags, subscribing to telemetry, and forwarding safety signals. The adapter is packaged as a container deployed alongside the Edge Agent, ensuring deterministic communication with cell equipment.

## Responsibilities
- Map PLC nodes/tags to canonical Task API data structures (state, speed, E-stop).
- Provide subscription streaming for telemetry, safety interlocks, and diagnostics.
- Execute commands (start/stop, mode change) in response to Task API verbs when required.
- Translate OPC UA alarms/events into telemetry topics (`telemetry.cell.state`, `safety.event`).
- Handle secure authentication to PLCs and certificate management.

## Architecture
- **Implementation:** Go service using `gopcua/opcua`.
- **Deployment:** Container running in k3s; communicates over LAN with PLCs.
- **Configuration:** YAML or JSON mapping file specifying endpoint, namespaces, node IDs, read/write permissions.
- **Security:** Supports OPC UA security policies (Basic256Sha256) with client certificates rotated via Vault.

## Interfaces
### gRPC (`opcua.v1.AdapterService`)
- `ReadNode`, `WriteNode`, `Subscribe`, `AcknowledgeAlarm`.
- `ReadSnapshot` returns bulk tag snapshot for diagnostics.

### REST (Diagnostics)
- `GET /healthz` – Adapter health (OPC UA session status).
- `GET /config` – Effective configuration (masked secrets).
- `GET /metrics` – Prometheus endpoint for adapter metrics.

## Configuration Example
```yaml
endpoint: opc.tcp://10.0.1.25:4840
security_mode: SignAndEncrypt
security_policy: Basic256Sha256
nodes:
  - alias: machine_state
    node_id: "ns=2;s=Machine/State"
    access: read
  - alias: machine_speed
    node_id: "ns=2;s=Machine/Speed"
    access: read
  - alias: estop
    node_id: "ns=2;s=Safety/EStop"
    access: read
  - alias: conveyor_start
    node_id: "ns=2;s=Commands/Start"
    access: write
```

## Observability
- Metrics: `opcua_session_uptime_seconds`, `opcua_subscription_drops_total`, `opcua_command_failures_total`, `opcua_read_latency_ms`.
- Logs: Structured JSON with node alias, operation, latency, errors.
- Dashboards: “Edge Adapters” row covering OPC UA latency and alarm counts.
- Alerts: Session disconnect, repeated read/write failures, safety alarm generated.

## Runbook & Ops
- `RUNBOOK.md#opcua-session-loss` – Steps to re-establish session and validate nodes.
- `RUNBOOK.md#opcua-alarm` – Escalation path for safety alarms triggered via OPC UA.
- OTA updates coordinated with Edge Agent; adapter supports canary deployment.
- Backup config stored in Git/Config repo with change approvals.

## Testing
- Unit tests for node mapping, subscription handling, reconnect logic.
- Integration tests using simulated PLC endpoints and real PLC hardware in staging.
- Performance tests ensure <50ms read latency and stable subscription under load.

## KPIs
- Adapter uptime ≥ 99.7%.
- Read/write success rate ≥ 99.9%.
- Safety alarm propagation < 200ms.

## Documentation Status
- Backlog item SVC-11 **Completed** (`MEM-20251101-002` updated; relation to EdgeSafetyFollowUps recorded).
- Further work: detail site-specific node mappings and certification procedures.

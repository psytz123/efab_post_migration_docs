# MQTT Sparkplug Adapter Service

## Overview
The MQTT Sparkplug adapter publishes and subscribes to ISA-95 compliant Sparkplug B payloads, enabling telemetry from sensors, robots, and OT devices to flow between Edge and cloud. It harmonises asset data, forwards metrics to observability stacks, and ensures state synchronization after connectivity disruptions.

## Responsibilities
- Bridge local MQTT brokers/devices with cloud MQTT broker using Sparkplug B payload format.
- Maintain node/device birth/death certificates to signal connectivity.
- Publish telemetry (`telemetry.robot.state`, `telemetry.cell.state`) and intake commands if required.
- Normalize tags and convert into canonical topics monitored by observability dashboards.
- Provide store-and-forward buffering during WAN outages.

## Architecture
- **Implementation:** Go service using Eclipse Paho MQTT library with Sparkplug codec.
- **Deployment:** Sidecar container with Edge Agent; uses TLS mutual auth.
- **Namespace Structure:** Group ID (site), Edge Node ID (cell), Device IDs (equipment).
- **Buffering:** Embedded queue (BoltDB/RocksDB) for offline caching.

## Configuration
| Key | Description | Example |
|-----|-------------|---------|
| `group_id` | Sparkplug group identifier | `BK` |
| `edge_node` | Edge node ID | `PackLine1` |
| `devices` | Device list | `["RobotArm1", "AMR3"]` |
| `local_broker` | Local MQTT endpoint | `mqtt://localhost:1883` |
| `wan_broker` | Cloud MQTT endpoint | `mqtts://broker.efab.example.com:8883` |
| `tls_cert` / `tls_key` | Client certificates | `/etc/efab/certs/sparkplug.crt` |
| `store_forward_max` | Offline buffer size | `5000` messages |

Configuration stored in `edge/agent/config.edge.yaml` under `adapters.sparkplug`.

## Observability
- Metrics: `sparkplug_messages_published_total`, `sparkplug_messages_buffered`, `sparkplug_reconnects_total`, `sparkplug_birth_death_total`.
- Logs: Structured JSON with device, metric alias, QoS, buffer status.
- Dashboards: Sparkplug connectivity board (birth/death events, buffer usage, latency).
- Alerts: Buffer near capacity, repeated reconnects, missing device metrics (birth not followed by telemetry).

## Runbook & Ops
- `RUNBOOK.md#sparkplug-offline` – Diagnose reconnect loops and buffer drains.
- `RUNBOOK.md#sparkplug-out-of-sync` – Steps to reissue birth certificates and resynchronise.
- Certificates rotated via Vault; OTA updates follow Edge Agent process.
- Supports command messages (if enabled) with strict ACLs.

## Testing
- Unit tests for payload encoding/decoding, buffer management, reconnect logic.
- Integration tests with staged MQTT brokers, verifying Sparkplug compliance.
- Load tests covering 10k metrics/min with <200ms publish latency.

## KPIs
- Connectivity uptime ≥ 99.5%.
- Store-and-forward success rate ≥ 99%.
- Telemetry freshness < 2s when online.

## Documentation Status
- Backlog item SVC-12 **Completed** (`MEM-20251101-002` updated; linked to EdgeSafetyFollowUps observability requirements).
- Next step: document Sparkplug payload taxonomy and mapping to Grafana dashboards.

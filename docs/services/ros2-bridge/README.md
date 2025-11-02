# ROS2 Bridge Service

## Overview
The ROS2 Bridge connects the cloud Task API verb model to on-site ROS 2 ecosystems (Humble). Implemented in Rust for deterministic performance, it provides zero-copy translation between Task API commands and ROS 2 actions/topics, enforces safety zones, and streams telemetry back to Edge and cloud services.

## Responsibilities
- Subscribe to Edge Agent command channel and translate verbs into ROS 2 actions (`/move_base`, `/grasp`, `/place`, `/handoff`).
- Manage lifecycle of ROS 2 nodes, executors, and QoS profiles for multiple robots in a cell.
- Enforce safety parameters (speed limits, keepout volumes) and integrate with PLC safety IO via OPC UA callbacks.
- Publish telemetry (`telemetry.robot.state`, `telemetry.robot.pose`) and diagnostics for observability.
- Provide health endpoints for OTA/monitoring and support deterministic failover.

## Architecture
- **Language:** Rust (tokio + rclrs) with minimal unsafe usage (only in FFI wrappers).
- **Process Model:** Multi-threaded executors per robot namespace; message passing via channels.
- **Zero-Copy Transport:** Uses loaned messages and `rclrs` zero-copy support to minimise latency.
- **Safety Integration:** Hooks into Edge Agent safety guard; E-stop triggers immediate action cancellation.
- **Configuration:** YAML file specifying ROS 2 namespace, action mappings, keepout volumes, and adapters.

## Interfaces
### Commands (from Edge Agent)
- gRPC streaming channel `ExecuteVerbs` (Edge Agent ↔ ROS2 Bridge) carrying verb/op arguments.
- Each verb translated to ROS 2 action goal or service call; results streamed back.

### ROS 2 Actions / Topics
- Actions: `/move_base`, `/follow_path`, `/grasp`, `/place`, `/handoff`.
- Topics: `/robot_state`, `/battery_state`, `/safety_zone_status`, `/diagnostics`.
- Services: `/cancel_goal`, `/set_speed_limit`.

### Health API
- REST `GET /healthz` – returns readiness (ROS 2 graph, adapter connectivity).
- REST `GET /metrics` – Prometheus exporter with bridge metrics.

## Safety Enforcement
- Speed limits applied via dynamic reconfigure or ROS 2 parameter updates.
- Keepout volumes enforced through planner wrappers; tasks violating safety constraints rejected.
- E-stop integration: listens to OPC UA adapter events; triggers `CancelGoal` and publishes `task.execution.update` with `state=failed` and `reason=safety`.

## Configuration Example
```yaml
bridge:
  namespace: /packline1
  verbs:
    walk_to: { action: /move_base, frame: map }
    grasp:   { action: /grasp, frame: base_link }
    place:   { action: /place, frame: map }
  safety:
    max_speed_mps: 0.3
    keepout: [0,0,0,3,2,2]
  telemetry:
    publish_pose: true
    diagnostics_interval_sec: 5
```

## Observability
- Metrics: `ros_bridge_command_latency_ms`, `ros_bridge_goal_success_total`, `ros_bridge_safety_abort_total`, `ros_bridge_zero_copy_usage_ratio`.
- Logs: Structured JSON with verb, goal ID, robot namespace; stored locally and forwarded via Edge Agent.
- Traces: Optional instrumentation into OTel exporter for command/feedback spans.
- Dashboards: “Robot Bridge” panel showing latency, success rate, safety aborts.
- Alerts: Latency > 200ms p95, safety aborts > threshold, ROS 2 graph disconnects.

## Runbook & Ops
- `RUNBOOK.md#ros2-bridge-failure` – Steps to restart nodes, inspect DDS network, check OTA status.
- `RUNBOOK.md#safety-incident` – Investigate safety aborts and coordinate with Edge Agent.
- OTA: Container image built via Cargo + cross-compilation, signed per supply-chain policy.
- DR: Standby bridge node available; failover triggered via Edge Agent orchestrator.

## Testing
- Unit tests for verb mapping, safety guard logic, telemetry serialization.
- Integration tests using Gazebo/ROS 2 simulator; verifies action flows and telemetry publication.
- Miri + clippy to ensure memory safety; Criterion benchmarks for latency.
- Load tests mimic high-frequency command sequences with <100ms jitter target.

## KPIs
- Command-to-feedback latency ≤ 150ms p95.
- Safety aborts < 0.5% of commands (excluding real incidents).
- Zero memory leaks or executor panics (tracked via long-run soak tests).
- OTA success rate ≥ 99%.

## Documentation Status
- Backlog item SVC-13 **Completed** (`MEM-20251101-002` updated).
- Next steps: Document multi-robot coordination pattern and integration with predictive maintenance telemetry.

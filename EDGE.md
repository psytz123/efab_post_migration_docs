# Edge — Agent & Adapters (Factory)

## Bring‑up (sim → production)
1) Run Edge stack in sim mode to validate task execution loop.
2) Add OPC UA nodes (state/speed/E‑Stop) and ROS 2 actions for the pilot cell.
3) Configure safety zones; PLC retains final safety authority.

## Reference Config (edge/agent/config.edge.yaml)
```yaml
site_id: "bk-mill-01"
cluster: "k3s-local"
wan:
  broker_url: "mqtts://broker.efab.example.com"
  kafka_bootstrap: "kafka1:9092"
secrets:
  provider: "vault"
  path: "kv/efab/bk-mill-01"
adapters:
  opcua:
    endpoint: "opc.tcp://10.0.1.25:4840"
    nodes: ["ns=2;s=Machine/State", "ns=2;s=Machine/Speed"]
  ros2:
    namespace: "/packline1"
    actions: ["/move_base", "/grasp", "/place"]
  sparkplug:
    group_id: "BK"
    edge_node: "PackLine1"
    devices: ["RobotArm1", "AMR3"]
safety:
  zones:
    - id: "packline1-zone"
      max_speed_mps: 0.3
      keepout: [0,0,0, 3,2,2]
  plc_e_stop_tag: "ns=2;s=Safety/EStop"
```

## Edge Compose (cell PC)
```yaml
version: "3.9"
services:
  edge-agent:
    image: ghcr.io/efab/edge-agent:0.1.0
    network_mode: host
    volumes: ["./config.edge.yaml:/etc/efab/config.yaml:ro"]
  opcua-adapter:
    image: ghcr.io/efab/opcua-adapter:0.1.0
    network_mode: host
  ros2-bridge:
    image: ghcr.io/efab/ros2-bridge:humble-0.1.0
    network_mode: host
  mqtt-sparkplug:
    image: ghcr.io/efab/mqtt-sparkplug:0.1.0
    network_mode: host
```

## Safety Notes
- Task API never overrides PLC safety circuits.
- Define zones per cell; enforce max speeds and keepouts at Edge.
- All emergency stops broadcast to `telemetry.robot.state` and halt tasks.

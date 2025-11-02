# Mock Observability Stack

Spin up Prometheus + Grafana locally to visualise metrics exposed by the Orders mock service.

## 1. Prerequisites
- Docker Desktop with WSL integration enabled.
- Orders service running locally (`scripts/launch_orders_mock.sh`). Ensure `/dashboard/api/metrics` is reachable.

## 2. Start the stack
```bash
cd observability/mock-stack
docker compose up -d
```

Components:
- `metrics-exporter` polls `http://host.docker.internal:8080/dashboard/api/metrics` and exposes Prom-compatible gauges on `9108`.
- `prometheus` scrapes the exporter.
- `grafana` auto-loads the provided dashboard (username/password: `admin/admin`).

View Grafana: http://localhost:3000 (Orders Service > Orders Service Overview)

## 3. Update metrics source
Set `ORDERS_BASE_URL` to target a different Orders deployment:
```bash
ORDERS_BASE_URL=http://orders-staging.local docker compose up -d
```

## 4. Tear down
```bash
docker compose down -v
```

## 5. Extend the stack
- Add more exporters under `metrics-exporter/` and update `prometheus.yml`.
- Drop new dashboards into `grafana/dashboards/` (auto-loaded).
- Feed real Prometheus scrape targets when staging infra is ready.

# Orders Service Mock Environment Guide

The production deployment plan expects Postgres, Kafka, and TLS infrastructure that may not be available in early development or documentation review stages. This guide explains how to exercise the Orders service locally with mock data and in-memory integrations.

## 1. Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r services/orders/requirements.txt
```

## 2. Launch the Mock Service
```bash
source .venv/bin/activate
scripts/launch_orders_mock.sh
```

What happens:
- SQLite database created at `workspace/services/orders/mock/orders.db`.
- Event publisher set to `memory://` (no Kafka required).
- Five mock orders seeded via `scripts/seed_orders_mock.py` (adjust with `MOCK_SEED_COUNT`).

Override defaults if needed:
```bash
ORDERS_PORT=8090 MOCK_SEED_COUNT=20 scripts/launch_orders_mock.sh
```

## 3. Interact with the API
```bash
curl http://localhost:8080/orders | jq
curl -X POST http://localhost:8080/orders -H "Content-Type: application/json" \
  -d '{"sku":"MOCK-SKU-99","quantity":42,"due_date":"2025-12-01T00:00:00Z","site_id":"bk-mill-mock"}'
```

## 4. Run Tests Against Mock Data
With the service running you can execute:
```bash
locust -f services/orders/tests/performance/locustfile.py \
  --host http://localhost:8080 \
  --users 1 \
  --spawn-rate 1 \
  --headless \
  --run-time 5m \
  --csv reports/perf/orders-mock
scripts/owasp_baseline.sh http://host.docker.internal:8080
```
> Expect informational warnings from ZAP about cache-control and Spectre mitigation in the mock setup; document them and revisit once the service runs behind staging infrastructure.

For audit retention validation without AWS access:
```bash
python scripts/configure_audit_retention.py --bucket efab-audit/orders --region us-east-1 --dry-run
```

## 5. Resetting the Environment
- Stop the server (`Ctrl+C`).
- Remove the database if you need a clean slate: `rm workspace/services/orders/mock/orders.db`.
- Rerun `scripts/launch_orders_mock.sh` to recreate schema and seed data.

## 6. Troubleshooting
- Ensure the virtual environment is active before launching scripts.
- If port `8080` is in use, set `ORDERS_PORT` to another value.
- When running OWASP ZAP containers, start the API with `--host 0.0.0.0` and target `http://host.docker.internal:8080` so the container can reach the mock service.
- SQLite concurrency errors indicate the service was started before `launch_orders_mock.sh` applied the `check_same_thread=False` setting—restart using the script.

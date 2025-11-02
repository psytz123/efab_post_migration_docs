# Orders Service Dry-Run Checklist

> **No staging access?** Use the mock workflow described in `docs/environment/orders-mock-environment.md`. Record outputs in the same evidence locations noted below.

## Prerequisites
- Kafka/Redpanda staging cluster reachable
- Postgres staging instance with schema applied
- Apply mTLS secrets: `kubectl apply -f deploy/secrets/orders-staging-tls.yaml`
- Use staging overrides: `deploy/helm/orders/values-staging.yaml`

## Steps
1. `helm upgrade --install orders deploy/helm/orders -n staging -f deploy/helm/orders/values-staging.yaml`
2. Run database migrations (Flyway job) and verify `orders` schema seeded.
3. Execute synthetic Locust run (use `http://localhost:8080` when running the mock environment):
   ```bash
   locust -f services/orders/tests/performance/locustfile.py --host https://orders-stg.example.com --users 25 --spawn-rate 5 --run-time 10m
   ```
4. Execute OWASP ZAP baseline (mock: `http://localhost:8080`):
   ```bash
   scripts/owasp_baseline.sh https://orders-stg.example.com
   ```
5. Verify mTLS connectivity: ensure Orders pods mount `/etc/orders/tls` and curl upstreams with client certs.
6. Configure audit retention (S3 bucket `efab-audit/orders`) via `scripts/configure_audit_retention.py --bucket efab-audit/orders --region <aws-region>`.
7. Capture metrics snapshots and attach to runbook entry.

# Orders Service Security & Load Validation Playbook

## Overview
This runbook describes how to execute the mandated Wave 5 validation tasks for the Orders service using the mock environment:

- Launch the Orders FastAPI app locally via `scripts/launch_orders_mock.sh`.
- Run an OWASP ZAP baseline scan against the mock endpoint.
- Execute the Locust scenario to validate 100 orders/minute throughput expectations.
- Collect evidence files for compliance review, even when running with mocked data.

All steps assume you are working from the repository root with the `.venv` environment activated. Replace URLs if you stand up the mock service elsewhere.

## Prerequisites
- Start the mock Orders service (see `docs/environment/orders-mock-environment.md`):
  ```bash
  source .venv/bin/activate
  scripts/launch_orders_mock.sh
  ```
- Ensure Python dependencies are installed (`pip install -r services/orders/requirements.txt`).
- Docker daemon running locally for the OWASP ZAP container.
- Optional: AWS CLI configured if you wish to test the audit retention script against a sandbox account; otherwise run with `--dry-run`.

## OWASP ZAP Baseline
1. Ensure Docker is running and the staging ingress is reachable.
2. Execute the baseline scan script (if you are running the API locally, prefer `http://host.docker.internal:8080` so the container can reach the host):
   ```bash
   scripts/owasp_baseline.sh http://host.docker.internal:8080
   ```
   The script respects `ZAP_DOCKER_IMAGE` and defaults to `ghcr.io/zaproxy/zaproxy:stable`.
3. On completion, capture the generated report paths (HTML/JSON) under `reports/owasp/`.
4. Archive reports to `.agent-workspace/outputs/wave-6/security/` and attach the summary to the handoff log.
> If Docker is unavailable, document the blocker in the handoff and schedule the scan for the next environment with container support.
> The mock scan currently surfaces informational warnings for cacheability and Spectre heuristics; review but defer remediation until staging confirms whether headers need further hardening.

## Locust Load Test
1. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   ```
2. Run the mock scenario. When using SQLite, keep concurrency low (`--users 1`) to avoid lock contention:
   ```bash
   locust -f services/orders/tests/performance/locustfile.py \
       --host http://localhost:8080 \
       --users 1 \
       --spawn-rate 1 \
       --run-time 5m \
       --headless \
       --csv reports/perf/orders-mock
   ```
3. Verify p95 latency remains below 200ms and failure ratio < 1%.
4. Store the generated CSV metrics in `.agent-workspace/outputs/wave-6/performance/` and update the Wave 6 summary.

## Audit Retention Verification
1. Apply retention automation:
   ```bash
   python scripts/configure_audit_retention.py \
       --bucket efab-audit/orders \
       --region us-east-1 \
       --dry-run
   ```
2. Validate lifecycle configuration:
   ```bash
   aws s3api get-bucket-lifecycle-configuration --bucket efab-audit/orders
   aws s3api get-bucket-encryption --bucket efab-audit/orders
   ```
3. Capture CLI outputs and store under `.agent-workspace/outputs/wave-6/audit/`.

## Evidence Checklist
- [ ] OWASP HTML + JSON reports archived and referenced from handoff (mock endpoint).
- [ ] Locust CSV results and summary metrics recorded using mock service.
- [ ] AWS CLI verification of lifecycle/encryption saved as text or note `--dry-run`.
- [ ] Dry-run checklist (`deploy/orders-staging-dryrun.md`) annotated with mock execution timestamps.
- [ ] Follow-up issues filed for any failed gates.

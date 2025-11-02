# Observability — Metrics, Logs, Traces

**Reference**: [ADR-005: Observability Stack](docs/adr/ADR-005-observability.md)

## Overview

This document describes the eFab platform's observability stack, including metrics collection, alerting, dashboarding, and CI automation. The implementation follows ADR-005 and emphasizes:

- **Infrastructure as Code**: Dashboards and alerts defined in Jsonnet
- **Site/Cell Scoping**: All metrics tagged and filtered by site/cell
- **Automated Validation**: CI pipeline ensures configuration quality
- **Runbook Integration**: All alerts linked to operational runbooks

## Tracing

- **OpenTelemetry** SDK in Flask (legacy) and all new services
- Distributed tracing for cross-service request flows
- Trace correlation with metrics and logs

## Metrics

### Core Metrics Categories

#### API Metrics
- Request rate (req/sec)
- Latency percentiles (p50/p90/p99)
- Error rate and status codes
- Endpoint-specific metrics

#### Scheduler Metrics
- Task wait time
- Plan adherence percentage
- Scheduling latency

#### Task API Metrics
- Intents per second
- Task lifecycle events (run/complete/fail)
- Safety gate hit count

#### Edge Metrics
- Command latency
- ROS/OPC UA roundtrip time
- Offline duration
- Heartbeat staleness

#### Cell KPIs
- OEE (Overall Equipment Effectiveness)
- Changeover time
- Scrap rate
- First Pass Yield (FPY)

#### FinOps Metrics
- Unit cost variance
- ROI trends
- Cost allocation accuracy

### Metric Naming Convention

All metrics follow Prometheus naming conventions:
```
<component>_<metric>_<unit>_<aggregation>
```

Examples:
- `edge_heartbeat_seconds` - Edge agent heartbeat age
- `task_intent_latency_ms_bucket` - Task intent latency histogram
- `cell_oee_percent` - Cell OEE percentage
- `finops_cost_variance` - Cost variance ratio

## Logs

- **Structured JSON format** → Loki/ELK
- **PII/SPI redaction** at source
- **Correlation IDs** for trace/log linking
- **Log levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Retention policy**: 30 days hot, 90 days archive

## Dashboards & Alerts

### Dashboard as Code (Jsonnet)

Dashboards are defined in `organized/observability/dashboard_main.jsonnet` using Grafonnet library.

**Parameters**:
- `site`: Factory site identifier (e.g., `factory-01`)
- `cell`: Cell identifier (e.g., `cell-a`)
- `environment`: Deployment environment (`prod`, `staging`, `dev`)

**Compilation**:
```bash
jsonnet dashboard_main.jsonnet \
  --tla-str site=factory-01 \
  --tla-str cell=cell-a \
  --tla-str environment=prod \
  > dashboard.json
```

**Dashboard Categories**:
1. **Production KPIs**: OEE, task latency, throughput
2. **Safety & Edge Health**: Safety gates, heartbeat status
3. **FinOps & Cost**: Unit cost variance, ROI trends

### Alert Rules (Jsonnet)

Alert rules are defined in `organized/observability/alerts_main.jsonnet`.

**Alert Groups**:
1. **Safety Alerts** (Critical Priority)
   - `EdgeHeartbeatStale`: Edge agent heartbeat stale >15s
   - `SafetyGateSpike`: Safety gate activations exceeding threshold

2. **FinOps Alerts**
   - `UnitCostVarianceHigh`: Cost variance >5% for 15min
   - `ROITrendNegative`: ROI negative for 30min

3. **Performance Alerts**
   - `TaskIntentLatencyHigh`: p99 latency >500ms
   - `OEEBelowTarget`: OEE <85% for 15min

**Required Annotations**:
- `summary`: Brief alert description
- `description`: Detailed alert context with templated values
- `runbook_url`: Link to operational runbook
- `dashboard_url`: Link to relevant dashboard
- `owner`: Team responsible for alert
- `priority`: P1 (critical), P2 (high), P3 (medium)
- `impact`: Business/operational impact statement

**Compilation**:
```bash
jsonnet alerts_main.jsonnet \
  --tla-str site=factory-01 \
  --tla-str cell=cell-a \
  --tla-str environment=prod \
  --tla-str slack_channel=#alerts \
  --yaml-stream > alerts.yml
```

## Alertmanager Configuration

### Routing Strategy

Alert routing is configured in `organized/observability/alertmanager_config.yml`.

**Routing Rules**:
1. **Critical Alerts** → PagerDuty + Slack
   - Group wait: 10s
   - Repeat interval: 1h
   - Receivers: `pagerduty-critical`, `slack-critical`

2. **Safety Alerts** → PagerDuty (high priority) + Slack
   - Group wait: 5s
   - Repeat interval: 30min
   - Receivers: `pagerduty-safety`, `slack-safety`

3. **FinOps Alerts** → Slack + Email (critical only)
   - Receivers: `slack-finops`, `email-finops-team`

4. **Performance Alerts** → Slack
   - Receiver: `slack-platform`

5. **Warning Alerts** → Slack only (no pages)
   - Group wait: 2min
   - Repeat interval: 6h
   - Receiver: `slack-warnings`

### Environment-Specific Routing

- **Production**: Dedicated PagerDuty integration with 5s group wait
- **Staging**: Slack-only routing with 5min group wait

### Inhibition Rules

Suppress dependent alerts to reduce noise:

1. **Suppress warnings when critical alerts firing** (same alert group/environment)
2. **Suppress performance alerts when safety alerts firing**
3. **Suppress service-specific alerts when cluster-wide alerts firing**

### Receiver Configuration

**PagerDuty**:
- Integration keys configured via secrets: `PAGERDUTY_CRITICAL_KEY`, `PAGERDUTY_SAFETY_KEY`
- Includes runbook URLs and dashboard links in incident details

**Slack**:
- Webhook URL: `SLACK_WEBHOOK_URL` (injected via secret)
- Channels: `#alerts-critical`, `#alerts-safety`, `#alerts-finops`, `#alerts-platform`, `#alerts-warnings`
- Formatted messages with runbook/dashboard links

**Email**:
- SMTP configuration for FinOps team escalations
- HTML-formatted emails with actionable links

## CI Validation Pipeline

### GitHub Actions Workflow

File: `.github/workflows/observability-check.yml`

**Validation Jobs**:

#### 1. Jsonnet Validation
- **Format checking**: `jsonnetfmt --test` for all `.jsonnet` files
- **Compilation testing**: Compiles dashboards and alerts with sample parameters
- **Parameterization testing**: Tests multiple site/cell/environment combinations

#### 2. Prometheus Rules Validation
- **promtool validation**: `promtool check rules` on compiled alert YAML
- **Annotation checking**: Validates required annotations (summary, description, runbook_url)
- **Label checking**: Validates required labels (severity, environment)

#### 3. Metrics Schema Lint
- **Schema validation**: Runs `metrics_lint.py --strict` to enforce naming conventions
- **Metric cardinality checks**: Warns on high-cardinality metrics
- **Label validation**: Ensures consistent label usage

#### 4. Runbook URL Validation
- **URL format validation**: Validates runbook_url format and HTTPS requirement
- **Reachability checking**: HTTP HEAD requests to verify runbook URLs (optional)
- **Placeholder detection**: Identifies TODO/FIXME placeholders

#### 5. Integration Test
- **Full pipeline test**: Compiles dashboards and alerts with production-like parameters
- **Artifact upload**: Stores compiled configs for 7 days

### Blocking Merge Criteria

Pull requests are **blocked** if:
- Jsonnet files fail formatting check
- Alert rules fail promtool validation
- Required annotations/labels are missing
- Runbook URLs are invalid (strict mode)
- Metrics schema violations detected

### Running Validation Locally

**Format Jsonnet files**:
```bash
cd organized/observability
jsonnetfmt -i *.jsonnet
```

**Validate alerts**:
```bash
jsonnet alerts_main.jsonnet \
  --tla-str site=factory-01 \
  --tla-str cell=cell-a \
  --tla-str environment=prod \
  --tla-str slack_channel=#alerts \
  --yaml-stream | promtool check rules /dev/stdin
```

**Validate runbook URLs**:
```bash
python organized/observability/runbook_validator.py \
  --input organized/observability/alerts_main.jsonnet \
  --fail-on-404
```

**Run metrics linter**:
```bash
python organized/observability/metrics_lint.py --strict
```

## Runbook Validator

### Purpose

Validates that all `runbook_url` annotations in Prometheus alert rules are:
1. Properly formatted (valid HTTPS URLs)
2. Reachable (return HTTP 200/300 series status codes)
3. Not placeholders (no TODO/FIXME/example.com)

### Usage

**Basic validation**:
```bash
python runbook_validator.py --input alerts_main.jsonnet
```

**Strict mode (fail on 404)**:
```bash
python runbook_validator.py --input alerts_main.jsonnet --fail-on-404
```

**Dry-run mode (skip HTTP requests)**:
```bash
python runbook_validator.py --input alerts_main.jsonnet --dry-run
```

### Features

- **Jsonnet compilation**: Automatically compiles Jsonnet to JSON before validation
- **Retry logic**: Exponential backoff for transient failures (default: 3 retries)
- **Caching**: 5-minute TTL cache for URL validation results
- **Format validation**: Regex-based URL format checking
- **HTTPS enforcement**: Requires HTTPS for production runbooks
- **Placeholder detection**: Warns on TODO/example.com/localhost URLs

### Validation Results

**Exit Codes**:
- `0`: All runbook URLs valid and reachable
- `1`: Validation failures detected (format errors, 404s, 5xx errors)

**Output**:
```
Extracting runbook URLs from: alerts_main.jsonnet
Found 6 runbook URL(s) to validate

Validating: EdgeHeartbeatStale
  URL: https://wiki.efab.example.com/runbooks/edge-heartbeat-stale
  Status: OK (200)

Validating: SafetyGateSpike
  URL: https://wiki.efab.example.com/runbooks/safety-gate-spike
  Status: OK (200)

======================================================================
VALIDATION SUMMARY
======================================================================
Total URLs:        6
Reachable:         5
Placeholders:      1
Failed:            0

PLACEHOLDER URLs (need attention):
  - UnitCostVarianceHigh: https://wiki.efab.example.com/runbooks/TODO
```

### Integration with CI

The runbook validator runs automatically on every pull request affecting `organized/observability/**`:

```yaml
- name: Run runbook validator
  run: |
    cd organized/observability
    python runbook_validator.py --input alerts_main.jsonnet --fail-on-404
```

## Troubleshooting

### Jsonnet Compilation Errors

**Symptom**: `ERROR: Failed to compile Jsonnet`

**Solutions**:
1. Check Jsonnet syntax: `jsonnet alerts_main.jsonnet` (without parameters)
2. Verify all required parameters: `--tla-str site=X --tla-str cell=Y`
3. Check import paths and library dependencies
4. Run `jsonnetfmt -i file.jsonnet` to auto-format

### Prometheus Rule Validation Failures

**Symptom**: `promtool check rules` fails

**Common Causes**:
1. **Invalid PromQL expression**: Check `expr` field syntax
2. **Missing required fields**: Ensure `alert`, `expr`, `labels`, `annotations` present
3. **Invalid duration**: Check `for` field format (e.g., `5m`, `1h`)

**Debugging**:
```bash
# Test PromQL expression in Prometheus UI
http://prometheus:9090/graph

# Validate specific rule
promtool check rules alerts.yml
```

### Alertmanager Routing Issues

**Symptom**: Alerts not routing to expected receivers

**Debugging Steps**:
1. **Check label matching**: Verify alert labels match routing rules
2. **Test routing**: Use `amtool` to simulate routing
   ```bash
   amtool config routes test --config.file=alertmanager_config.yml \
     --tree \
     severity=critical \
     alertgroup=safety \
     environment=prod
   ```
3. **Verify receiver config**: Check Slack webhook/PagerDuty integration keys
4. **Check inhibition rules**: Ensure alerts aren't being suppressed

### Runbook URL Validation Failures

**Symptom**: `VALIDATION FAILED` with unreachable URLs

**Solutions**:
1. **Format errors**: Ensure URLs use `https://` scheme
2. **DNS resolution**: Verify domain resolves (check `/etc/hosts` for local testing)
3. **Network access**: Ensure runner/CI has network access to runbook URLs
4. **Placeholder URLs**: Replace TODO/example.com with real URLs
5. **Use dry-run mode**: Skip HTTP checks during development
   ```bash
   python runbook_validator.py --input alerts_main.jsonnet --dry-run
   ```

### CI Pipeline Failures

**Symptom**: GitHub Actions workflow fails

**Common Issues**:
1. **Missing dependencies**: Check `go install` and `pip install` steps
2. **Path issues**: Ensure `$GITHUB_PATH` updated for Go binaries
3. **Artifact paths**: Verify `/tmp/` paths exist before artifact upload
4. **Timeout**: Increase `timeout` parameter for slow HTTP checks

**Logs**:
```bash
# View workflow logs
gh run view <run-id> --log

# Re-run failed jobs
gh run rerun <run-id> --failed
```

### Metrics Schema Violations

**Symptom**: `metrics_lint.py --strict` fails

**Common Violations**:
1. **Naming convention**: Use `<component>_<metric>_<unit>` format
2. **High cardinality**: Avoid unbounded labels (user IDs, timestamps)
3. **Inconsistent labels**: Use same label names across related metrics
4. **Missing help text**: Add `# HELP` and `# TYPE` comments

**Fix**:
```python
# Bad: Inconsistent naming
edge_heartbeat = Gauge('heartbeat', 'Edge heartbeat')

# Good: Consistent naming with unit
edge_heartbeat_seconds = Gauge(
    'edge_heartbeat_seconds',
    'Time since last edge agent heartbeat',
    ['site', 'cell']
)
```

## Testing

### Unit Tests

Test suite: `organized/observability/tests/test_runbook_validator.py`

**Run tests**:
```bash
cd organized/observability
pytest tests/ -v --cov=. --cov-report=term-missing
```

**Coverage expectations**: >90% code coverage for validators

### Integration Tests

**End-to-end pipeline test**:
```bash
cd organized/observability

# 1. Compile dashboard
jsonnet dashboard_main.jsonnet \
  --tla-str site=factory-01 \
  --tla-str cell=cell-a \
  --tla-str environment=prod \
  > /tmp/dashboard.json

# 2. Compile alerts
jsonnet alerts_main.jsonnet \
  --tla-str site=factory-01 \
  --tla-str cell=cell-a \
  --tla-str environment=prod \
  --tla-str slack_channel=#alerts \
  --yaml-stream > /tmp/alerts.yml

# 3. Validate alerts
promtool check rules /tmp/alerts.yml

# 4. Validate runbooks
python runbook_validator.py --input alerts_main.jsonnet

# 5. Validate Alertmanager config
amtool check-config alertmanager_config.yml
```

## Deployment

### Kubernetes Deployment

**Apply dashboards**:
```bash
# Generate ConfigMap
kubectl create configmap grafana-dashboards \
  --from-file=dashboard.json \
  --dry-run=client -o yaml | kubectl apply -f -
```

**Apply alert rules**:
```bash
# Generate PrometheusRule CR
cat <<EOF | kubectl apply -f -
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: efab-alerts-factory-01-cell-a
  namespace: monitoring
spec:
  $(cat /tmp/alerts.yml)
EOF
```

**Apply Alertmanager config**:
```bash
kubectl create secret generic alertmanager-config \
  --from-file=alertmanager.yml=alertmanager_config.yml \
  --namespace=monitoring \
  --dry-run=client -o yaml | kubectl apply -f -
```

### Parameterized Deployment

Deploy dashboards and alerts for multiple sites/cells:

```bash
#!/bin/bash
SITES=("factory-01" "factory-02")
CELLS=("cell-a" "cell-b")
ENV="prod"

for site in "${SITES[@]}"; do
  for cell in "${CELLS[@]}"; do
    echo "Deploying observability for $site/$cell"

    # Compile dashboard
    jsonnet dashboard_main.jsonnet \
      --tla-str site=$site \
      --tla-str cell=$cell \
      --tla-str environment=$ENV \
      > "/tmp/dashboard-$site-$cell.json"

    # Compile alerts
    jsonnet alerts_main.jsonnet \
      --tla-str site=$site \
      --tla-str cell=$cell \
      --tla-str environment=$ENV \
      --tla-str slack_channel="#alerts-$site" \
      --yaml-stream > "/tmp/alerts-$site-$cell.yml"

    # Deploy to Kubernetes
    kubectl apply -f "/tmp/dashboard-$site-$cell.json"
    kubectl apply -f "/tmp/alerts-$site-$cell.yml"
  done
done
```

## Best Practices

### Alert Design

1. **Symptom-based alerts**: Alert on user-visible symptoms, not implementation details
2. **Actionable**: Every alert should have a clear runbook and remediation steps
3. **Severity classification**:
   - **Critical**: Immediate action required, page on-call
   - **Warning**: Investigate during business hours
   - **Info**: Logging/audit purposes only
4. **Avoid flapping**: Use appropriate `for` durations and thresholds
5. **Test alerts**: Validate with `amtool` before deploying

### Dashboard Design

1. **Progressive disclosure**: Start with high-level KPIs, drill down to details
2. **Consistent time ranges**: Default to 6h lookback, allow user override
3. **Template variables**: Use `site`, `cell`, `environment` for filtering
4. **Annotations**: Link to runbooks and related dashboards
5. **SLO tracking**: Visualize error budgets and burn rates

### Runbook Maintenance

1. **Keep runbooks updated**: Review quarterly or after incidents
2. **Include context**: Why alert fires, what's normal, what's abnormal
3. **Step-by-step remediation**: Clear, numbered steps for on-call engineers
4. **Escalation paths**: Who to contact if runbook doesn't resolve issue
5. **Post-incident updates**: Update runbooks after every incident

### Metrics Hygiene

1. **Limit cardinality**: Avoid unbounded labels (user IDs, request IDs)
2. **Consistent naming**: Follow Prometheus naming conventions
3. **Appropriate aggregation**: Use histograms for latencies, counters for events
4. **Label consistency**: Use same label names across related metrics
5. **Documentation**: Add help text to all metrics

## References

- [ADR-005: Observability Stack](docs/adr/ADR-005-observability.md)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
- [Alertmanager Configuration](https://prometheus.io/docs/alerting/latest/configuration/)
- [Grafonnet Documentation](https://grafana.github.io/grafonnet-lib/)
- [Jsonnet Tutorial](https://jsonnet.org/learning/tutorial.html)

## Automation Files

- **CI Pipeline**: `.github/workflows/observability-check.yml`
- **Dashboards**: `organized/observability/dashboard_main.jsonnet`
- **Alerts**: `organized/observability/alerts_main.jsonnet`
- **Alertmanager**: `organized/observability/alertmanager_config.yml`
- **Runbook Validator**: `organized/observability/runbook_validator.py`
- **Metrics Linter**: `organized/observability/metrics_lint.py`
- **Tests**: `organized/observability/tests/test_runbook_validator.py`

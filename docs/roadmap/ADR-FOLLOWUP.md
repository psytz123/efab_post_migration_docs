# ADR Follow-up Implementation Plan
**Generated:** 2025-11-01

This plan translates ADR-004 through ADR-008 into actionable engineering tasks. Owners align with multi-agent roles previously used.

## Summary Table
| ADR | Theme | Key Actions | Owner(s) | Target Window |
|-----|-------|-------------|----------|---------------|
| ADR-004 | Safety Governance | Sync safety zones Task API ↔ Edge; automate E-stop propagation tests; update Runbook audit steps | manufacturing-ai-consultant, sre-engineer | Nov 2025 Wk 1 |
| ADR-005 | Observability Integration | Dashboard-as-code repo; Alertmanager routing; metrics schema lint in CI | sre-engineer, documentation-engineer | Nov 2025 Wk 1–2 |
| ADR-006 | Manufacturing Graph Modelling | Implement indexes/mat views; latency SLO dashboards; define graph DB trigger criteria | data-engineer | Nov 2025 Wk 2 |
| ADR-007 | OTA & Signing | Extend CI pipeline with signed manifests; edge verification hook; update OTA runbook; automate simulator canary | manufacturing-ai-consultant, security-auditor | Nov 2025 Wk 2 |
| ADR-008 | FinOps Cost Allocation | Build allocation weight module; reconciliation jobs; policy repo; variance alert rules | documentation-engineer, finops-analyst | Nov 2025 Wk 3 |

## Detailed Tasks

### ADR-004 – Safety Governance
1. **Safety Zone Sync Automation**
   - ✅ Script available (`organized/safety/safety_zone_diff.py`) with remediation hints and CI flags.
   - ⏳ Add CI check blocking deploy when mismatch > 0 (wire `--fail-on-diff` into pipeline).
2. **E-stop Propagation Test Suite**
   - Build integration tests simulating PLC E-stop, verifying Task API audit log entry within 5s.
   - Integrate into staging pipeline before OTA promotion.
3. **Runbook Update**
   - Expand `RUNBOOK.md#safety-incident` with audit checklist referencing ADR.

### ADR-005 – Observability Integration
1. **Dashboard-as-Code Repository**
   - ✅ Dashboard template parameterised for site/cell/environment (`organized/observability/dashboard_main.jsonnet`).
   - ⏳ Link CI job to validate dashboards before merge.
2. **Alert Routing Configuration**
   - ✅ Alertmanager bundle generated (`organized/observability/alerts_main.jsonnet`) with Slack channel annotations.
   - ⏳ Add automated test ensuring Runbook URL resolves (HTTP 200).
3. **Metrics Schema Lint**
   - Add CI step verifying Prometheus metric naming and label conventions.

### ADR-006 – Manufacturing Graph Modelling
1. **Index & Materialized View Implementation**
   - Create Flyway migrations adding GIN indexes and materialized views for routing lookup.
2. **Latency SLO Monitoring**
   - Instrument service to emit `mfg_graph_routing_lookup_duration_seconds` and alert when >50ms p95.
3. **Graph DB Trigger Document**
   - Author living document listing thresholds (e.g., >5k operations) that trigger reevaluation.

### ADR-007 – OTA & Signing Policy
1. **CI/CD Signing Integration**
   - Update GitHub Actions to sign OTA manifests with Cosign and attach provenance.
2. **Edge Verification Hook**
   - Modify Edge Agent OTA module to verify signatures offline using cached trust bundle.
3. **Simulator Canary Workflow**
   - Extend OTA rollout to run simulator test before production cell; capture metrics.
4. **Runbook Refresh**
   - Update `RUNBOOK.md#ota-failure` steps referencing signature checks.

### ADR-008 – FinOps Cost Allocation
1. **Allocation Weight Module**
   - ✅ Core allocation engine implemented (`organized/finops/allocation.py`) with pytest coverage.
   - ⏳ Build API/UI for finance to manage allocation weights with audit log.
2. **ERP Reconciliation Job**
   - ✅ Reconciliation CLI prototype created (`organized/finops/reconciliation_job.py`) plus sample actuals payload.
   - ⏳ Schedule nightly job comparing FinOps totals vs ERP ledger; alert on variance >5%.
3. **Policy Repository**
   - Store allocation policies in `.finops/policies/`, version-controlled with change approvals.
4. **Variance Alert Rule**
   - Configure FinOps alert for cost variance breaches, tied to new Runbook entry (coordinate with observability bundle).

## Tracking & Reporting
- Add these items to program backlog (JIRA/ADO) referencing ADR IDs.
- Progress reviewed in weekly architecture sync; status updated in `.agent-workspace/outputs/integration/efab-docs-execution-summary.md`.

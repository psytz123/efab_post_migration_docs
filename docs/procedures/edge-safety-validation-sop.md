# Edge Safety Validation SOP

**Document ID**: SOP-SAFETY-001
**Version**: 1.0
**Effective Date**: 2025-11-01
**Owner**: Safety Engineering Team
**References**: ADR-004 Safety Governance

## Purpose

This Standard Operating Procedure (SOP) defines the validation procedures for edge agent safety systems, ensuring compliance with ADR-004 safety governance requirements and maintaining <5 second E-stop propagation latency.

## Scope

This SOP applies to:
- Edge agent deployments and updates
- Safety zone configuration changes
- PLC integration testing
- Offline behavior validation
- E-stop system verification

## Roles and Responsibilities

| Role | Responsibilities |
|------|------------------|
| Safety Engineer | Approve safety configuration changes, conduct validation |
| Edge Engineer | Implement edge agent updates, execute validation tests |
| QA Engineer | Execute test procedures, document results |
| Production Manager | Authorize production deployments |
| On-call Engineer | Respond to safety incidents per escalation procedures |

## Definitions

- **Edge Agent**: Local control system managing safety policies at edge locations
- **PLC**: Programmable Logic Controller providing hardware E-stop authority
- **Safety Zone**: Physical area with defined safety parameters and controls
- **E-stop**: Emergency stop signal requiring immediate system halt
- **Cache TTL**: Time-to-live for cached safety policies (default: 300 seconds)

## Validation Procedures

### 1. Pre-Deployment Validation

**Objective**: Verify edge agent safety systems before production deployment.

**Prerequisites**:
- [ ] Edge agent code review completed
- [ ] Safety configuration reviewed by safety engineer
- [ ] Test environment mirrors production configuration
- [ ] PLC simulator or test PLC available

**Procedure**:

#### 1.1 Safety Configuration Validation

```bash
# Step 1: Load safety configuration
cd organized/safety/config
cat safety-zones.yml

# Step 2: Validate configuration schema
python scripts/validate-safety-config.py \
  --config safety-zones.yml \
  --schema safety-schema.json

# Step 3: Run safety zone diff
python scripts/safety-zone-diff.py \
  --base origin/main \
  --head HEAD \
  --output validation-report.json

# Step 4: Review diff report
cat validation-report.json
```

**Expected Results**:
- Configuration passes schema validation
- No unapproved critical changes detected
- Diff report generated successfully

**Failure Actions**:
- Critical changes detected → Escalate to safety engineer
- Schema validation fails → Fix configuration, repeat validation
- Unapproved changes → Obtain safety team approval

#### 1.2 E-stop Propagation Testing

```bash
# Step 1: Run E-stop propagation tests
pytest organized/safety/tests/test_estop_propagation.py \
  -v \
  --tb=short \
  --cov=organized/safety \
  --cov-fail-under=90

# Step 2: Verify latency requirements
# All tests must pass with <5 second latency
grep "PASSED" pytest-output.log

# Step 3: Check coverage report
coverage report --include="organized/safety/*"
```

**Expected Results**:
- All tests pass (100% success rate)
- E-stop latency < 5 seconds (all scenarios)
- Test coverage ≥ 90%

**Failure Actions**:
- Test failures → Debug and fix issues, repeat testing
- Latency threshold exceeded → Investigate performance, optimize
- Coverage below 90% → Add additional test coverage

#### 1.3 Offline Behavior Validation

**Objective**: Verify edge agent operates safely when disconnected from Task API.

```bash
# Step 1: Test offline E-stop handling
pytest organized/safety/tests/test_estop_propagation.py::test_estop_offline_edge_behavior -v

# Step 2: Test network partition resilience
pytest organized/safety/tests/test_estop_propagation.py::test_network_partition_resilience -v

# Step 3: Test cache expiration handling
pytest organized/safety/tests/test_estop_propagation.py::test_cache_expiration -v
```

**Expected Results**:
- Edge agent continues safety operations offline
- Cached policies used correctly (TTL=300s)
- Events queued for sync when reconnected

**Failure Actions**:
- Offline operation fails → Fix edge agent logic, repeat tests
- Cache not used → Verify cache implementation
- Event loss detected → Fix event queue logic

### 2. PLC Authority Matrix Validation

**Objective**: Verify hardware E-stop authority supersedes software controls.

**PLC Authority Matrix**:

| Override Source | Authority Level | Can Override | Cannot Override |
|----------------|-----------------|--------------|------------------|
| Hardware E-stop | 1 (Highest) | All software controls | None |
| PLC Software | 2 | Edge agent commands | Hardware E-stop |
| Edge Agent | 3 | Task API commands | PLC controls |
| Task API | 4 (Lowest) | User commands | Edge/PLC controls |

**Procedure**:

#### 2.1 Hardware E-stop Authority Test

```bash
# Step 1: Test hardware E-stop override
pytest organized/safety/tests/test_estop_propagation.py::test_hardware_estop_authority -v

# Step 2: Verify PLC status reflects hardware override
# Check test output for hardware_override=True flag

# Step 3: Verify audit log captures authority level
grep "hardware_override" test-audit-log.json
```

**Expected Results**:
- Hardware E-stop cannot be overridden by software
- PLC status correctly reports hardware override
- Audit log records authority level

**Failure Actions**:
- Software override detected → Fix authority logic, repeat test
- Audit log missing authority → Add audit logging
- PLC status incorrect → Fix PLC integration

#### 2.2 Authority Escalation Test

```bash
# Manual test procedure with PLC simulator

# Step 1: Trigger software E-stop from Task API
curl -X POST http://edge-agent/api/v1/estop \
  -H "Content-Type: application/json" \
  -d '{"source": "task_api", "reason": "maintenance"}'

# Step 2: Attempt to override with PLC software
# Should succeed - PLC authority level 2 > Task API level 4

# Step 3: Trigger hardware E-stop
# Press physical E-stop button on test PLC

# Step 4: Attempt to clear from software
curl -X POST http://edge-agent/api/v1/estop/clear \
  -H "Content-Type: application/json"

# Step 5: Verify clear request rejected
# Expected: 403 Forbidden - Hardware E-stop active
```

**Expected Results**:
- PLC overrides Task API commands
- Hardware E-stop cannot be cleared by software
- Authority levels enforced correctly

**Failure Actions**:
- Authority violation detected → Fix authority matrix logic
- Hardware override allowed → Fix PLC integration
- Incorrect error response → Update API error handling

### 3. Safety Zone Sync Verification

**Objective**: Verify safety zone configurations sync correctly between systems.

**Procedure**:

#### 3.1 Zone Configuration Sync

```bash
# Step 1: Deploy new safety configuration
kubectl apply -f organized/safety/config/safety-zones.yml

# Step 2: Verify edge agent receives update
curl http://edge-agent/api/v1/safety/zones

# Step 3: Check cache timestamp
curl http://edge-agent/api/v1/safety/cache/status

# Step 4: Verify PLC configuration matches
# Compare edge agent zones with PLC configuration
python scripts/compare-plc-zones.py \
  --edge-zones edge-zones.json \
  --plc-zones plc-zones.json
```

**Expected Results**:
- Edge agent receives configuration within 60 seconds
- Cache updated with new timestamp
- PLC and edge agent zones match

**Failure Actions**:
- Sync delay > 60s → Investigate network/messaging issues
- Cache not updated → Debug edge agent sync logic
- Zone mismatch → Reconcile configurations, redeploy

#### 3.2 Zone Boundary Validation

```bash
# Step 1: Load zone boundary definitions
cat organized/safety/config/zone-boundaries.json

# Step 2: Validate boundary coordinates
python scripts/validate-zone-boundaries.py \
  --zones zone-boundaries.json \
  --tolerance 0.01

# Step 3: Check for zone overlaps
python scripts/check-zone-overlaps.py \
  --zones zone-boundaries.json
```

**Expected Results**:
- All zone boundaries valid
- No overlapping zones (unless intentional)
- Coordinate precision within tolerance

**Failure Actions**:
- Invalid boundaries → Correct zone definitions
- Overlaps detected → Resolve boundary conflicts
- Precision issues → Adjust coordinate values

### 4. Production Deployment Validation

**Objective**: Final validation before production deployment.

**Prerequisites**:
- [ ] All pre-deployment tests passed
- [ ] Safety engineer approval obtained
- [ ] Production deployment window scheduled
- [ ] Rollback plan documented

**Procedure**:

#### 4.1 Canary Deployment

```bash
# Step 1: Deploy to canary edge agent (1% traffic)
kubectl apply -f deployments/edge-agent-canary.yml

# Step 2: Monitor canary metrics (30 minutes)
kubectl logs -f deployment/edge-agent-canary

# Step 3: Verify E-stop latency on canary
curl http://canary-edge/api/v1/metrics/estop-latency

# Step 4: Check error rate
curl http://canary-edge/api/v1/metrics/error-rate
```

**Success Criteria**:
- E-stop latency < 5 seconds (p99)
- Error rate < 0.1%
- No safety incidents during canary period

**Rollback Triggers**:
- E-stop latency > 5 seconds
- Error rate > 0.5%
- Any safety incident
- Hardware E-stop failure

#### 4.2 Full Production Rollout

```bash
# Step 1: Gradual rollout (10%, 25%, 50%, 100%)
for PERCENT in 10 25 50 100; do
  kubectl patch deployment edge-agent \
    -p "{\"spec\":{\"replicas\":$((TOTAL_REPLICAS * PERCENT / 100))}}"

  # Wait and monitor
  sleep 300

  # Check metrics
  curl http://edge-agent/api/v1/metrics | jq '.estop_latency_p99'
done

# Step 2: Verify all agents synced
kubectl get pods -l app=edge-agent -o wide

# Step 3: Run production smoke tests
pytest organized/safety/tests/smoke/ -v --env=production
```

**Expected Results**:
- All edge agents deployed successfully
- E-stop latency remains < 5 seconds across fleet
- No degradation in safety metrics

**Failure Actions**:
- Latency spike → Pause rollout, investigate
- Agent failure → Rollback to previous version
- Safety metric degradation → Full rollback

### 5. Post-Deployment Validation

**Objective**: Verify production system after deployment.

**Procedure**:

#### 5.1 End-to-End E-stop Test

```bash
# Step 1: Trigger test E-stop (coordinated with production)
curl -X POST http://production-edge/api/v1/test/estop \
  -H "X-Test-Mode: true" \
  -H "Authorization: Bearer $SAFETY_TEST_TOKEN"

# Step 2: Verify propagation to Task API
curl http://task-api/api/v1/audit/latest?event_type=estop

# Step 3: Measure end-to-end latency
python scripts/measure-estop-latency.py \
  --start-time "$ESTOP_TRIGGER_TIME" \
  --audit-id "$AUDIT_LOG_ID"

# Step 4: Clear test E-stop
curl -X DELETE http://production-edge/api/v1/test/estop \
  -H "X-Test-Mode: true"
```

**Expected Results**:
- E-stop propagates to Task API
- End-to-end latency < 5 seconds
- Audit log entry created

**Failure Actions**:
- Propagation failure → Investigate connectivity
- Latency exceeded → Performance investigation
- Missing audit entry → Check Task API logging

#### 5.2 Continuous Monitoring

```bash
# Step 1: Enable safety dashboards
# Open Grafana dashboard: safety-metrics-overview

# Step 2: Configure alerts
kubectl apply -f monitoring/safety-alerts.yml

# Step 3: Verify alert routing
curl http://alertmanager/api/v1/alerts
```

**Monitoring Metrics**:
- E-stop latency (p50, p95, p99)
- Edge agent online status
- Cache hit rate
- Audit log write latency
- Safety zone sync lag

**Alert Thresholds**:
- E-stop latency p99 > 4 seconds (warning)
- E-stop latency p99 > 5 seconds (critical)
- Edge agent offline > 60 seconds (critical)
- Cache miss rate > 5% (warning)
- Audit log lag > 10 seconds (warning)

## Emergency Procedures

### E-stop System Failure

**Symptoms**:
- E-stop signal not propagating
- Latency exceeding 5 seconds
- Hardware E-stop not responding

**Immediate Actions**:

1. **Activate Manual Shutdown Protocol**
   ```bash
   # Immediately halt all robotic systems
   ssh production-plc
   ./manual-shutdown-all.sh
   ```

2. **Isolate Affected Systems**
   ```bash
   # Disable affected edge agents
   kubectl scale deployment edge-agent --replicas=0
   ```

3. **Notify Safety Team**
   - Page safety engineer (PagerDuty: safety-critical)
   - Escalate to production manager
   - Log incident: `incidents/safety-incident-$(date +%Y%m%d-%H%M%S).md`

4. **Root Cause Investigation**
   - Collect logs: `kubectl logs deployment/edge-agent > incident-logs.txt`
   - Review audit trail
   - Analyze metrics dashboards
   - Document timeline

5. **Recovery Procedure**
   - Fix identified issues
   - Re-run full validation suite
   - Obtain safety engineer approval
   - Gradual re-deployment with enhanced monitoring

### Cache Expiration During Network Outage

**Symptoms**:
- Edge agent offline > 5 minutes (cache TTL)
- Cached policies expired
- Safety operations uncertain

**Immediate Actions**:

1. **Maintain Safe State**
   ```bash
   # Edge agent should enter fail-safe mode
   # Verify fail-safe active
   curl http://edge-agent/api/v1/status | jq '.fail_safe_mode'
   ```

2. **Extend Cache TTL (Emergency Only)**
   ```bash
   # Temporarily extend cache TTL
   curl -X PATCH http://edge-agent/api/v1/config \
     -d '{"cache_ttl_seconds": 3600}' \
     -H "Authorization: Bearer $EMERGENCY_TOKEN"
   ```

3. **Restore Connectivity**
   - Investigate network issues
   - Establish backup connectivity if available
   - Sync latest policies once restored

4. **Post-Incident Review**
   - Document outage duration
   - Review fail-safe behavior
   - Assess cache TTL adequacy
   - Update procedures if needed

## Validation Checklist

Use this checklist for each edge agent deployment:

### Pre-Deployment
- [ ] Code review completed
- [ ] Safety configuration reviewed
- [ ] Schema validation passed
- [ ] E-stop tests passed (100%)
- [ ] Offline behavior validated
- [ ] PLC authority matrix verified
- [ ] Safety zone sync confirmed
- [ ] Coverage ≥ 90%

### Deployment
- [ ] Canary deployment successful
- [ ] Metrics within thresholds
- [ ] No safety incidents during canary
- [ ] Gradual rollout completed
- [ ] All agents online and synced

### Post-Deployment
- [ ] End-to-end E-stop test passed
- [ ] Latency < 5 seconds verified
- [ ] Audit logging confirmed
- [ ] Monitoring dashboards configured
- [ ] Alerts routed correctly
- [ ] Documentation updated

### Approval
- [ ] Safety engineer sign-off
- [ ] Production manager approval
- [ ] Deployment documented
- [ ] Runbook updated

## References

- **ADR-004**: Safety Governance Framework
- **RUNBOOK.md**: Operational procedures and incident response
- **organized/safety/tests/**: Automated test suite
- **scripts/safety-zone-diff.py**: Configuration diff analyzer
- **.github/workflows/safety-check.yml**: CI/CD safety pipeline

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-01 | Safety Engineering | Initial release |

## Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Safety Engineer | | | |
| Edge Engineering Lead | | | |
| Production Manager | | | |

---

**Document Classification**: Safety Critical
**Review Period**: Quarterly
**Next Review Date**: 2026-02-01

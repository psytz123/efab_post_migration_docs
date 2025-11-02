# Runbook — Operations & SLOs

## SLOs (initial)
- Gateway read paths p99 < 200ms; Task intent latency WAN-OK < 150ms.
- Edge command roundtrip < 250ms on LAN.
- **E-stop propagation latency p99 < 5 seconds** (per ADR-004)
- Edge agent offline tolerance: 5 minutes (cache TTL)
- Error budget: 99.5% monthly availability (pilot).

## Safety SLOs (ADR-004 Compliance)
- **E-stop Latency**: PLC → Edge → Task API < 5 seconds (p99)
- **Edge Uptime**: 99.9% monthly (offline tolerance: 5 min with cache)
- **Audit Log Lag**: Safety events logged within 10 seconds
- **Cache Hit Rate**: >95% during normal operations
- **Hardware E-stop Response**: Immediate (hardware authority level 1)

## Rollout
1. Deploy Gateway + Task API + Bus to `staging`.
2. Validate end-to-end simulator loop; run chaos (bus down, WAN drop).
3. **Run safety validation suite** (see Edge Safety Validation SOP).
4. Promote to `prod` and light up one pilot cell.
5. **Canary deployment** for edge agents (1% → 10% → 50% → 100%).

## Rollback
- Helm chart versioned; `helm rollback` + feature flags.
- Database migrations reversible (Flyway).
- **Safety rollback**: Immediate if E-stop latency > 5s or safety incidents.

## DR/Backups
- Nightly Postgres backups; Kafka snapshots; S3 replication.
- **Safety audit logs**: 90-day retention, backed up daily.
- **Edge agent policies**: Cached locally (TTL: 300s), backed up to S3.

## On-call

### Escalation Contacts
- **Primary**: On-call engineer (PagerDuty rotation)
- **Safety Critical**: Safety engineer (24/7 pager)
- **Executive**: Production manager (safety incidents only)

### Runbooks by Incident Type

#### 1. Bus Outage
**Symptoms**: Kafka broker down, message delivery failures

**Actions**:
```bash
# Check Kafka cluster health
kubectl get pods -n kafka
kubectl logs -n kafka kafka-broker-0

# Verify consumer lag
kafka-consumer-groups --bootstrap-server kafka:9092 --describe --group task-api

# Restart broker if needed
kubectl rollout restart statefulset/kafka -n kafka
```

**Escalation**: If outage > 15 minutes, page infrastructure team.

#### 2. Edge Offline
**Symptoms**: Edge agent not reporting, cache may expire

**Actions**:
```bash
# Check edge agent status
kubectl get pods -l app=edge-agent -o wide

# Review edge agent logs
kubectl logs deployment/edge-agent --tail=100

# Check network connectivity
curl http://edge-agent/api/v1/health

# Verify cache status
curl http://edge-agent/api/v1/safety/cache/status | jq '.ttl_remaining'
```

**Safety Considerations**:
- **If offline < 5 minutes**: Edge operates on cached policies (normal)
- **If offline > 5 minutes**: Cache may expire, edge enters fail-safe mode
- **Action required**: Restore connectivity or extend cache TTL (emergency only)

**Escalation**: If offline > 5 minutes, page safety engineer immediately.

#### 3. Safety Trip / E-stop Incident
**Symptoms**: E-stop triggered, safety system activation

**IMMEDIATE ACTIONS** (within 60 seconds):

1. **Verify E-stop Status**
   ```bash
   # Check PLC status
   curl http://plc-gateway/api/v1/status | jq '.estop_active'

   # Check edge agent E-stop state
   curl http://edge-agent/api/v1/safety/estop/status

   # Verify audit log entry
   curl http://task-api/api/v1/audit/latest?event_type=estop
   ```

2. **Assess Safety State**
   - **Hardware E-stop**: Cannot be cleared remotely (physical intervention required)
   - **Software E-stop**: Can be cleared after investigation
   - **Authority level**: Check which system triggered (PLC authority matrix)

3. **Notify Safety Team**
   ```bash
   # Page safety engineer
   # PagerDuty: safety-critical incident

   # Log incident
   ./scripts/create-safety-incident.sh \
     --type estop \
     --severity critical \
     --timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
   ```

4. **Collect Evidence**
   ```bash
   # Gather logs from all systems
   kubectl logs deployment/edge-agent > incident-edge-logs.txt
   curl http://plc-gateway/api/v1/logs > incident-plc-logs.txt
   curl http://task-api/api/v1/audit?start=$(date -d '30 minutes ago' -u +%Y-%m-%dT%H:%M:%SZ) > incident-audit.json

   # Capture metrics snapshot
   curl http://prometheus/api/v1/query?query=estop_latency_seconds > incident-metrics.json
   ```

**INVESTIGATION CHECKLIST** (per ADR-004):

Safety Audit Checklist:
- [ ] E-stop trigger source identified (PLC/Edge/Task API)
- [ ] Propagation latency measured (must be < 5 seconds)
- [ ] Hardware override status verified
- [ ] Edge agent cache state at time of incident
- [ ] Network connectivity status confirmed
- [ ] Audit log completeness verified (90-day retention)
- [ ] Authority matrix compliance checked
- [ ] Offline edge behavior validated (if applicable)
- [ ] Safety zone configuration reviewed
- [ ] Root cause documented

**RECOVERY PROCEDURE**:

1. **Root Cause Analysis**
   - Review collected logs and metrics
   - Identify trigger event
   - Verify latency requirement met (<5s)
   - Document timeline

2. **Clear E-stop** (Safety Engineer Approval Required)
   ```bash
   # Software E-stop clear (requires authorization)
   curl -X POST http://edge-agent/api/v1/safety/estop/clear \
     -H "Authorization: Bearer $SAFETY_ENGINEER_TOKEN" \
     -H "X-Incident-ID: $INCIDENT_ID" \
     -d '{"cleared_by": "safety_engineer", "reason": "root_cause_resolved"}'

   # Verify clear propagated
   curl http://task-api/api/v1/audit/latest?event_type=estop_cleared
   ```

   **Hardware E-stop clear**: Requires physical button reset on PLC.

3. **System Validation**
   ```bash
   # Re-run safety validation suite
   pytest organized/safety/tests/test_estop_propagation.py -v

   # Verify latency back to normal
   curl http://edge-agent/api/v1/metrics | jq '.estop_latency_p99'

   # Check all systems online
   kubectl get pods --all-namespaces | grep -E "(edge|task|plc)"
   ```

4. **Resume Operations**
   - Safety engineer sign-off required
   - Production manager notification
   - Document incident in safety log
   - Update procedures if needed

**ESCALATION THRESHOLDS**:
- **E-stop latency > 5 seconds**: Immediate safety engineer escalation
- **Hardware E-stop failure**: Immediate executive escalation + facility lockdown
- **Repeated E-stops** (>3 in 1 hour): Safety team review required
- **Cache expiration during offline**: Emergency cache extension + investigation

**REFERENCE DOCUMENTS**:
- Edge Safety Validation SOP: `docs/procedures/edge-safety-validation-sop.md`
- ADR-004 Safety Governance: `docs/adrs/ADR-004-safety-governance.md`
- PLC Authority Matrix: See Edge Safety Validation SOP Section 2

#### 4. Database Failover
**Symptoms**: Primary database down, replica promotion needed

**Actions**:
```bash
# Check database cluster status
kubectl get pods -n postgres

# Verify replication lag
psql -h postgres-replica -c "SELECT pg_last_wal_receive_lsn();"

# Trigger failover (if needed)
kubectl patch postgresql postgres-cluster \
  -p '{"spec":{"enableMasterOnline":false}}'

# Verify new primary
kubectl get postgresql postgres-cluster -o jsonpath='{.status.primary}'
```

**Escalation**: If failover takes > 5 minutes, page DBA and infrastructure team.

## Safety Monitoring Dashboards

### Grafana Dashboards
- **safety-metrics-overview**: Real-time safety system health
- **estop-latency-tracking**: E-stop propagation latency trends
- **edge-cache-performance**: Cache hit rates and TTL monitoring
- **audit-log-compliance**: Audit trail completeness and lag

### Key Metrics to Monitor
```
# E-stop latency percentiles
estop_latency_seconds{quantile="0.99"} < 5

# Edge agent online status
edge_agent_online_status == 1

# Cache hit rate
edge_cache_hit_rate > 0.95

# Audit log write latency
audit_log_write_latency_seconds < 10

# Safety zone sync lag
safety_zone_sync_lag_seconds < 60
```

### Alert Thresholds

**Critical Alerts** (Page immediately):
- E-stop latency p99 > 5 seconds
- Edge agent offline > 60 seconds
- Hardware E-stop failure
- Audit log write failures

**Warning Alerts** (Ticket creation):
- E-stop latency p99 > 4 seconds
- Cache hit rate < 95%
- Audit log lag > 10 seconds
- Safety zone sync lag > 60 seconds

## E-stop Escalation Procedures

### Escalation Matrix

| Severity | Condition | Response Time | Escalation Path |
|----------|-----------|---------------|-----------------|
| P0 - Critical | Hardware E-stop failure | Immediate | Safety Engineer → Production Manager → Executive |
| P1 - High | E-stop latency > 5s | 5 minutes | On-call → Safety Engineer |
| P2 - Medium | Edge offline > 5 min | 15 minutes | On-call → Edge Team |
| P3 - Low | Cache hit rate < 95% | 1 hour | Ticket → Edge Team |

### Incident Communication

**Safety Incident Report Template**:
```markdown
# Safety Incident Report

**Incident ID**: SI-YYYYMMDD-HHMMSS
**Severity**: [P0/P1/P2/P3]
**Date/Time**: [UTC timestamp]
**Reported By**: [Name/Role]

## Summary
[Brief description of incident]

## Timeline
- [HH:MM] - Initial trigger
- [HH:MM] - Detection
- [HH:MM] - Response initiated
- [HH:MM] - Resolved

## Impact
- Systems affected: [List]
- Safety implications: [Description]
- Operations impact: [Description]

## Root Cause
[Detailed root cause analysis]

## Resolution
[Steps taken to resolve]

## Prevention
[Actions to prevent recurrence]

## Checklist (ADR-004)
- [ ] E-stop propagation latency verified
- [ ] Authority matrix compliance checked
- [ ] Audit log completeness confirmed
- [ ] Edge cache behavior validated
- [ ] Safety engineer review completed
- [ ] Procedures updated (if needed)

## Approvals
- Safety Engineer: [Signature/Date]
- Production Manager: [Signature/Date]
```

## Maintenance Windows

### Edge Agent Updates
1. **Pre-maintenance**: Run safety validation suite
2. **Maintenance window**: 2-hour window, off-peak hours
3. **Deployment**: Canary → gradual rollout
4. **Post-maintenance**: E-stop propagation test + SOP validation

### Safety Configuration Changes
1. **Change review**: Safety engineer approval required
2. **Diff analysis**: Run `safety-zone-diff.py --fail-on-diff`
3. **Testing**: Full validation suite + offline tests
4. **Deployment**: Synchronized PLC + Edge update
5. **Validation**: End-to-end E-stop test

## Compliance and Audit

### Safety Audit Requirements (ADR-004)
- **Frequency**: Quarterly
- **Scope**: E-stop system, edge caching, PLC integration
- **Documentation**: Incident logs, test results, configuration changes
- **Retention**: 90 days minimum (audit logs), 2 years (incident reports)

### Pre-Audit Checklist
- [ ] All safety incidents documented
- [ ] E-stop latency metrics reviewed (past 90 days)
- [ ] Edge cache performance validated
- [ ] Audit log completeness verified
- [ ] Configuration change log updated
- [ ] Test results archived
- [ ] SOP compliance verified
- [ ] Training records current

## Training Requirements

### On-call Engineer Training
- [ ] Safety incident response procedures
- [ ] E-stop escalation matrix
- [ ] Edge agent troubleshooting
- [ ] Audit checklist usage
- [ ] PLC authority matrix understanding

### Safety Engineer Certification
- [ ] ADR-004 governance framework
- [ ] Edge Safety Validation SOP
- [ ] PLC integration architecture
- [ ] Incident investigation procedures
- [ ] Root cause analysis methodology

## References
- **ADR-004**: Safety Governance Framework
- **Edge Safety Validation SOP**: `docs/procedures/edge-safety-validation-sop.md`
- **Safety Test Suite**: `organized/safety/tests/test_estop_propagation.py`
- **CI Pipeline**: `.github/workflows/safety-check.yml`
- **Safety Zone Diff**: `scripts/safety-zone-diff.py`

---

**Document Owner**: Operations Team
**Last Updated**: 2025-11-01
**Review Cycle**: Monthly
**Next Review**: 2025-12-01

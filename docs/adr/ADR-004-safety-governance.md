# ADR-004: Safety Governance Architecture
**Status:** Proposed • **Date:** 2025-11-01

## Context
The eFab robot-ready platform introduces autonomous systems controlled through Task API, Edge Agent, and factory PLCs. Documentation updates detail Task API safety validation, Edge safety validation plan (`EdgeSafetyFollowUps`), and service interfaces handling safety events. We must formalize how safety authority is distributed across cloud and edge to satisfy OSHA/ISO requirements and ensure safe operation during offline conditions.

## Decision
Adopt a **Hybrid Safety Governance** model:
- PLCs retain final braking authority and enforce hard E-stop circuits.
- Task API performs safety zone validation and role-based checks before issuing intents.
- Edge Agent enforces dynamic speed/keepout parameters and relays PLC safety events to the cloud.
- Safety policies managed through OPA/OPAL with signed bundles; Edge maintains cached policy for offline enforcement.

## Rationale
- Meets regulatory expectations keeping hardware interlocks in PLC domain.
- Provides layered protection: policy validation (Task API), runtime enforcement (Edge), physical cut-off (PLC).
- Supports offline resilience—Edge can enforce cached policies when WAN unavailable.
- Aligns with documentation in `docs/services/task-api/README.md` and `docs/services/edge-agent/README.md`.

## Alternatives Considered
1. **Software-only Enforcement** (Task API & Edge, no PLC control) – Rejected due to regulatory risk and latency concerns.
2. **PLC-Only Safety** (Cloud blind to safety events) – Rejected because cloud would lack telemetry/audit needed for compliance and analytics.

## Consequences
- Requires synchronized safety zone definitions between Task API and Edge; automated tests must verify parity.
- E-stop propagation testing becomes mandatory before each deployment (see `edge-safety-validation-plan.md`).
- Policies must be versioned and signed; Edge OTA updates must include policy validation step.

## Follow-up Actions
- Implement automated checks ensuring safety zone updates apply to both Task API and Edge configs.
- Extend Runbook (`RUNBOOK.md#safety-incident`) with auditing steps referencing this ADR.
- Add integration test verifying PLC E-stop events reach Task API audit trail.

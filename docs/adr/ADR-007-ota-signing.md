# ADR-007: Edge OTA & Signing Policy
**Status:** Proposed • **Date:** 2025-11-01

## Context
Edge components (Edge Agent, OPC UA adapter, ROS2 bridge, MQTT Sparkplug) receive OTA updates. Supply-chain gap analysis (SC-06) identified unsigned OTA bundles and missing verification. Safety ADR (ADR-004) mandates PLC authority but requires software layers to prevent tampered code. We must formalize OTA signing, promotion, and rollback process.

## Decision
Implement a **Signed OTA Pipeline** with staged rollouts:
- Build pipeline generates container images and OTA bundles signed via Sigstore Cosign using keyless workflow.
- OTA manifest includes image digests, policy version, and rollback reference. Manifest signed and stored in secure registry.
- Edge Agent verifies signatures before applying updates; offline bundles pre-verified with cached trust roots.
- Rollout sequence: staging → canary node (standby cell) → production cell after validation tests.
- Rollback uses previous signed manifest stored locally; automatic trigger if health checks fail.

## Rationale
- Aligns with supply-chain security practices (SLSA, signed artifacts) and prevents tampered deployments.
- Supports controlled rollout with explicit verification steps, reducing downtime risk.
- Works with existing tooling (GitHub Actions, Vault, Edge Agent OTA component) with minimal new infra.

## Alternatives Considered
1. **Unsigned OTA with checksum only** – Inadequate security; fails compliance.
2. **Manual USB-based updates** – Operationally heavy, hinders rapid iteration.

## Consequences
- Requires infrastructure to manage Sigstore verification at edge (cached trust bundles, offline support).
- OTA pipeline must block promotion when signatures or attestations missing.
- Additional testing stage needed (edge simulator run) before promoting to production cell.

## Follow-up Actions
- Implement verification hook in Edge Agent OTA module referencing this ADR.
- Update `RUNBOOK.md#ota-failure` with signed artifact troubleshooting.
- Extend CI/CD pipeline to produce signed manifests and attach provenance.

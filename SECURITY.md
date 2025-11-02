# Security, Identity & Safety Governance

## Identity
- **OIDC** for all UIs & APIs (Auth0/Entra/Keycloak).
- **Gateway‑enforced** JWT verification; downstream mTLS (SPIFFE/SPIRE).

## Authorization
- Role‑based (Planner, Scheduler, Operator, Integrator, Admin).
- **OPA/OPAL** policies for Task API (emit/approve tasks; safety overrides).

## Secrets & Supply Chain
- Secrets in **Vault/KMS**; no secrets in code/images.
- SBOM (Syft) + image scanning (Grype/Trivy), SLSA provenance.
- Signed containers; admission policy rejects unsigned images.

## Safety
- PLC retains final authority; e‑stops break power, not just software paths.
- Task API validates **SafetyZone** and max speeds; Edge enforces at runtime.
- Full audit trail for every task state change.

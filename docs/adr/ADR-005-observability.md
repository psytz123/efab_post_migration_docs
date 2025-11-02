# ADR-005: Observability Integration Strategy
**Status:** Proposed • **Date:** 2025-11-01

## Context
Observability documentation defines metrics, logs, traces, dashboards, and alerts across eFab services. We must cement the architecture for aggregating data from Task API, Edge, and manufacturing services while linking alerts to Runbook procedures. Decisions impact Grafana/Prometheus setup, alert routing, and compliance visibility.

## Decision
Implement a **Unified Observability Stack** with the following structure:
- Prometheus (core + federated) scrapes services and edge exporters; Alertmanager routes incidents.
- Grafana dashboards use folder per domain (Production, Safety, FinOps) with templated panels from Observability Integration Plan.
- Loki collects structured logs; Tempo captures traces via OpenTelemetry collectors.
- Alert routing integrated with PagerDuty; each alert includes Runbook link and ownership metadata.

## Rationale
- Aligns with existing documentation and SRE expertise; leverages open-source stack already in CI/CD.
- Simplifies edge/cloud monitoring by federating metrics while keeping local scraping for low latency.
- Ensures compliance by maintaining auditable alert metadata and correlation with Runbook sections.

## Alternatives Considered
1. **Vendor SaaS Observability** – Rejected due to data residency and cost concerns.
2. **Per-service bespoke monitoring** – Rejected; inconsistent dashboards and higher maintenance burden.

## Consequences
- Requires standardized instrumentation (OTel) and metrics naming conventions across services.
- Need to manage Grafana provisioning and secret rotation (API keys, dashboards as code).
- Alert fatigue risk if thresholds poorly calibrated – must follow Observability plan.

## Follow-up Actions
- Implement dashboard-as-code repository referencing this ADR.
- Configure Alertmanager routes matching Runbook owners; add automated test for Runbook link validity.
- Extend CI/CD to validate metrics schema compatibility before deploy.

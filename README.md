# eFab — Robot‑Ready ERP (Post‑Migration) Documentation
**Version:** v1.0 • **Date:** 2025-11-01

This documentation set describes the **combined software program post‑migration**: the existing `beverly_knits_erp_v2` (Flask monolith) operating alongside the **eFab robot‑ready slice** (Task API, Event Bus, Edge adapters, Manufacturing Graph, and modern control plane).

> Goal: Pilot a robot/AMR‑integrated production cell, deliver measurable KPIs (OEE ↑, changeover ↓, scrap ↓), then scale across cells with minimal disruption to current ERP operations.

## Contents
- `ARCHITECTURE.md` — High‑level & detailed architecture with Mermaid diagrams
- `MIGRATION.md` — Fit‑vs‑gap, phased plan, cross‑walk to current ERP
- `TASK_API.md` — REST & gRPC contracts, examples, policies
- `EDGE.md` — Edge Agent & adapters, configs, cell bring‑up
- `DATA_MODEL.md` — Manufacturing Graph schema, topics, payloads
- `SECURITY.md` — Identity, RBAC, safety governance
- `OBSERVABILITY.md` — Metrics, logs, traces, dashboards
- `CI_CD.md` — Build, scan, release, GitOps
- `RUNBOOK.md` — Operations, SLOs, rollout/rollback, DR
- `GLOSSARY.md` — Common terms and abbreviations
- `docs/services/*` — Service‑level READMEs
- `docs/adr/*` — Architecture Decision Records

## Directory map (docs)
```text
efab_post_migration_docs/
├─ README.md
├─ ARCHITECTURE.md
├─ MIGRATION.md
├─ TASK_API.md
├─ EDGE.md
├─ DATA_MODEL.md
├─ SECURITY.md
├─ OBSERVABILITY.md
├─ CI_CD.md
├─ RUNBOOK.md
├─ GLOSSARY.md
└─ docs/
   ├─ services/
   │  ├─ orders/README.md
   │  ├─ inventory/README.md
   │  ├─ mfg-graph/README.md
   │  ├─ scheduler/README.md
   │  ├─ task-api/README.md
   │  ├─ event-router/README.md
   │  ├─ quality/README.md
   │  ├─ maintenance/README.md
   │  ├─ finops/README.md
   │  ├─ edge-agent/README.md
   │  ├─ opcua-adapter/README.md
   │  ├─ mqtt-sparkplug/README.md
   │  └─ ros2-bridge/README.md
   └─ adr/
      ├─ ADR-001-monorepo.md
      ├─ ADR-002-event-bus.md
      └─ ADR-003-task-api.md
```

## Quick start (pilot flow)
1. Stand up `Task API` and `Event Bus` next to `beverly_knits_erp_v2`.
2. Wire `Edge Agent` in **sim mode**; run end‑to‑end intent→execution loop.
3. Connect OPC UA tags and ROS 2 actions for **one pilot cell**; introduce safety zones.
4. Measure KPIs, then replicate to additional cells.

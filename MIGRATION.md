# Migration Plan — From `beverly_knits_erp_v2` to eFab Robot‑Ready

## Fit vs Gap (current → target)
- **ERP core:** Keep the Flask monolith for core CRUD/reporting; expose via Gateway.
- **Event backbone:** Introduce Kafka/Redpanda for order→task→telemetry streams.
- **Task API:** New service to express robot‑safe verbs tied to orders/lots/cells.
- **Edge adapters:** New OPC UA, Sparkplug B, and ROS 2 bridges for a pilot cell.
- **Identity:** Add OIDC (Auth0/Entra/Keycloak) in front of Gateway; legacy ERP behind it.
- **Observability:** Extend current Prom/Grafana with OTel traces/logs.

## Phased Execution
**Phase 0 — Bootstrap (2 weeks)**  
- Monorepo skeleton, CI pipelines, OTel wiring, ADR‑001.

**Phase 1 — Core & Graph (4–6 weeks)**  
- Stand up `orders`, `inventory`, `mfg-graph` (Postgres + Flyway).  
- Planner UI MVP; ERP remains system of record during cut‑over.

**Phase 2 — Scheduler & Task API (4–6 weeks)**  
- Implement Task API (REST+gRPC) + topics; simulate cell execution E2E.

**Phase 3 — Edge Integration (4–8 weeks)**  
- Edge Agent, OPC UA adapter, Sparkplug, ROS 2 bridge; wire **PackLine1**.

**Phase 4 — Quality & Traceability (4–6 weeks)**  
- Vision kit → S3; inspection events; NCR workflows.

**Phase 5 — Humanoid Pilot (8–12 weeks)**  
- Safety zones, Open‑RMF; pilot with KPI guardrails.

## Cross‑walk to current ERP
- Gateway routes `/legacy/*` → Flask and `/api/*` → new services.
- ERP schedule events trigger `TaskIntent` emission (feature flag).
- Task actuals update ERP tables via integration layer.
- Celery/Redis stays for business jobs; Kafka handles robot/event streams.

## KPIs per Phase
- OEE +≥5 pts; changeover −≥25%; FPY +≥3 pts. Zero safety incidents; audit complete.

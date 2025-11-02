# ADR-003: Task API Design
**Status:** Accepted • **Date:** 2025-11-01

- REST (OpenAPI) for planners/integrations; gRPC for Edge path.
- Verbs: walk_to, grasp, place, actuate, inspect, handoff.
- SafetyZone embedded in each intent; server‑side validation and audit.

# ADR-006: Manufacturing Graph Modelling Approach
**Status:** Proposed • **Date:** 2025-11-01

## Context
The Manufacturing Graph service stores production topology and routing data. Current documentation describes a Postgres schema with JSONB columns plus Redis caching. We evaluated alternative graph databases to support complex routing queries and scalability. We must formalize the approach before implementation extends beyond pilot.

## Decision
Continue with **Postgres JSONB + Indexing** for the manufacturing graph, augmented by Redis caching for hot queries.
- Use normalized tables for primary entities (cells, operations, routings) with JSONB for capability metadata.
- Create GIN indexes on JSONB attributes frequently queried (capabilities, safety zones).
- Employ materialized views for common joins supporting Scheduler/Task API.
- Redis caches simulation results and capability lookups with defined TTL.

## Rationale
- Aligns with existing tooling (Postgres expertise, Flyway migrations) and simplifies transactional consistency.
- Graph workloads remain manageable (single-site pilot scaling to multi-site) with optimized indexes and caching.
- Avoids additional operational overhead of running separate graph database while still meeting latency targets.

## Alternatives Considered
1. **Neo4j / JanusGraph** – Provides native graph queries but increases infrastructure complexity and licensing considerations.
2. **Document Store (MongoDB)** – Easier schema evolution but weaker transactional guarantees and joins.

## Consequences
- Need disciplined schema management and indexing strategy to keep query performance acceptable.
- Complex graph analytics may require offline processing (e.g., using DuckDB snapshots).
- Future multi-site scaling might revisit graph database option; clearly document triggers.

## Follow-up Actions
- Define performance SLOs (e.g., routing lookup ≤50ms) and monitor via Observability stack.
- Document migration path should a dedicated graph database become necessary.
- Update data governance documents with ownership and change control policies.

# ADR-008: FinOps Cost Allocation Methodology
**Status:** Proposed • **Date:** 2025-11-01

## Context
FinOps service aggregates cost data across orders, inventory, maintenance, quality, and energy usage. Documentation now details data pipelines and KPIs. We need an authoritative decision on allocation methodology to ensure consistent reporting and integration with finance systems.

## Decision
Adopt a **Hybrid Cost Allocation** approach:
- **Direct Costs:** Material usage, labour, and maintenance charged directly to order/lot via events (`orders.actuals`, `maintenance.workorder.completed`).
- **Shared Costs:** Energy and overhead allocated using cell runtime and throughput metrics from Task API/Edge telemetry.
- **Capital/Automation ROI:** Tracked per project, amortized across production volume with monthly updates.
- FinOps service maintains configuration for allocation weights (YAML + database table) versioned via Git and auditable.

## Rationale
- Balances accuracy with manageability; direct costs remain precise while shared costs use measurable drivers.
- Supports KPI reporting (unit cost variance, ROI) described in FinOps documentation.
- Aligns with finance requirements for auditable sources and ability to adjust weights.

## Alternatives Considered
1. **Flat percentage allocation** – Simpler but ignores actual usage data, reducing accuracy.
2. **Full activity-based costing** – Highly accurate but complex; up-front effort too high for pilot stage.

## Consequences
- FinOps service must provide UI/API for adjusting allocation weights with effective dates.
- Requires synchronization with ERP finance ledger; reconciliation jobs need to compare totals.
- Changes in allocation policy must trigger FinOps alerts and require approval workflow.

## Follow-up Actions
- Implement allocation weight management module with audit trail.
- Schedule monthly reconciliation and variance review meetings with finance stakeholders.
- Document governance process and store policy versions in `.finops/policies/` repo.

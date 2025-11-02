# FinOps Allocation Toolkit

## Components
- `allocation_policy.yaml`: Template for configuring direct/shared cost weights and capital project amortization.
- `allocation.py`: Allocation engine for applying policy weights to cost records.
- `reconciliation_job.py`: CLI entrypoint to run nightly reconciliation and emit JSON payloads.

## Reconciliation Job Outline
1. Nightly job aggregates order/lot costs (orders.actuals, maintenance.workorder.completed, inventory usage).
2. Apply allocation weights from `allocation_policy.yaml` and compute unit cost variance vs targets.
3. Compare totals with ERP ledger (ERP_FINANCE). If variance > thresholds, create alert (`finops.cost.variance`).
4. Persist reconciliation report to S3 (`s3://efab-finops-reports`) and notify finance via Slack/PagerDuty.

### Running the Prototype
```bash
python reconciliation_job.py \
  --policy allocation_policy.yaml \
  --actuals sample_actuals.json \
  --output reconciliation_report.json
```
`sample_actuals.json` in this directory provides a representative payload for dry runs.
The JSON `actuals` payload must include:
```json
{
  "records": [
    {
      "identifier": "cell-a",
      "units_produced": 10,
      "direct_costs": {"material": 100, "labor": 50},
      "drivers": {"runtime_minutes": 60},
      "target_unit_cost": 18.5
    }
  ],
  "shared_metrics": {"edge_energy_kwh": 120, "production_overhead_cost": 900},
  "capital_projects": [{"amortized_monthly_cost": 1200}]
}
```

## Policy Governance
- Store policy files in `.finops/policies/` with change approvals.
- Maintain audit log and metadata (owner, effective dates).
- Update policy when ROI or variance deviates from ADR-008 triggers.

## Next Steps
- Build API/UI for finance to manage allocation weights with audit log.
- Automate reconciliation job orchestration using Airflow or Prefect.
- Extend observability dashboards with FinOps panels referencing variance metrics.

# Observability Dashboard-as-Code Seed

## Contents
- `dashboard_main.jsonnet`: Grafonnet dashboard template aligning with ADR-005 (parameterised by site/cell/environment).
- `alerts_main.jsonnet`: Alertmanager rule bundle mirroring dashboard KPIs.

## Usage
1. Install Grafonnet (`jsonnet-bundler` recommended) and render the dashboard:
   ```bash
   jb install grafana/grafonnet-lib
   jsonnet \
     --ext-str site=detroit \
     --ext-str cell=humanoid-line \
     --ext-str environment=production \
     dashboard_main.jsonnet > dashboard.json
   ```
2. Apply via Grafana provisioning or API (`grafana-toolkit`).
3. Store rendered dashboards in Git for review.
4. Generate Alertmanager rules with matching parameters:
   ```bash
   jsonnet \
     --ext-str site=detroit \
     --ext-str cell=humanoid-line \
     --ext-str environment=production \
     --ext-str slack_channel='#efab-ops' \
     alerts_main.jsonnet > alert-rules.json
   ```

## Lint & Testing Notes
- Add Jsonnet formatting via `jsonnetfmt` and CI job.
- Create metrics lint script to validate Prometheus queries exist (todo).
- Add unit tests with `jsonnet-bundler` overlays to ensure panel structure consistent.

## Next Steps
- Introduce jsonnet-bundler overlays for per-phase variants.
- Hook `alerts_main.jsonnet` into CI to validate rule syntax (`promtool check rules`).

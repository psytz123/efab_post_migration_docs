local grafana = import 'https://grafana.github.io/grafonnet-lib/grafonnet/grafana.libsonnet';

// Parameterised dashboard-as-code template per ADR-005 follow-ups.
// Pass `--ext-str site`, `--ext-str cell`, and optionally `--ext-str environment`.
local cfg = {
  site: std.extVar('site'),
  cell: std.extVar('cell'),
  environment: std.extVar('environment'),
};

local labelSelector = '{site="' + cfg.site + '",cell="' + cfg.cell + '"}';

{
  dashboard:
    grafana.dashboard.new('eFab Production Overview - ' + cfg.site + ' / ' + cfg.cell) +
    grafana.dashboard.tags(['efab', cfg.environment, cfg.site, cfg.cell]) +
    grafana.dashboard.time(from='now-6h', to='now') +
    grafana.dashboard.addRow(
      grafana.row.new('Production KPIs').addPanels([
        grafana.statPanel.new('OEE') + grafana.statPanel.unit('percent') +
          grafana.statPanel.target(
            expr='avg_over_time(cell_oee_percent' + labelSelector + '[5m])',
          ),
        grafana.statPanel.new('Task Intent Latency p99') + grafana.statPanel.unit('ms') +
          grafana.statPanel.target(
            expr='histogram_quantile(0.99, sum(rate(task_intent_latency_ms_bucket' + labelSelector + '[5m])) by (le))',
          ),
      ])
    ) +
    grafana.dashboard.addRow(
      grafana.row.new('Safety & Edge Health').addPanels([
        grafana.timeSeriesPanel.new('Safety Gate Hits') +
          grafana.timeSeriesPanel.target(
            expr='increase(edge_safety_gate_hits_total' + labelSelector + '[5m])',
          ),
        grafana.timeSeriesPanel.new('Edge Connectivity (s)') +
          grafana.timeSeriesPanel.target(
            expr='max(edge_heartbeat_seconds' + labelSelector + ')',
          ),
      ])
    ) +
    grafana.dashboard.addRow(
      grafana.row.new('FinOps & Cost').addPanels([
        grafana.statPanel.new('Unit Cost Variance') +
          grafana.statPanel.target(
            expr='avg(finops_cost_variance' + labelSelector + ')',
          ),
        grafana.statPanel.new('ROI Trend') +
          grafana.statPanel.target(
            expr='avg(finops_roi' + labelSelector + ')',
          ),
      ])
    ),
}

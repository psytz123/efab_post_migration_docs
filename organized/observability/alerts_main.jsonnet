// Alertmanager rule template scoped by site/cell environment.
// Enhanced with runbook URLs, PagerDuty routing, and proper alert ownership.
// ADR-005 follow-up implementation.
local cfg = {
  site: std.extVar('site'),
  cell: std.extVar('cell'),
  environment: std.extVar('environment'),
  slack_channel: std.extVar('slack_channel'),
};

local selector = '{site="' + cfg.site + '",cell="' + cfg.cell + '"}';

// Base runbook URL - customize per deployment
local runbookBaseUrl = 'https://wiki.efab.example.com/runbooks';

// PagerDuty routing keys by severity (customize per environment)
local pagerdutyKeys = {
  critical: 'pagerduty_critical_key',
  warning: 'pagerduty_warning_key',
};

{
  groups: [
    {
      name: 'safety-' + cfg.site + '-' + cfg.cell,
      rules: [
        {
          alert: 'EdgeHeartbeatStale',
          expr: 'max_over_time(edge_heartbeat_seconds' + selector + '[5m]) > 15',
          for: '2m',
          labels: {
            severity: 'critical',
            environment: cfg.environment,
            team: 'platform-edge',
            component: 'edge-agent',
            alertgroup: 'safety',
          },
          annotations: {
            summary: 'Edge heartbeat stalled for ' + cfg.site + '/' + cfg.cell,
            description: 'Edge agent has not reported within 15 seconds. Initiate fallback safety procedures. Last heartbeat: {{ $value }}s ago.',
            runbook_url: runbookBaseUrl + '/edge-heartbeat-stale',
            channel: cfg.slack_channel,
            dashboard_url: 'https://grafana.efab.example.com/d/edge-health',
            owner: 'platform-edge-team',
            priority: 'P1',
            impact: 'Production safety systems may be degraded',
          },
        },
        {
          alert: 'SafetyGateSpike',
          expr: 'increase(edge_safety_gate_hits_total' + selector + '[10m]) > 10',
          for: '5m',
          labels: {
            severity: 'warning',
            environment: cfg.environment,
            team: 'platform-safety',
            component: 'safety-controller',
            alertgroup: 'safety',
          },
          annotations: {
            summary: 'Safety gate activations rising for ' + cfg.site + '/' + cfg.cell,
            description: 'Investigate potential robot interference or calibration drift. Safety gates triggered {{ $value }} times in 10 minutes.',
            runbook_url: runbookBaseUrl + '/safety-gate-spike',
            channel: cfg.slack_channel,
            dashboard_url: 'https://grafana.efab.example.com/d/safety-metrics',
            owner: 'platform-safety-team',
            priority: 'P2',
            impact: 'Increased safety gate activations may indicate calibration issues',
          },
        },
      ],
    },
    {
      name: 'finops-' + cfg.site + '-' + cfg.cell,
      rules: [
        {
          alert: 'UnitCostVarianceHigh',
          expr: 'avg_over_time(finops_cost_variance' + selector + '[1h]) > 0.05',
          for: '15m',
          labels: {
            severity: 'critical',
            environment: cfg.environment,
            team: 'finops',
            component: 'cost-analytics',
            alertgroup: 'finops',
          },
          annotations: {
            summary: 'FinOps cost variance exceeded targets',
            description: 'Variance above 5% persists for more than 15 minutes. Coordinate with FinanceOps. Current variance: {{ $value | humanizePercentage }}.',
            runbook_url: runbookBaseUrl + '/finops-cost-variance',
            channel: cfg.slack_channel,
            dashboard_url: 'https://grafana.efab.example.com/d/finops-overview',
            owner: 'finops-team',
            priority: 'P1',
            impact: 'Cost overruns affecting budget projections',
            action_required: 'Review allocation weights and investigate cost drivers',
          },
        },
        {
          alert: 'ROITrendNegative',
          expr: 'avg_over_time(finops_roi' + selector + '[6h]) < 0',
          for: '30m',
          labels: {
            severity: 'warning',
            environment: cfg.environment,
            team: 'finops',
            component: 'roi-calculator',
            alertgroup: 'finops',
          },
          annotations: {
            summary: 'ROI trending negative for ' + cfg.site + '/' + cfg.cell,
            description: 'Confirm allocation weights and investigate unusual cost drivers. Current ROI: {{ $value }}.',
            runbook_url: runbookBaseUrl + '/finops-roi-negative',
            channel: cfg.slack_channel,
            dashboard_url: 'https://grafana.efab.example.com/d/finops-roi',
            owner: 'finops-team',
            priority: 'P2',
            impact: 'Negative ROI trend requires investigation',
            action_required: 'Validate cost allocation and review revenue metrics',
          },
        },
      ],
    },
    {
      name: 'performance-' + cfg.site + '-' + cfg.cell,
      rules: [
        {
          alert: 'TaskIntentLatencyHigh',
          expr: 'histogram_quantile(0.99, sum(rate(task_intent_latency_ms_bucket' + selector + '[5m])) by (le)) > 500',
          for: '10m',
          labels: {
            severity: 'warning',
            environment: cfg.environment,
            team: 'platform-core',
            component: 'task-scheduler',
            alertgroup: 'performance',
          },
          annotations: {
            summary: 'Task intent latency p99 exceeds 500ms',
            description: 'Task scheduling performance degraded. P99 latency: {{ $value | humanizeDuration }}. Investigate task queue depth and worker pool utilization.',
            runbook_url: runbookBaseUrl + '/task-intent-latency',
            channel: cfg.slack_channel,
            dashboard_url: 'https://grafana.efab.example.com/d/task-performance',
            owner: 'platform-core-team',
            priority: 'P2',
            impact: 'User experience may be degraded due to slow task execution',
          },
        },
        {
          alert: 'OEEBelowTarget',
          expr: 'avg_over_time(cell_oee_percent' + selector + '[30m]) < 85',
          for: '15m',
          labels: {
            severity: 'warning',
            environment: cfg.environment,
            team: 'operations',
            component: 'cell-controller',
            alertgroup: 'performance',
          },
          annotations: {
            summary: 'OEE below target threshold (85%) for ' + cfg.site + '/' + cfg.cell,
            description: 'Overall Equipment Effectiveness has dropped below 85% for 15+ minutes. Current OEE: {{ $value }}%. Review downtime logs and quality metrics.',
            runbook_url: runbookBaseUrl + '/oee-below-target',
            channel: cfg.slack_channel,
            dashboard_url: 'https://grafana.efab.example.com/d/production-kpis',
            owner: 'operations-team',
            priority: 'P2',
            impact: 'Production efficiency reduced',
            action_required: 'Investigate availability, performance, and quality factors',
          },
        },
      ],
    },
  ],
}

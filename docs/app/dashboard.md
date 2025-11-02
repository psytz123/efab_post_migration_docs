# Orders Dashboard Guide

## Pages
- `/dashboard`: Overview metrics (totals, 24h throughput, state breakdown, recents).
- `/dashboard/orders`: Filterable orders table (state + limit selectors).
- `/dashboard/audit`: Recent state transitions with pagination controls via `limit`.
- `/dashboard/performance`: Real-time charts backed by `/dashboard/api/metrics`.
- `/dashboard/executive`: Executive summary (SLA, backlog, milestones).
- `/dashboard/api/metrics`: JSON payload consumed by the Prometheus exporter.

## Running locally
1. Launch the mock service:
   ```bash
   scripts/launch_orders_mock.sh
   ```
2. Visit http://localhost:8080/dashboard.
3. Seed additional data if needed:
   ```bash
   python scripts/seed_orders_mock.py --count 10
   ```

## Notes
- All responses carry strict cache-busting headers; browser refresh fetches fresh data.
- Templates live in `services/orders/app/templates/` and inherit from `base.html`.
- Metrics backing the dashboard are produced by `repository.get_dashboard_metrics`.
- For staging, point `/dashboard/api/metrics` exporter at the deployment URL.

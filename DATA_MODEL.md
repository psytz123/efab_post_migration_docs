# Data Model — Manufacturing Graph & Events

## Manufacturing Graph (tables — Postgres)
```sql
CREATE TABLE cells (
  cell_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  zone JSONB NOT NULL
);

CREATE TABLE operations (
  op_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  standard_time_sec INTEGER,
  changeover_sec INTEGER
);

CREATE TABLE routings (
  sku TEXT NOT NULL,
  seq INTEGER NOT NULL,
  op_id TEXT NOT NULL REFERENCES operations(op_id),
  cell_id TEXT REFERENCES cells(cell_id),
  yield_pct NUMERIC,
  CONSTRAINT pk_routings PRIMARY KEY (sku, seq)
);

CREATE TABLE task_actuals (
  task_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  lot TEXT NOT NULL,
  cell_id TEXT NOT NULL,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  scrap_qty NUMERIC DEFAULT 0,
  metrics JSONB
);
```

## Event Envelope
```json
{
  "event_id": "uuid",
  "ts": "2025-11-01T20:00:00Z",
  "source": "scheduler",
  "type": "schedule.task.intent.created",
  "site": "bk-mill-01",
  "payload": { "task_id": "T-001", "cell": "PackLine1", "lot": "123A" }
}
```

## Topics
- `orders.created` | `orders.updated`
- `schedule.task.intent.created` | `schedule.task.intent.updated`
- `task.execution.update`
- `quality.inspection.picture` | `quality.inspection.result`
- `telemetry.cell.state` | `telemetry.robot.state`

## Retention & Replay
- Command topics: 1–7 days (idempotent replay safe).
- Telemetry: 3–14 days hot; archive to S3 for cold analytics.

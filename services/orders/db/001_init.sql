-- Orders service initial schema
-- Generated 2025-11-01 (Wave 2)

CREATE SCHEMA IF NOT EXISTS orders;
SET search_path TO orders;

CREATE TYPE order_state AS ENUM ('draft', 'firm', 'released', 'paused', 'completed', 'cancelled');

CREATE TABLE orders (
  order_id TEXT PRIMARY KEY,
  customer_ref TEXT,
  sku TEXT NOT NULL,
  quantity NUMERIC(18,4) NOT NULL CHECK (quantity > 0),
  uom TEXT DEFAULT 'ea',
  state order_state NOT NULL DEFAULT 'draft',
  priority SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
  due_date TIMESTAMPTZ NOT NULL,
  site_id TEXT NOT NULL,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_lines (
  order_id TEXT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
  line_no INTEGER NOT NULL,
  op_id TEXT NOT NULL,
  cell_id TEXT,
  changeover_sec INTEGER,
  yield_pct NUMERIC(5,2),
  PRIMARY KEY (order_id, line_no)
);

CREATE TABLE order_lots (
  lot_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
  quantity NUMERIC(18,4) NOT NULL CHECK (quantity > 0),
  cell_id TEXT NOT NULL,
  planned_start TIMESTAMPTZ,
  planned_end TIMESTAMPTZ,
  state order_state NOT NULL DEFAULT 'firm'
);

CREATE TABLE order_actuals (
  order_id TEXT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
  lot_id TEXT REFERENCES order_lots(lot_id) ON DELETE SET NULL,
  task_id TEXT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  scrap_qty NUMERIC(18,4) DEFAULT 0,
  metrics JSONB,
  PRIMARY KEY (order_id, task_id)
);

CREATE TABLE order_audit (
  audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id TEXT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
  previous_state order_state,
  new_state order_state,
  changed_by TEXT NOT NULL,
  reason TEXT,
  changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_orders_state_site ON orders(state, site_id);
CREATE INDEX idx_orders_due_date ON orders(due_date DESC);
CREATE INDEX idx_order_lots_order ON order_lots(order_id);
CREATE INDEX idx_order_actuals_task ON order_actuals(task_id);

CREATE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_orders_updated
BEFORE UPDATE ON orders
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Comments for documentation tooling
COMMENT ON TABLE orders IS 'Order headers synced with gateway and Task API';
COMMENT ON TABLE order_lines IS 'Manufacturing routing steps linked to Manufacturing Graph operations';
COMMENT ON TABLE order_lots IS 'Lots released to cells with quantity and schedule details';
COMMENT ON TABLE order_audit IS 'Audit trail for state transitions and approvals';

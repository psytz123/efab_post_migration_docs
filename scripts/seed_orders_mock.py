#!/usr/bin/env python3
"""Seed mock Orders data into the configured database.

Example:
    ORDERS_DATABASE_URL=sqlite+pysqlite:///./workspace/services/orders/mock/orders.db \\
        scripts/seed_orders_mock.py --count 5
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from typing import Iterable
from uuid import uuid4

from services.orders.app import db, models, repository, schemas


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed mock Orders records.")
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of mock orders to create (default: 5).",
    )
    parser.add_argument(
        "--site-id",
        default="bk-mill-mock",
        help="Site identifier to assign to mock orders.",
    )
    return parser.parse_args()


def ensure_schema() -> None:
    """Create database schema if it does not exist."""
    models.Base.metadata.create_all(bind=db.engine)


def build_mock_orders(count: int, site_id: str) -> Iterable[schemas.OrderCreate]:
    """Generate deterministic mock order payloads."""
    now = datetime.now(timezone.utc)
    for idx in range(count):
        due_date = now + timedelta(hours=idx + 1)
        lot_id = f"MOCK-LOT-{idx:03d}"
        sku = f"MOCK-SKU-{(idx % 5) + 1:02d}"
        yield schemas.OrderCreate(
            customer_ref=f"MOCK-PO-{idx:04d}",
            sku=sku,
            quantity=10 + idx,
            uom="ea",
            priority=3,
            due_date=due_date,
            site_id=site_id,
            routings=[
                schemas.OrderRouting(seq=0, op_id="cutting", cell_id="Cell-A", changeover_sec=60),
                schemas.OrderRouting(seq=1, op_id="assembly", cell_id="Cell-B", changeover_sec=90),
            ],
            lots=[
                schemas.OrderLot(
                    lot_id=lot_id,
                    quantity=float(10 + idx),
                    cell_id="Cell-A",
                    planned_start=now + timedelta(minutes=idx * 5),
                    planned_end=due_date,
                )
            ],
            metadata={"source": "mock-generator"},
        )


def seed_orders(count: int, site_id: str) -> None:
    ensure_schema()
    with db.session_scope() as session:
        for payload in build_mock_orders(count, site_id):
            order_id = str(uuid4())
            repository.create_order(session, payload, order_id)
    db_url = db.engine.url.render_as_string(hide_password=True)
    print(f"Seeded {count} mock orders into {db_url}")


def main() -> None:
    args = parse_args()
    seed_orders(args.count, args.site_id)


if __name__ == "__main__":
    main()

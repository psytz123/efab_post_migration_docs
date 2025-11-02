"""Data access helpers for Orders service."""

from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models, schemas


def list_orders(session: Session, state: Optional[str] = None, cell: Optional[str] = None, limit: int = 50) -> List[models.Order]:
    query = select(models.Order).order_by(models.Order.due_date.asc())
    if state:
        query = query.where(models.Order.state == state)
    if cell:
        query = query.where(models.Order.lots.any(models.OrderLot.cell_id == cell))
    return session.execute(query.limit(limit)).scalars().all()


def get_order(session: Session, order_id: str) -> Optional[models.Order]:
    return session.get(models.Order, order_id)


def create_order(session: Session, payload: schemas.OrderCreate, order_id: str) -> models.Order:
    order = models.Order(
        order_id=order_id,
        customer_ref=payload.customer_ref,
        sku=payload.sku,
        quantity=payload.quantity,
        uom=payload.uom,
        priority=payload.priority,
        due_date=payload.due_date,
        site_id=payload.site_id,
        attributes=payload.metadata,
    )
    order.lines = [
        models.OrderLine(
            order_id=order_id,
            line_no=r.seq,
            op_id=r.op_id,
            cell_id=r.cell_id,
            changeover_sec=r.changeover_sec,
        )
        for r in payload.routings
    ]
    order.lots = [
        models.OrderLot(
            lot_id=lot.lot_id,
            order_id=order_id,
            quantity=lot.quantity,
            cell_id=lot.cell_id,
            planned_start=lot.planned_start,
            planned_end=lot.planned_end,
            state=lot.state.value,
        )
        for lot in payload.lots
    ]
    session.add(order)
    return order


def get_dashboard_metrics(session: Session) -> dict:
    """Aggregate counts and recents for dashboard rendering."""
    now = datetime.now(timezone.utc)
    lookback = now - timedelta(hours=24)
    due_horizon = now + timedelta(hours=24)

    total_orders = session.scalar(select(func.count()).select_from(models.Order)) or 0
    orders_last_24h = (
        session.scalar(
            select(func.count())
            .select_from(models.Order)
            .where(models.Order.created_at >= lookback)
        )
        or 0
    )

    due_within_24h = (
        session.scalar(
            select(func.count())
            .select_from(models.Order)
            .where(models.Order.state != "completed")
            .where(models.Order.due_date.isnot(None))
            .where(models.Order.due_date <= due_horizon)
        )
        or 0
    )

    high_priority_backlog = (
        session.scalar(
            select(func.count())
            .select_from(models.Order)
            .where(models.Order.state.notin_(["completed", "cancelled"]))
            .where(models.Order.priority <= 2)
        )
        or 0
    )

    state_rows = session.execute(
        select(models.Order.state, func.count())
        .group_by(models.Order.state)
        .order_by(models.Order.state.asc())
    ).all()
    state_counts = {str(state): count for state, count in state_rows}

    recent_orders = [
        {
            "order_id": row.order_id,
            "sku": row.sku,
            "state": str(row.state),
            "quantity": float(row.quantity),
            "created_at": row.created_at,
        }
        for row in session.execute(
            select(
                models.Order.order_id,
                models.Order.sku,
                models.Order.state,
                models.Order.quantity,
                models.Order.created_at,
            )
            .order_by(models.Order.created_at.desc())
            .limit(5)
        )
    ]

    recent_audit = [
        {
            "order_id": row.order_id,
            "previous_state": str(row.previous_state) if row.previous_state else None,
            "new_state": str(row.new_state),
            "changed_by": row.changed_by,
            "changed_at": row.changed_at,
        }
        for row in session.execute(
            select(
                models.OrderAudit.order_id,
                models.OrderAudit.previous_state,
                models.OrderAudit.new_state,
                models.OrderAudit.changed_by,
                models.OrderAudit.changed_at,
            )
            .order_by(models.OrderAudit.changed_at.desc())
            .limit(5)
        )
    ]

    throughput_per_hour = round(orders_last_24h / 24, 2) if orders_last_24h else 0.0

    return {
        "total_orders": total_orders,
        "orders_last_24h": orders_last_24h,
        "throughput_per_hour": throughput_per_hour,
        "due_within_24h": due_within_24h,
        "high_priority_backlog": high_priority_backlog,
        "state_counts": state_counts,
        "recent_orders": recent_orders,
        "recent_audit": recent_audit,
        "generated_at": now,
    }


def list_orders_summary(session: Session, state: Optional[str] = None, limit: int = 25) -> List[models.Order]:
    query = select(models.Order).order_by(models.Order.created_at.desc())
    if state:
        query = query.where(models.Order.state == state)
    return session.execute(query.limit(limit)).scalars().all()


def list_audit_events(session: Session, limit: int = 25) -> List[models.OrderAudit]:
    return (
        session.execute(
            select(models.OrderAudit).order_by(models.OrderAudit.changed_at.desc()).limit(limit)
        )
        .scalars()
        .all()
    )


def update_order(session: Session, order: models.Order, payload: schemas.OrderUpdate) -> models.Order:
    if payload.priority is not None:
        order.priority = payload.priority
    if payload.due_date is not None:
        order.due_date = payload.due_date
    if payload.state is not None:
        order.state = payload.state.value
    order.updated_at = datetime.now(timezone.utc)
    return order


def upsert_lots(session: Session, order: models.Order, lots: Iterable[schemas.OrderLot]) -> models.Order:
    existing = {lot.lot_id: lot for lot in order.lots}
    for lot in lots:
        if lot.lot_id in existing:
            entry = existing[lot.lot_id]
            entry.quantity = lot.quantity
            entry.cell_id = lot.cell_id
            entry.planned_start = lot.planned_start
            entry.planned_end = lot.planned_end
            entry.state = lot.state.value
        else:
            session.add(
                models.OrderLot(
                    lot_id=lot.lot_id,
                    order_id=order.order_id,
                    quantity=lot.quantity,
                    cell_id=lot.cell_id,
                    planned_start=lot.planned_start,
                    planned_end=lot.planned_end,
                    state=lot.state.value,
                )
            )
    return order

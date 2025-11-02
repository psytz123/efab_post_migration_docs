"""SQLAlchemy models for Orders service."""

from datetime import datetime, timezone
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .db import Base


def utcnow() -> datetime:
    """Return timezone-aware UTC timestamp for SQLAlchemy defaults."""
    return datetime.now(timezone.utc)

order_state_enum = Enum(
    "draft",
    "firm",
    "released",
    "paused",
    "completed",
    "cancelled",
    name="order_state",
)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="orders_quantity_positive"),
        CheckConstraint("priority BETWEEN 1 AND 5", name="orders_priority_bounds"),
    )

    order_id = Column(String, primary_key=True)
    customer_ref = Column(String, nullable=True)
    sku = Column(String, nullable=False)
    quantity = Column(Numeric(18, 4), nullable=False)
    uom = Column(String, default="ea")
    state = Column(order_state_enum, default="draft", nullable=False)
    priority = Column(SmallInteger, default=3, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)
    site_id = Column(String, nullable=False)
    attributes = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    lines = relationship("OrderLine", cascade="all, delete-orphan", back_populates="order")
    lots = relationship("OrderLot", cascade="all, delete-orphan", back_populates="order")
    actuals = relationship("OrderActual", cascade="all, delete-orphan", back_populates="order")

class OrderLine(Base):
    __tablename__ = "order_lines"

    order_id = Column(String, ForeignKey("orders.order_id", ondelete="CASCADE"), primary_key=True)
    line_no = Column(Integer, primary_key=True)
    op_id = Column(String, nullable=False)
    cell_id = Column(String, nullable=True)
    changeover_sec = Column(Integer, nullable=True)
    yield_pct = Column(Numeric(5, 2), nullable=True)

    order = relationship("Order", back_populates="lines")


class OrderLot(Base):
    __tablename__ = "order_lots"

    lot_id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Numeric(18, 4), nullable=False)
    cell_id = Column(String, nullable=False)
    planned_start = Column(DateTime(timezone=True))
    planned_end = Column(DateTime(timezone=True))
    state = Column(order_state_enum, default="firm", nullable=False)

    order = relationship("Order", back_populates="lots")


class OrderActual(Base):
    __tablename__ = "order_actuals"
    __table_args__ = (
        CheckConstraint("scrap_qty >= 0", name="order_actuals_scrap_nonnegative"),
    )

    order_id = Column(String, ForeignKey("orders.order_id", ondelete="CASCADE"), primary_key=True)
    task_id = Column(String, primary_key=True)
    lot_id = Column(String, ForeignKey("order_lots.lot_id", ondelete="SET NULL"))
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    scrap_qty = Column(Numeric(18, 4), default=0)
    metrics = Column(JSON)

    order = relationship("Order", back_populates="actuals")
    lot = relationship("OrderLot")


class OrderAudit(Base):
    __tablename__ = "order_audit"

    audit_id = Column(UUID(as_uuid=True), primary_key=True)
    order_id = Column(String, ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False)
    previous_state = Column(order_state_enum, nullable=True)
    new_state = Column(order_state_enum, nullable=False)
    changed_by = Column(String, nullable=False)
    reason = Column(Text)
    changed_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    attributes = Column("metadata", JSON, default=dict)

    order = relationship("Order")

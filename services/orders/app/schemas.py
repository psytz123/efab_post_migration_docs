"""Pydantic schemas for Orders service."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic import ConfigDict


class OrderState(str, Enum):
    draft = "draft"
    firm = "firm"
    released = "released"
    paused = "paused"
    completed = "completed"
    cancelled = "cancelled"


class OrderRouting(BaseModel):
    seq: int = Field(ge=0)
    op_id: str
    cell_id: Optional[str]
    changeover_sec: Optional[int]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class OrderLot(BaseModel):
    lot_id: str
    quantity: float = Field(gt=0)
    cell_id: str
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    state: OrderState = OrderState.firm

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class OrderBase(BaseModel):
    customer_ref: Optional[str]
    sku: str
    quantity: float = Field(gt=0)
    uom: str = "ea"
    priority: int = Field(ge=1, le=5, default=3)
    due_date: datetime
    site_id: str
    routings: List[OrderRouting] = Field(default_factory=list)
    lots: List[OrderLot] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class OrderCreate(OrderBase):
    pass


class OrderUpdate(BaseModel):
    priority: Optional[int] = Field(None, ge=1, le=5)
    due_date: Optional[datetime] = None
    state: Optional[OrderState] = None
    pause_reason: Optional[str] = None


class Order(OrderBase):
    order_id: str
    state: OrderState
    metadata: dict = Field(
        default_factory=dict,
        validation_alias="attributes",
        serialization_alias="metadata",
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)



class OrderList(BaseModel):
    data: List[Order]
    next_cursor: Optional[str]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

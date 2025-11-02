"""FastAPI routes for Orders service."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from . import repository, schemas
from .db import session_scope
from .events import OrderEvent

router = APIRouter(prefix="/orders", tags=["orders"])


def get_session():
    with session_scope() as session:
        yield session


@router.post("", response_model=schemas.Order, status_code=status.HTTP_201_CREATED)
async def create_order(payload: schemas.OrderCreate, request: Request, session: Session = Depends(get_session)):
    supplied_id = payload.metadata.get("order_id") if payload.metadata else None
    order_id = supplied_id or f"ORD-{uuid4().hex}"
    if repository.get_order(session, order_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order already exists")
    order = repository.create_order(session, payload, order_id)
    event = OrderEvent(
        event_type="orders.created",
        order_id=order.order_id,
        site_id=order.site_id,
        payload={"state": order.state, "priority": order.priority},
    )
    session.flush()
    await request.app.state.event_publisher.publish(event)
    request.app.state.telemetry.record_order_created(order.site_id)
    return order


@router.get("", response_model=schemas.OrderList)
async def list_orders(state: schemas.OrderState | None = None, cell: str | None = None, session: Session = Depends(get_session)):
    orders = repository.list_orders(session, state.value if state else None, cell)
    return schemas.OrderList(data=[schemas.Order.model_validate(o) for o in orders], next_cursor=None)


@router.get("/{order_id}", response_model=schemas.Order)
async def get_order(order_id: str, session: Session = Depends(get_session)):
    order = repository.get_order(session, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return schemas.Order.model_validate(order)


@router.patch("/{order_id}", response_model=schemas.Order)
async def update_order(order_id: str, payload: schemas.OrderUpdate, session: Session = Depends(get_session)):
    order = repository.get_order(session, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    repository.update_order(session, order, payload)
    return schemas.Order.model_validate(order)


@router.post("/{order_id}/lots", response_model=schemas.Order)
async def upsert_lots(order_id: str, request: dict, session: Session = Depends(get_session)):
    order = repository.get_order(session, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    lots_payload = [schemas.OrderLot(**lot) for lot in request.get("lots", [])]
    repository.upsert_lots(session, order, lots_payload)
    return schemas.Order.model_validate(order)


@router.post("/{order_id}/state", response_model=schemas.Order)
async def change_state(order_id: str, payload: schemas.OrderUpdate, request: Request, session: Session = Depends(get_session)):
    order = repository.get_order(session, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if not payload.state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="state is required")
    valid = {
        "draft": ["firm", "cancelled"],
        "firm": ["released", "cancelled"],
        "released": ["paused", "completed", "cancelled"],
        "paused": ["released", "cancelled"],
    }
    current_state = order.state
    next_state = payload.state.value
    if next_state not in valid.get(current_state, []):
        request.app.state.telemetry.record_state_denied(current_state, next_state)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invalid state transition")
    repository.update_order(session, order, payload)
    event = OrderEvent(
        event_type="orders.state.changed",
        order_id=order.order_id,
        site_id=order.site_id,
        payload={"previous": current_state, "next": next_state},
    )
    await request.app.state.event_publisher.publish(event)
    return schemas.Order.model_validate(order)

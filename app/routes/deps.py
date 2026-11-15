from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Order, OrderStatus

EDITABLE = {OrderStatus.draft, OrderStatus.awaiting_payment}


def get_order(order_id: str, db: Session = Depends(get_db)) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "Order not found")
    return order


def editable_order(order: Order = Depends(get_order)) -> Order:
    if order.status not in EDITABLE:
        raise HTTPException(409, "This order is already paid and can't be changed")
    return order

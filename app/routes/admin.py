import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Order, OrderStatus
from app.pipeline.runner import deliver
from app.routes.pages import templates

security = HTTPBasic()


def require_admin(creds: HTTPBasicCredentials = Depends(security)) -> None:
    s = get_settings()
    ok = secrets.compare_digest(creds.username, s.admin_user) and secrets.compare_digest(
        creds.password, s.admin_password
    )
    if not ok:
        raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})


router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


@router.get("")
def dashboard(request: Request, db: Session = Depends(get_db)):
    orders = db.scalars(
        select(Order).where(Order.status != OrderStatus.draft).order_by(Order.created_at.desc()).limit(100)
    ).all()
    return templates.TemplateResponse(request, "admin/index.html", {"orders": orders})


def _order(db: Session, order_id: str) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404)
    return order


@router.post("/orders/{order_id}/approve")
def approve(order_id: str, db: Session = Depends(get_db)):
    order = _order(db, order_id)
    if order.status != OrderStatus.in_review:
        raise HTTPException(409, "Only videos in review can be approved")
    deliver(db, order)
    return RedirectResponse("/admin", status_code=303)


@router.post("/orders/{order_id}/retry")
def retry(order_id: str, db: Session = Depends(get_db)):
    order = _order(db, order_id)
    if order.status not in (OrderStatus.failed, OrderStatus.in_review):
        raise HTTPException(409, "Only failed or in-review orders can be re-rendered")
    order.status = OrderStatus.queued
    order.rendered_at = None
    db.commit()
    return RedirectResponse("/admin", status_code=303)

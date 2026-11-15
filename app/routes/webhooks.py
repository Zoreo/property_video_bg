import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Order
from app.routes.pages import _after_payment
from app.services.payments import parse_webhook

router = APIRouter()
log = logging.getLogger("stripe")


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(""), db: Session = Depends(get_db)):
    payload = await request.body()
    try:
        event = parse_webhook(payload, stripe_signature)
    except Exception as e:
        raise HTTPException(400, "Invalid signature") from e
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order = db.get(Order, session.get("client_reference_id") or "")
        if order is None:
            log.warning("paid session %s has no matching order", session.get("id"))
        elif session.get("payment_status") == "paid":
            _after_payment(db, order)
    return {"ok": True}

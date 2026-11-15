"""Stripe Checkout. In fake mode, checkout marks the order paid straight away."""

import stripe

from app.config import get_settings
from app.models import Order
from app.pricing import CURRENCY


def create_checkout_url(order: Order) -> str:
    s = get_settings()
    if s.payments_mode != "stripe":
        return f"{s.base_url}/order/{order.id}/fake-pay"

    stripe.api_key = s.stripe_secret_key
    name = f"Property video ({order.template_label})"
    if order.staging:
        name += " with virtual staging"
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": CURRENCY,
                    "unit_amount": order.price_cents,
                    "product_data": {"name": name},
                },
                "quantity": 1,
            }
        ],
        customer_email=order.agent_email,
        client_reference_id=order.id,
        metadata={"order_id": order.id},
        success_url=f"{s.base_url}/order/{order.id}/thanks",
        cancel_url=f"{s.base_url}/order/{order.id}/photos",
    )
    order.stripe_session_id = session.id
    return session.url


def parse_webhook(payload: bytes, signature: str) -> dict:
    s = get_settings()
    return stripe.Webhook.construct_event(payload, signature, s.stripe_webhook_secret)

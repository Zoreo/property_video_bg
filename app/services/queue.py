"""The render queue is the orders table: oldest paid order first, one at a time."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Order, OrderStatus


def _start_of_day(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def rendered_today(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    return db.scalar(
        select(func.count()).select_from(Order).where(Order.rendered_at >= _start_of_day(now))
    ) or 0


def orders_ahead(db: Session) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.status.in_([OrderStatus.queued, OrderStatus.rendering]))
    ) or 0


def estimate_ready_at(db: Session, now: datetime | None = None, ahead: int | None = None) -> datetime:
    """Orders ahead x average render time; spills into later days past the daily cap."""
    s = get_settings()
    now = now or datetime.now(timezone.utc)
    ahead = orders_ahead(db) if ahead is None else ahead
    slots_today = max(s.daily_cap - rendered_today(db, now), 0)
    position = ahead + 1  # this order
    review_buffer = timedelta(hours=2) if s.require_approval else timedelta()
    if position <= slots_today:
        return now + timedelta(minutes=s.avg_render_minutes * position) + review_buffer
    days_later, pos_in_day = divmod(position - slots_today - 1, s.daily_cap)
    day_start = _start_of_day(now) + timedelta(days=days_later + 1, hours=9)
    return day_start + timedelta(minutes=s.avg_render_minutes * (pos_in_day + 1)) + review_buffer


def eta_text(ready_at: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    hours = (ready_at - now).total_seconds() / 3600
    if hours <= 1:
        return "within about an hour"
    if hours < 20:
        return f"within about {round(hours)} hours"
    days = max(round(hours / 24), 1)
    return "by tomorrow" if days == 1 else f"in about {days} days"


def mark_paid(db: Session, order: Order) -> bool:
    """Move an order into the queue. Returns False if it was already paid (webhook retries)."""
    res = db.execute(
        update(Order)
        .where(Order.id == order.id, Order.status.in_([OrderStatus.draft, OrderStatus.awaiting_payment]))
        .values(status=OrderStatus.queued, paid_at=datetime.now(timezone.utc))
    )
    db.commit()
    db.refresh(order)
    return res.rowcount == 1


def claim_next(db: Session) -> Order | None:
    """Take the oldest queued order, respecting the daily cap."""
    if rendered_today(db) >= get_settings().daily_cap:
        return None
    order = db.scalars(
        select(Order).where(Order.status == OrderStatus.queued).order_by(Order.paid_at).limit(1)
    ).first()
    if order is None:
        return None
    res = db.execute(
        update(Order)
        .where(Order.id == order.id, Order.status == OrderStatus.queued)
        .values(status=OrderStatus.rendering)
    )
    db.commit()
    if res.rowcount != 1:  # another worker took it
        return None
    db.refresh(order)
    return order

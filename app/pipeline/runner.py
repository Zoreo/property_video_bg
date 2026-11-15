"""Runs one paid order through the pipeline."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Job, Order, OrderStatus
from app.pipeline import registry
from app.pipeline.base import Aspect, ListingCard
from app.services.email import get_mailer, video_delivery
from app.services.storage import get_storage

log = logging.getLogger("pipeline")


def _card(order: Order) -> ListingCard:
    storage = get_storage()
    unit = {"m2": "m²", "ft2": "ft²", "ha": "ha", "acres": "acres"}.get(order.size_unit, order.size_unit)
    size = int(order.size) if float(order.size).is_integer() else order.size
    return ListingCard(
        template_label=order.template_label,
        address=order.address,
        city=order.city,
        neighbourhood=order.neighbourhood,
        size_text=f"{size} {unit}",
        bedrooms=order.bedrooms,
        bathrooms=order.bathrooms,
        parking_text="6+" if order.parking >= 6 else str(order.parking),
        agent_name=order.agent_name,
        agency=order.agency,
        agent_phone=order.agent_phone,
        agent_email=order.agent_email,
        agent_photo=storage.path(order.agent_photo_path) if order.agent_photo_path else None,
    )


def _aspects(order: Order) -> list[Aspect]:
    return {"landscape": ["16:9"], "portrait": ["9:16"], "both": ["16:9", "9:16"]}[order.video_format.value]


def run_order(db: Session, order: Order) -> None:
    s = get_settings()
    storage = get_storage()
    job = Job(order_id=order.id, attempt=len(order.jobs) + 1)
    db.add(job)
    db.commit()
    work = storage.path(f"orders/{order.id}/work")

    try:
        photos = order.photos
        if order.staging and order.staging_style:
            job.step = "staging"
            db.commit()
            stager = registry.stager()
            for p in photos:
                if p.is_empty_room:
                    key = f"orders/{order.id}/staged/{p.id}.jpg"
                    stager.stage(storage.path(p.path), order.staging_style.value, storage.path(key))
                    p.staged_path = key
            db.commit()

        job.step = "planning"
        db.commit()
        sources = [storage.path(p.staged_path or p.path) for p in photos]
        shots = registry.shot_planner().plan(sources)

        clips_gen, asm = registry.clip_generator(), registry.assembler()
        outputs = []
        for aspect in _aspects(order):
            job.step = f"clips {aspect}"
            db.commit()
            tag = aspect.replace(":", "x")
            clips = [
                clips_gen.generate(shot, s.seconds_per_photo, aspect, work / f"clip_{tag}_{i:02d}.mp4")
                for i, shot in enumerate(shots)
            ]
            job.step = f"assembly {aspect}"
            db.commit()
            key = f"orders/{order.id}/video_{tag}.mp4"
            asm.assemble(clips, _card(order), aspect, storage.path(key))
            outputs.append(key)

        order.video_path = outputs[0]
        order.rendered_at = datetime.now(timezone.utc)
        order.error = None
        job.step = "done"
        job.finished_at = datetime.now(timezone.utc)
        if s.require_approval:
            order.status = OrderStatus.in_review
        else:
            deliver(db, order)
        db.commit()
    except Exception as e:  # keep the worker alive; the order shows up as failed in admin
        log.exception("order %s failed at %s", order.id, job.step)
        db.rollback()
        order.status = OrderStatus.failed
        order.error = f"{job.step}: {e}"
        job.error = str(e)
        job.finished_at = datetime.now(timezone.utc)
        db.commit()


def deliver(db: Session, order: Order) -> None:
    get_mailer().send(video_delivery(order))
    order.status = OrderStatus.delivered
    order.delivered_at = datetime.now(timezone.utc)
    db.commit()

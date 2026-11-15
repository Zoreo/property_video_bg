from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import (
    STYLE_LABELS,
    TEMPLATE_LABELS,
    Order,
    OrderStatus,
    StagingStyle,
    Template,
    VideoFormat,
)
from app.pricing import BASE_PRICE_CENTS, STAGING_PRICE_CENTS, format_eur, order_price_cents
from app.routes.deps import editable_order, get_order
from app.services import queue
from app.services.email import get_mailer, order_confirmation
from app.services.images import BadImage, normalise
from app.services.payments import create_checkout_url
from app.services.storage import get_storage

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")
templates.env.globals.update(
    site_name=get_settings().site_name,
    format_eur=format_eur,
    base_price=BASE_PRICE_CENTS,
    staging_price=STAGING_PRICE_CENTS,
    template_labels={t.value: l for t, l in TEMPLATE_LABELS.items()},
    style_labels={s.value: l for s, l in STYLE_LABELS.items()},
)

SIZE_UNITS = {"m2": "m²", "ft2": "ft²", "ha": "ha", "acres": "acres"}


def _render(request: Request, name: str, **ctx):
    return templates.TemplateResponse(request, name, ctx)


@router.get("/")
def landing(request: Request):
    return _render(request, "landing.html")


DEFAULTS = {"template": "just_sold", "video_format": "landscape", "size_unit": "m2",
            "bedrooms": "1", "bathrooms": "1", "parking": "0"}
FORM_FIELDS = ["template", "video_format", "address", "city", "neighbourhood", "size", "size_unit", "bedrooms",
               "bathrooms", "parking", "agent_name", "agency", "agent_phone", "agent_email"]


def _form_values(order: Order | None) -> dict[str, str]:
    values = dict(DEFAULTS)
    if order is not None:
        for f in FORM_FIELDS:
            val = getattr(order, f)
            val = getattr(val, "value", val)
            if f == "size" and float(val).is_integer():
                val = int(val)
            values[f] = "" if val is None else str(val)
    return values


@router.get("/order")
def details_form(request: Request):
    return _render(request, "details.html", order=None, values=_form_values(None), units=SIZE_UNITS, step=1)


@router.get("/order/{order_id}/details")
def details_edit(request: Request, order: Order = Depends(editable_order)):
    return _render(request, "details.html", order=order, values=_form_values(order), units=SIZE_UNITS, step=1)


async def _agent_photo(order: Order, upload: UploadFile | None) -> None:
    if upload is None or not upload.filename:
        return
    data = await upload.read()
    if not data:
        return
    try:
        jpeg, _, _ = normalise(data, max_side=800)
    except BadImage as e:
        raise HTTPException(400, f"Agent photo: {e}") from e
    order.agent_photo_path = get_storage().save(f"orders/{order.id}/agent.jpg", jpeg)


@router.post("/order")
async def details_submit(
    request: Request,
    db: Session = Depends(get_db),
    order_id: str = Form(""),
    template: Template = Form(...),
    video_format: VideoFormat = Form(VideoFormat.landscape),
    address: str = Form(""),
    city: str = Form(...),
    neighbourhood: str = Form(""),
    size: float = Form(..., gt=0),
    size_unit: str = Form("m2"),
    bedrooms: int = Form(..., ge=0, le=20),
    bathrooms: int = Form(..., ge=0, le=20),
    parking: int = Form(0, ge=0, le=6),
    agent_name: str = Form(...),
    agency: str = Form(""),
    agent_phone: str = Form(...),
    agent_email: str = Form(...),
    agent_photo: UploadFile | None = File(None),
):
    if size_unit not in SIZE_UNITS:
        raise HTTPException(400, "Unknown size unit")
    order = db.get(Order, order_id) if order_id else None
    if order is not None and order.status not in (OrderStatus.draft, OrderStatus.awaiting_payment):
        raise HTTPException(409, "This order is already paid")
    if order is None:
        order = Order(template=template, city=city, size=size, bedrooms=bedrooms, bathrooms=bathrooms,
                      agent_name=agent_name, agent_phone=agent_phone, agent_email=agent_email)
        db.add(order)
        db.flush()
    fields = dict(template=template, video_format=video_format, address=address.strip(), city=city.strip(),
                  neighbourhood=neighbourhood.strip(), size=size, size_unit=size_unit, bedrooms=bedrooms,
                  bathrooms=bathrooms, parking=parking, agent_name=agent_name.strip(), agency=agency.strip(),
                  agent_phone=agent_phone.strip(), agent_email=agent_email.strip())
    for k, v in fields.items():
        setattr(order, k, v)
    await _agent_photo(order, agent_photo)
    order.price_cents = order_price_cents(order.staging)
    db.commit()
    return RedirectResponse(f"/order/{order.id}/photos", status_code=303)


@router.get("/order/{order_id}/photos")
def photos_page(request: Request, order: Order = Depends(editable_order), db: Session = Depends(get_db)):
    ready_at = queue.estimate_ready_at(db)
    return _render(request, "photos.html", order=order, step=2, eta=queue.eta_text(ready_at),
                   max_photos=get_settings().max_photos, seconds_per_photo=get_settings().seconds_per_photo)


@router.post("/order/{order_id}/checkout")
def checkout(
    order: Order = Depends(editable_order),
    db: Session = Depends(get_db),
    staging: bool = Form(False),
    staging_style: StagingStyle | None = Form(None),
):
    if not order.photos:
        raise HTTPException(400, "Add at least one photo")
    if staging and staging_style is None:
        raise HTTPException(400, "Pick a staging style")
    if staging and not any(p.is_empty_room for p in order.photos):
        raise HTTPException(400, "Mark at least one photo as an empty room to stage")
    order.staging = staging
    order.staging_style = staging_style if staging else None
    order.price_cents = order_price_cents(staging)
    order.status = OrderStatus.awaiting_payment
    url = create_checkout_url(order)
    db.commit()
    return RedirectResponse(url, status_code=303)


def _after_payment(db: Session, order: Order) -> None:
    """Shared by the Stripe webhook and fake mode."""
    ahead = queue.orders_ahead(db)
    if queue.mark_paid(db, order):
        ready_at = queue.estimate_ready_at(db, ahead=ahead)
        get_mailer().send(order_confirmation(order, queue.eta_text(ready_at)))


@router.get("/order/{order_id}/fake-pay")
def fake_pay(order: Order = Depends(get_order), db: Session = Depends(get_db)):
    if get_settings().payments_mode == "stripe":
        raise HTTPException(404)
    _after_payment(db, order)
    return RedirectResponse(f"/order/{order.id}/thanks", status_code=303)


@router.get("/order/{order_id}/thanks")
def thanks(request: Request, order: Order = Depends(get_order), db: Session = Depends(get_db)):
    paid = order.status not in (OrderStatus.draft, OrderStatus.awaiting_payment)
    eta = queue.eta_text(queue.estimate_ready_at(db)) if paid else None
    return _render(request, "thanks.html", order=order, paid=paid, eta=eta)


@router.get("/v/{order_id}")
def download_page(request: Request, order: Order = Depends(get_order)):
    if order.status != OrderStatus.delivered or not order.video_path:
        raise HTTPException(404, "This video isn't ready yet")
    return _render(request, "download.html", order=order, files=_video_files(order))


def _video_files(order: Order) -> list[tuple[str, str]]:
    storage = get_storage()
    out = []
    for tag, label in (("16x9", "Landscape 16:9"), ("9x16", "Portrait 9:16")):
        key = f"orders/{order.id}/video_{tag}.mp4"
        if storage.path(key).exists():
            out.append((tag, label))
    return out


@router.get("/v/{order_id}/{tag}.mp4")
def download_file(tag: str, order: Order = Depends(get_order), download: bool = False):
    if order.status not in (OrderStatus.delivered, OrderStatus.in_review) or tag not in ("16x9", "9x16"):
        raise HTTPException(404)
    path = get_storage().path(f"orders/{order.id}/video_{tag}.mp4")
    if not path.exists():
        raise HTTPException(404)
    name = f"property-video-{tag}.mp4" if download else None
    return FileResponse(path, media_type="video/mp4", filename=name)

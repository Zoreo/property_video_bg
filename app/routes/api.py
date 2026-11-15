from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Order, Photo
from app.routes.deps import editable_order, get_order
from app.services.images import BadImage, normalise
from app.services.storage import get_storage

router = APIRouter(prefix="/api/orders/{order_id}")


def _photo_json(order: Order, p: Photo) -> dict:
    return {"id": p.id, "position": p.position, "is_empty_room": p.is_empty_room,
            "url": f"/api/orders/{order.id}/photos/{p.id}/image"}


@router.get("/photos")
def list_photos(order: Order = Depends(get_order)):
    return [_photo_json(order, p) for p in order.photos]


@router.post("/photos", status_code=201)
async def upload_photo(file: UploadFile = File(...), order: Order = Depends(editable_order),
                       db: Session = Depends(get_db)):
    s = get_settings()
    if len(order.photos) >= s.max_photos:
        raise HTTPException(400, f"You can add up to {s.max_photos} photos")
    data = await file.read()
    if len(data) > s.max_photo_mb * 1024 * 1024:
        raise HTTPException(413, f"Photos must be under {s.max_photo_mb} MB")
    try:
        jpeg, w, h = normalise(data)
    except BadImage as e:
        raise HTTPException(400, str(e)) from e
    position = max((p.position for p in order.photos), default=-1) + 1
    photo = Photo(order_id=order.id, position=position, path="", width=w, height=h)
    db.add(photo)
    db.flush()
    photo.path = get_storage().save(f"orders/{order.id}/photos/{photo.id}.jpg", jpeg)
    db.commit()
    db.refresh(order)
    return _photo_json(order, photo)


class Reorder(BaseModel):
    ids: list[int]


@router.put("/photos/order")
def reorder(body: Reorder, order: Order = Depends(editable_order), db: Session = Depends(get_db)):
    by_id = {p.id: p for p in order.photos}
    if sorted(body.ids) != sorted(by_id):
        raise HTTPException(400, "The list must contain each photo once")
    for i, pid in enumerate(body.ids):
        by_id[pid].position = i
    db.commit()
    db.refresh(order)
    return [_photo_json(order, p) for p in order.photos]


class PhotoPatch(BaseModel):
    is_empty_room: bool


def _photo(order: Order, photo_id: int) -> Photo:
    for p in order.photos:
        if p.id == photo_id:
            return p
    raise HTTPException(404, "Photo not found")


@router.patch("/photos/{photo_id}")
def patch_photo(photo_id: int, body: PhotoPatch, order: Order = Depends(editable_order),
                db: Session = Depends(get_db)):
    p = _photo(order, photo_id)
    p.is_empty_room = body.is_empty_room
    db.commit()
    return _photo_json(order, p)


@router.delete("/photos/{photo_id}", status_code=204)
def delete_photo(photo_id: int, order: Order = Depends(editable_order), db: Session = Depends(get_db)):
    p = _photo(order, photo_id)
    get_storage().delete(p.path)
    order.photos.remove(p)
    for i, q in enumerate(order.photos):
        q.position = i
    db.commit()


@router.get("/photos/{photo_id}/image")
def photo_image(photo_id: int, order: Order = Depends(get_order)):
    return FileResponse(get_storage().path(_photo(order, photo_id).path), media_type="image/jpeg")

from app.models import Order, OrderStatus
from tests.conftest import DETAILS, jpeg


def _create(client, **over):
    r = client.post("/order", data={**DETAILS, **over}, follow_redirects=False)
    assert r.status_code == 303, r.text
    return r.headers["location"].split("/")[2]


def _upload(client, oid, n=3):
    ids = []
    for i in range(n):
        r = client.post(f"/api/orders/{oid}/photos", files={"file": (f"p{i}.jpg", jpeg((40 * i, 80, 120)), "image/jpeg")})
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    return ids


def test_pages_render(client):
    for path in ("/", "/order", "/healthz"):
        assert client.get(path).status_code == 200


def test_details_then_photos(client):
    oid = _create(client)
    r = client.get(f"/order/{oid}/photos")
    assert r.status_code == 200
    assert "Just Sold" in r.text
    # editing keeps the values
    r = client.get(f"/order/{oid}/details")
    assert 'value="Sofia"' in r.text


def test_upload_reorder_delete(client):
    oid = _create(client)
    a, b, c = _upload(client, oid)
    r = client.put(f"/api/orders/{oid}/photos/order", json={"ids": [c, a, b]})
    assert [p["id"] for p in r.json()] == [c, a, b]
    assert client.put(f"/api/orders/{oid}/photos/order", json={"ids": [a, b]}).status_code == 400
    assert client.delete(f"/api/orders/{oid}/photos/{a}").status_code == 204
    assert [p["id"] for p in client.get(f"/api/orders/{oid}/photos").json()] == [c, b]


def test_photo_limit_and_bad_file(client):
    oid = _create(client)
    _upload(client, oid, 10)
    r = client.post(f"/api/orders/{oid}/photos", files={"file": ("x.jpg", jpeg(), "image/jpeg")})
    assert r.status_code == 400
    oid2 = _create(client)
    r = client.post(f"/api/orders/{oid2}/photos", files={"file": ("x.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 400


def test_price_with_and_without_staging(client):
    from app.db import SessionLocal

    oid = _create(client)
    (pid,) = _upload(client, oid, 1)
    # staging needs an empty room
    r = client.post(f"/order/{oid}/checkout", data={"staging": "true", "staging_style": "japandi"}, follow_redirects=False)
    assert r.status_code == 400
    client.patch(f"/api/orders/{oid}/photos/{pid}", json={"is_empty_room": True})
    r = client.post(f"/order/{oid}/checkout", data={"staging": "true", "staging_style": "japandi"}, follow_redirects=False)
    assert r.status_code == 303
    with SessionLocal() as db:
        assert db.get(Order, oid).price_cents == 2000

    oid = _create(client)
    _upload(client, oid, 1)
    client.post(f"/order/{oid}/checkout", data={}, follow_redirects=False)
    with SessionLocal() as db:
        assert db.get(Order, oid).price_cents == 1500


def test_full_flow_fake_pipeline(client):
    from app.db import SessionLocal
    from app.services.email import ConsoleMailer
    from app.worker import run_once

    ConsoleMailer.sent.clear()
    oid = _create(client)
    _upload(client, oid, 2)
    r = client.post(f"/order/{oid}/checkout", data={}, follow_redirects=True)
    assert "Thank you" in r.text
    assert ConsoleMailer.sent[-1].to == "maria@example.com"
    # paid orders can't be edited
    assert client.post(f"/api/orders/{oid}/photos", files={"file": ("x.jpg", jpeg(), "image/jpeg")}).status_code == 409

    assert run_once() is True
    with SessionLocal() as db:
        order = db.get(Order, oid)
        assert order.status == OrderStatus.in_review, order.error

    auth = ("admin", "secret")
    assert client.get("/admin").status_code == 401
    assert "Approve and send" in client.get("/admin", auth=auth).text
    r = client.post(f"/admin/orders/{oid}/approve", auth=auth, follow_redirects=False)
    assert r.status_code == 303
    assert ConsoleMailer.sent[-1].subject == "Your property video is ready"
    r = client.get(f"/v/{oid}")
    assert r.status_code == 200
    video = client.get(f"/v/{oid}/16x9.mp4")
    assert video.status_code == 200 and len(video.content) > 10_000


def test_eta_spills_past_daily_cap():
    from datetime import datetime, timezone

    from app.db import SessionLocal
    from app.services.queue import estimate_ready_at

    now = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
    with SessionLocal() as db:
        soon = estimate_ready_at(db, now=now, ahead=0)
        later = estimate_ready_at(db, now=now, ahead=15)
    assert soon.date() == now.date()
    assert later.date() > now.date()

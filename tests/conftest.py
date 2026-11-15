import io
import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["DATA_DIR"] = _tmp
os.environ["PAYMENTS_MODE"] = "fake"
os.environ["ADMIN_PASSWORD"] = "secret"


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.db import Base, engine
    from app.main import app

    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        yield c


def jpeg(color=(120, 90, 60), size=(640, 480)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return buf.getvalue()


DETAILS = {
    "template": "just_sold",
    "video_format": "landscape",
    "address": "ul. Shipka 12",
    "city": "Sofia",
    "neighbourhood": "Lozenets",
    "size": "84",
    "size_unit": "m2",
    "bedrooms": "2",
    "bathrooms": "1",
    "parking": "1",
    "agent_name": "Maria Ivanova",
    "agency": "Sofia Homes",
    "agent_phone": "+359 888 123 456",
    "agent_email": "maria@example.com",
}

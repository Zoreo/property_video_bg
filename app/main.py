import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routes import admin, api, pages, webhooks


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(level=logging.INFO)
    init_db()
    yield


app = FastAPI(title="Property videos", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(pages.router)
app.include_router(api.router)
app.include_router(webhooks.router)
app.include_router(admin.router)


@app.get("/healthz")
def healthz():
    return {"ok": True}

"""Background worker: renders one paid order at a time.

Run with:  python -m app.worker
"""

import logging
import time

from app.db import SessionLocal, init_db
from app.pipeline.runner import run_order
from app.services.queue import claim_next

log = logging.getLogger("worker")


def run_once() -> bool:
    with SessionLocal() as db:
        order = claim_next(db)
        if order is None:
            return False
        log.info("rendering order %s (%d photos)", order.id, len(order.photos))
        run_order(db, order)
        log.info("order %s -> %s", order.id, order.status.value)
        return True


def main(poll_seconds: int = 10) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    init_db()
    log.info("worker started")
    while True:
        if not run_once():
            time.sleep(poll_seconds)


if __name__ == "__main__":
    main()

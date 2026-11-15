"""Outgoing email. Console mailer for local work; Resend in production."""

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import get_settings

log = logging.getLogger("mailer")


@dataclass
class Email:
    to: str
    subject: str
    text: str


class Mailer(Protocol):
    def send(self, email: Email) -> None: ...


class ConsoleMailer:
    sent: list[Email] = []

    def send(self, email: Email) -> None:
        self.sent.append(email)
        log.info("EMAIL to=%s subject=%s\n%s", email.to, email.subject, email.text)


class ResendMailer:
    def __init__(self, api_key: str, sender: str):
        self.api_key, self.sender = api_key, sender

    def send(self, email: Email) -> None:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"from": self.sender, "to": [email.to], "subject": email.subject, "text": email.text},
            timeout=20,
        )
        r.raise_for_status()


def get_mailer() -> Mailer:
    s = get_settings()
    if s.mailer == "resend":
        return ResendMailer(s.resend_api_key, s.email_from)
    return ConsoleMailer()


def order_confirmation(order, eta_text: str) -> Email:
    s = get_settings()
    return Email(
        to=order.agent_email,
        subject="We're making your property video",
        text=(
            f"Hi {order.agent_name},\n\n"
            f"Thanks for your order for {order.address or order.city}. "
            f"Your video should be ready {eta_text}.\n\n"
            f"Order status: {s.base_url}/order/{order.id}/thanks\n"
        ),
    )


def video_delivery(order) -> Email:
    s = get_settings()
    return Email(
        to=order.agent_email,
        subject="Your property video is ready",
        text=(
            f"Hi {order.agent_name},\n\n"
            f"Your video for {order.address or order.city} is ready:\n"
            f"{s.base_url}/v/{order.id}\n\n"
            "The link stays active for 90 days.\n"
        ),
    )

import enum
import secrets
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _order_id() -> str:
    # Unguessable: the id is also the customer's private link to the order.
    return secrets.token_urlsafe(16)


class OrderStatus(str, enum.Enum):
    draft = "draft"
    awaiting_payment = "awaiting_payment"
    queued = "queued"
    rendering = "rendering"
    in_review = "in_review"
    delivered = "delivered"
    failed = "failed"
    refunded = "refunded"


class Template(str, enum.Enum):
    just_sold = "just_sold"
    sold = "sold"
    new_listing = "new_listing"
    for_rent = "for_rent"


TEMPLATE_LABELS = {
    Template.just_sold: "Just Sold",
    Template.sold: "Sold",
    Template.new_listing: "New Listing",
    Template.for_rent: "For Rent",
}


class VideoFormat(str, enum.Enum):
    landscape = "landscape"  # 16:9
    portrait = "portrait"  # 9:16
    both = "both"


class StagingStyle(str, enum.Enum):
    modern = "modern"
    mid_century = "mid_century"
    scandinavian = "scandinavian"
    traditional = "traditional"
    coastal = "coastal"
    japandi = "japandi"


STYLE_LABELS = {
    StagingStyle.modern: "Modern",
    StagingStyle.mid_century: "Mid Century",
    StagingStyle.scandinavian: "Scandinavian",
    StagingStyle.traditional: "Traditional",
    StagingStyle.coastal: "Coastal",
    StagingStyle.japandi: "Japandi",
}


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_order_id)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.draft, index=True)

    template: Mapped[Template] = mapped_column(Enum(Template))
    video_format: Mapped[VideoFormat] = mapped_column(Enum(VideoFormat), default=VideoFormat.landscape)

    address: Mapped[str] = mapped_column(String(200), default="")
    city: Mapped[str] = mapped_column(String(100))
    neighbourhood: Mapped[str] = mapped_column(String(100), default="")
    size: Mapped[float] = mapped_column()
    size_unit: Mapped[str] = mapped_column(String(10), default="m2")
    bedrooms: Mapped[int] = mapped_column(Integer)
    bathrooms: Mapped[int] = mapped_column(Integer)
    parking: Mapped[int] = mapped_column(Integer, default=0)  # 6 means "6+"

    agent_name: Mapped[str] = mapped_column(String(100))
    agency: Mapped[str] = mapped_column(String(100), default="")
    agent_phone: Mapped[str] = mapped_column(String(40))
    agent_email: Mapped[str] = mapped_column(String(200))
    agent_photo_path: Mapped[str | None] = mapped_column(String(300), nullable=True)

    staging: Mapped[bool] = mapped_column(Boolean, default=False)
    staging_style: Mapped[StagingStyle | None] = mapped_column(Enum(StagingStyle), nullable=True)

    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    stripe_session_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    video_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rendered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    photos: Mapped[list["Photo"]] = relationship(
        back_populates="order", order_by="Photo.position", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(back_populates="order", cascade="all, delete-orphan")

    @property
    def template_label(self) -> str:
        return TEMPLATE_LABELS[self.template]

    @property
    def staging_style_label(self) -> str | None:
        return STYLE_LABELS[self.staging_style] if self.staging_style else None


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(String(300))
    staged_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_empty_room: Mapped[bool] = mapped_column(Boolean, default=False)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)

    order: Mapped[Order] = relationship(back_populates="photos")


class Job(Base):
    """One pipeline run of one order, kept so failures can be inspected and retried."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    step: Mapped[str] = mapped_column(String(40), default="")
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped[Order] = relationship(back_populates="jobs")

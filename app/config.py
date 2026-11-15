from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    site_name: str = "Property Video Studio"
    base_url: str = "http://localhost:8000"
    database_url: str = "sqlite:///./data/app.db"
    data_dir: Path = Path("./data")

    admin_user: str = "admin"
    admin_password: str = "change-me"

    payments_mode: str = "fake"  # fake | stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    mailer: str = "console"  # console | resend
    resend_api_key: str = ""
    email_from: str = "videos@example.com"

    shot_planner: str = "fake"
    stager: str = "fake"
    clip_generator: str = "fake"
    assembler: str = "ffmpeg"
    fal_key: str = ""
    anthropic_api_key: str = ""

    daily_cap: int = 10
    avg_render_minutes: int = 30
    require_approval: bool = True

    max_photos: int = 10
    max_photo_mb: int = 20
    seconds_per_photo: int = 6


@lru_cache
def get_settings() -> Settings:
    return Settings()

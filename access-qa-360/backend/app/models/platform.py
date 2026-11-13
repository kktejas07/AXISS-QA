"""Platform-wide settings a super admin manages from the console instead of the server's environment."""
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class PlatformSetting(Base):
    """
    One value, encrypted. A key such as "STRIPE_SECRET_KEY" replaces the server's
    environment value of the same name; a key starting "check:" holds the result of
    the last test of a group of settings.
    """

    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

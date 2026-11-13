from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.core.database import Base
import uuid

ROLE_USER = "user"
ROLE_SUPER_ADMIN = "super_admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # "user" or "super_admin". Super admins see every organisation's data in /admin.
    role: Mapped[str] = mapped_column(String(20), default="user", server_default="user", nullable=False)
    # The one organisation this user belongs to, and their role in it:
    # "owner" | "admin" | "member" | "viewer". Filled in on sign-up or on first request.
    organization_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=True, index=True)
    org_role: Mapped[str] = mapped_column(String(16), default="owner", server_default="owner", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Sign-ins from before this moment stop working, so a reset signs out every other device.
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    projects: Mapped[list["Project"]] = relationship("Project", back_populates="owner", lazy="select")

    @property
    def is_super_admin(self) -> bool:
        return self.role == ROLE_SUPER_ADMIN

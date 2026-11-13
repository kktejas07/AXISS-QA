from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_token
from dataclasses import dataclass

from app.models.organization import Organization
from app.models.user import User
from app.services.orgs import PERMISSIONS, ROLE_NAMES, ensure_org

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required")
    return current_user


_DENIED = {
    "scan.run": "cannot create or start scans",
    "members.manage": "cannot manage the team",
    "org.edit": "cannot change organisation settings",
}


@dataclass
class OrgContext:
    """The signed-in user together with their organisation and role in it."""

    user: User
    org: Organization
    role: str

    def can(self, action: str) -> bool:
        return self.role in PERMISSIONS[action]

    def require(self, action: str) -> None:
        if not self.can(action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your role ({ROLE_NAMES.get(self.role, self.role)}) {_DENIED[action]}. Ask an owner or admin to change it.",
            )


async def get_org_context(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgContext:
    org = await ensure_org(db, current_user)
    return OrgContext(user=current_user, org=org, role=current_user.org_role)

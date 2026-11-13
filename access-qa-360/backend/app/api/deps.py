from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_token, token_is_current
from dataclasses import dataclass
from datetime import datetime, timezone

from app.models.integration import ApiKey
from app.services.api_keys import API_KEY_PREFIX, hash_api_key

from app.models.organization import Organization
from app.models.user import User
from app.services.orgs import PERMISSIONS, ROLE_NAMES, ensure_org

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    if token.startswith(API_KEY_PREFIX):
        return await _user_for_api_key(db, token)
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not token_is_current(token, user.password_changed_at):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your password was changed. Sign in again.")
    return user


async def _user_for_api_key(db: AsyncSession, token: str) -> User:
    """The person an API key acts for. The key stops working if it is revoked or they leave the organisation."""
    key = (
        await db.execute(select(ApiKey).where(ApiKey.key_hash == hash_api_key(token), ApiKey.revoked_at.is_(None)))
    ).scalar_one_or_none()
    user = await db.get(User, key.created_by) if key else None
    if not key or not user or not user.is_active or user.organization_id != key.organization_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This API key is not valid or has been revoked")
    key.last_used_at = datetime.now(timezone.utc)
    # Marks the request as made by a key, which limits what it may do (see OrgContext).
    user.via_api_key = True
    return user


async def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if getattr(current_user, "via_api_key", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API keys cannot use the admin console")
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
    # True when the request was made with an API key instead of a person's sign-in.
    via_api_key: bool = False

    def can(self, action: str) -> bool:
        # A key can see results and run scans, but never manage people, settings or other keys.
        if self.via_api_key and action != "scan.run":
            return False
        return self.role in PERMISSIONS[action]

    def require(self, action: str) -> None:
        if self.via_api_key and action != "scan.run":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API keys can view results and run scans only. Sign in to do this.")
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
    return OrgContext(user=current_user, org=org, role=current_user.org_role, via_api_key=getattr(current_user, "via_api_key", False))

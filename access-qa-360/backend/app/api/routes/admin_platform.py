"""Super admin: the platform's own keys and settings. Secrets go in and are tested, but never come back out."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core import platform
from app.core.database import get_db
from app.core.providers import PROVIDERS
from app.models.user import User
from app.services.orgs import log_admin_action

router = APIRouter(prefix="/admin/platform", tags=["admin"], dependencies=[Depends(require_super_admin)])


async def _page(db: AsyncSession) -> dict:
    return {"groups": await platform.overview(db), "providers": [{"id": key, "name": info["name"]} for key, info in PROVIDERS.items()]}


@router.get("")
async def settings_page(db: AsyncSession = Depends(get_db)):
    return await _page(db)


class Values(BaseModel):
    # Setting name -> new value. An empty value removes the console's value, so the server's own applies again.
    values: dict[str, str]


@router.put("")
async def save(body: Values, db: AsyncSession = Depends(get_db), admin: User = Depends(require_super_admin)):
    cleaned = {}
    for key, value in body.values.items():
        try:
            cleaned[key] = platform.clean(key, value) if value.strip() else ""
            if key not in platform.KEYS:
                raise platform.SettingError("That setting cannot be changed here")
        except platform.SettingError as e:
            label = platform.KEYS[key][1] if key in platform.KEYS else key
            raise HTTPException(422, f"{label}: {e}")
    for key, what in await platform.save(db, cleaned, admin.id):
        await log_admin_action(db, admin, "platform.setting", platform.KEYS[key][1], what)
    return await _page(db)


@router.post("/{group}/test")
async def test(group: str, db: AsyncSession = Depends(get_db), admin: User = Depends(require_super_admin)):
    """Make one small real call with the group's current settings and remember how it went."""
    try:
        ok, detail = await platform.try_out(group)
    except platform.SettingError as e:
        raise HTTPException(404, str(e))
    await platform.remember_check(db, group, ok, detail)
    await log_admin_action(db, admin, "platform.test", platform.GROUPS[group][0], "passed" if ok else ("could not be checked" if ok is None else "failed"))
    return {"ok": ok, "detail": detail}

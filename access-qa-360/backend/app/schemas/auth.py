from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    # From an invitation link; joins that organisation instead of creating a new one.
    invite_token: str | None = None


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    role: str = "user"
    organization_id: str | None = None
    org_role: str = "owner"

    model_config = {"from_attributes": True}


class OrgBrief(BaseModel):
    id: str
    name: str
    account_type: str
    status: str


class MeOut(UserOut):
    organization: OrgBrief
    # What this user's role allows, e.g. "scan.run", "members.manage"
    permissions: list[str]

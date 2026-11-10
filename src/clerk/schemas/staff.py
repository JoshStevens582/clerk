from typing import Literal

from pydantic import BaseModel, Field, field_validator

StaffRole = Literal["staff", "manager"]


class StaffUserOut(BaseModel):
    username: str
    role: StaffRole
    display_name: str | None = None
    email: str | None = None


class StaffAdminOut(BaseModel):
    username: str
    role: StaffRole
    email: str | None = None
    mfa_enabled: bool = False
    active: bool = True


class SetStaffRoleIn(BaseModel):
    role: StaffRole


class CreateStaffIn(BaseModel):
    username: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9_-]+$")
    password: str = Field(min_length=8, max_length=256)
    role: StaffRole = "staff"
    display_name: str | None = Field(default=None, max_length=128)
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("A valid email address is required for password reset.")
        return normalized

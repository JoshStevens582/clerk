from typing import Literal

from pydantic import BaseModel, Field

StaffRole = Literal["staff", "manager"]


class StaffUserOut(BaseModel):
    username: str
    role: StaffRole
    display_name: str | None = None
    email: str | None = None


class CreateStaffIn(BaseModel):
    username: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9_-]+$")
    password: str = Field(min_length=8, max_length=256)
    role: StaffRole = "staff"
    display_name: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=320)

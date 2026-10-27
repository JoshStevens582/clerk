from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from clerk.config import Settings
from clerk.schemas.staff import StaffRole


@dataclass(frozen=True)
class StaffSession:
    user_id: int
    username: str
    role: StaffRole


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_staff_session(request: Request) -> StaffSession:
    session = request.session
    user_id = session.get("staff_user_id")
    username = session.get("staff_username")
    role = session.get("staff_role")
    if not isinstance(user_id, int) or not isinstance(username, str) or role not in {
        "staff",
        "manager",
    }:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required.",
        )
    typed_role: StaffRole = "manager" if role == "manager" else "staff"
    return StaffSession(user_id=user_id, username=username, role=typed_role)


def require_staff(request: Request) -> StaffSession:
    return get_staff_session(request)


def require_manager(
    staff: Annotated[StaffSession, Depends(get_staff_session)],
) -> StaffSession:
    if staff.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required.",
        )
    return staff


SettingsDep = Annotated[Settings, Depends(get_settings)]
StaffDep = Annotated[StaffSession, Depends(require_staff)]
ManagerDep = Annotated[StaffSession, Depends(require_manager)]

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from clerk.repositories.staff_repo import StaffRepository
from clerk.schemas.staff import StaffRole
from clerk.services.jwt_tokens import verify_access_token

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class StaffSession:
    user_id: int
    username: str
    role: StaffRole
    mfa_enabled: bool


def _db_factory(request: Request) -> sessionmaker[Session]:
    factory = getattr(request.app.state, "db_factory", None)
    if not isinstance(factory, sessionmaker):
        raise RuntimeError("Database session factory is not configured.")
    return factory


async def require_staff(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> StaffSession:
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not credentials.credentials
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username = verify_access_token(request.app.state.settings, credentials.credentials)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    with _db_factory(request)() as session:
        row = StaffRepository(session).get_by_username(username)
    if row is None or not row.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    role: StaffRole = "manager" if row.role == "manager" else "staff"
    return StaffSession(
        user_id=row.id,
        username=row.username,
        role=role,
        mfa_enabled=row.mfa_enabled_at is not None,
    )


async def require_manager(
    staff: Annotated[StaffSession, Depends(require_staff)],
) -> StaffSession:
    if staff.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager only.",
        )
    return staff


StaffDep = Annotated[StaffSession, Depends(require_staff)]
ManagerDep = Annotated[StaffSession, Depends(require_manager)]

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from clerk.api.deps import ManagerDep
from clerk.repositories.staff_repo import StaffRepository
from clerk.schemas.auth import MessageOut
from clerk.schemas.staff import CreateStaffIn, SetStaffRoleIn, StaffAdminOut, StaffUserOut
from clerk.services.mfa import AuthError, clear_user_mfa
from clerk.services.staff_admin import (
    StaffAdminError,
    StaffAdminNotFoundError,
    list_staff_admin_users,
    set_staff_user_active,
    set_staff_user_role,
)
from clerk.services.staff_auth import hash_password, staff_user_out

router = APIRouter(prefix="/api/staff", tags=["staff"])


def _admin_http(exc: StaffAdminError) -> HTTPException:
    if isinstance(exc, StaffAdminNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/users", response_model=list[StaffAdminOut])
async def list_staff_users(request: Request, _: ManagerDep) -> list[StaffAdminOut]:
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    return list_staff_admin_users(db_factory)


@router.post("/users", response_model=StaffUserOut, status_code=status.HTTP_201_CREATED)
async def create_staff_user(
    payload: CreateStaffIn,
    request: Request,
    _: ManagerDep,
) -> StaffUserOut:
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    with db_factory() as session:
        repo = StaffRepository(session)
        if repo.get_by_username(payload.username) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That username is already in use.",
            )
        row = repo.create_user(
            username=payload.username,
            password_hash=hash_password(payload.password),
            role=payload.role,
            display_name=payload.display_name,
            email=payload.email,
        )
        session.commit()
        return staff_user_out(row)


@router.post("/users/{username}/role", response_model=StaffAdminOut)
async def change_staff_role(
    username: str,
    payload: SetStaffRoleIn,
    request: Request,
    manager: ManagerDep,
) -> StaffAdminOut:
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    try:
        return set_staff_user_role(
            db_factory,
            actor_username=manager.username,
            username=username,
            role=payload.role,
        )
    except StaffAdminError as exc:
        raise _admin_http(exc) from exc


@router.post("/users/{username}/disable", response_model=StaffAdminOut)
async def disable_staff_user(
    username: str,
    request: Request,
    manager: ManagerDep,
) -> StaffAdminOut:
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    try:
        return set_staff_user_active(
            db_factory,
            actor_username=manager.username,
            username=username,
            active=False,
        )
    except StaffAdminError as exc:
        raise _admin_http(exc) from exc


@router.post("/users/{username}/enable", response_model=StaffAdminOut)
async def enable_staff_user(
    username: str,
    request: Request,
    manager: ManagerDep,
) -> StaffAdminOut:
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    try:
        return set_staff_user_active(
            db_factory,
            actor_username=manager.username,
            username=username,
            active=True,
        )
    except StaffAdminError as exc:
        raise _admin_http(exc) from exc


@router.post("/users/{username}/mfa/reset", response_model=MessageOut)
async def reset_user_mfa(
    username: str,
    request: Request,
    manager: ManagerDep,
) -> MessageOut:
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    try:
        clear_user_mfa(
            db_factory,
            actor_username=manager.username,
            username=username.strip().lower(),
        )
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MessageOut(message=f"Authenticator cleared for {username.strip().lower()}.")

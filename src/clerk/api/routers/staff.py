from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from clerk.api.deps import ManagerDep
from clerk.repositories.staff_repo import StaffRepository
from clerk.schemas.staff import CreateStaffIn, StaffUserOut
from clerk.services.staff_auth import hash_password, staff_user_out

router = APIRouter(prefix="/api/staff", tags=["staff"])


@router.get("/users", response_model=list[StaffUserOut])
async def list_staff_users(request: Request, _: ManagerDep) -> list[StaffUserOut]:
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    with db_factory() as session:
        rows = StaffRepository(session).list_active()
        return [staff_user_out(row) for row in rows]


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
        )
        session.commit()
        return staff_user_out(row)

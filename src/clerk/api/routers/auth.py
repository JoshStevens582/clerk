from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from clerk.api.deps import StaffDep, get_staff_session
from clerk.schemas.staff import LoginIn, LoginOut, StaffUserOut
from clerk.services.staff_auth import authenticate

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut)
async def login(payload: LoginIn, request: Request) -> LoginOut:
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    with db_factory() as session:
        user = authenticate(session, username=payload.username, password=payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )
    with db_factory() as session:
        from clerk.repositories.staff_repo import StaffRepository

        row = StaffRepository(session).get_by_username(user.username)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password.",
            )
        request.session["staff_user_id"] = row.id
        request.session["staff_username"] = row.username
        request.session["staff_role"] = row.role
    return LoginOut(user=user)


@router.get("/me", response_model=StaffUserOut)
async def me(staff: StaffDep) -> StaffUserOut:
    return StaffUserOut(username=staff.username, role=staff.role, display_name=None)


@router.post("/logout")
async def logout(request: Request) -> dict[str, bool]:
    request.session.clear()
    return {"ok": True}


@router.get("/session", response_model=StaffUserOut | None)
async def read_session(request: Request) -> StaffUserOut | None:
    try:
        staff = get_staff_session(request)
    except HTTPException:
        return None
    return StaffUserOut(username=staff.username, role=staff.role, display_name=None)

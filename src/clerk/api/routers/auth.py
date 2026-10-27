from fastapi import APIRouter, HTTPException, Request, status

from clerk.api.deps import SettingsDep, verify_owner_password
from clerk.schemas.api import LoginIn, LoginOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut)
async def login(payload: LoginIn, request: Request, settings: SettingsDep) -> LoginOut:
    if not verify_owner_password(settings, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password.",
        )
    request.session["owner_authenticated"] = True
    return LoginOut()


@router.post("/logout", response_model=LoginOut)
async def logout(request: Request) -> LoginOut:
    request.session.clear()
    return LoginOut()

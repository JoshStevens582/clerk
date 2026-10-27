import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from clerk.config import Settings


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def require_owner(request: Request) -> None:
    session = request.session
    if not session.get("owner_authenticated"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required.",
        )


def verify_owner_password(settings: Settings, password: str) -> bool:
    expected = settings.owner_password
    if not expected:
        return False
    return secrets.compare_digest(password, expected)


SettingsDep = Annotated[Settings, Depends(get_settings)]
OwnerDep = Annotated[None, Depends(require_owner)]

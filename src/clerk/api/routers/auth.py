from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from clerk.api.auth_security import (
    ForgotPasswordRateLimitDep,
    LoginRateLimitDep,
    RefreshRateLimitDep,
    assert_login_not_locked,
    clear_login_lockout,
    record_login_outcome,
)
from clerk.api.deps import StaffDep
from clerk.repositories.staff_repo import StaffRepository
from clerk.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginIn,
    MeOut,
    MessageOut,
    MfaCodeRequest,
    MfaConfirmOut,
    MfaDisableRequest,
    MfaLoginRequest,
    MfaSetupOut,
    MfaSetupRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenOut,
    UpdateEmailRequest,
)
from clerk.schemas.staff import StaffUserOut
from clerk.services.jwt_tokens import issue_mfa_challenge_token, verify_mfa_challenge_token
from clerk.services.mfa import (
    AuthError as MfaAuthError,
)
from clerk.services.mfa import (
    MfaRejected,
    accept_second_factor,
    begin_mfa_setup,
    confirm_mfa_setup,
    disable_mfa,
    regenerate_recovery_codes,
)
from clerk.services.password_reset import (
    AuthError as ResetAuthError,
)
from clerk.services.password_reset import (
    request_password_reset,
    reset_password_with_token,
)
from clerk.services.refresh_tokens import (
    RefreshError,
    issue_session_pair,
    revoke_all_refresh_sessions,
    revoke_refresh_token,
    rotate_refresh_token,
    staff_role,
)
from clerk.services.staff_auth import authenticate, hash_password, staff_user_out, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _require_auth_secret(request: Request) -> None:
    if not request.app.state.settings.clerk_auth_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CLERK_AUTH_SECRET is not set.",
        )


def _token_out_from_pair(pair: object) -> TokenOut:
    from clerk.services.refresh_tokens import SessionPair

    if not isinstance(pair, SessionPair):
        raise TypeError("Expected SessionPair")
    return TokenOut(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        username=pair.username,
        role=pair.role,
    )


def _complete_login(request: Request, user: object, username: str) -> TokenOut:
    from clerk.repositories.models import StaffUserRow

    if not isinstance(user, StaffUserRow):
        raise TypeError("Expected StaffUserRow")
    settings = request.app.state.settings
    if user.mfa_enabled_at is not None:
        return TokenOut(
            username=username,
            role=staff_role(user),
            mfa_required=True,
            mfa_token=issue_mfa_challenge_token(settings, username),
        )
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    pair = issue_session_pair(db_factory, settings, user=user)
    return _token_out_from_pair(pair)


@router.post("/login", response_model=TokenOut)
async def login(
    payload: LoginIn,
    request: Request,
    _: LoginRateLimitDep,
) -> TokenOut:
    _require_auth_secret(request)
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    await assert_login_not_locked(request, payload.username)
    with db_factory() as session:
        user_out = authenticate(session, username=payload.username, password=payload.password)
    if user_out is None:
        await record_login_outcome(request, username=payload.username, success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )
    with db_factory() as session:
        row = StaffRepository(session).get_by_username(user_out.username)
    if row is None or not row.active:
        await record_login_outcome(request, username=payload.username, success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )
    token = _complete_login(request, row, row.username)
    if token.mfa_required:
        return token
    await record_login_outcome(request, username=row.username, success=True)
    return token


@router.post("/login/mfa", response_model=TokenOut)
async def login_mfa(
    payload: MfaLoginRequest,
    request: Request,
    _: LoginRateLimitDep,
) -> TokenOut:
    _require_auth_secret(request)
    settings = request.app.state.settings
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    username = verify_mfa_challenge_token(settings, payload.mfa_token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="That sign-in step expired. Enter your password again.",
        )
    await assert_login_not_locked(request, username)
    with db_factory() as session:
        user = StaffRepository(session).get_by_username(username)
    if user is None or not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="That sign-in step expired. Enter your password again.",
        )
    if user.mfa_enabled_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticator is not on for this account.",
        )
    try:
        accept_second_factor(
            db_factory,
            settings,
            username=username,
            code=payload.code,
        )
    except MfaRejected as exc:
        await record_login_outcome(request, username=username, success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except MfaAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await record_login_outcome(request, username=username, success=True)
    pair = issue_session_pair(db_factory, settings, user=user)
    return _token_out_from_pair(pair)


@router.post("/refresh", response_model=TokenOut)
async def refresh_session(
    payload: RefreshTokenRequest,
    request: Request,
    _: RefreshRateLimitDep,
) -> TokenOut:
    _require_auth_secret(request)
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    try:
        pair = rotate_refresh_token(
            db_factory,
            request.app.state.settings,
            raw_refresh_token=payload.refresh_token,
        )
    except RefreshError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    return _token_out_from_pair(pair)


@router.post("/logout", response_model=MessageOut)
async def logout_session(
    payload: RefreshTokenRequest,
    request: Request,
) -> MessageOut:
    _require_auth_secret(request)
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    revoke_refresh_token(db_factory, raw_refresh_token=payload.refresh_token)
    return MessageOut(message="Signed out.")


@router.get("/me", response_model=MeOut)
async def me(staff: StaffDep, request: Request) -> MeOut:
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    with db_factory() as session:
        row = StaffRepository(session).get_by_id(staff.user_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    return MeOut(user=staff_user_out(row), mfa_enabled=staff.mfa_enabled)


@router.post("/forgot-password", response_model=MessageOut)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    _: ForgotPasswordRateLimitDep,
) -> MessageOut:
    _require_auth_secret(request)
    result = await request_password_reset(
        request.app.state.db_factory,
        request.app.state.settings,
        username=payload.username,
    )
    return MessageOut(message=result.message, dev_reset_token=result.dev_reset_token)


@router.post("/reset-password", response_model=MessageOut)
async def reset_password_route(
    payload: ResetPasswordRequest,
    request: Request,
    _: LoginRateLimitDep,
) -> MessageOut:
    _require_auth_secret(request)
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    try:
        username = reset_password_with_token(
            db_factory,
            raw_token=payload.token,
            new_password=payload.password,
        )
    except ResetAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    with db_factory() as session:
        row = StaffRepository(session).get_by_username(username)
    if row is not None:
        revoke_all_refresh_sessions(db_factory, user_id=row.id)
    await clear_login_lockout(request, username)
    return MessageOut(message="Password updated. You can sign in with the new password.")


@router.post("/profile/email", response_model=StaffUserOut)
async def update_email(
    payload: UpdateEmailRequest,
    request: Request,
    staff: StaffDep,
) -> StaffUserOut:
    normalized = payload.email.strip().lower()
    if not normalized or "@" not in normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email.")
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    with db_factory() as session:
        repo = StaffRepository(session)
        row = repo.get_by_id(staff.user_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated.",
            )
        existing = repo.get_by_email(normalized)
        if existing is not None and existing.id != row.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That email is in use.",
            )
        row.email = normalized
        session.commit()
        return staff_user_out(row)


@router.post("/change-password", response_model=MessageOut)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    staff: StaffDep,
) -> MessageOut:
    _require_auth_secret(request)
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    with db_factory() as session:
        row = StaffRepository(session).get_by_id(staff.user_id)
        if row is None or not verify_password(payload.current_password, row.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password did not match.",
            )
        row.password_hash = hash_password(payload.new_password)
        session.commit()
    revoke_all_refresh_sessions(db_factory, user_id=staff.user_id)
    await clear_login_lockout(request, staff.username)
    return MessageOut(message="Password updated. Sign in again on other devices.")


@router.post("/mfa/setup", response_model=MfaSetupOut)
async def mfa_setup(
    payload: MfaSetupRequest,
    request: Request,
    staff: StaffDep,
) -> MfaSetupOut:
    _require_auth_secret(request)
    try:
        setup = begin_mfa_setup(
            request.app.state.db_factory,
            request.app.state.settings,
            username=staff.username,
            password=payload.password,
        )
    except MfaRejected as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except MfaAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MfaSetupOut(
        secret=setup.secret,
        otpauth_uri=setup.otpauth_uri,
        qr_data_uri=setup.qr_data_uri,
    )


@router.post("/mfa/confirm", response_model=MfaConfirmOut)
async def mfa_confirm(
    payload: MfaCodeRequest,
    request: Request,
    staff: StaffDep,
) -> MfaConfirmOut:
    _require_auth_secret(request)
    try:
        codes = confirm_mfa_setup(
            request.app.state.db_factory,
            request.app.state.settings,
            username=staff.username,
            code=payload.code,
        )
    except (MfaRejected, MfaAuthError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    revoke_all_refresh_sessions(request.app.state.db_factory, user_id=staff.user_id)
    return MfaConfirmOut(recovery_codes=codes)


@router.post("/mfa/disable", response_model=MessageOut)
async def mfa_disable(
    payload: MfaDisableRequest,
    request: Request,
    staff: StaffDep,
) -> MessageOut:
    _require_auth_secret(request)
    try:
        disable_mfa(
            request.app.state.db_factory,
            request.app.state.settings,
            username=staff.username,
            password=payload.password,
            code=payload.code,
        )
    except (MfaRejected, MfaAuthError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    revoke_all_refresh_sessions(request.app.state.db_factory, user_id=staff.user_id)
    return MessageOut(message="Authenticator turned off.")


@router.post("/mfa/recovery-codes/regenerate", response_model=MfaConfirmOut)
async def mfa_regenerate_recovery_codes(
    payload: MfaDisableRequest,
    request: Request,
    staff: StaffDep,
) -> MfaConfirmOut:
    _require_auth_secret(request)
    try:
        codes = regenerate_recovery_codes(
            request.app.state.db_factory,
            request.app.state.settings,
            username=staff.username,
            password=payload.password,
            code=payload.code,
        )
    except (MfaRejected, MfaAuthError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MfaConfirmOut(recovery_codes=codes)

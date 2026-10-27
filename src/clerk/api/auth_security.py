import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from clerk.services.auth_rate_limit import (
    AuthRateLimiter,
    RateLimiterUnavailable,
    RateLimitExceeded,
)
from clerk.services.login_lockout import (
    AccountLocked,
    LoginLockout,
    LoginLockoutUnavailable,
)

logger = logging.getLogger("clerk.auth_security")


def _client_ip(request: Request) -> str:
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


def _get_auth_rate_limiter(request: Request) -> AuthRateLimiter | None:
    limiter = getattr(request.app.state, "auth_rate_limiter", None)
    if limiter is None:
        return None
    if not isinstance(limiter, AuthRateLimiter):
        raise RuntimeError("Auth rate limiter is misconfigured.")
    return limiter


def _get_login_lockout(request: Request) -> LoginLockout | None:
    lockout = getattr(request.app.state, "login_lockout", None)
    if lockout is None:
        return None
    if not isinstance(lockout, LoginLockout):
        raise RuntimeError("Login lockout is misconfigured.")
    return lockout


async def enforce_login_rate_limit(request: Request) -> None:
    await _enforce_bucket(request, subject=_client_ip(request), bucket="login")


async def enforce_refresh_rate_limit(request: Request) -> None:
    await _enforce_bucket(request, subject=_client_ip(request), bucket="refresh")


async def _enforce_bucket(request: Request, *, subject: str, bucket: str) -> None:
    settings = request.app.state.settings
    if not settings.rate_limit_enabled:
        return
    limiter = _get_auth_rate_limiter(request)
    if limiter is None:
        if settings.rate_limit_fail_closed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Rate limiting requires Redis. Start Redis or set "
                    "RATE_LIMIT_FAIL_CLOSED=false for local use without Redis."
                ),
            )
        return
    try:
        await limiter.hit(subject=subject, bucket=bucket)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=exc.detail,
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except RateLimiterUnavailable as exc:
        logger.warning("auth rate limiter unavailable")
        if settings.rate_limit_fail_closed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Rate limiting requires Redis. Start Redis or set "
                    "RATE_LIMIT_FAIL_CLOSED=false for local use without Redis."
                ),
            ) from exc


async def assert_login_not_locked(request: Request, username: str) -> None:
    settings = request.app.state.settings
    if not settings.login_lockout_enabled:
        return
    lockout = _get_login_lockout(request)
    if lockout is None:
        if settings.login_lockout_fail_closed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Login lockout requires Redis. Start Redis or set "
                    "LOGIN_LOCKOUT_ENABLED=false for local use without lockout."
                ),
            )
        return
    try:
        await lockout.assert_not_locked(username)
    except AccountLocked as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=exc.detail,
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except LoginLockoutUnavailable as exc:
        logger.warning("login lockout unavailable mid-request")
        if settings.login_lockout_fail_closed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Login lockout requires Redis. Start Redis or set "
                    "LOGIN_LOCKOUT_ENABLED=false for local use without lockout."
                ),
            ) from exc


async def record_login_outcome(
    request: Request, *, username: str, success: bool
) -> None:
    settings = request.app.state.settings
    if not settings.login_lockout_enabled:
        return
    lockout = _get_login_lockout(request)
    if lockout is None:
        if settings.login_lockout_fail_closed and not success:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Login lockout requires Redis. Start Redis or set "
                    "LOGIN_LOCKOUT_ENABLED=false for local use without lockout."
                ),
            )
        return
    try:
        if success:
            await lockout.record_success(username)
            return
        locked = await lockout.record_failure(username)
        if locked:
            duration = max(1, settings.login_lockout_duration_seconds)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Too many failed login attempts for this account. "
                    f"Try again in {duration} seconds."
                ),
                headers={"Retry-After": str(duration)},
            )
    except LoginLockoutUnavailable as exc:
        logger.warning("login lockout unavailable recording outcome")
        if settings.login_lockout_fail_closed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Login lockout requires Redis. Start Redis or set "
                    "LOGIN_LOCKOUT_ENABLED=false for local use without lockout."
                ),
            ) from exc


async def clear_login_lockout(request: Request, username: str) -> None:
    settings = request.app.state.settings
    if not settings.login_lockout_enabled:
        return
    lockout = _get_login_lockout(request)
    if lockout is None:
        return
    try:
        await lockout.record_success(username)
    except LoginLockoutUnavailable:
        logger.warning("login lockout unavailable while clearing after password change")


LoginRateLimitDep = Annotated[None, Depends(enforce_login_rate_limit)]
RefreshRateLimitDep = Annotated[None, Depends(enforce_refresh_rate_limit)]

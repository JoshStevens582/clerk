from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_AUTH_SECRET = "dev-only-change-me"
MIN_AUTH_SECRET_BYTES = 32
UNSET_OPENAI_API_KEY_PLACEHOLDER = "openai-api-key-not-set"


class InsecureAuthSecretError(RuntimeError):
    """CLERK_AUTH_SECRET is missing a real value at startup."""


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    pages_dir: str = "./pages"
    database_url: str = "sqlite:///./data/clerk.db"
    cors_origins: str = "http://localhost:5175,http://127.0.0.1:5175"
    clerk_auth_secret: str = "dev-only-change-me"
    owner_password: str = "demo-owner"
    clerk_bootstrap_staff: str = ""
    clerk_admin_usernames: str = "owner"
    redis_url: str = "redis://127.0.0.1:6379/1"
    redis_required: bool = False
    access_token_ttl_seconds: int = 15 * 60
    refresh_token_ttl_seconds: int = 60 * 60 * 24 * 30
    mfa_challenge_ttl_seconds: int = 5 * 60
    rate_limit_enabled: bool = True
    rate_limit_fail_closed: bool = True
    rate_limit_window_seconds: int = 60
    rate_limit_login_per_minute: int = 10
    rate_limit_login_per_day: int = 100
    rate_limit_refresh_per_minute: int = 30
    rate_limit_refresh_per_day: int = 500
    login_lockout_enabled: bool = True
    login_lockout_fail_closed: bool = True
    login_lockout_max_failures: int = 5
    login_lockout_failure_window_seconds: int = 15 * 60
    login_lockout_duration_seconds: int = 15 * 60
    # Workflow / patient message caps (SQLite counters, separate from auth Redis limits)
    rate_limit_per_minute: int = 10
    rate_limit_per_day: int = 40
    rate_limit_global_per_day: int = 200
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def openai_configured(self) -> bool:
        key = self.openai_api_key.strip()
        return bool(key) and key != UNSET_OPENAI_API_KEY_PLACEHOLDER


def load_settings() -> Settings:
    return Settings()


def require_secure_auth_secret(settings: Settings) -> None:
    secret = settings.clerk_auth_secret
    if not secret:
        return
    if secret == INSECURE_DEFAULT_AUTH_SECRET:
        raise InsecureAuthSecretError(
            "CLERK_AUTH_SECRET is still the shipped default "
            f"({INSECURE_DEFAULT_AUTH_SECRET!r}). Set a random secret before production."
        )
    if len(secret.encode("utf-8")) < MIN_AUTH_SECRET_BYTES:
        raise InsecureAuthSecretError(
            f"CLERK_AUTH_SECRET is under {MIN_AUTH_SECRET_BYTES} bytes. "
            "Set a longer random secret before production."
        )

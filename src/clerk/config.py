from pydantic_settings import BaseSettings, SettingsConfigDict

UNSET_OPENAI_API_KEY_PLACEHOLDER = "openai-api-key-not-set"


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    pages_dir: str = "./pages"
    database_url: str = "sqlite:///./data/clerk.db"
    cors_origins: str = "http://localhost:5175,http://127.0.0.1:5175"
    session_secret: str = "change-me-in-production"
    # Deprecated: v1 single password. Used only to seed the first "owner" user when
    # clerk_bootstrap_staff is empty and the staff_users table is new.
    owner_password: str = "demo-owner"
    # Comma-separated "user:pass" or "user:pass:manager" entries for first boot.
    clerk_bootstrap_staff: str = ""
    # Usernames forced to manager role when present in clerk_bootstrap_staff.
    clerk_admin_usernames: str = "owner"
    session_cookie_name: str = "clerk_session"
    session_max_age_seconds: int = 60 * 60 * 12
    rate_limit_enabled: bool = True
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

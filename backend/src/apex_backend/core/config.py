"""Application configuration loaded from environment variables.

All configuration is read from the environment so that no secret is ever
hard-coded in the source tree. Nothing in this module is exposed to the
browser: the frontend only ever receives the public Supabase values.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the APEX backend.

    Values are read from the process environment and from an optional
    ``.env`` file located in the repository root or the backend folder.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Server ---
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    reload: bool = Field(default=True)

    # --- CORS ---
    # Comma separated list of allowed browser origins.
    cors_origins: str = Field(default="http://localhost:3000")

    # --- Database ---
    # Optional. When empty, database-backed features are disabled.
    database_url: str = Field(default="", repr=False)

    # --- Supabase (used to verify incoming access tokens) ---
    supabase_url: str = Field(default="")
    supabase_anon_key: str = Field(default="")
    # Optional. When set, tokens are verified offline instead of via a
    # network call to Supabase Auth. Leave empty for hosted Supabase projects.
    supabase_jwt_secret: str = Field(default="")

    @field_validator("reload", mode="before")
    @classmethod
    def _parse_bool(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return value

    @property
    def allowed_origins(self) -> list[str]:
        """Origins that CORS middleware is allowed to trust."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def supabase_is_configured(self) -> bool:
        """True when the backend can actually verify access tokens."""
        return bool(self.supabase_url and self.supabase_anon_key)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Cached so that environment parsing happens once per process instead of
    on every request.
    """
    return Settings()
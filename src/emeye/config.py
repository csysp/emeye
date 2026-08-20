# SPDX-License-Identifier: AGPL-3.0-or-later
"""Single source of environment truth.

Nothing else in this codebase reads ``os.environ``. If a value comes from the
environment, it is declared here, documented in ``.env.example``, and reached
through :func:`get_settings`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, loaded from the environment and ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="EMEYE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- Database ---------------------------------------------------------
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "emeye"
    postgres_user: str = "emeye"
    postgres_password: SecretStr  # no default: a missing value must fail loudly

    # -- HTTP politeness --------------------------------------------------
    # Required, no default. The collection posture in CLAUDE.md commits us to
    # identifying honestly, and a default would let that quietly go unset.
    user_agent: str
    default_rate_limit_per_sec: float = 1.0
    http_timeout_seconds: float = 30.0
    max_retries: int = 5

    # -- Paths ------------------------------------------------------------
    data_dir: Path = Path("/data")
    export_dir: Path = Path("/data/exports")

    # -- Source enable flags ----------------------------------------------
    # All default False. Merging a collector must never start collection;
    # enabling one is a deliberate act by the owner.
    enable_beatport: bool = False
    enable_musicbrainz: bool = False
    enable_discogs: bool = False
    enable_deezer: bool = False
    enable_lastfm: bool = False
    enable_listenbrainz: bool = False
    enable_spotify: bool = False

    # -- Source credentials -----------------------------------------------
    discogs_token: SecretStr | None = None
    lastfm_api_key: SecretStr | None = None
    spotify_client_id: str | None = None
    spotify_client_secret: SecretStr | None = None

    # -- Logging ----------------------------------------------------------
    log_level: str = "INFO"
    log_json: bool | None = Field(
        default=None,
        description="Force JSON logs. None auto-detects: text on a TTY, JSON otherwise.",
    )
    service_name: str = "emeye"

    @field_validator(
        "log_json",
        "discogs_token",
        "lastfm_api_key",
        "spotify_client_id",
        "spotify_client_secret",
        mode="before",
    )
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        """Treat an empty environment variable as absent.

        ``.env`` files and Compose both routinely pass ``KEY=`` for a value the
        user has not filled in yet. Without this, ``EMEYE_LOG_JSON=`` fails
        validation outright, and ``EMEYE_DISCOGS_TOKEN=`` becomes a
        ``SecretStr("")`` that is truthy — so a credential check would read an
        unset token as present.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def database_url(self) -> str:
        """SQLAlchemy URL for the warehouse.

        Deliberately a plain property, not a ``computed_field``: a computed
        field is included in ``repr()`` and ``model_dump()``, which would put
        the plaintext password into any log line or dump of this object.
        """
        return (
            f"postgresql+psycopg://{self.postgres_user}:"
            f"{self.postgres_password.get_secret_value()}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, constructed once."""
    return Settings()  # type: ignore[call-arg]

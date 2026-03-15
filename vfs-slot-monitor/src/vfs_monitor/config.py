"""Configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class CenterConfig(BaseModel):
    """Configuration for a single TLScontact visa center to monitor.

    TLScontact URL pattern:
      https://visas-{country_code}.tlscontact.com/visa/{from_country}/{issuer_id}/home
    Example:
      https://visas-fr.tlscontact.com/visa/gb/gbLON2fr/home
      https://visas-de.tlscontact.com/visa/gb/gbEDI2de/home

    The issuer_id encodes: {from_country}{city_code}2{destination_country}
    """

    country_code: str  # TLS country code in URL: "fr", "de", "nl", etc.
    country_name: str  # Display name: "France", "Germany", etc.
    from_country: str = "gb"  # Country you're applying FROM (default: UK)
    issuer_id: str = ""  # Full issuer ID, e.g., "gbLON2fr" (discovered via --discover)
    city: str = "London"  # City name for display
    enabled: bool = False


class PollingConfig(BaseModel):
    """Polling interval settings.

    TLScontact is more aggressive with anti-bot measures than VFS.
    Minimum recommended interval is 300 seconds (5 minutes).
    Some users report being blocked with intervals below 300s.
    """

    slot_check_interval_seconds: int = 300  # 5 minutes minimum recommended
    session_refresh_hours: float = 4.0  # Re-login every N hours
    error_backoff_base: int = 60  # Base seconds for exponential backoff
    error_backoff_max: int = 1800  # Max backoff (30 minutes)
    notification_cooldown_seconds: int = 300


class ProxyConfig(BaseModel):
    """Proxy rotation settings."""

    enabled: bool = False
    urls: list[str] = Field(default_factory=list)
    rotation: str = "round_robin"


class CaptchaConfig(BaseModel):
    """CAPTCHA solving service settings."""

    provider: str = "2captcha"
    enabled: bool = False


class BrowserConfig(BaseModel):
    """Browser automation settings.

    For TLScontact, headless mode is generally fine for slot checking,
    but discovery mode always runs with a visible browser.
    """

    headless: bool = True
    user_data_dir: str = ""  # Persist browser profile (cookies/session)


class EnvConfig(BaseSettings):
    """Secrets loaded from environment variables / .env file."""

    telegram_bot_token: str = ""
    telegram_admin_ids: str = ""
    tls_email: str = ""
    tls_password: str = ""
    captcha_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def admin_ids(self) -> list[int]:
        if not self.telegram_admin_ids:
            return []
        return [int(x.strip()) for x in self.telegram_admin_ids.split(",") if x.strip()]


class AppConfig(BaseModel):
    """Complete application configuration."""

    centers: list[CenterConfig] = Field(default_factory=list)
    polling: PollingConfig = Field(default_factory=PollingConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    captcha: CaptchaConfig = Field(default_factory=CaptchaConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    env: EnvConfig = Field(default_factory=EnvConfig)

    @property
    def enabled_centers(self) -> list[CenterConfig]:
        return [c for c in self.centers if c.enabled]


def load_config(config_path: str | None = None) -> AppConfig:
    """Load configuration from YAML file and environment variables."""
    if config_path is None:
        candidates = [
            Path("config/config.yaml"),
            Path("config.yaml"),
            Path("/app/config/config.yaml"),
        ]
        for candidate in candidates:
            if candidate.exists():
                config_path = str(candidate)
                break

    yaml_data = {}
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            yaml_data = yaml.safe_load(f) or {}

    env_file = Path(".env")
    if not env_file.exists():
        env_file = Path("/app/.env")

    env_config = EnvConfig(
        _env_file=str(env_file) if env_file.exists() else None,
    )
    yaml_data["env"] = env_config

    return AppConfig(**yaml_data)

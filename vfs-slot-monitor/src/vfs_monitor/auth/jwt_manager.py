"""JWT token lifecycle management.

Handles token storage, expiry detection, and triggers browser re-login
when the token needs refreshing.
"""

from __future__ import annotations

import asyncio
import base64
import datetime
import json
import time

import structlog

from vfs_monitor.auth.browser_login import login_and_get_jwt
from vfs_monitor.auth.captcha_solver import CaptchaSolver
from vfs_monitor.config import AppConfig

log = structlog.get_logger()


def _decode_jwt_expiry(token: str) -> datetime.datetime | None:
    """Decode the expiry time from a JWT token's payload."""
    try:
        payload = token.split(".")[1]
        # Add padding
        payload += "=" * (4 - len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        exp = data.get("exp")
        if exp:
            return datetime.datetime.utcfromtimestamp(exp)
    except Exception:
        pass
    return None


class JWTManager:
    """Manages the VFS Global JWT token lifecycle."""

    def __init__(self, config: AppConfig, captcha_solver: CaptchaSolver | None = None):
        self.config = config
        self.captcha_solver = captcha_solver
        self._token: str | None = None
        self._expiry: datetime.datetime | None = None
        self._last_refresh: float = 0
        self._consecutive_failures: int = 0
        self._lock = asyncio.Lock()
        self._refresh_callback: object | None = None

    @property
    def token(self) -> str | None:
        return self._token

    @property
    def is_valid(self) -> bool:
        if not self._token:
            return False
        if self._expiry:
            # Refresh 5 minutes before actual expiry
            buffer = datetime.timedelta(minutes=5)
            return datetime.datetime.utcnow() < (self._expiry - buffer)
        # If we can't determine expiry, use configured refresh interval
        elapsed = time.time() - self._last_refresh
        return elapsed < (self.config.polling.jwt_refresh_hours * 3600)

    @property
    def status_text(self) -> str:
        if not self._token:
            return "No token"
        if not self.is_valid:
            return "Expired"
        if self._expiry:
            remaining = self._expiry - datetime.datetime.utcnow()
            mins = int(remaining.total_seconds() / 60)
            return f"Valid ({mins}m remaining)"
        return "Valid"

    async def get_valid_token(self) -> str | None:
        """Get a valid JWT token, refreshing via browser if needed."""
        if self.is_valid:
            return self._token

        async with self._lock:
            # Double-check after acquiring lock
            if self.is_valid:
                return self._token
            return await self._refresh_token()

    async def _refresh_token(self) -> str | None:
        """Run browser login in a thread to get a fresh JWT."""
        log.info("jwt_refresh_starting", failures=self._consecutive_failures)

        # Run the synchronous browser login in a thread pool
        loop = asyncio.get_event_loop()
        country = "fra"  # Default country for login
        enabled = self.config.enabled_centers
        if enabled:
            country = enabled[0].country_code

        token = await loop.run_in_executor(
            None,
            login_and_get_jwt,
            self.config,
            country,
            self.captcha_solver,
        )

        if token:
            self._token = token
            self._expiry = _decode_jwt_expiry(token)
            self._last_refresh = time.time()
            self._consecutive_failures = 0
            log.info(
                "jwt_refresh_success",
                expiry=self._expiry.isoformat() if self._expiry else "unknown",
            )
            return token
        else:
            self._consecutive_failures += 1
            backoff = min(
                self.config.polling.error_backoff_base * (2 ** self._consecutive_failures),
                self.config.polling.error_backoff_max,
            )
            log.error(
                "jwt_refresh_failed",
                consecutive_failures=self._consecutive_failures,
                next_retry_seconds=backoff,
            )
            return None

    async def force_refresh(self) -> str | None:
        """Force a token refresh regardless of current validity."""
        self._token = None
        return await self.get_valid_token()

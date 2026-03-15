"""Browser session lifecycle management for TLScontact.

Unlike VFS Global which uses JWT tokens for a lightweight API, TLScontact
requires an active browser session for all slot checking. This manager
handles:
- Creating and maintaining the browser session
- Re-authentication when sessions expire
- Thread-safe access to the shared browser instance
"""

from __future__ import annotations

import asyncio
import time

import structlog

from vfs_monitor.auth.browser_login import (
    _is_logged_in,
    _save_debug_screenshot,
    check_slots_browser,
    login_to_tls,
)
from vfs_monitor.auth.captcha_solver import CaptchaSolver
from vfs_monitor.config import AppConfig, CenterConfig
from vfs_monitor.models import AppointmentSlot, CheckResult

log = structlog.get_logger()


class SessionManager:
    """Manages the TLScontact browser session lifecycle."""

    def __init__(self, config: AppConfig, captcha_solver: CaptchaSolver | None = None):
        self.config = config
        self.captcha_solver = captcha_solver
        self._driver = None
        self._last_login: float = 0
        self._consecutive_failures: int = 0
        self._lock = asyncio.Lock()

    @property
    def is_active(self) -> bool:
        """Check if we have an active browser session."""
        if not self._driver:
            return False
        try:
            # Check if the browser is still alive
            _ = self._driver.title
            return True
        except Exception:
            self._driver = None
            return False

    @property
    def status_text(self) -> str:
        if not self._driver:
            return "No session"
        if not self.is_active:
            return "Session crashed"
        elapsed = time.time() - self._last_login
        mins = int(elapsed / 60)
        return f"Active ({mins}m old)"

    async def ensure_session(self, center: CenterConfig) -> bool:
        """Ensure we have an active, authenticated browser session."""
        if self.is_active and self._is_session_fresh():
            return True

        async with self._lock:
            # Double-check after acquiring lock
            if self.is_active and self._is_session_fresh():
                return True
            return await self._login(center)

    def _is_session_fresh(self) -> bool:
        """Check if the session is still within the refresh window."""
        if self._last_login == 0:
            return False
        elapsed = time.time() - self._last_login
        max_age = self.config.polling.session_refresh_hours * 3600
        return elapsed < max_age

    async def _login(self, center: CenterConfig) -> bool:
        """Create a new browser session via login."""
        log.info("session_login_starting", failures=self._consecutive_failures)

        # Close any existing driver
        self._close_driver()

        loop = asyncio.get_event_loop()
        driver = await loop.run_in_executor(
            None,
            login_to_tls,
            self.config,
            center,
            self.captcha_solver,
            None,  # headless - use config default
        )

        if driver:
            self._driver = driver
            self._last_login = time.time()
            self._consecutive_failures = 0
            log.info("session_login_success")
            return True
        else:
            self._consecutive_failures += 1
            backoff = min(
                self.config.polling.error_backoff_base * (2 ** self._consecutive_failures),
                self.config.polling.error_backoff_max,
            )
            log.error(
                "session_login_failed",
                consecutive_failures=self._consecutive_failures,
                next_retry_seconds=backoff,
            )
            return False

    async def check_slots(self, center: CenterConfig) -> CheckResult:
        """Check for available slots using the browser session."""
        start = time.monotonic()

        if not self.is_active:
            return CheckResult(
                country_code=center.country_code,
                country_name=center.country_name,
                center=center.city,
                success=False,
                error="No active browser session",
                response_time_ms=0,
            )

        loop = asyncio.get_event_loop()
        try:
            raw_slots = await loop.run_in_executor(
                None,
                check_slots_browser,
                self._driver,
                center,
            )

            elapsed_ms = (time.monotonic() - start) * 1000

            # Check if session expired during the check
            if not self.is_active:
                return CheckResult(
                    country_code=center.country_code,
                    country_name=center.country_name,
                    center=center.city,
                    success=False,
                    error="Session expired during check",
                    response_time_ms=elapsed_ms,
                )

            # Convert raw slot dicts to AppointmentSlot objects
            import datetime

            booking_url = f"https://visas-{center.country_code}.tlscontact.com"
            slots = []
            for raw in raw_slots:
                date_str = raw.get("date")
                if not date_str or date_str == "unknown":
                    continue
                try:
                    date = datetime.date.fromisoformat(date_str)
                except (ValueError, TypeError):
                    continue

                time_slots = []
                if raw.get("time"):
                    time_slots = [raw["time"]]

                slots.append(AppointmentSlot(
                    country_code=center.country_code,
                    country_name=center.country_name,
                    center=center.city,
                    date=date,
                    time_slots=time_slots,
                    is_prime=raw.get("is_prime", False),
                    booking_url=booking_url,
                ))

            log.info(
                "slot_check_complete",
                center=center.country_name,
                city=center.city,
                slots_found=len(slots),
                response_ms=round(elapsed_ms),
            )

            return CheckResult(
                country_code=center.country_code,
                country_name=center.country_name,
                center=center.city,
                slots=slots,
                success=True,
                response_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            log.error("slot_check_error", center=center.country_name, error=str(e))
            return CheckResult(
                country_code=center.country_code,
                country_name=center.country_name,
                center=center.city,
                success=False,
                error=str(e),
                response_time_ms=elapsed_ms,
            )

    async def force_refresh(self, center: CenterConfig) -> bool:
        """Force a session refresh regardless of current state."""
        self._close_driver()
        return await self.ensure_session(center)

    def _close_driver(self) -> None:
        """Safely close the browser driver."""
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    async def shutdown(self) -> None:
        """Clean up browser resources."""
        self._close_driver()
        log.info("session_manager_shutdown")

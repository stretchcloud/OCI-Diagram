"""Main application orchestrator.

Runs two concurrent async tasks:
1. Slot checking loop - uses browser to scrape TLScontact every 5+ minutes
2. Telegram bot - listens for user commands

Architecture difference from VFS Global:
- VFS had: JWT refresh loop + lightweight API polling (every 8s)
- TLS has: Browser session manager + browser-based scraping (every 300s+)

TLScontact doesn't expose a REST API, so every slot check requires
the browser to navigate to the appointment page and scrape the DOM.
"""

from __future__ import annotations

import asyncio
import random
import time

import structlog

from vfs_monitor.auth.captcha_solver import CaptchaSolver
from vfs_monitor.auth.session_manager import SessionManager
from vfs_monitor.checker.slot_differ import SlotDiffer
from vfs_monitor.config import AppConfig
from vfs_monitor.notifier.telegram_bot import TelegramNotifier
from vfs_monitor.storage.database import Database
from vfs_monitor.utils.proxy import ProxyRotator

log = structlog.get_logger()


class TLSMonitorApp:
    """Main application that coordinates all components."""

    def __init__(self, config: AppConfig):
        self.config = config
        self._running = False
        self._start_time = time.time()

        # Initialize components
        self.db = Database()
        self.proxy_rotator = ProxyRotator(config.proxy) if config.proxy.enabled else None

        captcha_solver = None
        if config.captcha.enabled and config.env.captcha_api_key:
            captcha_solver = CaptchaSolver(
                api_key=config.env.captcha_api_key,
                provider=config.captcha.provider,
            )

        self.session_manager = SessionManager(config, captcha_solver)
        self.slot_differ = SlotDiffer(
            cooldown_seconds=config.polling.notification_cooldown_seconds,
        )
        self.notifier = TelegramNotifier(config, self.db, self.session_manager)

        # Backoff tracking
        self._consecutive_errors = 0

    async def run(self) -> None:
        """Start all components and run until stopped."""
        self._running = True
        self._start_time = time.time()

        await self.db.initialize()
        log.info("database_initialized")

        enabled = self.config.enabled_centers
        if not enabled:
            log.error("no_centers_enabled", hint="Enable at least one center in config.yaml")
            return

        log.info(
            "tls_monitor_starting",
            centers=[f"{c.country_name} ({c.city})" for c in enabled],
            interval=self.config.polling.slot_check_interval_seconds,
        )

        # Establish initial browser session
        log.info("establishing_initial_session")
        first_center = enabled[0]
        session_ok = await self.session_manager.ensure_session(first_center)
        if not session_ok:
            log.error(
                "initial_session_failed",
                hint="Check TLS credentials in .env. Run with --login-test to debug.",
            )
            # Continue anyway - the check loop will retry

        # Start tasks concurrently
        tasks = [
            asyncio.create_task(self._checking_loop(), name="checking"),
            asyncio.create_task(self._start_telegram_bot(), name="telegram"),
        ]

        try:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
            for task in done:
                if task.exception():
                    log.error("task_crashed", task=task.get_name(), error=str(task.exception()))
        except asyncio.CancelledError:
            log.info("app_cancelled")
        finally:
            self._running = False
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.stop()

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._running = False
        await self.session_manager.shutdown()
        await self.notifier.stop()
        await self.db.close()
        log.info("tls_monitor_stopped")

    async def _start_telegram_bot(self) -> None:
        """Start the Telegram bot."""
        await self.notifier.start(self._start_time)
        while self._running:
            await asyncio.sleep(1)

    async def _checking_loop(self) -> None:
        """Main slot checking loop - uses browser to scrape TLScontact."""
        while self._running:
            for center in self.config.enabled_centers:
                if not self._running:
                    break

                # Ensure we have an active session
                session_ok = await self.session_manager.ensure_session(center)
                if not session_ok:
                    log.warning("session_not_available", center=center.country_name)
                    self._consecutive_errors += 1

                    if self._consecutive_errors == 5:
                        await self.notifier.send_admin_alert(
                            "5 consecutive session/check failures.\n"
                            f"Center: {center.country_name} ({center.city})\n"
                            "Check TLS credentials and browser configuration."
                        )
                    continue

                # Check for slots
                result = await self.session_manager.check_slots(center)
                await self.db.record_check(result)

                if result.success:
                    self._consecutive_errors = 0

                    if result.slots:
                        new_slots = self.slot_differ.get_new_slots(result.slots)
                        if new_slots:
                            log.info(
                                "new_slots_found",
                                center=center.country_name,
                                city=center.city,
                                count=len(new_slots),
                            )
                            await self.notifier.notify_new_slots(new_slots)
                else:
                    self._consecutive_errors += 1

                    if self._consecutive_errors == 5:
                        await self.notifier.send_admin_alert(
                            f"5 consecutive check failures.\n"
                            f"Last error: {result.error}\n"
                            f"Center: {center.country_name} ({center.city})"
                        )

                    # If session seems dead, force refresh
                    if result.error and "session" in result.error.lower():
                        log.info("forcing_session_refresh")
                        await self.session_manager.force_refresh(center)

                # Brief pause between centers
                if len(self.config.enabled_centers) > 1:
                    await asyncio.sleep(random.uniform(5, 15))

            # Check for force check request from Telegram /check command
            if getattr(self.notifier, "_force_check_requested", False):
                self.notifier._force_check_requested = False
                continue

            # Calculate next interval
            interval = self._next_interval()
            log.debug("next_check_in", seconds=round(interval, 1))
            await asyncio.sleep(interval)

    def _next_interval(self) -> float:
        """Calculate next checking interval with jitter and backoff."""
        base = self.config.polling.slot_check_interval_seconds

        if self._consecutive_errors > 0:
            backoff = min(
                self.config.polling.error_backoff_base * (2 ** self._consecutive_errors),
                self.config.polling.error_backoff_max,
            )
            return backoff + random.uniform(0, backoff * 0.1)

        # Add jitter (10-20% of base interval)
        jitter = base * random.uniform(0.1, 0.2)
        return base + jitter

    async def run_single_check(self) -> None:
        """Run a single check cycle (for --check-test mode)."""
        await self.db.initialize()

        first_center = self.config.enabled_centers[0] if self.config.enabled_centers else None
        if not first_center:
            log.error("no_centers_enabled")
            return

        session_ok = await self.session_manager.ensure_session(first_center)
        if not session_ok:
            log.error("session_failed")
            return

        for center in self.config.enabled_centers:
            result = await self.session_manager.check_slots(center)
            if result.success:
                log.info(
                    "check_result",
                    center=center.country_name,
                    city=center.city,
                    slots=len(result.slots),
                    response_ms=round(result.response_time_ms),
                )
                for slot in result.slots:
                    log.info(
                        "slot_found",
                        date=slot.date,
                        center=slot.center,
                        is_prime=slot.is_prime,
                    )
            else:
                log.error("check_failed", center=center.country_name, error=result.error)

        await self.session_manager.shutdown()
        await self.db.close()

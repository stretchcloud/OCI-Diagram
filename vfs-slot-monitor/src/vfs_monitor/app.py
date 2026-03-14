"""Main application orchestrator.

Runs three concurrent async tasks:
1. Slot polling loop - checks the VFS API every 5-10 seconds
2. JWT refresh loop - re-authenticates via browser every few hours
3. Telegram bot - listens for user commands
"""

from __future__ import annotations

import asyncio
import random
import time

import structlog

from vfs_monitor.auth.captcha_solver import CaptchaSolver
from vfs_monitor.auth.jwt_manager import JWTManager
from vfs_monitor.checker.api_client import VFSAPIClient
from vfs_monitor.checker.slot_differ import SlotDiffer
from vfs_monitor.config import AppConfig
from vfs_monitor.notifier.telegram_bot import TelegramNotifier
from vfs_monitor.storage.database import Database
from vfs_monitor.utils.proxy import ProxyRotator

log = structlog.get_logger()


class VFSMonitorApp:
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

        self.jwt_manager = JWTManager(config, captcha_solver)
        self.api_client = VFSAPIClient(
            vfs_email=config.env.vfs_email,
            proxy_rotator=self.proxy_rotator,
        )
        self.slot_differ = SlotDiffer(
            cooldown_seconds=config.polling.notification_cooldown_seconds,
        )
        self.notifier = TelegramNotifier(config, self.db, self.jwt_manager)

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
            "vfs_monitor_starting",
            centers=[c.country_name for c in enabled],
            interval=self.config.polling.slot_check_interval_seconds,
        )

        # Get initial JWT token
        log.info("obtaining_initial_jwt")
        token = await self.jwt_manager.get_valid_token()
        if not token:
            log.error(
                "initial_jwt_failed",
                hint="Check VFS credentials in .env. Run with --login-test to debug.",
            )
            # Continue anyway - the refresh loop will retry

        # Start all tasks concurrently
        tasks = [
            asyncio.create_task(self._polling_loop(), name="polling"),
            asyncio.create_task(self._jwt_refresh_loop(), name="jwt_refresh"),
            asyncio.create_task(self._start_telegram_bot(), name="telegram"),
        ]

        try:
            # Wait for any task to complete (which means it crashed or we're stopping)
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
        await self.notifier.stop()
        await self.db.close()
        log.info("vfs_monitor_stopped")

    async def _start_telegram_bot(self) -> None:
        """Start the Telegram bot."""
        await self.notifier.start(self._start_time)
        # Keep running until cancelled
        while self._running:
            await asyncio.sleep(1)

    async def _polling_loop(self) -> None:
        """Main slot checking loop - polls the API at configured intervals."""
        while self._running:
            token = self.jwt_manager.token
            if not token:
                log.warning("polling_skipped_no_token", hint="Waiting for JWT...")
                await asyncio.sleep(10)
                continue

            for center in self.config.enabled_centers:
                if not self._running:
                    break

                # Check if JWT is still valid
                if not self.jwt_manager.is_valid:
                    log.info("jwt_expired_during_polling")
                    break

                result = await self.api_client.check_slots(center, token)
                await self.db.record_check(result)

                if result.success:
                    self._consecutive_errors = 0

                    if result.slots:
                        new_slots = self.slot_differ.get_new_slots(result.slots)
                        if new_slots:
                            log.info(
                                "new_slots_found",
                                center=center.country_name,
                                count=len(new_slots),
                            )
                            await self.notifier.notify_new_slots(new_slots)
                else:
                    self._consecutive_errors += 1

                    # If auth expired, trigger refresh
                    if result.error and "401" in result.error:
                        log.info("triggering_jwt_refresh_due_to_401")
                        await self.jwt_manager.force_refresh()
                        break

                    # Alert admin on repeated failures
                    if self._consecutive_errors == 5:
                        await self.notifier.send_admin_alert(
                            f"5 consecutive check failures.\n"
                            f"Last error: {result.error}\n"
                            f"Center: {center.country_name}"
                        )

                # Brief pause between centers
                if len(self.config.enabled_centers) > 1:
                    await asyncio.sleep(random.uniform(1, 3))

            # Check for force check request from Telegram /check command
            if getattr(self.notifier, "_force_check_requested", False):
                self.notifier._force_check_requested = False
                continue  # Skip the sleep, run another check immediately

            # Calculate next interval
            interval = self._next_interval()
            log.debug("next_check_in", seconds=round(interval, 1))
            await asyncio.sleep(interval)

    def _next_interval(self) -> float:
        """Calculate next polling interval with jitter and backoff."""
        base = self.config.polling.slot_check_interval_seconds

        if self._consecutive_errors > 0:
            backoff = min(
                self.config.polling.error_backoff_base * (2 ** self._consecutive_errors),
                self.config.polling.error_backoff_max,
            )
            return backoff + random.uniform(0, backoff * 0.1)

        # Add small jitter (10-20% of base interval)
        jitter = base * random.uniform(0.1, 0.2)
        return base + jitter

    async def _jwt_refresh_loop(self) -> None:
        """Proactively refresh JWT before it expires."""
        refresh_interval = self.config.polling.jwt_refresh_hours * 3600

        while self._running:
            await asyncio.sleep(refresh_interval)

            if not self._running:
                break

            log.info("proactive_jwt_refresh")
            token = await self.jwt_manager.force_refresh()

            if not token:
                await self.notifier.send_admin_alert(
                    "JWT refresh failed. Slot monitoring may be interrupted.\n"
                    "Check browser login - CAPTCHAs or credential issues possible."
                )

    async def run_single_check(self) -> None:
        """Run a single check cycle (for --api-test mode)."""
        await self.db.initialize()

        token = await self.jwt_manager.get_valid_token()
        if not token:
            log.error("no_jwt_token")
            return

        for center in self.config.enabled_centers:
            result = await self.api_client.check_slots(center, token)
            if result.success:
                log.info(
                    "check_result",
                    center=center.country_name,
                    slots=len(result.slots),
                    response_ms=round(result.response_time_ms),
                )
                for slot in result.slots:
                    log.info("slot_found", date=slot.date, center=slot.center)
            else:
                log.error("check_failed", center=center.country_name, error=result.error)

        await self.db.close()

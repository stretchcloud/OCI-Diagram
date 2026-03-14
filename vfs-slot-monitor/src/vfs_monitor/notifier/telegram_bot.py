"""Telegram bot for subscriber management and slot notifications."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog
from telegram import Bot, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from vfs_monitor.models import AppointmentSlot
from vfs_monitor.notifier.message_formatter import (
    format_multi_slot_notification,
    format_slot_notification,
    format_status_message,
)
from vfs_monitor.storage.database import Database

if TYPE_CHECKING:
    from vfs_monitor.auth.jwt_manager import JWTManager
    from vfs_monitor.config import AppConfig

log = structlog.get_logger()


class TelegramNotifier:
    """Telegram bot that handles commands and sends slot notifications."""

    def __init__(
        self,
        config: AppConfig,
        db: Database,
        jwt_manager: JWTManager | None = None,
    ):
        self.config = config
        self.db = db
        self.jwt_manager = jwt_manager
        self.bot = Bot(token=config.env.telegram_bot_token)
        self._application = None
        self._start_time: float = 0

    async def start(self, start_time: float) -> None:
        """Initialize and start the Telegram bot polling."""
        self._start_time = start_time

        self._application = (
            ApplicationBuilder()
            .token(self.config.env.telegram_bot_token)
            .build()
        )

        self._application.add_handler(CommandHandler("start", self._cmd_start))
        self._application.add_handler(CommandHandler("subscribe", self._cmd_subscribe))
        self._application.add_handler(CommandHandler("unsubscribe", self._cmd_unsubscribe))
        self._application.add_handler(CommandHandler("status", self._cmd_status))
        self._application.add_handler(CommandHandler("check", self._cmd_check))
        self._application.add_handler(CommandHandler("help", self._cmd_help))

        await self._application.initialize()
        await self._application.start()
        if self._application.updater:
            await self._application.updater.start_polling(drop_pending_updates=True)

        log.info("telegram_bot_started")

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        if self._application:
            if self._application.updater:
                await self._application.updater.stop()
            await self._application.stop()
            await self._application.shutdown()
            log.info("telegram_bot_stopped")

    def _is_admin(self, chat_id: int) -> bool:
        """Check if the chat ID belongs to an admin."""
        admin_ids = self.config.env.admin_ids
        return not admin_ids or chat_id in admin_ids

    # --- Notification sending ---

    async def notify_new_slots(self, slots: list[AppointmentSlot]) -> int:
        """
        Send notifications for new slots to all subscribers.

        Returns the number of notifications sent.
        """
        if not slots:
            return 0

        subscribers = await self.db.get_active_subscribers()
        if not subscribers:
            log.debug("no_subscribers_to_notify")
            return 0

        # Group slots by country for cleaner notifications
        by_country: dict[str, list[AppointmentSlot]] = {}
        for slot in slots:
            key = f"{slot.country_code}:{slot.center}"
            by_country.setdefault(key, []).append(slot)

        sent = 0
        for group_slots in by_country.values():
            if len(group_slots) > 1:
                message = format_multi_slot_notification(group_slots)
            else:
                message = format_slot_notification(group_slots[0])

            for sub in subscribers:
                try:
                    await self.bot.send_message(
                        chat_id=sub["chat_id"],
                        text=message,
                        parse_mode="HTML",
                        disable_web_page_preview=False,
                    )
                    sent += 1
                    # Respect Telegram rate limits (1 msg/sec per chat)
                    await asyncio.sleep(0.05)
                except Exception as e:
                    log.error(
                        "notification_send_failed",
                        chat_id=sub["chat_id"],
                        error=str(e),
                    )

            # Record notifications in DB
            for slot in group_slots:
                await self.db.record_notification(slot)

        log.info("notifications_sent", count=sent, slots=len(slots))
        return sent

    async def send_admin_alert(self, message: str) -> None:
        """Send an alert message to all admin chat IDs."""
        for admin_id in self.config.env.admin_ids:
            try:
                await self.bot.send_message(
                    chat_id=admin_id,
                    text=f"\u26a0\ufe0f <b>Alert</b>\n\n{message}",
                    parse_mode="HTML",
                )
            except Exception as e:
                log.error("admin_alert_failed", admin_id=admin_id, error=str(e))

    # --- Command handlers ---

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat:
            return
        await update.effective_chat.send_message(
            "\U0001f44b <b>VFS Slot Monitor</b>\n\n"
            "I monitor VFS Global for Schengen visa appointment slots "
            "and notify you instantly when slots become available.\n\n"
            "<b>Commands:</b>\n"
            "/subscribe - Get notified when slots appear\n"
            "/unsubscribe - Stop notifications\n"
            "/status - Check monitor status\n"
            "/check - Force an immediate check\n"
            "/help - Show this help\n\n"
            "Use /subscribe to get started!",
            parse_mode="HTML",
        )

    async def _cmd_subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.effective_user:
            return

        chat_id = update.effective_chat.id
        if not self._is_admin(chat_id):
            await update.effective_chat.send_message(
                "\u274c You are not authorized. Contact the bot admin."
            )
            return

        username = update.effective_user.username
        await self.db.add_subscriber(chat_id, username)
        centers = [c.country_name for c in self.config.enabled_centers]
        await update.effective_chat.send_message(
            "\u2705 <b>Subscribed!</b>\n\n"
            f"You'll be notified when visa slots appear for:\n"
            + "\n".join(f"  \u2022 {c}" for c in centers)
            + "\n\nUse /unsubscribe to stop.",
            parse_mode="HTML",
        )
        log.info("subscriber_added", chat_id=chat_id, username=username)

    async def _cmd_unsubscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat:
            return
        removed = await self.db.remove_subscriber(update.effective_chat.id)
        if removed:
            await update.effective_chat.send_message(
                "\U0001f44b Unsubscribed. You won't receive any more notifications.\n"
                "Use /subscribe to re-subscribe."
            )
        else:
            await update.effective_chat.send_message("You weren't subscribed.")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat:
            return

        import time
        stats = await self.db.get_stats(hours=24)
        jwt_status = self.jwt_manager.status_text if self.jwt_manager else "N/A"
        centers = [c.country_name for c in self.config.enabled_centers]
        uptime = time.time() - self._start_time if self._start_time else 0

        message = format_status_message(stats, jwt_status, centers, uptime)
        await update.effective_chat.send_message(message, parse_mode="HTML")

    async def _cmd_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Force an immediate slot check (admin only)."""
        if not update.effective_chat:
            return
        if not self._is_admin(update.effective_chat.id):
            await update.effective_chat.send_message("\u274c Admin only command.")
            return
        await update.effective_chat.send_message(
            "\U0001f50d Forcing immediate check... Results will be sent as notifications."
        )
        # The actual check is triggered by setting a flag that app.py monitors
        # This is a simple approach - the main loop checks this flag
        self._force_check_requested = True

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat:
            return
        await update.effective_chat.send_message(
            "<b>Available Commands:</b>\n\n"
            "/subscribe - Start receiving slot notifications\n"
            "/unsubscribe - Stop notifications\n"
            "/status - Monitor health & statistics\n"
            "/check - Force immediate check (admin)\n"
            "/help - Show this help message",
            parse_mode="HTML",
        )

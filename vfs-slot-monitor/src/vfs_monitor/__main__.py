"""Entry point: python -m vfs_monitor"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys

from vfs_monitor.config import load_config
from vfs_monitor.utils.logging import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="vfs_monitor",
        description="VFS Global visa appointment slot monitor with Telegram notifications",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config.yaml (default: config/config.yaml)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    # Run modes
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Load and validate config, then exit",
    )
    mode.add_argument(
        "--login-test",
        action="store_true",
        help="Test browser login and JWT extraction",
    )
    mode.add_argument(
        "--api-test",
        action="store_true",
        help="Run a single API check cycle",
    )
    mode.add_argument(
        "--notify-test",
        action="store_true",
        help="Send a test notification to all subscribers",
    )
    mode.add_argument(
        "--discover",
        metavar="COUNTRY_CODE",
        help="Discover center codes for a country (e.g., --discover fra)",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)

    import structlog
    log = structlog.get_logger()

    # Load config
    try:
        config = load_config(args.config)
    except Exception as e:
        log.error("config_load_failed", error=str(e))
        sys.exit(1)

    # Dry run mode
    if args.dry_run:
        log.info("config_valid", centers=len(config.centers), enabled=len(config.enabled_centers))
        for c in config.enabled_centers:
            log.info("center", country=c.country_name, code=c.country_code)
        log.info("telegram_token_set", value=bool(config.env.telegram_bot_token))
        log.info("vfs_email_set", value=bool(config.env.vfs_email))
        sys.exit(0)

    # Login test mode
    if args.login_test:
        from vfs_monitor.auth.browser_login import login_and_get_jwt
        from vfs_monitor.auth.captcha_solver import CaptchaSolver

        solver = None
        if config.captcha.enabled and config.env.captcha_api_key:
            solver = CaptchaSolver(config.env.captcha_api_key, config.captcha.provider)

        country = config.enabled_centers[0].country_code if config.enabled_centers else "fra"
        jwt = login_and_get_jwt(config, country, solver)
        if jwt:
            log.info("login_test_success", token_length=len(jwt), prefix=jwt[:30])
        else:
            log.error("login_test_failed")
            sys.exit(1)
        sys.exit(0)

    # Discover mode
    if args.discover:
        from vfs_monitor.auth.browser_login import discover_center_codes

        result = discover_center_codes(config, args.discover)
        if result and result.get("requests"):
            log.info("discovery_complete", requests_found=len(result["requests"]))
        else:
            log.warning("discovery_no_results")
        sys.exit(0)

    # API test mode
    if args.api_test:
        from vfs_monitor.app import VFSMonitorApp

        app = VFSMonitorApp(config)
        asyncio.run(app.run_single_check())
        sys.exit(0)

    # Notify test mode
    if args.notify_test:
        import datetime
        from vfs_monitor.models import AppointmentSlot
        from vfs_monitor.storage.database import Database
        from vfs_monitor.notifier.telegram_bot import TelegramNotifier

        async def send_test():
            db = Database()
            await db.initialize()
            notifier = TelegramNotifier(config, db)
            await notifier.start(0)

            test_slot = AppointmentSlot(
                country_code="nld",
                country_name="Netherlands",
                center="London",
                date=datetime.date.today() + datetime.timedelta(days=7),
                slot_count=3,
                booking_url="https://visa.vfsglobal.com/gbr/en/nld/book-an-appointment",
            )
            sent = await notifier.notify_new_slots([test_slot])
            log.info("test_notification_sent", recipients=sent)

            await notifier.stop()
            await db.close()

        asyncio.run(send_test())
        sys.exit(0)

    # Normal run mode
    from vfs_monitor.app import VFSMonitorApp

    app = VFSMonitorApp(config)
    loop = asyncio.new_event_loop()

    def signal_handler():
        log.info("shutdown_signal_received")
        loop.create_task(app.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        loop.run_until_complete(app.run())
    except KeyboardInterrupt:
        log.info("keyboard_interrupt")
    finally:
        loop.close()


if __name__ == "__main__":
    main()

"""Tests for SQLite database operations."""

import datetime
import tempfile
from pathlib import Path

import pytest

from vfs_monitor.models import AppointmentSlot, CheckResult
from vfs_monitor.storage.database import Database


@pytest.fixture
async def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    database = Database(db_path)
    await database.initialize()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_add_subscriber(db):
    result = await db.add_subscriber(12345, "testuser")
    assert result is True

    subs = await db.get_active_subscribers()
    assert len(subs) == 1
    assert subs[0]["chat_id"] == 12345
    assert subs[0]["username"] == "testuser"


@pytest.mark.asyncio
async def test_remove_subscriber(db):
    await db.add_subscriber(12345, "testuser")
    result = await db.remove_subscriber(12345)
    assert result is True

    subs = await db.get_active_subscribers()
    assert len(subs) == 0


@pytest.mark.asyncio
async def test_resubscribe(db):
    await db.add_subscriber(12345, "testuser")
    await db.remove_subscriber(12345)
    await db.add_subscriber(12345, "testuser")

    subs = await db.get_active_subscribers()
    assert len(subs) == 1


@pytest.mark.asyncio
async def test_notification_dedup(db):
    slot = AppointmentSlot(
        country_code="fra",
        country_name="France",
        center="London",
        date=datetime.date(2026, 3, 20),
        booking_url="https://example.com",
    )

    # First notification
    was_notified = await db.was_recently_notified(slot, cooldown_seconds=300)
    assert was_notified is False

    await db.record_notification(slot)

    # Should now be recently notified
    was_notified = await db.was_recently_notified(slot, cooldown_seconds=300)
    assert was_notified is True


@pytest.mark.asyncio
async def test_record_check_and_stats(db):
    result = CheckResult(
        country_code="fra",
        country_name="France",
        center="London",
        success=True,
        response_time_ms=150.0,
    )
    await db.record_check(result)

    stats = await db.get_stats(hours=24)
    assert stats["total_checks"] == 1
    assert stats["successful_checks"] == 1
    assert stats["success_rate"] == 100.0


@pytest.mark.asyncio
async def test_stats_with_failures(db):
    for i in range(3):
        await db.record_check(CheckResult(
            country_code="fra", country_name="France",
            center="London", success=True, response_time_ms=100,
        ))
    await db.record_check(CheckResult(
        country_code="fra", country_name="France",
        center="London", success=False, error="timeout", response_time_ms=5000,
    ))

    stats = await db.get_stats(hours=24)
    assert stats["total_checks"] == 4
    assert stats["successful_checks"] == 3
    assert stats["success_rate"] == 75.0

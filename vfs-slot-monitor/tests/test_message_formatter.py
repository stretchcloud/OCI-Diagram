"""Tests for message formatting."""

import datetime

from vfs_monitor.models import AppointmentSlot
from vfs_monitor.notifier.message_formatter import (
    format_multi_slot_notification,
    format_slot_notification,
    format_status_message,
)


def _make_slot(**kwargs) -> AppointmentSlot:
    defaults = {
        "country_code": "nl",
        "country_name": "Netherlands",
        "center": "London",
        "date": datetime.date(2026, 3, 15),
        "booking_url": "https://visas-nl.tlscontact.com",
        "discovered_at": datetime.datetime(2026, 3, 14, 14, 32, 5),
    }
    defaults.update(kwargs)
    return AppointmentSlot(**defaults)


def test_single_slot_notification():
    slot = _make_slot(slot_count=3)
    msg = format_slot_notification(slot)

    assert "VISA SLOT AVAILABLE" in msg
    assert "Netherlands" in msg
    assert "London" in msg
    assert "15 March 2026" in msg
    assert "3 slot(s)" in msg
    assert "Book now" in msg
    assert "TLScontact" in msg
    assert "14:32:05 UTC" in msg


def test_slot_with_time_slots():
    slot = _make_slot(time_slots=["09:00", "10:30", "14:00"])
    msg = format_slot_notification(slot)
    assert "09:00" in msg
    assert "10:30" in msg


def test_prime_slot_indicated():
    slot = _make_slot(is_prime=True)
    msg = format_slot_notification(slot)
    assert "Prime" in msg


def test_multi_slot_notification():
    slots = [
        _make_slot(date=datetime.date(2026, 3, 15)),
        _make_slot(date=datetime.date(2026, 3, 17)),
        _make_slot(date=datetime.date(2026, 3, 20)),
    ]
    msg = format_multi_slot_notification(slots)
    assert "VISA SLOTS AVAILABLE" in msg
    assert "15 Mar 2026" in msg
    assert "17 Mar 2026" in msg
    assert "20 Mar 2026" in msg


def test_multi_slot_single_falls_back():
    slots = [_make_slot()]
    msg = format_multi_slot_notification(slots)
    assert "VISA SLOT AVAILABLE" in msg  # Singular


def test_status_message():
    stats = {
        "total_checks": 287,
        "successful_checks": 282,
        "success_rate": 98.2,
        "total_slots_found": 3,
        "avg_response_ms": 145.3,
        "last_check": "2026-03-14T14:30:00",
    }
    msg = format_status_message(stats, "Active (45m old)", ["Netherlands", "France"], 7200)

    assert "287 checks" in msg
    assert "98.2%" in msg
    assert "Active (45m old)" in msg
    assert "Netherlands" in msg
    assert "France" in msg
    assert "2h 0m" in msg
    assert "TLScontact" in msg

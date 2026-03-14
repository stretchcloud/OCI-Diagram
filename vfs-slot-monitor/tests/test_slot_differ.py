"""Tests for slot differ."""

import datetime

from vfs_monitor.checker.slot_differ import SlotDiffer
from vfs_monitor.models import AppointmentSlot


def _make_slot(country: str = "fra", center: str = "London", days_ahead: int = 7) -> AppointmentSlot:
    return AppointmentSlot(
        country_code=country,
        country_name="France",
        center=center,
        date=datetime.date.today() + datetime.timedelta(days=days_ahead),
        booking_url="https://example.com",
    )


def test_first_slots_are_all_new():
    differ = SlotDiffer(cooldown_seconds=300)
    slots = [_make_slot(days_ahead=i) for i in range(3)]
    new = differ.get_new_slots(slots)
    assert len(new) == 3


def test_same_slots_not_repeated():
    differ = SlotDiffer(cooldown_seconds=300)
    slots = [_make_slot(days_ahead=7)]

    new1 = differ.get_new_slots(slots)
    assert len(new1) == 1

    new2 = differ.get_new_slots(slots)
    assert len(new2) == 0


def test_different_slots_are_new():
    differ = SlotDiffer(cooldown_seconds=300)

    slots1 = [_make_slot(days_ahead=7)]
    new1 = differ.get_new_slots(slots1)
    assert len(new1) == 1

    slots2 = [_make_slot(days_ahead=14)]
    new2 = differ.get_new_slots(slots2)
    assert len(new2) == 1


def test_expired_slots_become_new_again():
    differ = SlotDiffer(cooldown_seconds=0)  # Instant expiry
    slots = [_make_slot(days_ahead=7)]

    new1 = differ.get_new_slots(slots)
    assert len(new1) == 1

    new2 = differ.get_new_slots(slots)
    assert len(new2) == 1  # Should be new again since cooldown is 0


def test_different_centers_tracked_separately():
    differ = SlotDiffer(cooldown_seconds=300)

    slot_london = _make_slot(center="London", days_ahead=7)
    slot_manchester = _make_slot(center="Manchester", days_ahead=7)

    new1 = differ.get_new_slots([slot_london])
    assert len(new1) == 1

    new2 = differ.get_new_slots([slot_manchester])
    assert len(new2) == 1


def test_summary():
    differ = SlotDiffer(cooldown_seconds=300)
    slots = [
        _make_slot(country="fra", days_ahead=7),
        _make_slot(country="fra", days_ahead=14),
        _make_slot(country="nld", days_ahead=7),
    ]
    differ.get_new_slots(slots)

    summary = differ.summary()
    assert summary["total_tracked"] == 3
    assert summary["by_country"]["fra"] == 2
    assert summary["by_country"]["nld"] == 1

"""Tests for VFS API client response parsing."""

import datetime

from vfs_monitor.checker.api_client import _parse_slots_response
from vfs_monitor.config import CenterConfig


def _center():
    return CenterConfig(
        country_code="nld",
        country_name="Netherlands",
        mission_code="nld",
        center_code="NLUK",
        visa_category_code="002",
        centers=["London"],
        enabled=True,
    )


def test_parse_list_of_date_strings():
    data = ["2026-03-15", "2026-03-17", "2026-03-20"]
    slots = _parse_slots_response(data, _center())
    assert len(slots) == 3
    assert slots[0].date == datetime.date(2026, 3, 15)
    assert slots[0].country_code == "nld"
    assert slots[0].center == "London"


def test_parse_list_of_objects():
    data = [
        {"date": "2026-03-15", "count": 3, "timeSlots": ["09:00", "10:30"]},
        {"date": "2026-03-17", "count": 1},
    ]
    slots = _parse_slots_response(data, _center())
    assert len(slots) == 2
    assert slots[0].slot_count == 3
    assert slots[0].time_slots == ["09:00", "10:30"]
    assert slots[1].slot_count == 1


def test_parse_wrapped_response():
    data = {"data": [{"date": "2026-03-15"}, {"date": "2026-03-17"}]}
    slots = _parse_slots_response(data, _center())
    assert len(slots) == 2


def test_parse_empty_list():
    slots = _parse_slots_response([], _center())
    assert len(slots) == 0


def test_parse_empty_dict():
    slots = _parse_slots_response({}, _center())
    assert len(slots) == 0


def test_parse_datetime_string():
    data = [{"appointmentDate": "2026-03-15T09:00:00"}]
    slots = _parse_slots_response(data, _center())
    assert len(slots) == 1
    assert slots[0].date == datetime.date(2026, 3, 15)


def test_parse_invalid_date_skipped():
    data = ["not-a-date", "2026-03-15"]
    slots = _parse_slots_response(data, _center())
    assert len(slots) == 1
    assert slots[0].date == datetime.date(2026, 3, 15)

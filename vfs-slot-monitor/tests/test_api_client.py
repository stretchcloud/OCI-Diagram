"""Tests for TLScontact browser-based slot checking.

Note: The actual browser-based slot checking (browser_login.py) requires
a running Chrome browser and cannot be unit-tested easily. These tests
cover the helper functions that can be tested in isolation.
"""

import datetime

from vfs_monitor.auth.browser_login import _extract_date_from_context


def test_extract_date_from_month_name():
    result = _extract_date_from_context("15", "March", "2026 Calendar")
    assert result == "2026-03-15"


def test_extract_date_from_abbreviated_month():
    result = _extract_date_from_context("7", "Jul slots", "2026")
    assert result == "2026-07-07"


def test_extract_date_no_month():
    result = _extract_date_from_context("15", "some text", "no month here")
    assert result is None


def test_extract_date_invalid_day():
    result = _extract_date_from_context("32", "February", "2026")
    assert result is None

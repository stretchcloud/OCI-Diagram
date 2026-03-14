"""Data models for VFS slot monitor."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field


@dataclass
class AppointmentSlot:
    """A single available appointment slot discovered from the VFS API."""

    country_code: str
    country_name: str
    center: str
    date: datetime.date
    time_slots: list[str] = field(default_factory=list)
    slot_count: int | None = None
    booking_url: str = ""
    discovered_at: datetime.datetime = field(default_factory=datetime.datetime.utcnow)

    @property
    def dedup_key(self) -> str:
        """Unique key for deduplication: (country, center, date)."""
        return f"{self.country_code}:{self.center}:{self.date.isoformat()}"


@dataclass
class CheckResult:
    """Result of a single slot check cycle."""

    country_code: str
    country_name: str
    center: str
    slots: list[AppointmentSlot] = field(default_factory=list)
    checked_at: datetime.datetime = field(default_factory=datetime.datetime.utcnow)
    success: bool = True
    error: str | None = None
    response_time_ms: float = 0.0

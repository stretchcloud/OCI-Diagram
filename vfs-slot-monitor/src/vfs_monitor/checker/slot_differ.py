"""Slot differ: detect newly appeared appointment slots.

Compares current check results against recently seen slots to identify
genuinely new availability, preventing notification spam.
"""

from __future__ import annotations

import datetime
from collections import defaultdict

from vfs_monitor.models import AppointmentSlot


class SlotDiffer:
    """Track seen slots and identify new ones."""

    def __init__(self, cooldown_seconds: int = 300):
        self.cooldown_seconds = cooldown_seconds
        # Map of dedup_key -> last seen timestamp
        self._seen: dict[str, datetime.datetime] = {}

    def get_new_slots(self, slots: list[AppointmentSlot]) -> list[AppointmentSlot]:
        """
        Filter slots to only those not seen within the cooldown period.

        Args:
            slots: All slots from the current check.

        Returns:
            Only genuinely new slots that haven't been seen recently.
        """
        now = datetime.datetime.utcnow()
        cutoff = now - datetime.timedelta(seconds=self.cooldown_seconds)
        new_slots = []

        for slot in slots:
            last_seen = self._seen.get(slot.dedup_key)
            if last_seen is None or last_seen < cutoff:
                new_slots.append(slot)

            # Update last seen time for all current slots
            self._seen[slot.dedup_key] = now

        # Cleanup old entries to prevent memory growth
        self._cleanup(cutoff)

        return new_slots

    def _cleanup(self, cutoff: datetime.datetime) -> None:
        """Remove entries older than the cutoff to prevent unbounded memory growth."""
        expired = [key for key, ts in self._seen.items() if ts < cutoff]
        for key in expired:
            del self._seen[key]

    def summary(self) -> dict:
        """Return a summary of currently tracked slots."""
        by_country: dict[str, int] = defaultdict(int)
        for key in self._seen:
            country = key.split(":")[0]
            by_country[country] += 1
        return {
            "total_tracked": len(self._seen),
            "by_country": dict(by_country),
        }

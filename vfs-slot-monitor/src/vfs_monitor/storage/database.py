"""SQLite storage for subscribers, slot history, and check logs."""

from __future__ import annotations

import datetime
from pathlib import Path

import aiosqlite

from vfs_monitor.models import AppointmentSlot, CheckResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS subscribers (
    chat_id INTEGER PRIMARY KEY,
    username TEXT,
    subscribed_at TEXT NOT NULL DEFAULT (datetime('now')),
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS slot_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    center TEXT NOT NULL,
    date TEXT NOT NULL,
    slot_count INTEGER,
    discovered_at TEXT NOT NULL,
    notified_at TEXT,
    dedup_key TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_slot_dedup ON slot_history(dedup_key, notified_at);

CREATE TABLE IF NOT EXISTS check_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    center TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    success INTEGER NOT NULL,
    slots_found INTEGER NOT NULL DEFAULT 0,
    response_time_ms REAL NOT NULL DEFAULT 0,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_check_log_time ON check_log(checked_at);
"""


class Database:
    """Async SQLite database for persistent state."""

    def __init__(self, db_path: str = "data/vfs_monitor.db"):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    # --- Subscribers ---

    async def add_subscriber(self, chat_id: int, username: str | None = None) -> bool:
        """Add a subscriber. Returns True if newly added."""
        assert self._db
        try:
            await self._db.execute(
                "INSERT INTO subscribers (chat_id, username) VALUES (?, ?)"
                " ON CONFLICT(chat_id) DO UPDATE SET active = 1, username = ?",
                (chat_id, username, username),
            )
            await self._db.commit()
            return True
        except Exception:
            return False

    async def remove_subscriber(self, chat_id: int) -> bool:
        assert self._db
        cursor = await self._db.execute(
            "UPDATE subscribers SET active = 0 WHERE chat_id = ?", (chat_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def get_active_subscribers(self) -> list[dict]:
        assert self._db
        cursor = await self._db.execute(
            "SELECT chat_id, username FROM subscribers WHERE active = 1"
        )
        rows = await cursor.fetchall()
        return [{"chat_id": row["chat_id"], "username": row["username"]} for row in rows]

    # --- Slot History ---

    async def was_recently_notified(self, slot: AppointmentSlot, cooldown_seconds: int) -> bool:
        """Check if we already notified about this slot recently."""
        assert self._db
        cutoff = (
            datetime.datetime.utcnow() - datetime.timedelta(seconds=cooldown_seconds)
        ).isoformat()
        cursor = await self._db.execute(
            "SELECT 1 FROM slot_history WHERE dedup_key = ? AND notified_at > ? LIMIT 1",
            (slot.dedup_key, cutoff),
        )
        return await cursor.fetchone() is not None

    async def record_notification(self, slot: AppointmentSlot) -> None:
        assert self._db
        now = datetime.datetime.utcnow().isoformat()
        await self._db.execute(
            "INSERT INTO slot_history (country_code, center, date, slot_count,"
            " discovered_at, notified_at, dedup_key) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                slot.country_code,
                slot.center,
                slot.date.isoformat(),
                slot.slot_count,
                slot.discovered_at.isoformat(),
                now,
                slot.dedup_key,
            ),
        )
        await self._db.commit()

    # --- Check Log ---

    async def record_check(self, result: CheckResult) -> None:
        assert self._db
        await self._db.execute(
            "INSERT INTO check_log (country_code, center, checked_at, success,"
            " slots_found, response_time_ms, error) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                result.country_code,
                result.center,
                result.checked_at.isoformat(),
                int(result.success),
                len(result.slots),
                result.response_time_ms,
                result.error,
            ),
        )
        await self._db.commit()

    async def get_stats(self, hours: int = 24) -> dict:
        """Get check statistics for the last N hours."""
        assert self._db
        cutoff = (
            datetime.datetime.utcnow() - datetime.timedelta(hours=hours)
        ).isoformat()

        cursor = await self._db.execute(
            "SELECT COUNT(*) as total, SUM(success) as successes,"
            " SUM(slots_found) as total_slots, AVG(response_time_ms) as avg_response"
            " FROM check_log WHERE checked_at > ?",
            (cutoff,),
        )
        row = await cursor.fetchone()

        cursor2 = await self._db.execute(
            "SELECT checked_at FROM check_log ORDER BY id DESC LIMIT 1"
        )
        last_row = await cursor2.fetchone()

        total = row["total"] if row["total"] else 0
        successes = row["successes"] if row["successes"] else 0

        return {
            "total_checks": total,
            "successful_checks": successes,
            "success_rate": (successes / total * 100) if total > 0 else 0,
            "total_slots_found": row["total_slots"] if row["total_slots"] else 0,
            "avg_response_ms": round(row["avg_response"] or 0, 1),
            "last_check": last_row["checked_at"] if last_row else None,
        }

"""Rich HTML message formatting for Telegram notifications."""

from __future__ import annotations

from vfs_monitor.models import AppointmentSlot

# Country code to flag emoji mapping
COUNTRY_FLAGS = {
    "fra": "\U0001f1eb\U0001f1f7",
    "nld": "\U0001f1f3\U0001f1f1",
    "ita": "\U0001f1ee\U0001f1f9",
    "deu": "\U0001f1e9\U0001f1ea",
    "esp": "\U0001f1ea\U0001f1f8",
    "prt": "\U0001f1f5\U0001f1f9",
    "grc": "\U0001f1ec\U0001f1f7",
    "che": "\U0001f1e8\U0001f1ed",
    "aut": "\U0001f1e6\U0001f1f9",
    "dnk": "\U0001f1e9\U0001f1f0",
    "swe": "\U0001f1f8\U0001f1ea",
    "nor": "\U0001f1f3\U0001f1f4",
    "fin": "\U0001f1eb\U0001f1ee",
    "bel": "\U0001f1e7\U0001f1ea",
    "pol": "\U0001f1f5\U0001f1f1",
    "cze": "\U0001f1e8\U0001f1ff",
    "hun": "\U0001f1ed\U0001f1fa",
}


def format_slot_notification(slot: AppointmentSlot) -> str:
    """Format a single slot as a rich HTML notification for Telegram."""
    flag = COUNTRY_FLAGS.get(slot.country_code, "\U0001f30d")
    date_str = slot.date.strftime("%A, %d %B %Y")

    lines = [
        "\U0001f514 <b>VISA SLOT AVAILABLE</b>",
        "",
        f"{flag} <b>{slot.country_name}</b> - Schengen Visa",
        f"\U0001f4cd {slot.center}",
        f"\U0001f4c5 {date_str}",
    ]

    if slot.slot_count is not None:
        lines.append(f"\U0001f552 {slot.slot_count} slot(s) available")

    if slot.time_slots:
        times = ", ".join(slot.time_slots[:5])
        if len(slot.time_slots) > 5:
            times += f" (+{len(slot.time_slots) - 5} more)"
        lines.append(f"\U0001f553 Times: {times}")

    lines.extend([
        "",
        f'\U0001f517 <a href="{slot.booking_url}">Book now on VFS Global</a>',
        "",
        f"\u23f0 Detected at {slot.discovered_at.strftime('%H:%M:%S UTC')}",
    ])

    return "\n".join(lines)


def format_multi_slot_notification(slots: list[AppointmentSlot]) -> str:
    """Format multiple slots (same country) into a single notification."""
    if not slots:
        return ""

    if len(slots) == 1:
        return format_slot_notification(slots[0])

    first = slots[0]
    flag = COUNTRY_FLAGS.get(first.country_code, "\U0001f30d")

    lines = [
        "\U0001f514 <b>VISA SLOTS AVAILABLE</b>",
        "",
        f"{flag} <b>{first.country_name}</b> - Schengen Visa",
        f"\U0001f4cd {first.center}",
        "",
    ]

    for slot in slots[:10]:
        date_str = slot.date.strftime("%d %b %Y")
        count = f" ({slot.slot_count} slots)" if slot.slot_count else ""
        lines.append(f"  \U0001f4c5 {date_str}{count}")

    if len(slots) > 10:
        lines.append(f"  ... and {len(slots) - 10} more dates")

    lines.extend([
        "",
        f'\U0001f517 <a href="{first.booking_url}">Book now on VFS Global</a>',
        "",
        f"\u23f0 Detected at {first.discovered_at.strftime('%H:%M:%S UTC')}",
    ])

    return "\n".join(lines)


def format_status_message(
    stats: dict,
    jwt_status: str,
    monitored_centers: list[str],
    uptime_seconds: float,
) -> str:
    """Format the /status command response."""
    hours = int(uptime_seconds // 3600)
    mins = int((uptime_seconds % 3600) // 60)

    lines = [
        "<b>VFS Slot Monitor Status</b>",
        "\u2500" * 30,
        "",
        f"\U0001f7e2 Uptime: {hours}h {mins}m",
        f"\U0001f512 JWT: {jwt_status}",
        "",
        f"\U0001f4ca Last 24h: {stats['total_checks']} checks, "
        f"{stats['success_rate']:.1f}% success",
        f"\u23f1 Avg response: {stats['avg_response_ms']}ms",
        f"\U0001f3af Slots found: {stats['total_slots_found']}",
    ]

    if stats["last_check"]:
        lines.append(f"\U0001f550 Last check: {stats['last_check']}")

    if monitored_centers:
        lines.extend(["", "\U0001f50d Monitoring:"])
        for center in monitored_centers:
            lines.append(f"  \u2022 {center}")

    return "\n".join(lines)

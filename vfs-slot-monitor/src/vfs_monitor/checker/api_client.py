"""Lightweight HTTP client for the VFS Global appointment slots API.

This is the hot path - runs every 5-10 seconds. Makes a single HTTP GET
request to the VFS slots API instead of a full browser page load.
"""

from __future__ import annotations

import datetime
import time

import httpx
import structlog

from vfs_monitor.config import CenterConfig
from vfs_monitor.models import AppointmentSlot, CheckResult
from vfs_monitor.utils.proxy import ProxyRotator

log = structlog.get_logger()

VFS_API_BASE = "https://lift-api.vfsglobal.com"
SLOTS_ENDPOINT = f"{VFS_API_BASE}/appointment/slots"


class VFSAPIClient:
    """Async HTTP client for the VFS Global slots API."""

    def __init__(
        self,
        vfs_email: str,
        proxy_rotator: ProxyRotator | None = None,
        timeout: float = 30.0,
    ):
        self.vfs_email = vfs_email
        self.proxy_rotator = proxy_rotator
        self.timeout = timeout

    async def check_slots(
        self,
        center: CenterConfig,
        jwt_token: str,
    ) -> CheckResult:
        """
        Query the VFS slots API for a specific center.

        Args:
            center: The center configuration to check.
            jwt_token: Valid JWT token from browser login.

        Returns:
            CheckResult with any discovered appointment slots.
        """
        start = time.monotonic()
        params = {
            "countryCode": "gbr",
            "missionCode": center.mission_code,
            "centerCode": center.center_code,
            "loginUser": self.vfs_email,
            "visaCategoryCode": center.visa_category_code,
            "languageCode": "en-US",
            "applicantsCount": "1",
            "days": "90",
            "slotType": "2",
        }
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/json",
            "Origin": "https://visa.vfsglobal.com",
            "Referer": f"https://visa.vfsglobal.com/gbr/en/{center.country_code}/book-an-appointment",
        }

        proxy = self.proxy_rotator.get_httpx_proxy() if self.proxy_rotator else None

        try:
            async with httpx.AsyncClient(
                proxy=proxy,
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(
                    SLOTS_ENDPOINT,
                    params=params,
                    headers=headers,
                )

            elapsed_ms = (time.monotonic() - start) * 1000

            if response.status_code == 401:
                log.warning("api_auth_expired", center=center.country_name)
                return CheckResult(
                    country_code=center.country_code,
                    country_name=center.country_name,
                    center=center.centers[0] if center.centers else "Unknown",
                    success=False,
                    error="JWT expired (401)",
                    response_time_ms=elapsed_ms,
                )

            if response.status_code == 429:
                log.warning("api_rate_limited", center=center.country_name)
                return CheckResult(
                    country_code=center.country_code,
                    country_name=center.country_name,
                    center=center.centers[0] if center.centers else "Unknown",
                    success=False,
                    error="Rate limited (429)",
                    response_time_ms=elapsed_ms,
                )

            if response.status_code != 200:
                log.warning(
                    "api_unexpected_status",
                    status=response.status_code,
                    center=center.country_name,
                    body=response.text[:200],
                )
                return CheckResult(
                    country_code=center.country_code,
                    country_name=center.country_name,
                    center=center.centers[0] if center.centers else "Unknown",
                    success=False,
                    error=f"HTTP {response.status_code}",
                    response_time_ms=elapsed_ms,
                )

            # Parse the response
            slots = _parse_slots_response(response.json(), center)

            log.info(
                "api_check_complete",
                center=center.country_name,
                slots_found=len(slots),
                response_ms=round(elapsed_ms),
            )

            return CheckResult(
                country_code=center.country_code,
                country_name=center.country_name,
                center=center.centers[0] if center.centers else "Unknown",
                slots=slots,
                success=True,
                response_time_ms=elapsed_ms,
            )

        except httpx.TimeoutException:
            elapsed_ms = (time.monotonic() - start) * 1000
            log.warning("api_timeout", center=center.country_name)
            return CheckResult(
                country_code=center.country_code,
                country_name=center.country_name,
                center=center.centers[0] if center.centers else "Unknown",
                success=False,
                error="Request timeout",
                response_time_ms=elapsed_ms,
            )
        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            log.error("api_check_error", center=center.country_name, error=str(e))
            return CheckResult(
                country_code=center.country_code,
                country_name=center.country_name,
                center=center.centers[0] if center.centers else "Unknown",
                success=False,
                error=str(e),
                response_time_ms=elapsed_ms,
            )


def _parse_slots_response(
    data: dict | list, center: CenterConfig
) -> list[AppointmentSlot]:
    """
    Parse the VFS API JSON response into AppointmentSlot objects.

    The exact response format may vary. Common patterns observed:
    - List of date strings with available slots
    - Object with date keys and slot counts
    - Nested structure with time slot details
    """
    slots: list[AppointmentSlot] = []
    booking_url = (
        f"https://visa.vfsglobal.com/gbr/en/{center.country_code}/book-an-appointment"
    )

    if isinstance(data, list):
        for item in data:
            slot = _parse_single_slot(item, center, booking_url)
            if slot:
                slots.append(slot)
    elif isinstance(data, dict):
        # Could be a wrapper with a data/slots key
        for key in ("data", "slots", "appointments", "availableDates"):
            if key in data and isinstance(data[key], list):
                for item in data[key]:
                    slot = _parse_single_slot(item, center, booking_url)
                    if slot:
                        slots.append(slot)
                break
        else:
            # Try treating the dict itself as slot data
            slot = _parse_single_slot(data, center, booking_url)
            if slot:
                slots.append(slot)

    return slots


def _parse_single_slot(
    item: dict | str, center: CenterConfig, booking_url: str
) -> AppointmentSlot | None:
    """Parse a single slot entry from the API response."""
    if isinstance(item, str):
        # Plain date string
        try:
            date = datetime.date.fromisoformat(item)
            return AppointmentSlot(
                country_code=center.country_code,
                country_name=center.country_name,
                center=center.centers[0] if center.centers else "Unknown",
                date=date,
                booking_url=booking_url,
            )
        except ValueError:
            return None

    if isinstance(item, dict):
        # Try various date field names
        date_str = None
        for key in ("date", "appointmentDate", "slotDate", "availableDate"):
            if key in item:
                date_str = item[key]
                break

        if not date_str:
            return None

        try:
            # Handle both date-only and datetime strings
            if "T" in str(date_str):
                date = datetime.date.fromisoformat(str(date_str).split("T")[0])
            else:
                date = datetime.date.fromisoformat(str(date_str))
        except ValueError:
            return None

        # Extract time slots if available
        time_slots = []
        for key in ("timeSlots", "times", "slots"):
            if key in item and isinstance(item[key], list):
                time_slots = [str(t) for t in item[key]]
                break

        # Extract slot count
        slot_count = None
        for key in ("count", "slotCount", "available", "numberOfSlots"):
            if key in item:
                try:
                    slot_count = int(item[key])
                except (ValueError, TypeError):
                    pass
                break

        return AppointmentSlot(
            country_code=center.country_code,
            country_name=center.country_name,
            center=center.centers[0] if center.centers else "Unknown",
            date=date,
            time_slots=time_slots,
            slot_count=slot_count,
            booking_url=booking_url,
        )

    return None

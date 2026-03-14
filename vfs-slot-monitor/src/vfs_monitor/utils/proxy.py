"""Optional proxy rotation for API calls."""

from __future__ import annotations

import random
from itertools import cycle

from vfs_monitor.config import ProxyConfig


class ProxyRotator:
    """Rotate through a list of proxy URLs."""

    def __init__(self, config: ProxyConfig):
        self.config = config
        self._proxies = config.urls[:]
        self._cycle = cycle(self._proxies) if self._proxies else None

    def get_next(self) -> str | None:
        """Return the next proxy URL, or None if proxies are disabled."""
        if not self.config.enabled or not self._proxies:
            return None

        if self.config.rotation == "random":
            return random.choice(self._proxies)

        if self._cycle:
            return next(self._cycle)
        return None

    def get_httpx_proxy(self) -> dict[str, str] | None:
        """Return a proxy dict suitable for httpx."""
        url = self.get_next()
        if url is None:
            return None
        return {"http://": url, "https://": url}

"""Optional CAPTCHA solving via 2captcha or anti-captcha services."""

from __future__ import annotations

import structlog
from twocaptcha import TwoCaptcha

log = structlog.get_logger()


class CaptchaSolver:
    """Solve CAPTCHAs using an external service."""

    def __init__(self, api_key: str, provider: str = "2captcha"):
        self.api_key = api_key
        self.provider = provider
        self._solver = TwoCaptcha(api_key) if api_key else None

    @property
    def available(self) -> bool:
        return self._solver is not None

    def solve_recaptcha(self, site_key: str, page_url: str) -> str | None:
        """Solve a reCAPTCHA v2 challenge. Returns the g-recaptcha-response token."""
        if not self._solver:
            log.warning("captcha_solver_unavailable", reason="no API key configured")
            return None
        try:
            log.info("captcha_solving", provider=self.provider, type="recaptcha_v2")
            result = self._solver.recaptcha(sitekey=site_key, url=page_url)
            token = result.get("code") if isinstance(result, dict) else str(result)
            log.info("captcha_solved", provider=self.provider)
            return token
        except Exception as e:
            log.error("captcha_solve_failed", provider=self.provider, error=str(e))
            return None

    def solve_image(self, image_path: str) -> str | None:
        """Solve an image-based CAPTCHA. Returns the text solution."""
        if not self._solver:
            log.warning("captcha_solver_unavailable", reason="no API key configured")
            return None
        try:
            log.info("captcha_solving", provider=self.provider, type="image")
            result = self._solver.normal(image_path)
            text = result.get("code") if isinstance(result, dict) else str(result)
            log.info("captcha_solved", provider=self.provider)
            return text
        except Exception as e:
            log.error("captcha_solve_failed", provider=self.provider, error=str(e))
            return None

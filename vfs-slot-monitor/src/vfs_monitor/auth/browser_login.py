"""Browser-based login to VFS Global using undetected-chromedriver.

This module handles the heavy lifting of authenticating with VFS Global
through a real browser. It runs infrequently (every few hours) to obtain
a fresh JWT token that the lightweight API poller uses.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

import structlog
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from vfs_monitor.auth.captcha_solver import CaptchaSolver
from vfs_monitor.config import AppConfig

log = structlog.get_logger()

VFS_BASE_URL = "https://visa.vfsglobal.com/gbr/en"

# Common screen resolutions to randomize
VIEWPORTS = [
    (1920, 1080),
    (1366, 768),
    (1536, 864),
    (1440, 900),
    (1280, 720),
]

# Recent Chrome User-Agent strings
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]


def _human_delay(min_ms: int = 500, max_ms: int = 2000) -> None:
    """Sleep for a random human-like duration."""
    time.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


def _human_type(element, text: str) -> None:
    """Type text with random inter-key delays to mimic human typing."""
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))


def _create_driver(config: AppConfig) -> uc.Chrome:
    """Create an undetected Chrome browser instance."""
    options = uc.ChromeOptions()

    width, height = random.choice(VIEWPORTS)
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument("--lang=en-GB")
    options.add_argument("--disable-blink-features=AutomationControlled")

    if config.browser.headless:
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

    if config.proxy.enabled and config.proxy.urls:
        proxy_url = random.choice(config.proxy.urls)
        options.add_argument(f"--proxy-server={proxy_url}")

    if config.browser.user_data_dir:
        options.add_argument(f"--user-data-dir={config.browser.user_data_dir}")

    driver = uc.Chrome(options=options, version_main=None)
    driver.execute_cdp_cmd(
        "Network.setUserAgentOverride",
        {"userAgent": random.choice(USER_AGENTS)},
    )

    return driver


def _extract_jwt_from_storage(driver: uc.Chrome) -> str | None:
    """Try to extract JWT from localStorage, sessionStorage, or cookies."""
    # Try localStorage
    try:
        local_storage = driver.execute_script(
            "return Object.entries(localStorage).reduce((a, [k, v]) => ({...a, [k]: v}), {});"
        )
        for key, value in local_storage.items():
            if "token" in key.lower() or "jwt" in key.lower() or "auth" in key.lower():
                # Could be a raw token or JSON with a token field
                if value.startswith("eyJ"):
                    return value
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, dict):
                        for v in parsed.values():
                            if isinstance(v, str) and v.startswith("eyJ"):
                                return v
                except (json.JSONDecodeError, TypeError):
                    pass
    except Exception as e:
        log.debug("localstorage_extraction_failed", error=str(e))

    # Try sessionStorage
    try:
        session_storage = driver.execute_script(
            "return Object.entries(sessionStorage).reduce((a, [k, v]) => ({...a, [k]: v}), {});"
        )
        for key, value in session_storage.items():
            if "token" in key.lower() or "jwt" in key.lower() or "auth" in key.lower():
                if value.startswith("eyJ"):
                    return value
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, dict):
                        for v in parsed.values():
                            if isinstance(v, str) and v.startswith("eyJ"):
                                return v
                except (json.JSONDecodeError, TypeError):
                    pass
    except Exception as e:
        log.debug("sessionstorage_extraction_failed", error=str(e))

    # Try cookies
    try:
        cookies = driver.get_cookies()
        for cookie in cookies:
            if "token" in cookie["name"].lower() or "jwt" in cookie["name"].lower():
                value = cookie["value"]
                if value.startswith("eyJ"):
                    return value
    except Exception as e:
        log.debug("cookie_extraction_failed", error=str(e))

    return None


def _intercept_jwt_via_network(driver: uc.Chrome) -> str | None:
    """Try to capture JWT from network request logs (CDP)."""
    try:
        logs = driver.get_log("performance")
        for entry in logs:
            try:
                msg = json.loads(entry["message"])
                if msg.get("message", {}).get("method") == "Network.requestWillBeSent":
                    headers = (
                        msg["message"]["params"].get("request", {}).get("headers", {})
                    )
                    auth = headers.get("Authorization", "")
                    if auth.startswith("Bearer eyJ"):
                        return auth.replace("Bearer ", "")
            except (json.JSONDecodeError, KeyError):
                continue
    except Exception as e:
        log.debug("network_log_extraction_failed", error=str(e))

    return None


def login_and_get_jwt(
    config: AppConfig,
    country_code: str = "fra",
    captcha_solver: CaptchaSolver | None = None,
) -> str | None:
    """
    Log in to VFS Global and extract the JWT token.

    Args:
        config: Application configuration.
        country_code: Country code for the login URL.
        captcha_solver: Optional CAPTCHA solver instance.

    Returns:
        JWT token string, or None if login failed.
    """
    driver = None
    try:
        log.info("browser_login_starting", country=country_code)
        driver = _create_driver(config)

        # Enable performance logging for JWT interception
        driver.execute_cdp_cmd("Network.enable", {})

        # Navigate to the appointment page
        url = f"{VFS_BASE_URL}/{country_code}/book-an-appointment"
        driver.get(url)
        _human_delay(2000, 4000)

        # Wait for and click the login/sign-in button or find the login form
        wait = WebDriverWait(driver, 30)

        # Try to find email input field (various possible selectors)
        email_selectors = [
            "input[type='email']",
            "input[id*='email']",
            "input[name*='email']",
            "#mat-input-0",
            "input[formcontrolname='username']",
        ]

        email_field = None
        for selector in email_selectors:
            try:
                email_field = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if email_field:
                    break
            except Exception:
                continue

        if not email_field:
            _save_debug_screenshot(driver, "no_email_field")
            log.error("login_failed", reason="could not find email input field")
            return None

        # Type credentials with human-like delays
        _human_delay(500, 1000)
        email_field.click()
        _human_delay(200, 500)
        _human_type(email_field, config.env.vfs_email)
        _human_delay(300, 800)

        # Find password field
        password_selectors = [
            "input[type='password']",
            "input[id*='password']",
            "input[name*='password']",
            "#mat-input-1",
            "input[formcontrolname='password']",
        ]

        password_field = None
        for selector in password_selectors:
            try:
                password_field = driver.find_element(By.CSS_SELECTOR, selector)
                if password_field:
                    break
            except Exception:
                continue

        if not password_field:
            _save_debug_screenshot(driver, "no_password_field")
            log.error("login_failed", reason="could not find password input field")
            return None

        password_field.click()
        _human_delay(200, 500)
        _human_type(password_field, config.env.vfs_password)
        _human_delay(500, 1000)

        # Handle CAPTCHA if present
        _handle_captcha(driver, captcha_solver, url)

        # Click submit button
        submit_selectors = [
            "button[type='submit']",
            "button.mat-raised-button",
            "button[class*='sign']",
            "button[class*='login']",
        ]

        for selector in submit_selectors:
            try:
                submit_btn = driver.find_element(By.CSS_SELECTOR, selector)
                if submit_btn and submit_btn.is_displayed():
                    _human_delay(300, 700)
                    submit_btn.click()
                    break
            except Exception:
                continue

        # Wait for page to load after login
        _human_delay(3000, 6000)

        # Extract JWT token
        jwt = _extract_jwt_from_storage(driver)
        if not jwt:
            jwt = _intercept_jwt_via_network(driver)

        if jwt:
            log.info("browser_login_success", token_prefix=jwt[:20] + "...")
        else:
            _save_debug_screenshot(driver, "jwt_not_found")
            log.error("login_failed", reason="could not extract JWT token")

        return jwt

    except Exception as e:
        log.error("browser_login_error", error=str(e))
        if driver:
            _save_debug_screenshot(driver, "login_exception")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def discover_center_codes(config: AppConfig, country_code: str) -> dict | None:
    """
    Navigate through the VFS booking flow to discover center codes
    and visa category codes by intercepting network requests.

    Run in non-headless mode so the user can interact if needed.
    """
    driver = None
    discovered = {"requests": []}
    try:
        log.info("discover_mode_starting", country=country_code)

        # Force non-headless for discovery
        config_copy = config.model_copy(deep=True)
        config_copy.browser.headless = False
        driver = _create_driver(config_copy)
        driver.execute_cdp_cmd("Network.enable", {})

        url = f"{VFS_BASE_URL}/{country_code}/book-an-appointment"
        driver.get(url)

        print("\n" + "=" * 60)
        print("DISCOVERY MODE")
        print("=" * 60)
        print(f"\nNavigated to: {url}")
        print("\nPlease:")
        print("1. Log in with your VFS credentials")
        print("2. Navigate through the booking flow")
        print("3. Select your visa category and center")
        print("4. Wait for the calendar to load")
        print("\nThe tool will capture all API requests to find your codes.")
        print("Press Enter when you're done...")

        input()

        # Extract captured network requests
        try:
            logs = driver.get_log("performance")
            for entry in logs:
                try:
                    msg = json.loads(entry["message"])
                    if msg.get("message", {}).get("method") == "Network.requestWillBeSent":
                        req_url = msg["message"]["params"].get("request", {}).get("url", "")
                        if "lift-api.vfsglobal.com" in req_url:
                            discovered["requests"].append(req_url)
                            log.info("discovered_api_call", url=req_url)
                except (json.JSONDecodeError, KeyError):
                    continue
        except Exception as e:
            log.debug("discovery_log_failed", error=str(e))

        if discovered["requests"]:
            print("\n" + "=" * 60)
            print("DISCOVERED API CALLS:")
            print("=" * 60)
            for req_url in discovered["requests"]:
                print(f"\n  {req_url}")
                # Parse query params
                if "?" in req_url:
                    params = req_url.split("?")[1].split("&")
                    for p in params:
                        print(f"    {p}")
            print("\nCopy the centerCode and visaCategoryCode into your config.yaml")
        else:
            print("\nNo API calls captured. Make sure you completed the booking flow.")

        return discovered

    except Exception as e:
        log.error("discover_mode_error", error=str(e))
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def _handle_captcha(
    driver: uc.Chrome, solver: CaptchaSolver | None, page_url: str
) -> None:
    """Detect and attempt to solve CAPTCHA if present."""
    # Check for reCAPTCHA iframe
    try:
        recaptcha_frames = driver.find_elements(
            By.CSS_SELECTOR, "iframe[src*='recaptcha']"
        )
        if recaptcha_frames and solver and solver.available:
            # Extract sitekey from iframe src
            src = recaptcha_frames[0].get_attribute("src") or ""
            if "k=" in src:
                site_key = src.split("k=")[1].split("&")[0]
                token = solver.solve_recaptcha(site_key, page_url)
                if token:
                    driver.execute_script(
                        f'document.getElementById("g-recaptcha-response").innerHTML="{token}";'
                    )
                    _human_delay(500, 1000)
        elif recaptcha_frames:
            log.warning("captcha_detected_no_solver", type="recaptcha")
    except Exception as e:
        log.debug("captcha_check_failed", error=str(e))


def _save_debug_screenshot(driver: uc.Chrome, name: str) -> None:
    """Save a screenshot and page source for debugging."""
    try:
        debug_dir = Path("data/debug")
        debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        driver.save_screenshot(str(debug_dir / f"{name}_{timestamp}.png"))
        with open(debug_dir / f"{name}_{timestamp}.html", "w") as f:
            f.write(driver.page_source)
        log.info("debug_saved", name=name, dir=str(debug_dir))
    except Exception:
        pass

"""Browser-based login and slot scraping for TLScontact.

TLScontact uses Keycloak for authentication and does NOT expose a public
REST API for appointment slots. All slot checking must be done through
browser automation (scraping the appointment calendar page).

Key differences from VFS Global:
- No REST API → must scrape the DOM for available slots
- Keycloak login with button ID "kc-login"
- Cookie acceptance banner via "osano-cm-accept-all"
- Available slots marked with CSS class "-available"
- Rate limiting: TLS limits auth attempts per day (~5400s / 1.5h recommended)
- Anti-bot landing page protection
"""

from __future__ import annotations

import json
import pickle
import random
import re
import time
from pathlib import Path

import structlog
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from vfs_monitor.auth.captcha_solver import CaptchaSolver
from vfs_monitor.config import AppConfig, CenterConfig

log = structlog.get_logger()

TLS_BASE_URL = "https://visas-{country}.tlscontact.com"

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

COOKIE_FILE = Path("data/tls_cookies.pkl")


def _human_delay(min_ms: int = 500, max_ms: int = 2000) -> None:
    """Sleep for a random human-like duration."""
    time.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


def _human_type(element, text: str) -> None:
    """Type text with random inter-key delays to mimic human typing."""
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))


def _create_driver(config: AppConfig, headless: bool | None = None) -> uc.Chrome:
    """Create an undetected Chrome browser instance."""
    options = uc.ChromeOptions()

    width, height = random.choice(VIEWPORTS)
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument("--lang=en-GB")
    options.add_argument("--disable-blink-features=AutomationControlled")

    use_headless = headless if headless is not None else config.browser.headless
    if use_headless:
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


def _accept_cookies(driver: uc.Chrome) -> None:
    """Click the cookie consent banner if present (Osano)."""
    try:
        wait = WebDriverWait(driver, 5)
        accept_btn = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, ".osano-cm-accept-all, button.osano-cm-accept-all")
            )
        )
        accept_btn.click()
        _human_delay(500, 1000)
        log.debug("cookies_accepted")
    except Exception:
        log.debug("no_cookie_banner_found")


def _save_cookies(driver: uc.Chrome) -> None:
    """Save browser cookies to disk for session reuse."""
    try:
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        cookies = driver.get_cookies()
        with open(COOKIE_FILE, "wb") as f:
            pickle.dump(cookies, f)
        log.debug("cookies_saved", count=len(cookies))
    except Exception as e:
        log.debug("cookie_save_failed", error=str(e))


def _load_cookies(driver: uc.Chrome, domain: str) -> bool:
    """Load previously saved cookies into the browser."""
    if not COOKIE_FILE.exists():
        return False
    try:
        with open(COOKIE_FILE, "rb") as f:
            cookies = pickle.load(f)
        for cookie in cookies:
            # Only load cookies for the right domain
            if domain in cookie.get("domain", ""):
                try:
                    driver.add_cookie(cookie)
                except Exception:
                    pass
        log.debug("cookies_loaded", count=len(cookies))
        return True
    except Exception as e:
        log.debug("cookie_load_failed", error=str(e))
        return False


def _build_tls_url(center: CenterConfig) -> str:
    """Build the TLScontact home URL for a center."""
    base = TLS_BASE_URL.format(country=center.country_code)
    return f"{base}/visa/{center.from_country}/{center.issuer_id}/home"


def _build_appointment_url(center: CenterConfig) -> str:
    """Build a plausible TLScontact appointment booking URL."""
    base = TLS_BASE_URL.format(country=center.country_code)
    return f"{base}/appointment"


def login_to_tls(
    config: AppConfig,
    center: CenterConfig,
    captcha_solver: CaptchaSolver | None = None,
    headless: bool | None = None,
) -> uc.Chrome | None:
    """
    Log in to TLScontact and return the authenticated browser session.

    Unlike VFS Global, TLScontact doesn't use JWT tokens.
    Authentication is session/cookie-based via Keycloak.
    The browser must stay open for slot checking.

    Args:
        config: Application configuration.
        center: The center to log in for.
        captcha_solver: Optional CAPTCHA solver instance.
        headless: Override headless setting.

    Returns:
        Authenticated Chrome driver instance, or None if login failed.
    """
    driver = None
    try:
        log.info("tls_login_starting", country=center.country_code, city=center.city)
        driver = _create_driver(config, headless=headless)

        # Navigate to the TLS home page first (needed to set cookies)
        home_url = _build_tls_url(center)
        driver.get(home_url)
        _human_delay(2000, 4000)

        # Accept cookie banner
        _accept_cookies(driver)

        # Try to load saved cookies
        domain = f"tlscontact.com"
        cookies_loaded = _load_cookies(driver, domain)
        if cookies_loaded:
            driver.refresh()
            _human_delay(2000, 3000)

            # Check if we're already logged in (no login button visible)
            if _is_logged_in(driver):
                log.info("tls_login_restored_from_cookies")
                return driver

        # Click login button/link
        login_clicked = _click_login_link(driver)
        if not login_clicked:
            _save_debug_screenshot(driver, "no_login_link")
            log.error("login_failed", reason="could not find login link")
            driver.quit()
            return None

        _human_delay(1000, 2000)

        # Wait for Keycloak login form
        wait = WebDriverWait(driver, 30)

        # Find username/email field
        username_selectors = [
            "input#username",
            "input[name='username']",
            "input[type='email']",
            "input[id*='email']",
            "input[name*='email']",
        ]

        username_field = None
        for selector in username_selectors:
            try:
                username_field = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if username_field:
                    break
            except Exception:
                continue

        if not username_field:
            _save_debug_screenshot(driver, "no_username_field")
            log.error("login_failed", reason="could not find username/email field")
            driver.quit()
            return None

        # Type credentials with human-like delays
        _human_delay(500, 1000)
        username_field.click()
        _human_delay(200, 500)
        _human_type(username_field, config.env.tls_email)
        _human_delay(300, 800)

        # Find password field
        password_selectors = [
            "input#password",
            "input[name='password']",
            "input[type='password']",
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
            log.error("login_failed", reason="could not find password field")
            driver.quit()
            return None

        password_field.click()
        _human_delay(200, 500)
        _human_type(password_field, config.env.tls_password)
        _human_delay(500, 1000)

        # Handle CAPTCHA if present
        _handle_captcha(driver, captcha_solver, driver.current_url)

        # Click the Keycloak login button (id="kc-login")
        submit_selectors = [
            "input#kc-login",
            "button#kc-login",
            "input[name='login']",
            "button[type='submit']",
        ]

        submitted = False
        for selector in submit_selectors:
            try:
                submit_btn = driver.find_element(By.CSS_SELECTOR, selector)
                if submit_btn and submit_btn.is_displayed():
                    _human_delay(300, 700)
                    submit_btn.click()
                    submitted = True
                    break
            except Exception:
                continue

        if not submitted:
            _save_debug_screenshot(driver, "no_submit_button")
            log.error("login_failed", reason="could not find login submit button")
            driver.quit()
            return None

        # Wait for redirect back to TLScontact after Keycloak auth
        _human_delay(3000, 6000)

        # Verify we're logged in
        if _is_logged_in(driver):
            _save_cookies(driver)
            log.info("tls_login_success")
            return driver
        else:
            _save_debug_screenshot(driver, "login_not_confirmed")
            log.error("login_failed", reason="login did not complete - check credentials")
            driver.quit()
            return None

    except Exception as e:
        log.error("tls_login_error", error=str(e))
        if driver:
            _save_debug_screenshot(driver, "login_exception")
            driver.quit()
        return None


def _is_logged_in(driver: uc.Chrome) -> bool:
    """Check if the browser is logged in to TLScontact."""
    try:
        # After login, TLScontact shows the user's application dashboard
        # Look for indicators of being logged in
        page_source = driver.page_source.lower()

        # Logged-in indicators
        logged_in_signals = [
            "my-application",
            "travel-groups",
            "log out",
            "logout",
            "sign out",
            "dashboard",
            "my account",
        ]

        # Login page indicators (means NOT logged in)
        login_page_signals = [
            "kc-login",
            "sign in",
            "log in to your account",
        ]

        for signal in login_page_signals:
            if signal in page_source:
                return False

        for signal in logged_in_signals:
            if signal in page_source:
                return True

        return False
    except Exception:
        return False


def _click_login_link(driver: uc.Chrome) -> bool:
    """Find and click the login link on the TLScontact home page."""
    selectors = [
        "a[href*='login']",
        "button[class*='login']",
        "a[class*='login']",
        "a[href*='auth']",
        ".tls-button-primary",
        "a.button-neo-inside",
    ]

    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                if el.is_displayed():
                    el.click()
                    return True
        except Exception:
            continue

    # Try by link text
    for text in ["Log in", "Login", "Sign in", "Sign In"]:
        try:
            link = driver.find_element(By.LINK_TEXT, text)
            if link.is_displayed():
                link.click()
                return True
        except Exception:
            continue

    # Try partial link text
    for text in ["Log in", "Login", "Sign in"]:
        try:
            link = driver.find_element(By.PARTIAL_LINK_TEXT, text)
            if link.is_displayed():
                link.click()
                return True
        except Exception:
            continue

    return False


def check_slots_browser(
    driver: uc.Chrome,
    center: CenterConfig,
) -> list[dict]:
    """
    Navigate to the appointment page and scrape available slots.

    TLScontact marks available appointment slots with the CSS class
    "-available" on calendar day elements. The page also uses classes
    like "tls-button-primary" for navigation buttons.

    Args:
        driver: Authenticated Chrome driver.
        center: Center to check.

    Returns:
        List of dicts with slot info: {"date": str, "times": [...], "is_prime": bool}
    """
    slots = []
    try:
        log.debug("checking_slots_browser", country=center.country_code, city=center.city)

        # Navigate to appointment booking page
        # TLScontact appointment URLs vary, try multiple patterns
        base = TLS_BASE_URL.format(country=center.country_code)
        appointment_urls = [
            f"{base}/visa/{center.from_country}/{center.issuer_id}/home",
        ]

        # First navigate to the home page to ensure session is active
        driver.get(appointment_urls[0])
        _human_delay(2000, 4000)

        # Look for and click the appointment/booking button
        booking_clicked = _navigate_to_appointment_page(driver)
        if not booking_clicked:
            log.debug("could_not_navigate_to_appointment_page")
            return slots

        _human_delay(2000, 4000)

        # Scrape available slots from the calendar
        slots = _scrape_calendar_slots(driver, center)

        log.info(
            "slot_check_complete",
            country=center.country_name,
            city=center.city,
            slots_found=len(slots),
        )

    except Exception as e:
        log.error("slot_check_error", error=str(e), country=center.country_code)
        _save_debug_screenshot(driver, "slot_check_error")

    return slots


def _navigate_to_appointment_page(driver: uc.Chrome) -> bool:
    """Navigate from the TLS home/dashboard to the appointment booking page."""
    # Try clicking appointment-related buttons
    nav_selectors = [
        "a[href*='appointment']",
        "a[href*='booking']",
        "button.tls-button-primary",
        ".button-neo-inside.-primary",
        "a.tls-button-primary",
        "a[href*='workflow']",
    ]

    for selector in nav_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                text = (el.text or "").lower()
                if el.is_displayed() and any(
                    kw in text
                    for kw in ["appointment", "book", "continue", "next", "proceed"]
                ):
                    el.click()
                    _human_delay(1000, 2000)
                    return True
        except Exception:
            continue

    # If specific text buttons not found, try the primary action button
    try:
        primary_btns = driver.find_elements(
            By.CSS_SELECTOR, ".tls-button-primary, .button-neo-inside.-primary"
        )
        for btn in primary_btns:
            if btn.is_displayed():
                btn.click()
                _human_delay(1000, 2000)
                return True
    except Exception:
        pass

    return False


def _scrape_calendar_slots(driver: uc.Chrome, center: CenterConfig) -> list[dict]:
    """Scrape the TLScontact calendar for available appointment slots."""
    slots = []

    # TLScontact marks available dates with "-available" CSS class
    available_selectors = [
        ".-available",
        ".day.-available",
        "td.-available",
        "[class*='available']:not([class*='unavailable'])",
        ".appt-table-container .-available",
    ]

    for selector in available_selectors:
        try:
            available_elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if available_elements:
                log.debug(
                    "found_available_elements",
                    count=len(available_elements),
                    selector=selector,
                )
                for el in available_elements:
                    slot_info = _parse_calendar_element(el, center)
                    if slot_info:
                        slots.append(slot_info)
                break
        except Exception:
            continue

    # Also check for time slot elements directly
    time_selectors = [
        ".inner_timeslot",
        ".timeslot",
        ".time-slot",
        "[class*='timeslot']",
    ]

    for selector in time_selectors:
        try:
            time_elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if time_elements:
                for el in time_elements:
                    if el.is_displayed():
                        text = el.text.strip()
                        if text:
                            # Check if this is associated with an available day
                            is_prime = "prime" in (
                                el.get_attribute("class") or ""
                            ).lower()
                            slots.append({
                                "date": None,
                                "time": text,
                                "is_prime": is_prime,
                            })
                break
        except Exception:
            continue

    # Deduplicate and clean up
    seen_dates = set()
    unique_slots = []
    for slot in slots:
        key = f"{slot.get('date')}:{slot.get('time', '')}"
        if key not in seen_dates:
            seen_dates.add(key)
            unique_slots.append(slot)

    return unique_slots


def _parse_calendar_element(element, center: CenterConfig) -> dict | None:
    """Parse a single available calendar element into slot info."""
    try:
        # Try to extract date from the element or its parent
        date_str = None

        # Try data attributes
        for attr in ["data-date", "data-day", "data-value", "id"]:
            val = element.get_attribute(attr)
            if val and re.match(r"\d{4}-\d{2}-\d{2}", val):
                date_str = val[:10]
                break

        # Try the element text content
        if not date_str:
            text = element.text.strip()
            if text and text.isdigit():
                # Just a day number - try to build full date from context
                # Look at parent elements for month/year
                try:
                    parent = element.find_element(By.XPATH, "..")
                    parent_text = parent.text
                    # Try grandparent
                    grandparent = parent.find_element(By.XPATH, "..")
                    grandparent_text = grandparent.text
                    date_str = _extract_date_from_context(text, parent_text, grandparent_text)
                except Exception:
                    pass

        # Check for prime slot
        classes = element.get_attribute("class") or ""
        is_prime = "prime" in classes.lower()

        if date_str:
            return {
                "date": date_str,
                "time": None,
                "is_prime": is_prime,
            }
        else:
            # Still found an available element even without a date
            return {
                "date": "unknown",
                "time": None,
                "is_prime": is_prime,
            }

    except Exception:
        return None


def _extract_date_from_context(day: str, parent_text: str, grandparent_text: str) -> str | None:
    """Try to build a full date from a day number and surrounding context."""
    import datetime

    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4,
        "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    # Search for month name in parent/grandparent text
    combined = f"{parent_text} {grandparent_text}".lower()
    month = None
    for name, num in months.items():
        if name in combined:
            month = num
            break

    if not month:
        return None

    # Search for year
    year_match = re.search(r"20\d{2}", combined)
    year = int(year_match.group()) if year_match else datetime.datetime.now().year

    try:
        d = datetime.date(year, month, int(day))
        return d.isoformat()
    except (ValueError, TypeError):
        return None


def discover_issuer_ids(config: AppConfig, country_code: str) -> dict | None:
    """
    Navigate through TLScontact interactively to discover issuer IDs.

    Run in non-headless mode so the user can interact with the site.
    The user logs in, selects their city/visa type, and the tool captures
    the issuer_id from the URL.
    """
    driver = None
    discovered = {"issuer_ids": [], "urls_visited": []}
    try:
        log.info("discover_mode_starting", country=country_code)

        driver = _create_driver(config, headless=False)

        # Navigate to the TLS country page
        base_url = TLS_BASE_URL.format(country=country_code)
        driver.get(base_url)

        print("\n" + "=" * 60)
        print("TLScontact DISCOVERY MODE")
        print("=" * 60)
        print(f"\nNavigated to: {base_url}")
        print("\nPlease:")
        print("1. Accept cookies if prompted")
        print("2. Select your country/city (e.g., United Kingdom → London)")
        print("3. Note the URL changes - the issuer_id is in the URL")
        print("4. Log in with your TLScontact credentials")
        print("5. Navigate to the appointment booking page")
        print("")
        print("URL pattern to look for:")
        print(f"  https://visas-{country_code}.tlscontact.com/visa/gb/gbLON2{country_code}/home")
        print("                                                    ^^^^^^^^^^")
        print("                                                    This is your issuer_id")
        print("")
        print("Press Enter when you're done navigating...")

        input()

        # Capture the current URL
        current_url = driver.current_url
        discovered["urls_visited"].append(current_url)

        # Try to extract issuer_id from URL
        # Pattern: /visa/{from_country}/{issuer_id}/
        issuer_match = re.search(r"/visa/(\w+)/(\w+)/", current_url)
        if issuer_match:
            from_country = issuer_match.group(1)
            issuer_id = issuer_match.group(2)
            discovered["issuer_ids"].append({
                "from_country": from_country,
                "issuer_id": issuer_id,
                "url": current_url,
            })

        # Also check browser history for other issuer IDs
        try:
            logs = driver.get_log("performance")
            for entry in logs:
                try:
                    msg = json.loads(entry["message"])
                    if msg.get("message", {}).get("method") == "Network.requestWillBeSent":
                        req_url = msg["message"]["params"].get("request", {}).get("url", "")
                        if "tlscontact.com" in req_url:
                            discovered["urls_visited"].append(req_url)
                            m = re.search(r"/visa/(\w+)/(\w+)/", req_url)
                            if m and m.group(2) not in [
                                d["issuer_id"] for d in discovered["issuer_ids"]
                            ]:
                                discovered["issuer_ids"].append({
                                    "from_country": m.group(1),
                                    "issuer_id": m.group(2),
                                    "url": req_url,
                                })
                except (json.JSONDecodeError, KeyError):
                    continue
        except Exception as e:
            log.debug("discovery_log_failed", error=str(e))

        if discovered["issuer_ids"]:
            print("\n" + "=" * 60)
            print("DISCOVERED ISSUER IDs:")
            print("=" * 60)
            for item in discovered["issuer_ids"]:
                print(f"\n  issuer_id: {item['issuer_id']}")
                print(f"  from_country: {item['from_country']}")
                print(f"  URL: {item['url']}")
            print("\n\nAdd these to your config.yaml like:")
            print(f'  issuer_id: "{discovered["issuer_ids"][0]["issuer_id"]}"')
            print(f'  from_country: "{discovered["issuer_ids"][0]["from_country"]}"')
        else:
            print("\nNo issuer IDs captured from the URL.")
            print(f"Current URL: {current_url}")
            print("\nLook at the URL bar manually for the pattern:")
            print(f"  visas-{country_code}.tlscontact.com/visa/{{from_country}}/{{issuer_id}}/...")

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
    try:
        recaptcha_frames = driver.find_elements(
            By.CSS_SELECTOR, "iframe[src*='recaptcha']"
        )
        if recaptcha_frames and solver and solver.available:
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

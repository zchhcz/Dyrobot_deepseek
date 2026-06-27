import json
from pathlib import Path
from playwright.sync_api import Page, BrowserContext
from ..utils.logger import setup_logger

logger = setup_logger(__name__)

COOKIE_FILE = Path(__file__).parent.parent.parent / "data" / "cookies.json"
DOUYIN_URL = "https://www.douyin.com"


def save_cookies(context: BrowserContext) -> None:
    cookies = context.cookies()
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    COOKIE_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Cookies saved to %s", COOKIE_FILE)


def load_cookies(context: BrowserContext) -> bool:
    if not COOKIE_FILE.exists():
        logger.info("No saved cookies found at %s", COOKIE_FILE)
        return False
    try:
        cookies = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
        context.add_cookies(cookies)
        logger.info("Loaded %d cookies from %s", len(cookies), COOKIE_FILE)
        return True
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to parse cookies: %s", e)
        return False


def is_logged_in(page: Page) -> bool:
    """Check if the page shows a logged-in state using Playwright locators."""
    try:
        page.goto(DOUYIN_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # If a visible login button exists, we're not logged in
        # Use Playwright's text locator (safe — not a CSS selector)
        login_elements = page.locator('button:has-text("登录"), [role="button"]:has-text("登录")')
        visible_count = 0
        for i in range(login_elements.count()):
            if login_elements.nth(i).is_visible():
                visible_count += 1

        if visible_count > 0:
            logger.info("Login prompt detected — not logged in")
            return False

        logger.info("No login prompt found — logged in")
        return True
    except Exception as e:
        logger.warning("Login check failed, assuming not logged in: %s", e)
        return False


def login_with_qrcode(page: Page) -> bool:
    """Navigate to Douyin and wait for user to scan QR code."""
    # Only navigate if not already on douyin.com (is_logged_in may have already loaded it)
    if "douyin.com" not in page.url:
        page.goto(DOUYIN_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)

    # Try clicking the "扫码登录" tab in the login dialog
    try:
        qr_tab = page.locator('text="扫码登录"').first
        if qr_tab.is_visible():
            qr_tab.click()
            page.wait_for_timeout(1000)
            logger.info("Switched to QR code login tab")
    except Exception as e:
        logger.debug("Could not click QR code tab: %s", e)

    # If already logged in (cookies were valid), return immediately
    login_els = page.locator('button:has-text("登录"), [role="button"]:has-text("登录")')
    visible = sum(1 for i in range(login_els.count()) if login_els.nth(i).is_visible())
    if visible == 0:
        logger.info("Already logged in (cookies still valid)")
        return True

    logger.info("============================================")
    logger.info("Please scan the QR code on the page to log in")
    logger.info("Waiting for login...")
    logger.info("============================================")

    timeout_seconds = 300
    poll_interval = 2
    elapsed = 0
    while elapsed < timeout_seconds:
        try:
            visible = sum(1 for i in range(login_els.count()) if login_els.nth(i).is_visible())
            if visible == 0:
                logger.info("Login successful!")
                return True
        except Exception:
            pass
        page.wait_for_timeout(poll_interval * 1000)
        elapsed += poll_interval
        if elapsed % 10 == 0:
            logger.info("Still waiting for login... (%ds/%ds)", elapsed, timeout_seconds)

    logger.error("Login timed out after %d seconds", timeout_seconds)
    return False


def ensure_logged_in(context: BrowserContext, page: Page) -> bool:
    cookies_loaded = load_cookies(context)

    if cookies_loaded:
        if is_logged_in(page):
            logger.info("Cookie-based login successful")
            return True
        logger.info("Saved cookies expired, re-logging in")
        COOKIE_FILE.unlink(missing_ok=True)

    if login_with_qrcode(page):
        save_cookies(context)
        return True

    return False

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from ..utils.logger import setup_logger
from .login import ensure_logged_in

logger = setup_logger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class BrowserManager:
    def __init__(self, headless: bool = False, slow_mo: int = 100):
        self.headless = headless
        self.slow_mo = slow_mo
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def start(self) -> BrowserContext:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        self._context = self._browser.new_context(
            user_agent=_USER_AGENT,
            viewport={"width": 1280, "height": 720},
        )
        # Inject stealth script to mask automation
        self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            window.chrome = { runtime: {} };
        """)
        logger.info("Browser launched (headless=%s, slow_mo=%d)", self.headless, self.slow_mo)
        return self._context

    def login(self) -> Page:
        if self._context is None:
            raise RuntimeError("Browser not started. Call start() first.")
        page = self._context.new_page()
        if not ensure_logged_in(self._context, page):
            raise RuntimeError("Login failed. Cannot proceed without authentication.")
        logger.info("Login verified, browser ready for chat monitoring")
        return page

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("Browser not started. Call start() first.")
        return self._context

    def new_page(self) -> Page:
        return self._context.new_page()

    def stop(self) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        logger.info("Browser stopped")

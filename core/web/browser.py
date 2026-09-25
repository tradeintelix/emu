from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from config.settings import BRIGHTDATA_HOST, BRIGHTDATA_PORT, HEADLESS, PROXY_ENABLED
from core.web.browser_api import create_browser_api_driver
from core.web.proxy import build_auth_extension


def create_browser(solve_captcha=False, country=None):
    """Chrome via Selenium 4 (Selenium Manager downloads the matching chromedriver). Needs Chrome installed.

    solve_captcha=True runs on Bright Data's remote Browser API instead - the only Bright Data
    product that can actually solve a CAPTCHA mid-session (see core/web/browser_api.py). That
    replaces this whole local-Chrome path: headless and the residential/Web Unlocker proxy
    extension below don't apply to a remote session, so both are skipped in that case.
    country only affects the Browser API path (see create_browser_api_driver)."""
    if solve_captcha:
        return create_browser_api_driver(country=country)

    opts = Options()
    # ponytail: some SPAs (Uber's) keep background network activity going and never fire a full
    # "load" event, which hangs Selenium's default page-load wait. "eager" only waits for the DOM,
    # which is all our own explicit waits (WebDriverWait on a locator) need anyway.
    opts.page_load_strategy = "eager"
    if HEADLESS:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,900")
    # feeds core.web.monitors: console errors + network responses
    opts.set_capability("goog:loggingPrefs", {"browser": "ALL", "performance": "ALL"})

    if PROXY_ENABLED:
        opts.add_argument(f"--proxy-server=http://{BRIGHTDATA_HOST}:{BRIGHTDATA_PORT}")
        opts.add_argument(f"--load-extension={build_auth_extension()}")
        # ponytail: some Chrome builds don't load extensions in --headless=new (open Chromium bug).
        # If the proxy silently doesn't apply under HEADLESS=1, drop headless for that run, or ask
        # Bright Data to whitelist this machine's IP instead of username/password auth.

    return webdriver.Chrome(options=opts)

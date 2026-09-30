from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from config.settings import BRIGHTDATA_HOST, BRIGHTDATA_PORT, BRIGHTDATA_PASSWORD, BRIGHTDATA_USERNAME, HEADLESS, PROXY_ENABLED
from core.web import residential_proxy
from core.web.proxy import build_auth_extension


def create_browser(solve_captcha=False, country=None):
    """Local Chrome via Selenium 4 (Selenium Manager downloads chromedriver).

    solve_captcha is kept for backward compat with the old Bright Data Browser API
    path (now deleted): solving happens in-page via CapSolver (see core/web/outcome.py),
    so no remote browser is needed and the arg is ignored beyond this note.

    country picks the residential proxy's exit country (see core/web/residential_proxy.py)
    when BRIGHTDATA_CUSTOMER_ID/ZONE/ZONE_PASSWORD are set; otherwise the legacy
    BRIGHTDATA_* vars are used as a generic (non-geo-targeted) proxy; blank runs direct."""

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

    if residential_proxy.is_configured():
        user, password, host, port = residential_proxy.credentials(country=country)
        opts.add_argument(f"--proxy-server=http://{host}:{port}")
        opts.add_argument(f"--load-extension={build_auth_extension(host, port, user, password)}")
    elif PROXY_ENABLED:
        opts.add_argument(f"--proxy-server=http://{BRIGHTDATA_HOST}:{BRIGHTDATA_PORT}")
        opts.add_argument(f"--load-extension={build_auth_extension(BRIGHTDATA_HOST, BRIGHTDATA_PORT, BRIGHTDATA_USERNAME, BRIGHTDATA_PASSWORD)}")
        # ponytail: some Chrome builds don't load extensions in --headless=new (open Chromium bug).
        # If the proxy silently doesn't apply under HEADLESS=1, drop headless for that run.

    return webdriver.Chrome(options=opts)

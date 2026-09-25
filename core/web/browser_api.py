"""Bright Data Browser API (formerly "Scraping Browser"): a remote Chrome instance reached
over Selenium's remote WebDriver protocol, with CAPTCHA solving built in via a Chrome
DevTools command. This is NOT the Web Unlocker API - that one only does single
request-in/HTML-out calls and, per Bright Data's own docs, "is not made for use on browsers
or third party tools like ... Puppeteer, Playwright, or Selenium." Browser API is the product
actually meant for a live, multi-step UI session like ours.
Docs: https://docs.brightdata.com/scraping-automation/scraping-browser

Needs its own zone credentials - a Browser API / Scraping Browser zone, not the
residential/Web Unlocker zone used by core/web/proxy.py for plain IP/geo routing.
"""
from selenium.webdriver import Remote
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chromium.remote_connection import ChromiumRemoteConnection

from config.settings import require

ENDPOINT = "brd.superproxy.io:9515"  # Selenium's port; Puppeteer/Playwright use 9222 instead


def create_browser_api_driver(country=None):
    """country: two-letter ISO code (e.g. "in"), appended to the username per Bright Data's
    geolocation targeting - without it, the exit IP (and so the site's language/locale) is
    whatever Bright Data picks, which can silently break locators written against one locale
    (confirmed: Uber rendered fully in Spanish on an unpinned run)."""
    user = require("BRIGHTDATA_BROWSER_USERNAME")
    if country:
        user = f"{user}-country-{country.lower()}"
    password = require("BRIGHTDATA_BROWSER_PASSWORD")
    server_addr = f"https://{user}:{password}@{ENDPOINT}"
    connection = ChromiumRemoteConnection(server_addr, "goog", "chrome")
    opts = Options()
    # feeds core.web.monitors: console errors + network responses - same capability the local
    # Chrome path sets in core/web/browser.py, needed here too since this builds its own Options.
    opts.set_capability("goog:loggingPrefs", {"browser": "ALL", "performance": "ALL"})
    # ponytail: -country-in alone didn't change the page's language (confirmed: still Spanish
    # with it set) - Uber's language picks off the browser's own locale, not just exit-IP
    # geography, so it has to be forced here too. Our locators are written against English.
    opts.add_argument("--lang=en-US")
    return Remote(connection, options=opts)


def solve_captcha(driver, detect_timeout_s=10):
    """Bright Data detects and solves whatever CAPTCHA is on the current page (reCAPTCHA,
    hCaptcha, Cloudflare Turnstile, FunCaptcha/Arkose, etc.) on their end - no site-key or
    token handling here. Returns their reported status, e.g. "solve_finished", "not_detected",
    "solve_failed". A no-op (returns "not_detected"-like status) if nothing is on screen."""
    result = driver.execute("executeCdpCommand", {
        "cmd": "Captcha.waitForSolve",
        "params": {"detectTimeout": detect_timeout_s * 1000},
    })
    return result["value"]["status"]

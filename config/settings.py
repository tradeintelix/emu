"""Single place that reads configuration: a .env file at the repo root, overridden by real env vars."""
import os

from dotenv import load_dotenv

load_dotenv()  # real environment variables win over .env, so CI can override without editing the file

SDK = os.getenv("ANDROID_HOME") or os.getenv("ANDROID_SDK_ROOT") or os.path.expanduser("~/Library/Android/sdk")

AVD_NAME = os.getenv("AVD_NAME", "emu_test")
HEADLESS = os.getenv("HEADLESS", "0") == "1"  # set on CI: no window, software GPU
BOOT_TIMEOUT = int(os.getenv("BOOT_TIMEOUT", "240"))  # seconds

def require(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set. Add it to .env (see .env.example).")
    return value


APPIUM_URL =os.getenv("APPIUM_URL", "http://127.0.0.1:4723")

APP_PACKAGE =os.getenv("APP_PACKAGE", "")  # checked when the app is launched, so unit tests don't need it

# CapSolver (replaces Bright Data for CAPTCHA solving). Fund at capsolver.com,
# then set CAPSOLVER_API_KEY. Blank = detection-only: challenges are reported
# as "captcha" but never solved, so runs keep working before funding.
CAPSOLVER_API_KEY = os.getenv("CAPSOLVER_API_KEY", "")
CAPSOLVER_TIMEOUT = int(os.getenv("CAPSOLVER_TIMEOUT", "120"))  # seconds per solve

# Bright Data Residential IP proxy (core/web/residential_proxy.py). Fund a
# Residential zone at brightdata.com, then set these three. Blank = not
# configured, browsers run direct (or via the legacy vars below).
BRIGHTDATA_CUSTOMER_ID = os.getenv("BRIGHTDATA_CUSTOMER_ID", "")
BRIGHTDATA_ZONE = os.getenv("BRIGHTDATA_ZONE", "")
BRIGHTDATA_ZONE_PASSWORD = os.getenv("BRIGHTDATA_ZONE_PASSWORD", "")

# Exit country for the residential proxy (ISO-3166, e.g. "us", "in", or "eu").
# Set per run with `python run.py --web <name> --country <cc>`; falls back to
# the target's own target.py PROXY_COUNTRY when blank.
PROXY_COUNTRY = os.getenv("PROXY_COUNTRY", "")

# Legacy Bright Data proxy vars (deprecated, kept for backward compat).
# Blank = direct connection (current default since the CapSolver switch).
# If set, local Chrome / SB-CDP still route through them when the residential
# vars above aren't configured; CapSolver itself always uses
# FunCaptchaTaskProxyless (its own IP pool).
BRIGHTDATA_HOST = os.getenv("BRIGHTDATA_HOST", "")
BRIGHTDATA_PORT = os.getenv("BRIGHTDATA_PORT", "")
BRIGHTDATA_USERNAME = os.getenv("BRIGHTDATA_USERNAME", "")
BRIGHTDATA_PASSWORD = os.getenv("BRIGHTDATA_PASSWORD", "")
PROXY_ENABLED = bool(BRIGHTDATA_HOST and BRIGHTDATA_PORT and BRIGHTDATA_USERNAME)

# Bright Data Browser API (removed). Kept as empty placeholders so old .env
# files don't crash imports; core/web/browser_api.py is deleted.
BRIGHTDATA_BROWSER_USERNAME = os.getenv("BRIGHTDATA_BROWSER_USERNAME", "")
BRIGHTDATA_BROWSER_PASSWORD = os.getenv("BRIGHTDATA_BROWSER_PASSWORD", "")

# SeleniumBase Pure CDP avoidance (Uber spike). Real Chrome via CDP, no WebDriver,
# so TLS/JS fingerprints look like a human browser. See core/web/sb_browser.py.
# Persistent profile = cookie/storage continuity across runs (JS-coherence).
SB_HEADLESS = HEADLESS  # reuse HEADLESS: headed by default, stealth needs a window
SB_LANG = os.getenv("SB_LANG", "en-US")
SB_TZ = os.getenv("SB_TZ", "Asia/Kolkata")  # matches PROXY_COUNTRY=in
SB_USER_DATA_DIR = os.getenv("SB_USER_DATA_DIR", "")  # blank = targets/web/uber/.sb_profile
SB_PROXY = os.getenv("SB_PROXY", "")  # "none" = force direct; full "user:pass@host:port" to use a proxy
SB_SESSION = os.getenv("SB_SESSION", "")  # reserved for proxy sticky sessions; unused on direct

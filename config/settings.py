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

# Bright Data proxy (residential / Web Unlocker zone) for website tests. Blank = no proxy.
# Host/port/username/password all come from whichever zone you paste in - the code doesn't
# care if that zone is "residential" or "Web Unlocker", Bright Data authenticates the same way.
BRIGHTDATA_HOST = os.getenv("BRIGHTDATA_HOST", "")
BRIGHTDATA_PORT = os.getenv("BRIGHTDATA_PORT", "")
BRIGHTDATA_USERNAME = os.getenv("BRIGHTDATA_USERNAME", "")
BRIGHTDATA_PASSWORD = os.getenv("BRIGHTDATA_PASSWORD", "")
PROXY_ENABLED = bool(BRIGHTDATA_HOST and BRIGHTDATA_PORT and BRIGHTDATA_USERNAME)

# Bright Data Browser API (a.k.a. Scraping Browser) - a *different* zone from the one above.
# Only this one can solve a CAPTCHA mid-session; see core/web/browser_api.py for why.
BRIGHTDATA_BROWSER_USERNAME = os.getenv("BRIGHTDATA_BROWSER_USERNAME", "")
BRIGHTDATA_BROWSER_PASSWORD = os.getenv("BRIGHTDATA_BROWSER_PASSWORD", "")

# SeleniumBase Pure CDP avoidance (Uber spike). Real Chrome via CDP, no WebDriver,
# so TLS/JS fingerprints look like a human browser. See core/web/sb_browser.py.
# Persistent profile = cookie/storage continuity across runs (JS-coherence).
SB_HEADLESS = HEADLESS  # reuse HEADLESS: headed by default, stealth needs a window
SB_LANG = os.getenv("SB_LANG", "en-US")
SB_TZ = os.getenv("SB_TZ", "Asia/Kolkata")  # matches PROXY_COUNTRY=in
SB_USER_DATA_DIR = os.getenv("SB_USER_DATA_DIR", "")  # blank = targets/web/uber/.sb_profile
SB_PROXY = os.getenv("SB_PROXY", "")  # blank = derive from Bright Data; "none" = force direct
SB_SESSION = os.getenv("SB_SESSION", "")  # blank = random per run; set to reuse one exit IP

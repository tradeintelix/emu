"""Non-secret, per-target settings. Secrets (CapSolver key, phone numbers) stay in .env."""

# Confirmed authorized to test past Uber's sign-up CAPTCHA (not just detect-and-stop).
# Solved in-page via CapSolver (see core/web/outcome.py, core/web/sb_detect.py).
SOLVE_CAPTCHA = True

# Legacy exit-IP pin from the Bright Data era. Kept for compat but unused on
# direct connections; the page URL itself (/in/en/) keeps the English render.
# Locators are language-independent (IDs/hrefs, not labels).
PROXY_COUNTRY = "in"

# Primary Uber path is SeleniumBase CDP (test_sb_avoid_phone.py) with CapSolver
# solving when a challenge appears; test_signup_phone.py is the WebDriver twin.

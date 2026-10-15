"""Non-secret, per-target settings. Secrets (CapSolver key, phone numbers) stay in .env."""

# Confirmed authorized to test past Uber's sign-up CAPTCHA (not just detect-and-stop).
# Solved in-page via CapSolver (see core/web/outcome.py, core/web/sb_detect.py).
SOLVE_CAPTCHA = True

# Legacy exit-IP pin from the Bright Data era. Kept for compat but unused on
# direct connections; the page URL itself (/in/en/) keeps the English render.
# Locators are language-independent (IDs/hrefs, not labels).
PROXY_COUNTRY = "in"

# Country-coherent entry URLs: the page locale must match the proxy exit,
# browser timezone and typed number's country, or the risk engine sees a
# mismatch (e.g. Indian page + Bolivian number + Bolivian exit IP).
HOME_URLS = {
    "in": "https://www.uber.com/in/en/",
    "bo": "https://www.uber.com/bo/es/",
}


def home_url(country=None):
    """Entry URL for an exit country (ISO-3166, e.g. 'bo'). Falls back to the
    default country's page for unknown codes, never raises mid-run."""
    return HOME_URLS.get((country or "").lower(), HOME_URLS["in"])

# Primary Uber path is SeleniumBase CDP (test_sb_avoid_phone.py) with CapSolver
# solving when a challenge appears; test_signup_phone.py is the WebDriver twin.

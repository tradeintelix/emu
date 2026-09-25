"""Non-secret, per-target settings. Secrets (Bright Data creds, phone numbers) stay in .env."""

# Confirmed authorized to test past Uber's sign-up CAPTCHA (not just detect-and-stop).
SOLVE_CAPTCHA = True

# Pins Bright Data's exit IP so the page renders in English/India (locators are written
# against that) - without this, Bright Data can pick any country, and the page can render
# in a different language entirely (confirmed: Spanish, on an unpinned run).
PROXY_COUNTRY = "in"

# SeleniumBase Pure CDP avoidance spike (test_sb_avoid_phone.py): primary path tries
# zero-challenge via sb_cdp; fallback remains test_signup_phone.py via Browser API.
SB_MODE = "pure_cdp_avoid"

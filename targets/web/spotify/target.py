"""Non-secret, per-target settings. Secrets (Bright Data creds, phone numbers) stay in .env."""

# Confirmed authorized to test past Spotify's sign-up CAPTCHA (not just detect-and-stop).
SOLVE_CAPTCHA = True

# Pins Bright Data's exit IP so the page renders in English/India (locators are written
# against that, and SPOTIFY_PHONE is an Indian number) - see targets/web/uber/target.py
# for what happens without this (Uber rendered in Spanish on an unpinned run).
PROXY_COUNTRY = "in"

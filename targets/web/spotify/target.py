"""Non-secret, per-target settings. Secrets (CapSolver key, phone numbers) stay in .env."""

# Confirmed authorized to test past Spotify's sign-up CAPTCHA (not just detect-and-stop).
SOLVE_CAPTCHA = True

# Legacy exit-IP pin from the proxy era. Kept for compat but unused on direct
# connections (see targets/web/uber/target.py).

"""Non-secret, per-target settings. Secrets (phone numbers) stay in .env."""

APP_PACKAGE = "com.application.zomato"

# Clear app data before every run so the location/notification prompts and the
# login screen show up exactly as they do on a first launch.
FRESH_START = True

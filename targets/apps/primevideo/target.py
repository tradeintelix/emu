"""Non-secret, per-target settings. Secrets (phone numbers) stay in .env or --phone."""

APP_PACKAGE = "com.amazon.avod.thirdpartyclient"

# Clear app data before every run so Prime Video opens signed-out, as on a first launch.
FRESH_START = True

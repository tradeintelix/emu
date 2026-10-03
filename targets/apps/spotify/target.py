"""Non-secret, per-target settings. Secrets (phone numbers) stay in .env."""

APP_PACKAGE = "com.spotify.music"

# Clear app data before every run so Spotify opens on its logged-out welcome screen.
FRESH_START = True

# Country picked on the phone-login screen (Spotify defaults to the emulator's region).
COUNTRY = "India"

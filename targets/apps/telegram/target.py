"""Non-secret, per-target settings. The number is given per run, in international format:
python run.py --app telegram --phone-country Pakistan --phone +923345333345"""

APP_PACKAGE = "org.telegram.messenger"

# Clear app data before every run so Telegram opens on its welcome carousel.
FRESH_START = True

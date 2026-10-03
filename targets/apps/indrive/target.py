"""Non-secret, per-target settings. The phone country and number are given per run:
python run.py --app indrive --phone-country <name> --phone <number>"""

APP_PACKAGE = "sinet.startup.inDriver"

# Clear app data before every run so the permission prompts and welcome screen show up
# exactly as they do on a first launch.
FRESH_START = True

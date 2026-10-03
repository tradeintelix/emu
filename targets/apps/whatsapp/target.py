"""Non-secret, per-target settings. The number is given per run, in international format:
python run.py --app whatsapp --phone-country Pakistan --phone +923345333345"""

APP_PACKAGE = "com.whatsapp"

# Clear app data before every run so WhatsApp opens on its Welcome / terms screen.
FRESH_START = True

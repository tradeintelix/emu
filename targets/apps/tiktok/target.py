"""Non-secret, per-target settings. The phone country and number are given per run:
python run.py --app tiktok --phone-country India --phone 7420870251"""

APP_PACKAGE = "com.zhiliaoapp.musically"

# Keep app data: a cleared TikTok opens on a first-run onboarding instead of the home feed.
# The app is still force-stopped before every run (targets/apps/conftest.py), so it opens on Home.
FRESH_START = False

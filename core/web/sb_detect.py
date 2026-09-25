"""Challenge detection for SB CDP runs: first-class Success/Challenge/Blocked.

Mirrors core/web/outcome.py semantics but for sb_cdp (no WebDriver APIs).
Never solves - just classifies so callers can stop or fall back to Bright Data.
Visible widgets only: page source always mentions captcha/challenge/otp even
with nothing on screen, so text matching must never trigger.
"""
import time

CHALLENGE_SELECTORS = (
    "iframe[title*='recaptcha challenge' i]",
    "iframe[title*='hcaptcha challenge' i]",
    "iframe[title='Verification challenge']",
    "iframe[title*='funcaptcha' i]",
    "[class='cf-turnstile']",
    "#challenge-form div > div",
)

OTP_SELECTORS = (
    "input[autocomplete='one-time-code']",
    "input[name*='otp' i]",
    "input[name*='code' i]",
)


def is_challenge_page(sb):
    # Visible widget only: page source always contains captcha/challenge strings
    # (JS bundles, badge) even with no challenge on screen, so text alone must
    # never trigger. Mirrors outcome.py CHALLENGE_FRAME (challenge iframe, on screen).
    try:
        for sel in CHALLENGE_SELECTORS:
            if sb.is_element_visible(sel):
                return True
    except Exception:
        pass
    # Arkose shield: inert splash with Start Puzzle inside a challenge iframe.
    # data-theme is Arkose's own marker; only counts inside a visible iframe context
    # is too expensive here, so require the button visible in DOM + challenge text.
    try:
        if sb.is_element_visible("button[data-theme='home.verifyButton']"):
            return True
    except Exception:
        pass
    return False


def is_otp_page(sb):
    # Structural only: page copy always contains otp/code/sent words even with
    # no OTP on screen, so text must never trigger. Matches outcome.py: explicit
    # OTP attrs (Spotify-style) OR 4-8 narrow boxes (Uber box-per-digit).
    try:
        for sel in OTP_SELECTORS:
            if sb.is_element_visible(sel):
                return True
    except Exception:
        pass
    try:
        boxes = sb.find_visible_elements("input:not([type='hidden'])")
        narrow = [b for b in boxes if _element_width(b) < 100]
        if 4 <= len(narrow) <= 8:
            return True
    except Exception:
        pass
    return False


def _element_width(element):
    try:
        pos = element.get_position()
        return pos.width or 999
    except Exception:
        return 999


def wait_for_otp_or_blocked(sb, timeout=20, settle=5):
    """Poll until OTP (success) or challenge (blocked). Returns 'otp',
    'captcha'/'blocked', or 'timeout'. Settles briefly so SPAs finish rendering."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_otp_page(sb):
            return "otp"
        if is_challenge_page(sb):
            sb.sleep(settle if settle <= 3 else 3)
            return "captcha"
        sb.sleep(0.5)
    if is_otp_page(sb):
        return "otp"
    if is_challenge_page(sb):
        return "captcha"
    return "timeout"

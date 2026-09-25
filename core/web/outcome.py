"""Shared detection for what shows up right after a sign-up form is submitted: an OTP entry
field, or a CAPTCHA challenge. Every target's post-submit step calls this instead of each
re-guessing site-specific text - the two things we've actually seen (Spotify: reCAPTCHA,
Uber: an Arkose-style puzzle) both work through the same check.
"""
import time

from selenium.webdriver.common.by import By
from urllib3.exceptions import ReadTimeoutError

from core.web.browser_api import solve_captcha as brightdata_solve_captcha

OTP_INPUT = (By.CSS_SELECTOR,
    "input[autocomplete='one-time-code'], input[name*='otp' i], input[name*='code' i], input[maxlength='1']")
BOX_CANDIDATES = (By.CSS_SELECTOR, "input:not([type='hidden']):not([type='email']):not([type='checkbox'])")

# Every vendor also injects a near-invisible badge iframe on pages where no challenge ever
# fires (e.g. Google's reCAPTCHA badge) - matching that gives a false "captcha" positive, so
# this only matches each vendor's *challenge* iframe, and only counts it once it's on screen.
CHALLENGE_FRAME = (By.CSS_SELECTOR,
    "iframe[title*='recaptcha challenge' i], iframe[title*='hcaptcha challenge' i], "
    "iframe[title='Verification challenge'], iframe[title*='funcaptcha' i]")

# Arkose shows an inert "shield" splash first and only loads the actual puzzle once this is
# clicked. It lives inside the challenge iframe (confirmed on Uber, possibly nested further),
# so it's searched frame by frame. data-theme is Arkose's own marker, label-independent.
START_BUTTON = (By.XPATH,
    "//button[@data-theme='home.verifyButton' or contains(normalize-space(), 'Start Puzzle')]")

MAX_SOLVE_ATTEMPTS = 3


def _otp_visible(driver):
    """Uber's OTP boxes carry no otp/code attribute (unlike Spotify's), so besides the
    attribute match, also accept the box-per-digit layout itself: 4-8 narrow inputs on screen.
    The phone field is wide and type=email, so it never counts."""
    if any(e.is_displayed() for e in driver.find_elements(*OTP_INPUT)):
        return True
    boxes = [e for e in driver.find_elements(*BOX_CANDIDATES) if e.is_displayed() and e.size["width"] < 100]
    return 4 <= len(boxes) <= 8


def _click_start_in_frames(driver, depth=0):
    """Depth-first through nested iframes; returns True once a start button was clicked.
    Caller must switch back to default_content afterwards."""
    for btn in driver.find_elements(*START_BUTTON):
        if btn.is_displayed():
            btn.click()
            return True
    if depth >= 3:
        return False
    for frame in driver.find_elements(By.TAG_NAME, "iframe"):
        try:
            driver.switch_to.frame(frame)
            if _click_start_in_frames(driver, depth + 1):
                return True
            driver.switch_to.parent_frame()
        except Exception:  # frame detached mid-search; carry on with its siblings
            driver.switch_to.default_content()
            return False
    return False


def _solve(driver, timeout, label):
    try:
        status = brightdata_solve_captcha(driver, detect_timeout_s=timeout)
    except ReadTimeoutError:
        status = "bright_data_timeout"  # their endpoint went silent; treat as unsolved, don't crash
    print(f"Bright Data CAPTCHA status ({label}): {status}", flush=True)
    return status


def wait_for_otp_or_captcha(driver, timeout=20, captcha_settle=5, solve_captcha=False):
    """Polls until an OTP page or a CAPTCHA shows. With solve_captcha=False (the default),
    never interacts with a CAPTCHA - just reports it. With solve_captcha=True, asks Bright
    Data's Browser API to solve it so the flow continues to the OTP page.

    Bright Data's detection is inconsistent on Uber's SPA (confirmed: "not_detected" even with
    the puzzle on screen, "solve_finished" on another run), so it gets up to MAX_SOLVE_ATTEMPTS
    tries while a challenge is visible, clicking Start Puzzle before each retry. It is never
    called again after "solve_finished": a call with nothing to solve hung for 120s once."""
    attempts, solved = 0, False
    if solve_captcha:
        attempts += 1
        solved = _solve(driver, timeout, "attempt 1") == "solve_finished"
        if solved:
            time.sleep(captcha_settle)  # let the page dismiss the overlay itself

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _otp_visible(driver):
            return "otp"
        if any(f.is_displayed() for f in driver.find_elements(*CHALLENGE_FRAME)):
            if solve_captcha and not solved and attempts < MAX_SOLVE_ATTEMPTS:
                attempts += 1
                try:
                    clicked = _click_start_in_frames(driver)
                finally:
                    driver.switch_to.default_content()  # OTP/challenge checks live in the main document
                if clicked:
                    time.sleep(2)  # let the puzzle content mount before asking Bright Data
                note = "clicked Start Puzzle" if clicked else "no Start button found"
                solved = _solve(driver, timeout, f"attempt {attempts}, {note}") == "solve_finished"
                if solved:
                    time.sleep(captcha_settle)
                deadline = time.monotonic() + timeout  # fresh window after each attempt
                continue
            if not solved:
                time.sleep(captcha_settle)  # let it fully render before the screenshot
                return "captcha"
            # solved but overlay still up: keep waiting for the OTP page until the deadline
        time.sleep(0.5)
    if any(f.is_displayed() for f in driver.find_elements(*CHALLENGE_FRAME)):
        return "captcha"
    return "timeout"

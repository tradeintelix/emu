"""Shared detection for what shows up right after a sign-up form is submitted: an OTP entry
field, or a CAPTCHA challenge. Every target's post-submit step calls this instead of each
re-guessing site-specific text - the two things we've actually seen (Spotify: reCAPTCHA,
Uber: an Arkose-style puzzle) both work through the same check.
"""
import time

from selenium.webdriver.common.by import By

from config.settings import CAPSOLVER_TIMEOUT
from core.web import arkose, capsolver

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


def _challenge_visible(driver):
    try:
        return any(f.is_displayed() for f in driver.find_elements(*CHALLENGE_FRAME))
    except Exception:
        return False


def _start_visible(driver):
    """True while the shield splash (Start Puzzle) is still on screen - i.e. the
    real puzzle has NOT mounted yet and CapSolver params aren't ready."""
    try:
        for btn in driver.find_elements(*START_BUTTON):
            if btn.is_displayed():
                return True
    except Exception:
        pass
    return False


def _wait_for_puzzle(driver, timeout=10):
    """After clicking Start Puzzle, polls until the real captcha mounts (publicKey
    appears in DOM) or the timeout lapses. Returns the latest params dict so the
    caller can log whether the actual captcha ever appeared."""
    deadline = time.monotonic() + timeout
    params = {"publicKey": None, "surl": None, "data": None}
    while time.monotonic() < deadline:
        try:
            params = arkose.extract_params_webdriver(driver)
        except Exception:
            pass
        if params.get("publicKey"):
            return params
        # Shield gone but params not yet in DOM = puzzle still mounting.
        time.sleep(1)
    return params


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
    """One CapSolver FunCaptcha attempt. Returns solve_finished / solve_failed /
    not_detected / no_key (never raises - callers decide whether to retry)."""
    if not capsolver.is_configured():
        print(f"CapSolver ({label}): no_key - CAPSOLVER_API_KEY not set, reporting only", flush=True)
        return "no_key"
    try:
        params = arkose.extract_params_webdriver(driver)
    except Exception as e:
        print(f"CapSolver ({label}): param extraction failed: {type(e).__name__}: {e}", flush=True)
        return "solve_failed"
    if not params.get("publicKey"):
        print(f"CapSolver ({label}): not_detected - no Arkose publicKey in DOM", flush=True)
        return "not_detected"
    try:
        page_url = driver.current_url
    except Exception:
        page_url = ""
    try:
        user_agent = driver.execute_script("return navigator.userAgent")
    except Exception:
        user_agent = None
    print(f"CapSolver ({label}): solving publicKey={params['publicKey'][:8]}... "
          f"surl={params.get('surl')}", flush=True)
    try:
        token = capsolver.solve_funcaptcha(
            website_url=page_url,
            website_public_key=params["publicKey"],
            surl=params.get("surl"),
            data=params.get("data"),
            user_agent=user_agent,
            timeout_s=min(timeout, CAPSOLVER_TIMEOUT),
        )
    except capsolver.CapsolverError as e:
        print(f"CapSolver ({label}): solve_failed: {e}", flush=True)
        return "solve_failed"
    try:
        injected = arkose.inject_token_webdriver(driver, token)
    except Exception as e:
        print(f"CapSolver ({label}): injection error: {type(e).__name__}: {e}", flush=True)
        return "solve_failed"
    status = "solve_finished" if injected else "solve_failed"
    print(f"CapSolver ({label}): {status} (token injected: {injected})", flush=True)
    return status


def wait_for_otp_or_captcha(driver, timeout=90, captcha_settle=5, solve_captcha=False):
    """Polls until an OTP page or a CAPTCHA shows. With solve_captcha=False (the default),
    never interacts with a CAPTCHA - just reports it. With solve_captcha=True, solves it
    via CapSolver so the flow continues to the OTP page.

    Uber shows a shield splash ("Start Puzzle") first; the actual captcha only
    mounts AFTER that button is clicked, so every attempt clicks Start first,
    waits for the real puzzle (publicKey in DOM), then solves. CapSolver needs
    15-60s per FunCaptcha solve, so the default timeout is 90s and each attempt
    gets a fresh window. Up to MAX_SOLVE_ATTEMPTS tries while a challenge is
    visible. The solver is never called again after "solve_finished": with
    nothing left to solve the poll would just burn the task timeout."""

    def _attempt(label):
        """Clicks Start Puzzle if the shield is up, waits for the actual captcha
        to mount, then solves. Returns True only when a token was injected."""
        try:
            clicked = _click_start_in_frames(driver)
        finally:
            try:
                driver.switch_to.default_content()  # checks live in the main document
            except Exception:
                pass
        if clicked:
            print(f"CapSolver ({label}): clicked Start Puzzle - waiting for actual captcha",
                  flush=True)
            time.sleep(2)  # let the puzzle content start mounting
            params = _wait_for_puzzle(driver, timeout=10)
            if not params.get("publicKey"):
                print(f"CapSolver ({label}): actual captcha did not mount after Start click",
                      flush=True)
        else:
            print(f"CapSolver ({label}): no Start button found (puzzle may already be mounted)",
                  flush=True)
        return _solve(driver, timeout, label) == "solve_finished"

    attempts, solved = 0, False
    if solve_captcha:
        if _otp_visible(driver):
            return "otp"
        if _challenge_visible(driver):
            attempts += 1
            solved = _attempt("attempt 1")
            if solved:
                time.sleep(captcha_settle)  # let the page dismiss the overlay itself

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _otp_visible(driver):
            return "otp"
        if _challenge_visible(driver):
            if solve_captcha and not solved and attempts < MAX_SOLVE_ATTEMPTS:
                attempts += 1
                solved = _attempt(f"attempt {attempts}")
                if solved:
                    time.sleep(captcha_settle)
                deadline = time.monotonic() + timeout  # fresh window after each attempt
                continue
            if not solved:
                time.sleep(captcha_settle)  # let it fully render before the screenshot
                return "captcha"
            # solved but overlay still up: keep waiting for the OTP page until the deadline
        time.sleep(0.5)
    if _challenge_visible(driver):
        return "captcha"
    return "timeout"

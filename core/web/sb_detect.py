"""Challenge detection + CapSolver solving for SB CDP runs.

Mirrors core/web/outcome.py semantics but for sb_cdp (no WebDriver APIs).
Detection is visible-widgets-only: page source always mentions
captcha/challenge/otp even with nothing on screen, so text matching must
never trigger. Solving extracts Arkose params via JS, solves via CapSolver,
and injects the fc-token - same flow as the WebDriver path.
"""
import time

from config.settings import CAPSOLVER_TIMEOUT
from core.web import arkose, capsolver

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


MAX_SOLVE_ATTEMPTS = 3


def _solve_sb(sb, label, timeout):
    """One CapSolver attempt on the SB-CDP browser. Never raises."""
    if not capsolver.is_configured():
        print(f"CapSolver ({label}): no_key - CAPSOLVER_API_KEY not set, reporting only", flush=True)
        return "no_key"
    params = arkose.extract_params_sb(sb)
    if not params.get("publicKey"):
        print(f"CapSolver ({label}): not_detected - no Arkose publicKey in DOM", flush=True)
        return "not_detected"
    try:
        page_url = sb.get_current_url()
    except Exception:
        page_url = ""
    try:
        user_agent = sb.execute_script("return navigator.userAgent")
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
    injected = arkose.inject_token_sb(sb, token)
    status = "solve_finished" if injected else "solve_failed"
    print(f"CapSolver ({label}): {status} (token injected: {injected})", flush=True)
    return status


def _click_start_sb(sb):
    """Clicks Arkose's Start Puzzle splash on the SB-CDP browser. Returns True if clicked."""
    try:
        if sb.is_element_visible("button[data-theme='home.verifyButton']"):
            sb.click("button[data-theme='home.verifyButton']")
            return True
    except Exception:
        pass
    for sel in ("button:contains('Start Puzzle')",):
        try:
            els = sb.find_visible_elements(sel)
            if els:
                els[0].click()
                return True
        except Exception:
            pass
    return False


def _wait_for_puzzle_sb(sb, timeout=10):
    """After clicking Start Puzzle, polls until the actual captcha mounts
    (publicKey appears in DOM). Returns True when ready."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if arkose.extract_params_sb(sb).get("publicKey"):
                return True
        except Exception:
            pass
        sb.sleep(1)
    return False


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


def wait_for_otp_or_blocked(sb, timeout=20, settle=5, solve_captcha=False):
    """Poll until OTP (success) or challenge. With solve_captcha=False (default)
    just reports 'captcha'. With True, solves via CapSolver to reach OTP.

    Returns 'otp', 'captcha'/'blocked', or 'timeout'. Settles briefly so SPAs
    finish rendering. Without a funded CAPSOLVER_API_KEY, solving degrades to
    reporting (returns 'captcha'), so runs keep working before funding."""
    return wait_for_otp_or_captcha(sb, timeout=timeout, settle=settle, solve_captcha=solve_captcha)


def wait_for_otp_or_captcha(sb, timeout=90, settle=5, solve_captcha=False):
    """CapSolver-aware poll: OTP -> 'otp'; challenge with solve_captcha=True ->
    clicks Start Puzzle first (the actual captcha only mounts after it), waits
    for the real puzzle, then token-solves; challenge without solving ->
    'captcha'."""
    def _attempt(label):
        clicked = _click_start_sb(sb)
        if clicked:
            print(f"CapSolver ({label}): clicked Start Puzzle - waiting for actual captcha",
                  flush=True)
            sb.sleep(2)  # let the puzzle content start mounting
            if not _wait_for_puzzle_sb(sb, timeout=10):
                print(f"CapSolver ({label}): actual captcha did not mount after Start click",
                      flush=True)
        else:
            print(f"CapSolver ({label}): no Start button found (puzzle may already be mounted)",
                  flush=True)
        return _solve_sb(sb, label, timeout) == "solve_finished"

    attempts, solved = 0, False
    if solve_captcha and is_challenge_page(sb):
        # Shield splash counts as a challenge, so attempt 1 clicks Start before
        # solving instead of solving against the unmounted shield.
        if is_otp_page(sb):
            return "otp"
        attempts += 1
        solved = _attempt("attempt 1")
        if solved:
            sb.sleep(settle)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_otp_page(sb):
            return "otp"
        if is_challenge_page(sb):
            if solve_captcha and not solved and attempts < MAX_SOLVE_ATTEMPTS:
                attempts += 1
                solved = _attempt(f"attempt {attempts}")
                if solved:
                    sb.sleep(settle)
                deadline = time.monotonic() + timeout  # fresh window after each attempt
                continue
            if not solved:
                sb.sleep(settle if settle <= 3 else 3)  # let it render before screenshot
                return "captcha"
            # solved but overlay still up: keep waiting for OTP until deadline
        sb.sleep(0.5)
    if is_otp_page(sb):
        return "otp"
    if is_challenge_page(sb):
        return "captcha"
    return "timeout"

"""Uber signup via SeleniumBase Pure CDP (CapSolver solve path).

Flow mirrors test_signup_phone.py but runs on sb_cdp (no WebDriver):
home -> Sign up -> Ride -> guest-map Sign up -> phone -> Continue -> OTP.

Avoidance techniques (Browserless guide):
- real Chrome via CDP (TLS/JS coherence), headed, persistent profile
- locale en-US + tz Asia/Kolkata for header coherence
- visible-only clicks, human sleeps + human-speed typing, minimal pages
- honeypot-safe: exact IDs/hrefs only, never blind input dumps

On challenge: solve via CapSolver (same as the WebDriver path) to reach OTP.
Without CAPSOLVER_API_KEY the challenge only reports as 'captcha' and the
test fails as Blocked. Never types OTP.
"""
import random
import time
from pathlib import Path

from config.settings import PROXY_COUNTRY, require
from core.web.sb_browser import create_sb_cdp_browser, quit_sb
from core.web.sb_detect import is_challenge_page, wait_for_otp_or_captcha
from core.web.steps import StepRecorder
from targets.web.uber import target as target_cfg


HOME_URL = "https://www.uber.com/in/en/"
# Visible-only, locale-resilient selectors (href/ID, not labels).
RIDE_LINK = "a[href*='m.uber.com/looking']"
GUEST_SIGNUP = "a[href*='/go/sign-up']"
PHONE_FIELD = "#PHONE_NUMBER_or_EMAIL_ADDRESS"
CONTINUE_BTN = "#forward-button"


def human_pause(sb, lo=3.5, hi=6.5):
    """Reading-like pause with jitter: humans don't teleport between pages."""
    sb.sleep(random.uniform(lo, hi))


def _sb_step(rec, name, fn, *args, **kwargs):
    with rec.step(name):
        return fn(*args, **kwargs)


def _click_first_visible(sb, selector, timeout=20):
    """Uber repeats 'Sign up' in nav+footer; hover, read-pause, then click first on-screen match."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            for el in sb.find_visible_elements(selector):
                try:
                    el.scroll_into_view()
                    sb.sleep(random.uniform(0.6, 1.4))
                    el.click()
                    return
                except Exception:
                    continue
        except Exception:
            pass
        sb.sleep(0.8)
    raise AssertionError(f"No visible element for {selector}")


def _click_sign_up_header(sb, timeout=20):
    """Header 'Sign up' renders as <a> or <button> depending on profile/variant;
    match by visible text across both (fresh profiles use the button pill)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for tag in ("a", "button", None):
            try:
                el = sb.find_element_by_text("Sign up", tag_name=tag) if tag else sb.find_element_by_text("Sign up")
                if el:
                    try:
                        el.click()
                        return
                    except Exception:
                        pass
            except Exception:
                pass
        for sel in ("a:contains('Sign up')", "button:contains('Sign up')"):
            try:
                _click_first_visible(sb, sel, timeout=2)
                return
            except Exception:
                pass
        sb.sleep(0.8)
    raise AssertionError("No visible 'Sign up' link in header")


def _warm_up_on_page(sb, scrolls=3):
    """Human engagement: slow scrolls + dwells. Fresh profiles with zero
    engagement that teleport straight to signup score as bots."""
    for _ in range(scrolls):
        try:
            sb.scroll_down(random.uniform(300, 600))
        except Exception:
            break
        sb.sleep(random.uniform(1.2, 2.4))
    sb.sleep(random.uniform(1.0, 2.0))
    try:
        sb.scroll_to_top()
    except Exception:
        pass
    sb.sleep(random.uniform(1.0, 2.0))


def test_signup_avoid_captcha():
    import os
    dry_run = os.getenv("SB_DRY_RUN", "0") == "1"  # stop before Continue: no number burn
    phone = require("UBER_PHONE")
    target_dir = Path(__file__).parents[1]
    report_dir = target_dir / "reports" / time.strftime("%Y%m%d-%H%M%S-sb-cdp")
    country = PROXY_COUNTRY or target_cfg.PROXY_COUNTRY
    sb = create_sb_cdp_browser(url="about:blank", country=country)
    rec = StepRecorder(sb, report_dir)
    try:
        _sb_step(rec, "Open uber.com", sb.goto, HOME_URL)
        human_pause(sb, 5.0, 8.0)  # let SPA + risk engine settle; instant clicks flag bots
        with rec.step("Warm up on home page"):
            _warm_up_on_page(sb, scrolls=3)
            # Hover Sign up like a reading user, don't click instantly.
            try:
                sb.hover_element("a:contains('Sign up')")
                sb.sleep(random.uniform(0.8, 1.6))
            except Exception:
                pass

        _sb_step(rec, "Click Sign up", _click_sign_up_header, sb)
        human_pause(sb, 4.0, 6.5)

        _sb_step(rec, "Choose Ride", _click_first_visible, sb, RIDE_LINK)
        human_pause(sb, 5.0, 8.0)
        with rec.step("Warm up on ride page"):
            _warm_up_on_page(sb, scrolls=2)

        _sb_step(rec, "Click Sign up on the guest map page",
                 _click_first_visible, sb, GUEST_SIGNUP)
        human_pause(sb, 5.0, 8.0)

        def _enter_phone():
            sb.assert_element_present(PHONE_FIELD, timeout=20)
            sb.scroll_into_view(PHONE_FIELD)
            sb.sleep(random.uniform(0.8, 1.6))
            # CDP input (goes to the right window even with other Chromes open;
            # OS-level PyAutoGUI typed into the user's manual window instead).
            sb.click(PHONE_FIELD)
            sb.sleep(random.uniform(0.8, 1.5))
            sb.clear_input(PHONE_FIELD)
            sb.sleep(random.uniform(0.5, 1.0))
            # Char-by-char human typing: burst typing trips velocity checks.
            sb.click(PHONE_FIELD)
            for ch in phone:
                sb.press_keys(PHONE_FIELD, ch)
                sb.sleep(random.uniform(0.12, 0.32))
            sb.sleep(random.uniform(1.2, 2.2))
            # Guard against silent empty submits (field must hold the number).
            typed = (sb.get_attribute(PHONE_FIELD, "value") or "").replace(" ", "")
            want = phone.replace(" ", "")
            assert want[-10:] in typed, f"Phone field empty/mismatch: {typed!r}"
            # Blur the field so change/validation events fire like a Tab-out.
            sb.press_keys(PHONE_FIELD, "\t")
            sb.sleep(random.uniform(0.6, 1.2))

        _sb_step(rec, "Enter phone number", _enter_phone)
        if dry_run:
            # No-submit check: proves warm-up itself doesn't trigger a challenge
            # without burning the number again. Asserts phone page is clean.
            with rec.step("Dry-run check (no Continue)"):
                assert not is_challenge_page(sb), "Challenge before submit - warm-up failed"
                print("Dry-run OK: phone entered, no challenge pre-submit", flush=True)
            return
        human_pause(sb, 3.0, 5.0)  # read-back pause before submitting
        # Hover Continue like a human aiming the mouse, then CDP-click.
        try:
            sb.hover_element(CONTINUE_BTN)
            sb.sleep(random.uniform(0.8, 1.6))
        except Exception:
            pass

        _sb_step(rec, "Click Continue", sb.click, CONTINUE_BTN)
        sb.sleep(random.uniform(5.0, 7.0))  # let auth.uber.com settle before classifying

        with rec.step("Wait for OTP page or CAPTCHA"):
            outcome = wait_for_otp_or_captcha(sb, timeout=90, solve_captcha=True)
        print(f"Outcome: {outcome}", flush=True)
        assert outcome != "timeout", "Neither OTP nor CAPTCHA appeared after Continue"
        assert outcome == "otp", (
            f"Blocked by challenge ({outcome}). See {report_dir} - "
            "set CAPSOLVER_API_KEY for CapSolver to solve it."
        )

        with rec.step("Wait 10s on the OTP page"):
            # Never type OTP; pause so a person can read the phone if needed.
            if is_challenge_page(sb):
                raise AssertionError("Challenge appeared late on OTP page - stopping")
            time.sleep(10)
    finally:
        rec.finish()
        quit_sb(sb)

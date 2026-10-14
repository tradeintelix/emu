import time

from config.settings import PHONE, PHONE_COUNTRY, STOP_AT_OTP, require
from core.permissions import allow_permissions_until
from targets.apps.spotify import target
from targets.apps.spotify.pages.login_page import LoginPage
from targets.apps.spotify.pages.otp_page import OtpPage
from targets.apps.spotify.pages.phone_page import PhonePage
from targets.apps.spotify.pages.welcome_page import WelcomePage


RESEND_AFTER = 30  # seconds on the OTP screen before Resend code is tapped


def test_login_with_phone_number(steps):
    """First launch -> Log in -> Phone number -> country -> enter number -> Next -> OTP screen ->
    after RESEND_AFTER seconds without an OTP, Resend code is tapped once;
    SMPP decision (core/otp.py): REJECTED (delivered to a real handset) ends the flow without typing
    anything; ACCEPTED types the OTP from SMPP and waits for Spotify to leave the code screen."""
    country = PHONE_COUNTRY or target.COUNTRY
    phone = PHONE or require("SPOTIFY_PHONE")
    # field takes the national number; the calling code comes from the selected country.
    phone = "".join(c for c in phone if c.isdigit())  # --phone is already without the country code
    welcome, login = WelcomePage(steps.driver), LoginPage(steps.driver)
    phone_page, otp = PhonePage(steps.driver), OtpPage(steps.driver)

    with steps.step("Wait for welcome screen"):
        # first launch after a data wipe shows a blank screen for ~10s; allows any prompt meanwhile
        try:
            allow_permissions_until(steps.driver, welcome.is_open, timeout=45)
        except TimeoutError:  # the first launch sometimes hangs on a blank splash; a relaunch clears it
            steps.driver.terminate_app(target.APP_PACKAGE)
            steps.driver.activate_app(target.APP_PACKAGE)
            allow_permissions_until(steps.driver, welcome.is_open, timeout=90)
    with steps.step("Tap Log in"):
        welcome.tap_log_in()
    with steps.step("Choose Phone number"):
        login.choose_phone_number()
    with steps.step(f"Select country {country}"):
        phone_page.select_country(country)
    with steps.step("Enter phone number"):
        phone_page.enter_phone(phone)
    with steps.step("Tap Next"):
        phone_page.tap_next()
        steps.otp.otp_requested()
    with steps.step("Wait for OTP screen"):
        print(f"OTP screen: {otp.wait_until_open()}", flush=True)
    if STOP_AT_OTP:  # no SMPP decision in this mode: wait out the resend cooldown, tap Resend, then stop
        with steps.step(f"Wait {RESEND_AFTER}s on the OTP screen"):
            time.sleep(RESEND_AFTER)
        with steps.step("Tap Resend code"):
            otp.tap_resend()
        with steps.step("Wait 5s after resend"):
            time.sleep(5)
        return
    with steps.step(f"Wait for SMPP decision ({RESEND_AFTER}s)"):
        decision, code = steps.otp.wait(RESEND_AFTER, final=False)
    if not decision:  # nothing arrived yet: ask Spotify for a new code, then wait the full time
        with steps.step("Tap Resend code"):
            otp.tap_resend()
        with steps.step("Wait for SMPP decision"):
            decision, code = steps.otp.wait()
    print(f"SMPP decision: {decision}", flush=True)
    assert decision, "No SMPP decision before OTP_WAIT_TIMEOUT"
    if decision == "REJECTED":
        return  # delivered to a real handset: no OTP to enter, this number is done
    with steps.step("Enter OTP"):
        otp.enter_code(code)
    with steps.step("Wait for login to complete"):
        otp.wait_until_closed()

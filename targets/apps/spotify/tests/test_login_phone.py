import time

from config.settings import PHONE, PHONE_COUNTRY, require
from core.permissions import allow_permissions_until
from targets.apps.spotify import target
from targets.apps.spotify.pages.login_page import LoginPage
from targets.apps.spotify.pages.otp_page import OtpPage
from targets.apps.spotify.pages.phone_page import PhonePage
from targets.apps.spotify.pages.welcome_page import WelcomePage


def test_login_with_phone_number(steps):
    """First launch -> Log in -> Phone number -> country -> enter number -> Next -> OTP screen ->
    wait 30s -> Resend code -> wait 5s. Never types an OTP."""
    country = PHONE_COUNTRY or target.COUNTRY
    phone = PHONE or require("SPOTIFY_PHONE")
    # field takes the national number; the calling code comes from the selected country.
    # ponytail: last 10 digits fits India and Pakistan; other countries' number lengths differ
    phone = "".join(c for c in phone if c.isdigit())[-10:]
    welcome, login = WelcomePage(steps.driver), LoginPage(steps.driver)
    phone_page, otp = PhonePage(steps.driver), OtpPage(steps.driver)

    with steps.step("Wait for welcome screen"):
        # first launch after a data wipe shows a blank screen for ~10s; allows any prompt meanwhile
        allow_permissions_until(steps.driver, welcome.is_open)
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
    with steps.step("Wait for OTP screen"):
        print(f"OTP screen: {otp.wait_until_open()}", flush=True)
    with steps.step("Wait 30s on the OTP screen"):
        time.sleep(30)
    with steps.step("Tap Resend code"):
        otp.tap_resend()
    with steps.step("Wait 5s after resend"):
        time.sleep(5)

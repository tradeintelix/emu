import time

from config.settings import PHONE, PHONE_COUNTRY
from core.permissions import allow_permissions_until
from targets.apps.indrive.pages.otp_page import OtpPage
from targets.apps.indrive.pages.phone_page import PhonePage
from targets.apps.indrive.pages.welcome_page import WelcomePage


def test_login_with_phone_number(steps):
    """First launch -> allow prompts -> Continue with phone -> country -> number -> Next ->
    OTP screen -> wait 30s -> Resend code -> wait 5s. Never types an OTP."""
    assert PHONE_COUNTRY and PHONE, (
        "Give the country and number on the command line: "
        "python run.py --app indrive --phone-country <name> --phone <number>")
    phone = "".join(c for c in PHONE if c.isdigit())
    welcome, phone_page, otp = WelcomePage(steps.driver), PhonePage(steps.driver), OtpPage(steps.driver)

    with steps.step("Allow first-launch permissions"):
        allowed = allow_permissions_until(steps.driver, welcome.is_open)
        print(f"Allowed {allowed} permission prompt(s)", flush=True)
    with steps.step("Tap Continue with phone"):
        welcome.continue_with_phone()
    with steps.step(f"Select country {PHONE_COUNTRY}"):
        phone_page.select_country(PHONE_COUNTRY)
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

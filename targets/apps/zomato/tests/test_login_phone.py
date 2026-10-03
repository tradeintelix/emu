import time

from config.settings import PHONE, PHONE_COUNTRY, require
from core.permissions import allow_permissions_until
from targets.apps.zomato.pages.login_page import LoginPage
from targets.apps.zomato.pages.otp_page import OtpPage


def test_login_with_phone_number(steps):
    """First launch -> allow location + notifications -> enter number -> Continue -> OTP screen.
    Waits 5s on the OTP screen and stops; never types an OTP."""
    # the flow types next to a fixed +91; any other country's number would reach a stranger in India
    assert PHONE_COUNTRY in ("", "India"), f"Zomato flow only supports India numbers, got --phone-country {PHONE_COUNTRY}"
    phone = PHONE or require("ZOMATO_PHONE")
    login, otp = LoginPage(steps.driver), OtpPage(steps.driver)

    with steps.step("Allow first-launch permissions"):
        allowed = allow_permissions_until(steps.driver, login.is_open)
        print(f"Allowed {allowed} permission prompt(s)", flush=True)
    with steps.step("Enter phone number"):
        login.enter_phone(phone)
    with steps.step("Tap Continue"):
        login.submit()
    with steps.step("Wait for OTP screen"):
        otp.wait_until_open()
    with steps.step("Wait 5s on the OTP screen"):
        time.sleep(5)

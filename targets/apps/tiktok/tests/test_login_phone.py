import time

from config.settings import PHONE, PHONE_COUNTRY
from targets.apps.tiktok.pages.home_page import HomePage
from targets.apps.tiktok.pages.login_page import LoginSheet, PhoneLoginPage
from targets.apps.tiktok.pages.otp_page import OtpPage


def test_login_with_phone_number(steps):
    """Home feed -> Profile -> 'Use phone/email/username' -> Phone tab: country + number ->
    Continue -> OTP screen -> wait 5s. Never types the code."""
    assert PHONE_COUNTRY and PHONE, (
        "Give the country and number on the command line: "
        "python run.py --app tiktok --phone-country <name> --phone <number>")
    phone = "".join(c for c in PHONE if c.isdigit())
    # the feed's videos keep the screen from ever going idle, which stalls every lookup ~10s
    steps.driver.update_settings({"waitForIdleTimeout": 0})
    home, sheet, form, otp = (HomePage(steps.driver), LoginSheet(steps.driver),
                              PhoneLoginPage(steps.driver), OtpPage(steps.driver))

    with steps.step("Wait for Home feed"):
        print(f"Pressed Back {home.wait_until_open()} time(s) to clear popups", flush=True)
    with steps.step("Tap Profile"):
        home.open_profile()
    with steps.step("Tap Use phone/email/username"):
        sheet.use_phone()
    with steps.step(f"Select country {PHONE_COUNTRY}"):
        print(f"Country code: {form.select_country(PHONE_COUNTRY)}", flush=True)
    with steps.step("Enter phone number"):
        form.enter_phone(phone)
    with steps.step("Tap Continue"):
        form.tap_continue()
    with steps.step("Wait for OTP screen"):
        print(f"OTP screen: {otp.wait_until_open()}", flush=True)
    with steps.step("Wait 5s on the OTP screen"):
        time.sleep(5)

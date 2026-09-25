import time

from config.settings import require
from targets.web.uber.pages.guest_map_page import GuestMapPage
from targets.web.uber.pages.home_page import HomePage
from targets.web.uber.pages.signup_page import SignUpPage


def test_signup_with_phone_number(steps):
    """Home -> Sign up -> Ride -> (guest map) Sign up -> enter number -> Continue.
    Waits 10s on the OTP page if one appears; stops immediately on a CAPTCHA. Never types a
    real OTP - the code is only ever read off the phone by a person, never by this script."""
    phone = require("UBER_PHONE")
    home = HomePage(steps.driver)
    guest_map = GuestMapPage(steps.driver)
    signup = SignUpPage(steps.driver)

    with steps.step("Open uber.com"):
        home.open()
    with steps.step("Click Sign up"):
        home.click_sign_up()
    with steps.step("Choose Ride"):
        home.choose_ride()
    with steps.step("Click Sign up on the guest map page"):
        guest_map.click_sign_up()
    with steps.step("Enter phone number"):
        signup.enter_phone(phone)
    with steps.step("Click Continue"):
        signup.submit()
    with steps.step("Wait for OTP page or CAPTCHA"):
        outcome = signup.wait_for_otp_or_captcha(solve_captcha=steps.solve_captcha)
    print(f"Outcome: {outcome}", flush=True)
    assert outcome != "timeout", "Neither an OTP field nor a CAPTCHA showed up after Continue"

    if outcome == "otp":
        with steps.step("Wait 10s on the OTP page"):
            time.sleep(10)
    # "captcha": Bright Data either wasn't enabled or couldn't solve it - stop either way,
    # no manual bypass attempt. Never types a real OTP even when solve_captcha gets us there.

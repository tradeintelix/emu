from config.settings import require
from targets.web.spotify.pages.home_page import HomePage
from targets.web.spotify.pages.signup_page import SignUpPage


def test_signup_with_phone_number(steps):
    """Home -> Sign up -> 'Sign up with phone number' -> enter number -> Continue. Stops before the CAPTCHA."""
    phone = require("SPOTIFY_PHONE")
    home, signup = HomePage(steps.driver), SignUpPage(steps.driver)

    with steps.step("Open open.spotify.com"):
        home.open()
    with steps.step("Click Sign up"):
        home.click_sign_up()
    with steps.step("Choose Sign up with phone number"):
        signup.choose_phone()
    with steps.step("Enter phone number"):
        signup.enter_phone(phone)
    with steps.step("Click Continue"):
        signup.submit()
    with steps.step("Wait for OTP page or CAPTCHA"):
        outcome = signup.wait_for_otp_or_captcha(solve_captcha=steps.solve_captcha)
    print(f"Outcome: {outcome}", flush=True)
    assert outcome != "timeout", "Neither an OTP field nor a CAPTCHA showed up after Continue"
    # "captcha": Bright Data either wasn't enabled or couldn't solve it - stop either way.
    # "otp": never types a real OTP even when solve_captcha gets us there.

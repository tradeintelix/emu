import time

from config.settings import PHONE, PHONE_COUNTRY, require
from core.countries import calling_code
from core.permissions import allow_permissions_until
from targets.apps.primevideo.pages.otp_page import OtpPage
from targets.apps.primevideo.pages.signin_page import SignInPage
from targets.apps.primevideo.pages.start_page import StartPage


def test_signin_with_phone_number(steps):
    """First launch -> (homepage 'SIGN IN' | 'Login or Sign up') -> Welcome page -> make sure
    'Sign in' is selected -> enter number -> Continue -> OTP screen -> wait 5s. Never types an OTP.

    Number three ways (same as WhatsApp):
      --phone-country Pakistan --phone 3345333345   (code from core/countries.json)
      --phone +923345333345                          (international format)
      --phone 7420870251                             (bare = India)"""
    # No country picker: Amazon reads '+<code><number>' as that country, and a bare number as
    # Indian (the app's region). A bare foreign number would therefore reach a stranger in India.
    raw = (PHONE or require("PRIMEVIDEO_PHONE")).strip()
    digits = "".join(c for c in raw if c.isdigit())
    if raw.startswith("+"):
        phone = "+" + digits
    elif PHONE_COUNTRY and PHONE_COUNTRY != "India":
        phone = "+" + calling_code(PHONE_COUNTRY) + digits
    else:
        phone = digits[-10:]
    start, signin, otp = StartPage(steps.driver), SignInPage(steps.driver), OtpPage(steps.driver)

    with steps.step("Wait for first screen"):
        # 120s: over a slow VPN the homepage content takes a while to render
        allow_permissions_until(steps.driver, start.is_open, timeout=120)
    with steps.step("Open sign-in"):
        print(f"First screen: {start.open_sign_in()}", flush=True)
    with steps.step("Make sure Sign in is selected"):
        signin.ensure_sign_in_selected()
    with steps.step("Enter phone number"):
        # the sign-in window is FLAG_SECURE, so screenshots of it are black; log the field instead
        print(f"Number field holds: {signin.enter_phone(phone)}", flush=True)
    with steps.step("Tap Continue"):
        signin.tap_continue()
    with steps.step("Wait for OTP screen"):
        print(f"OTP screen: code sent to {otp.wait_until_open()}", flush=True)
    with steps.step("Wait 5s on the OTP screen"):
        time.sleep(5)

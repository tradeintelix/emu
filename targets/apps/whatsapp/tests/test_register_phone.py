import time

from config.settings import PHONE, PHONE_COUNTRY, require
from core.countries import calling_code
from core.permissions import allow_permissions_until
from targets.apps.whatsapp.pages.onboarding_page import OnboardingPage
from targets.apps.whatsapp.pages.otp_page import ConfirmNumberDialog, OtpPage
from targets.apps.whatsapp.pages.phone_page import PhonePage


def test_register_with_phone_number(steps):
    """First launch -> Agree and continue -> Continue (notifications) -> Allow -> set country +
    number -> Next -> confirm -> verification screen -> wait 5s. Never types the code.

    Number three ways:
      --phone-country Pakistan --phone 3345333345   (code from core/countries.json)
      --phone +923345333345                          (international format, any country)
      --phone 7420870251                             (bare = India)
    --phone-country is always asserted against the country WhatsApp resolves from the code."""
    raw = (PHONE or require("WHATSAPP_PHONE")).strip()
    digits = "".join(c for c in raw if c.isdigit())
    if raw.startswith("+"):
        with_cc = digits
    elif PHONE_COUNTRY:
        with_cc = calling_code(PHONE_COUNTRY) + digits
    else:
        with_cc = "91" + digits[-10:]  # bare number, no country = India

    onboard, phone_page = OnboardingPage(steps.driver), PhonePage(steps.driver)
    confirm, otp = ConfirmNumberDialog(steps.driver), OtpPage(steps.driver)

    with steps.step("Wait for Welcome screen"):
        allow_permissions_until(steps.driver, onboard.is_welcome_open)
    with steps.step("Agree and continue"):
        onboard.agree()
    with steps.step("Continue past notifications + Allow"):
        onboard.continue_notifications()
        allow_permissions_until(steps.driver, phone_page.is_open)
    with steps.step("Set country and number"):
        code, national, country = phone_page.split_code(with_cc)
        if PHONE_COUNTRY:
            assert PHONE_COUNTRY.lower() == country.lower(), (
                f"--phone-country {PHONE_COUNTRY} but calling code +{code} is {country}")
        phone_page.enter_number(national)
        print(f"Set +{code} {national} ({country})", flush=True)
    with steps.step("Tap Next"):
        phone_page.tap_next()
    with steps.step("Confirm the number"):
        confirm.confirm_if_present()
    with steps.step("Wait for verification screen"):
        print(f"Verification screen: {otp.wait_until_open()}", flush=True)
    with steps.step("Wait 5s on the verification screen"):
        time.sleep(5)

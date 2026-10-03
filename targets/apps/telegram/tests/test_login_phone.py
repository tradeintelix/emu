import time

from config.settings import PHONE, PHONE_COUNTRY, require
from core.countries import calling_code
from core.permissions import allow_permissions_until
from targets.apps.telegram.pages.code_page import CodePage, ConfirmNumberDialog
from targets.apps.telegram.pages.onboarding_page import OnboardingPage
from targets.apps.telegram.pages.permissions import dismiss_until
from targets.apps.telegram.pages.phone_page import PhonePage


def test_login_with_phone_number(steps):
    """Welcome -> Start Messaging -> (call-permission explainer + OS dialog) -> set country +
    number -> Done -> confirm Yes -> (call-log explainer + OS dialog) -> verification screen ->
    wait 5s. Never types the code.

    Number three ways:
      --phone-country Pakistan --phone 3345333345   (code from core/countries.json)
      --phone +923345333345                          (international format, any country)
      --phone 7420870251                             (bare = India)
    --phone-country is always asserted against the country Telegram resolves from the code."""
    raw = (PHONE or require("TELEGRAM_PHONE")).strip()
    digits = "".join(c for c in raw if c.isdigit())
    if raw.startswith("+"):
        with_cc = digits
    elif PHONE_COUNTRY:
        with_cc = calling_code(PHONE_COUNTRY) + digits
    else:
        with_cc = "91" + digits[-10:]  # bare number, no country = India

    onboard, phone_page = OnboardingPage(steps.driver), PhonePage(steps.driver)
    confirm, code = ConfirmNumberDialog(steps.driver), CodePage(steps.driver)

    with steps.step("Wait for Welcome screen"):
        allow_permissions_until(steps.driver, onboard.is_welcome_open)
    with steps.step("Start Messaging"):
        onboard.start()
    with steps.step("Dismiss the phone-call permission explainer"):
        dismiss_until(steps.driver, phone_page.is_open)
    with steps.step("Set country and number"):
        code_, national, country = phone_page.split_code(with_cc)
        if PHONE_COUNTRY:
            assert PHONE_COUNTRY.lower() == country.lower(), (
                f"--phone-country {PHONE_COUNTRY} but calling code +{code_} is {country}")
        phone_page.enter_number(national)
        print(f"Set +{code_} {national} ({country})", flush=True)
    with steps.step("Tap Done"):
        phone_page.tap_done()
    with steps.step("Confirm the number"):
        confirm.confirm_if_present()
    with steps.step("Dismiss the call-log permission explainer"):
        dismiss_until(steps.driver, code.is_open)
    with steps.step("Wait for verification screen"):
        print(f"Verification screen: {code.wait_until_open()}", flush=True)
    with steps.step("Wait 5s on the verification screen"):
        time.sleep(5)

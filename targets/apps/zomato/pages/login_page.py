import time

from appium.webdriver.common.appiumby import AppiumBy

from core.base_page import BasePage


def _by(selector):
    return (AppiumBy.ANDROID_UIAUTOMATOR, selector)


class LoginPage(BasePage):
    """'Log in or sign up' screen: mobile number field (+91 prefix is fixed) or social logins."""

    # Zomato's own ids (19.9.1). The country-flag picker beside +91 is also an EditText
    # (id/et_final), so never locate the phone field by class/position.
    PHONE = (AppiumBy.ID, "com.application.zomato:id/fw_mobile_edit_text")
    CONTINUE = (AppiumBy.ID, "com.application.zomato:id/send_otp_button")
    # Google's "Choose a phone number" sheet pops up when the field gets focus on Play-enabled devices
    PHONE_HINT_DISMISS = _by('new UiSelector().textMatches("(?i)none of the above")')

    def is_open(self):
        return bool(self.driver.find_elements(*self.PHONE))

    def enter_phone(self, phone):
        self.click(self.PHONE)
        self._dismiss_phone_hint()
        self.fill(self.PHONE, phone)
        typed = "".join(c for c in (self.find(self.PHONE).text or "") if c.isdigit())
        assert phone[-10:] in typed, f"Phone field holds {typed!r}, expected {phone!r}"

    def submit(self):
        self.click(self.CONTINUE)

    def _dismiss_phone_hint(self, wait=3):
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            hint = self.driver.find_elements(*self.PHONE_HINT_DISMISS)
            if hint:
                hint[0].click()
                return
            time.sleep(0.5)

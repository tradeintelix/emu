from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait

from core.base_page import BasePage


def _html_id(element_id):
    """The form is Amazon's web sign-in inside a WebView; Android exposes the HTML ids as
    resource ids without a package prefix."""
    return (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("{element_id}")')


class SignInPage(BasePage):
    """'Welcome' page: 'Create account' / 'Sign in' options, then 'Enter mobile number or email'."""

    SIGN_IN_OPTION = _html_id("login_accordion_header")
    PHONE = _html_id("ap_email_login")  # only rendered while 'Sign in' is the selected option
    CONTINUE = _html_id("continue")

    def ensure_sign_in_selected(self, timeout=30):
        """Waits for the WebView to load, then selects 'Sign in' if 'Create account' is open instead."""
        WebDriverWait(self.driver, timeout).until(
            lambda d: d.find_elements(*self.SIGN_IN_OPTION), message="Sign-in page did not load")
        if not self.driver.find_elements(*self.PHONE):
            self.click(self.SIGN_IN_OPTION)
        self.find(self.PHONE)

    def enter_phone(self, phone):
        """phone: '7420870251' (read as Indian) or '+923345333345' (international format)."""
        self.fill(self.PHONE, phone)
        typed = (self.find(self.PHONE).text or "").strip()
        digits = lambda s: "".join(c for c in s if c.isdigit())
        assert digits(typed) == digits(phone) and typed.startswith("+") == phone.startswith("+"), (
            f"Phone field holds {typed!r}, expected {phone!r}")
        return typed

    def tap_continue(self):
        self.click(self.CONTINUE)

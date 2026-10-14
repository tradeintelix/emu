import random
import secrets
import string
import time

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

    NAME = _html_id("ap_customer_name")
    PASSWORD = _html_id("ap_password")
    VERIFY = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches("(?i)verify mobile number")')

    def complete_create_account(self, timeout=20):
        """If Continue landed on 'Create account' (number not registered), fills a random name and
        password and taps 'Verify mobile number'. Returns True if it did, False if the page never showed."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.driver.find_elements(*self.NAME):
                break
            time.sleep(1)
        else:
            return False
        first = random.choice(["Aarav", "Liam", "Maya", "Noah", "Zara", "Ethan", "Nina", "Omar"])
        last = random.choice(["Smith", "Khan", "Patel", "Moyo", "Brown", "Ncube", "Lee", "Dube"])
        self.fill(self.NAME, f"{first} {last}")
        # ponytail: random letters+digits satisfies the 6+ char rule; the password is never kept
        self.fill(self.PASSWORD, "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12)) + "!1aA")
        try:
            self.click(self.VERIFY)
        except Exception:
            self.click(self.CONTINUE)  # the button's html id is also 'continue'
        return True

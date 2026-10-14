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
        for _ in range(3):  # the WebView sometimes re-renders and drops the typed text
            self.fill(self.PHONE, phone)
            typed = (self.find(self.PHONE).text or "").strip()
            if typed:
                break
        digits = lambda s: "".join(c for c in s if c.isdigit())
        assert digits(typed) == digits(phone) and typed.startswith("+") == phone.startswith("+"), (
            f"Phone field holds {typed!r}, expected {phone!r}")
        return typed

    def tap_continue(self):
        self.click(self.CONTINUE)

    NAME = _html_id("ap_customer_name")
    PASSWORD = _html_id("ap_password")
    COUNTRY_PICKER = _html_id("auth-country-picker")
    REG_PHONE = _html_id("ap_phone_number")

    def complete_create_account(self, country, national, timeout=45):
        """If Continue landed on 'Create account' (number not registered), fills a random name and
        password, picks the country and re-enters the number (this form's own field starts empty on
        India), then taps the submit button ('Verify mobile number'). Returns True if it did, False if the page never showed."""
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
        if self.driver.find_elements(*self.REG_PHONE):  # variant with its own country picker and empty number field
            self.click(self.COUNTRY_PICKER)
            # the list is a long popover; scroll the entry into view, then tap it
            entry = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiScrollable(new UiSelector().scrollable(true).instance(0))'
                     f'.scrollIntoView(new UiSelector().textStartsWith("{country} +"))')
            self.click(entry)
            time.sleep(2)  # let the popover close, or the field below still counts as covered
            self.click(self.REG_PHONE)
            self.fill(self.REG_PHONE, national)
        try:
            self.driver.hide_keyboard()  # the keyboard covers the Submit button
        except Exception:
            pass  # already hidden
        self.click_first_visible(self.CONTINUE)  # labelled 'Verify mobile number' once the form is complete
        return True

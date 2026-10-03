from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

from core.base_page import BasePage
from targets.apps.whatsapp.pages.phone_page import PhonePage


class ConfirmNumberDialog(BasePage):
    """After NEXT, WhatsApp shows 'You entered the phone number: +.... Is this OK...?' with
    EDIT / OK. Tapping OK is what actually requests the code."""

    OK = (AppiumBy.ID, "android:id/button1")  # the dialog's positive button

    def confirm_if_present(self, timeout=10):
        try:
            WebDriverWait(self.driver, timeout).until(lambda d: d.find_elements(*self.OK))
        except TimeoutException:
            return False
        self.click(self.OK)
        return True


class OtpPage(BasePage):
    """The verification / code-entry screen. Never typed into - the code is only ever read off
    the phone by a person."""

    # ponytail: text locator, WhatsApp's verify-screen ids not captured yet (reaching it sends
    # a real SMS). Swap to its resource ids from the first run's page source if this misfires.
    VERIFY_TEXT = (AppiumBy.ANDROID_UIAUTOMATOR,
                   'new UiSelector().textMatches("(?i).*(verif|enter.*code|sent.*code|6-digit|waiting).*")')

    def wait_until_open(self, timeout=60):
        try:
            # must have LEFT the phone-entry screen too: "WhatsApp will verify your account"
            # lives on the phone page, so verify-text alone would false-pass there.
            el = WebDriverWait(self.driver, timeout).until(
                lambda d: not d.find_elements(*PhonePage.PHONE) and (d.find_elements(*self.VERIFY_TEXT) or [None])[0])
            return el.text
        except TimeoutException:
            import re
            texts = [t for t in re.findall(r'text="([^"]+)"', self.driver.page_source) if t.strip()]
            raise AssertionError(f"Verification screen did not appear after confirming. Page shows: {texts[:15]}") from None

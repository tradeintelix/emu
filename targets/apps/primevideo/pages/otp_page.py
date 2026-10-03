import re

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

from core.base_page import BasePage


def _html_id(element_id):
    return (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("{element_id}")')


class OtpPage(BasePage):
    """'Authentication required' page after Continue (same sign-in WebView): 'IN +91...',
    'We've sent a security code to the mobile number above', code box, Resend code, Send code
    to WhatsApp. Never typed into - the code is only ever read off the phone by a person."""

    CODE_INPUT = _html_id("cvf-input-code")
    # "IN +917420870251", "PK +923345333345": two-letter country, then the full number
    SENT_TO = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches("[A-Z]{2} [+][0-9 ]+")')
    RESEND = _html_id("cvf-resend-link")

    def wait_until_open(self, timeout=45):
        """Returns the number Amazon says it sent the code to. On timeout, the error lists what
        the page shows instead (e.g. a password field or a CAPTCHA), since screenshots are black."""
        try:
            WebDriverWait(self.driver, timeout).until(lambda d: d.find_elements(*self.CODE_INPUT))
        except TimeoutException:
            texts = [t for t in re.findall(r'text="([^"]+)"', self.driver.page_source) if t.strip()]
            raise AssertionError(f"OTP screen did not appear after Continue. Page shows: {texts[:15]}") from None
        return self.find(self.SENT_TO).text.strip()

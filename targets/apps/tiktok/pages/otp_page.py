import re

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

from core.base_page import BasePage


class OtpPage(BasePage):
    """'Enter 6-digit code' / 'Your code was sent to +91 ...' / 'Resend code 59s'.
    Never typed into: the code is only read off the phone by a person."""

    HEADER = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textStartsWith("Enter 6-digit code")')

    def wait_until_open(self, timeout=60):
        """Returns the header line. On timeout, says what is on screen instead (e.g. a CAPTCHA)."""
        try:
            return WebDriverWait(self.driver, timeout).until(lambda d: d.find_elements(*self.HEADER))[0].text
        except TimeoutException:
            texts = [t for t in re.findall(r'text="([^"]+)"', self.driver.page_source) if t.strip()]
            raise AssertionError(f"OTP screen did not appear. Page shows: {texts[:15]}") from None

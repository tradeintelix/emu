from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait

from core.base_page import BasePage


class OtpPage(BasePage):
    """'OTP Verification' screen: one box per digit. Never typed into - the code is only
    ever read off the phone by a person."""

    HEADER = (AppiumBy.ANDROID_UIAUTOMATOR,
              'new UiSelector().textMatches("(?i).*(otp verification|verification code|enter otp).*")')
    BOXES = (AppiumBy.CLASS_NAME, "android.widget.EditText")

    def wait_until_open(self, timeout=30):
        """Header text, or the box-per-digit layout itself (4+ inputs; the login screen has one)."""
        WebDriverWait(self.driver, timeout).until(
            lambda d: d.find_elements(*self.HEADER) or len(d.find_elements(*self.BOXES)) >= 4,
            message="OTP screen did not appear after Continue",
        )

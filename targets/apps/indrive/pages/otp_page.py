from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.base_page import BasePage


def _tag(resource_id):
    """Compose test tags carry no package prefix, so AppiumBy.ID can't match them."""
    return (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("{resource_id}")')


class OtpPage(BasePage):
    """'Enter the code' screen with 4 code dots and 'Resend code'. Never typed into - the code
    is only ever read off the phone by a person."""

    SENT_TO = _tag("authorization_enter_code_subtitle")  # "We sent your code via SMS to +92 3345333345"
    RESEND = _tag("authorization_enter_code_resend_button")  # reads "Resend code 00:22" while disabled

    # Next can spin well past BasePage.TIMEOUT over a slow VPN exit before this screen shows,
    # and Resend stays disabled until its countdown ends.
    SLOW = 60

    def wait_until_open(self):
        """Returns the 'We sent your code via SMS to ...' line."""
        return WebDriverWait(self.driver, self.SLOW).until(
            EC.visibility_of_element_located(self.SENT_TO), message="OTP screen did not appear after Next").text

    def tap_resend(self):
        WebDriverWait(self.driver, self.SLOW).until(
            EC.element_to_be_clickable(self.RESEND), message="Resend code never became tappable").click()

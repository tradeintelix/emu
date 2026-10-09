import time

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

    # Sometimes inDrive asks "SMS or WhatsApp?" after Next, sometimes it sends straight away.
    # Matched by visible text (no ids known); exact "SMS" can't match the "...via SMS to +92..." subtitle.
    SMS_OPTION = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches("(?i)sms")')
    CONFIRM = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches("(?i)(continue|next|send)").clickable(true)')

    # Next can spin well past BasePage.TIMEOUT over a slow VPN exit before this screen shows,
    # and Resend stays disabled until its countdown ends.
    SLOW = 60

    def wait_until_open(self):
        """Picks SMS on the channel popup if it shows. Returns the 'We sent your code via SMS to ...' line."""
        deadline = time.monotonic() + self.SLOW
        while time.monotonic() < deadline:
            sent_to = self.driver.find_elements(*self.SENT_TO)
            if sent_to:
                return sent_to[0].text
            sms = self.driver.find_elements(*self.SMS_OPTION)
            if sms:
                sms[0].click()
                confirm = self.driver.find_elements(*self.CONFIRM)
                if confirm:
                    confirm[-1].click()  # last = topmost, the popup's button rather than the page behind it
            time.sleep(1)
        raise TimeoutError("OTP screen did not appear after Next")

    def tap_resend(self):
        WebDriverWait(self.driver, self.SLOW).until(
            EC.element_to_be_clickable(self.RESEND), message="Resend code never became tappable").click()

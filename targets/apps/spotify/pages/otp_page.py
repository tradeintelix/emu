from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.base_page import BasePage


class OtpPage(BasePage):
    """'Enter your code' screen after Next. The code is only typed when the SMPP service accepted
    it (core/otp.py); a number delivered to a real handset is never typed into. Spotify marks
    its login windows FLAG_SECURE, so step screenshots of this screen come out black; the
    description text is the run's evidence instead."""

    CODE_INPUT = (AppiumBy.ID, "com.spotify.music:id/validate_otp")
    DESCRIPTION = (AppiumBy.ID, "com.spotify.music:id/otp_description")  # "We sent a 6-digit code to +91..."
    RESEND = (AppiumBy.ID, "com.spotify.music:id/resend_sms")

    def wait_until_open(self):
        """Returns the 'We sent a code to ...' line."""
        self.find(self.CODE_INPUT)
        return self.find(self.DESCRIPTION).text

    def enter_code(self, code):
        self.fill(self.CODE_INPUT, code)

    def wait_until_closed(self, timeout=30):
        """The code was accepted once Spotify leaves this screen; a wrong code keeps it open."""
        WebDriverWait(self.driver, timeout).until(EC.invisibility_of_element_located(self.CODE_INPUT))

    def tap_resend(self):
        self.click(self.RESEND)  # click() waits until it's enabled, in case a cooldown is still running

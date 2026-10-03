from appium.webdriver.common.appiumby import AppiumBy

from core.base_page import BasePage


class OtpPage(BasePage):
    """'Enter your code' screen after Next. Never typed into - the code is only ever read off
    the phone by a person. Spotify marks its login windows FLAG_SECURE, so step screenshots of
    this screen come out black; the description text is the run's evidence instead."""

    CODE_INPUT = (AppiumBy.ID, "com.spotify.music:id/validate_otp")
    DESCRIPTION = (AppiumBy.ID, "com.spotify.music:id/otp_description")  # "We sent a 6-digit code to +91..."
    RESEND = (AppiumBy.ID, "com.spotify.music:id/resend_sms")

    def wait_until_open(self):
        """Returns the 'We sent a code to ...' line."""
        self.find(self.CODE_INPUT)
        return self.find(self.DESCRIPTION).text

    def tap_resend(self):
        self.click(self.RESEND)  # click() waits until it's enabled, in case a cooldown is still running

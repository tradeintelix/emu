from appium.webdriver.common.appiumby import AppiumBy

from core.base_page import BasePage


class LoginPage(BasePage):
    """'Log in to Spotify': email field plus 'Or log in with' Phone number / Google / Facebook.
    The options are text-only (no ids); tapping the label reaches its row."""

    PHONE_NUMBER = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Phone number")')

    def choose_phone_number(self):
        self.click(self.PHONE_NUMBER)

from appium.webdriver.common.appiumby import AppiumBy

from core.base_page import BasePage


class WelcomePage(BasePage):
    """Logged-out first screen: 'Sign up free' / 'Log in'. The buttons have no ids (9.1.86)."""

    LOG_IN = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().className("android.widget.Button").text("Log in")')

    def is_open(self):
        return bool(self.driver.find_elements(*self.LOG_IN))

    def tap_log_in(self):
        self.click(self.LOG_IN)

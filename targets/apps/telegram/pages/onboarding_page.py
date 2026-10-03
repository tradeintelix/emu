from appium.webdriver.common.appiumby import AppiumBy

from core.base_page import BasePage


class OnboardingPage(BasePage):
    """Welcome carousel: logo, blurb, 'Start Messaging'."""

    START = (AppiumBy.XPATH, '//*[@text="Start Messaging"]')

    def is_welcome_open(self):
        return bool(self.driver.find_elements(*self.START))

    def start(self):
        self.click(self.START)

from appium.webdriver.common.appiumby import AppiumBy

from core.base_page import BasePage


class WelcomePage(BasePage):
    """'Your app for fair deals': Continue with Google / Continue with phone."""

    CONTINUE_WITH_PHONE = (AppiumBy.ID, "sinet.startup.inDriver:id/authorization_welcome_phone_button")

    def is_open(self):
        return bool(self.driver.find_elements(*self.CONTINUE_WITH_PHONE))

    def continue_with_phone(self):
        self.click(self.CONTINUE_WITH_PHONE)

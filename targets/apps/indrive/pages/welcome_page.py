from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

from core.base_page import BasePage


class WelcomePage(BasePage):
    """'Your app for fair deals': Continue with Google / Continue with phone."""

    CONTINUE_WITH_PHONE = (AppiumBy.ID, "sinet.startup.inDriver:id/authorization_welcome_phone_button")

    def is_open(self):
        return bool(self.driver.find_elements(*self.CONTINUE_WITH_PHONE))

    def continue_with_phone(self):
        # a tap that lands while the screen is still re-rendering is swallowed with no error,
        # so confirm the welcome screen is gone and tap again if not
        for _ in range(3):
            self.click(self.CONTINUE_WITH_PHONE)
            try:
                WebDriverWait(self.driver, 5).until_not(lambda _: self.is_open())
                return
            except TimeoutException:
                pass
        raise TimeoutException("Welcome screen still open after tapping Continue with phone 3 times")

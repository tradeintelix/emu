from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

from appium.webdriver.common.appiumby import AppiumBy

from core.base_page import BasePage


class OnboardingPage(BasePage):
    """'Welcome to WhatsApp' (Agree and continue), then WhatsApp's own 'Allow notifications'
    screen (Continue), which raises Android's notification prompt (handled by core.permissions)."""

    AGREE = (AppiumBy.ID, "com.whatsapp:id/eula_accept")
    NOTIFICATIONS_CONTINUE = (AppiumBy.ID, "com.whatsapp:id/primary_button")

    def is_welcome_open(self):
        return bool(self.driver.find_elements(*self.AGREE))

    def agree(self):
        self.click(self.AGREE)

    def continue_notifications(self):
        """Taps Continue on WhatsApp's notifications screen. Skips quietly if a build/version
        doesn't show that screen. Returns True if it tapped."""
        if self._appears(self.NOTIFICATIONS_CONTINUE):
            self.click(self.NOTIFICATIONS_CONTINUE)
            return True
        return False

    def _appears(self, locator, timeout=8):
        try:
            WebDriverWait(self.driver, timeout).until(lambda d: d.find_elements(*locator))
            return True
        except TimeoutException:
            return False

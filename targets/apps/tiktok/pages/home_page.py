import time

from appium.webdriver.common.appiumby import AppiumBy

from core.base_page import BasePage


class HomePage(BasePage):
    """'For You' feed with the bottom bar (Home / Friends / + / Inbox / Profile).
    TikTok's resource ids are obfuscated and change per release, so tabs go by content-desc."""

    PROFILE = (AppiumBy.ACCESSIBILITY_ID, "Profile")

    def wait_until_open(self, timeout=45):
        """Presses Back on anything covering the feed (startup promos, update prompts) until the
        Profile tab shows. Returns how many times Back was pressed."""
        backs = 0
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.driver.find_elements(*self.PROFILE):
                return backs
            time.sleep(3)  # splash first; only press Back if something is still covering the feed after that
            if not self.driver.find_elements(*self.PROFILE):
                self.driver.back()
                backs += 1
        raise TimeoutError(f"Home feed not reached within {timeout}s ({backs} Back press(es))")

    def open_profile(self):
        self.click(self.PROFILE)

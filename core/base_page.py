import time

from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class BasePage:
    """Locators are (strategy, value) tuples and live in the page classes, never in tests."""

    TIMEOUT = 15

    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, self.TIMEOUT)

    def click(self, locator):
        self.wait.until(EC.element_to_be_clickable(locator)).click()

    def click_first_visible(self, locator):
        """Some pages reuse the same visible text for several elements (nav + footer + a menu
        item), so a plain locator can match the wrong one. This waits for at least one match
        to be on screen, then clicks the first one that is.

        Retries on a stale element: right after a navigation, an SPA can re-render its header
        between when we find the element and when the click lands, which detaches the node we
        were about to click. Re-querying and clicking again is enough to recover from that."""
        deadline = time.monotonic() + self.TIMEOUT
        while time.monotonic() < deadline:
            try:
                for el in self.driver.find_elements(*locator):
                    if el.is_displayed():
                        el.click()
                        return
            except StaleElementReferenceException:
                pass
            time.sleep(0.2)
        raise NoSuchElementException(f"No visible, stable element for {locator}")

    def fill(self, locator, text):
        el = self.wait.until(EC.visibility_of_element_located(locator))
        el.clear()
        el.send_keys(text)

    def find(self, locator):
        return self.wait.until(EC.presence_of_element_located(locator))

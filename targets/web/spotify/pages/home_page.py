from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.base_page import BasePage


class HomePage(BasePage):
    URL = "https://open.spotify.com/"
    COOKIE_ACCEPT = (By.ID, "onetrust-accept-btn-handler")
    SIGN_UP = (By.XPATH, "//*[self::a or self::button][normalize-space()='Sign up']")

    def open(self):
        self.driver.get(self.URL)
        try:  # the cookie banner can cover the header buttons
            WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable(self.COOKIE_ACCEPT)).click()
        except TimeoutException:
            pass  # no banner (or a different one)

    def click_sign_up(self):
        self.click(self.SIGN_UP)

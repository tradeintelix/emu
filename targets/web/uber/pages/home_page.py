from selenium.webdriver.common.by import By

from core.base_page import BasePage


class HomePage(BasePage):
    URL = "https://www.uber.com/in/en/"  # default; open() resolves per country

    # "Sign up" text is repeated elsewhere on the page (footer links), so it's matched by
    # click_first_visible. The Ride menu item is matched by where it links, not its label.
    SIGN_UP = (By.XPATH, "//*[self::a or self::button][normalize-space()='Sign up']")
    RIDE_OPTION = (By.CSS_SELECTOR, "a[href*='m.uber.com/looking']")

    def open(self):
        from config.settings import PROXY_COUNTRY
        from targets.web.uber.target import home_url
        self.driver.get(home_url(PROXY_COUNTRY))

    def click_sign_up(self):
        """Opens a menu (Ride / Drive / Uber Eats / Business), it doesn't submit anything."""
        self.click_first_visible(self.SIGN_UP)

    def choose_ride(self):
        self.click_first_visible(self.RIDE_OPTION)

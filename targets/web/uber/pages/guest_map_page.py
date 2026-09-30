from selenium.webdriver.common.by import By

from core.base_page import BasePage


class GuestMapPage(BasePage):
    """The rider map Uber shows before you're signed in - landed on after choosing Ride.
    Its own "Sign up" (top right) is what actually reaches the phone/email form.
    Matched by href, not label: m.uber.com follows the browser/IP locale, and a
    proxied exit node sometimes renders it in Spanish ("Regístrate")."""
    SIGN_UP = (By.CSS_SELECTOR, "a[href*='/go/sign-up']")

    def click_sign_up(self):
        self.click_first_visible(self.SIGN_UP)

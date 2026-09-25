from selenium.webdriver.common.by import By

from core.base_page import BasePage
from core.web.outcome import wait_for_otp_or_captcha


class SignUpPage(BasePage):
    """auth.uber.com's phone/email entry page. Both locators are language-independent
    (confirmed identical on the English and Spanish renders of this page)."""
    PHONE_OR_EMAIL = (By.ID, "PHONE_NUMBER_or_EMAIL_ADDRESS")
    CONTINUE = (By.ID, "forward-button")  # "Continue" / "Continuar" depending on locale

    def enter_phone(self, number):
        # Pass the number with its country code (e.g. +918459292374). A bare number gets the
        # country Uber guesses from the exit IP, which on Bright Data isn't always India.
        self.fill(self.PHONE_OR_EMAIL, number)

    def submit(self):
        self.click(self.CONTINUE)

    def wait_for_otp_or_captcha(self, timeout=20, solve_captcha=False):
        return wait_for_otp_or_captcha(self.driver, timeout, solve_captcha=solve_captcha)

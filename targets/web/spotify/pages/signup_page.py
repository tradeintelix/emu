from selenium.webdriver.common.by import By

from core.base_page import BasePage
from core.web.outcome import wait_for_otp_or_captcha


class SignUpPage(BasePage):
    PHONE_OPTION = (By.XPATH, "//*[self::a or self::button][contains(normalize-space(), 'Sign up with phone number')]")
    PHONE_INPUT = (By.CSS_SELECTOR, "input[type='tel']")
    SUBMIT = (By.XPATH, "//button[normalize-space()='Continue' or normalize-space()='Submit']")

    def choose_phone(self):
        self.click(self.PHONE_OPTION)

    def enter_phone(self, number):
        self.fill(self.PHONE_INPUT, number)

    def submit(self):
        self.click(self.SUBMIT)

    def wait_for_otp_or_captcha(self, timeout=20, solve_captcha=False):
        return wait_for_otp_or_captcha(self.driver, timeout, solve_captcha=solve_captcha)

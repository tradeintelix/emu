import re

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

from core.base_page import BasePage


class ConfirmNumberDialog(BasePage):
    """After Done, Telegram shows 'Is this the correct number? +<num>' with Edit / Yes.
    Tapping Yes is what actually requests the code."""

    YES = (AppiumBy.XPATH, '//*[@text="Yes"]')

    def confirm_if_present(self, timeout=10):
        try:
            WebDriverWait(self.driver, timeout).until(lambda d: d.find_elements(*self.YES))
        except TimeoutException:
            return False
        self.click(self.YES)
        return True


class CodePage(BasePage):
    """The verification screen: 5 boxes for the code, delivered either by SMS or - if the number
    already has Telegram elsewhere - as a message to the Telegram app on that other device.
    Never typed into - the code is only ever read off a device by a person.

    Identified by its 5 empty code boxes rather than by header text: the wording differs by
    delivery method, and "enter your code" also appears in the call-log permission explainer
    shown just before this screen, so text alone would false-match there."""

    CODE_BOXES = (AppiumBy.CLASS_NAME, "android.widget.EditText")
    # ponytail: best-effort label for the printed step output; falls back to "" if wording drifts
    HEADER = (AppiumBy.ANDROID_UIAUTOMATOR,
              'new UiSelector().textMatches("(?i).*(verif|check.*telegram|sent.*code|sent.*sms).*")')

    def is_open(self):
        return len(self.driver.find_elements(*self.CODE_BOXES)) >= 5

    def wait_until_open(self, timeout=60):
        try:
            WebDriverWait(self.driver, timeout).until(lambda d: self.is_open())
        except TimeoutException:
            texts = [t for t in re.findall(r'text="([^"]+)"', self.driver.page_source) if t.strip()]
            raise AssertionError(f"Verification screen did not appear. Page shows: {texts[:15]}") from None
        headers = self.driver.find_elements(*self.HEADER)
        return headers[0].text if headers else ""


class EmailPage(BasePage):
    """'Add Email': Telegram asks for a login email before it sends the code, for some numbers.
    Located by its title and the screen's only text field (no ids known)."""

    TITLE = (AppiumBy.XPATH, '//*[@text="Add Email"]')
    FIELD = (AppiumBy.CLASS_NAME, "android.widget.EditText")
    DONE = (AppiumBy.ACCESSIBILITY_ID, "Done")  # the blue arrow; the keyboard's Enter doesn't submit

    def is_open(self):
        return bool(self.driver.find_elements(*self.TITLE))

    def submit(self, email):
        self.fill(self.FIELD, email)
        self.click(self.DONE)

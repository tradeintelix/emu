from appium.webdriver.common.appiumby import AppiumBy

from core.base_page import BasePage


class LoginSheet(BasePage):
    """'Log in to TikTok' sheet that Profile opens when logged out."""

    USE_PHONE = (AppiumBy.XPATH, '//*[@text="Use phone/email/username"]')

    def use_phone(self):
        self.click(self.USE_PHONE)


class PhoneLoginPage(BasePage):
    """'Log in' screen, Phone tab (the default): 'IN +91' code button + number field, then Continue."""

    CODE = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textStartsWith("+")')  # "+91", the only text starting with "+"
    PHONE = (AppiumBy.CLASS_NAME, "android.widget.EditText")  # the tab's only field
    CONTINUE = (AppiumBy.XPATH, '//android.widget.Button[@text="Continue"]')
    # country picker
    SEARCH = (AppiumBy.CLASS_NAME, "android.widget.EditText")

    def select_country(self, name):
        self.click(self.CODE)
        self.fill(self.SEARCH, name)
        # tv_name rows only: plain @text would also match the search box once it holds the name
        self.click((AppiumBy.XPATH, f'//*[contains(@resource-id,"tv_name") and @text="{name}"]'))
        return self.find(self.CODE).text

    def enter_phone(self, phone):
        self.fill(self.PHONE, phone)
        typed = "".join(c for c in (self.find(self.PHONE).text or "") if c.isdigit())
        assert typed == phone, f"Phone field holds {typed!r}, expected {phone!r}"

    def tap_continue(self):
        self.click(self.CONTINUE)

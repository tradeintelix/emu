from appium.webdriver.common.appiumby import AppiumBy

from core.base_page import BasePage


class PhonePage(BasePage):
    """'Enter phone number': country row, then calling code + number field, then Next."""

    COUNTRY = (AppiumBy.ID, "com.spotify.music:id/calling_code_country")
    CALLING_CODE = (AppiumBy.ID, "com.spotify.music:id/calling_code")
    PHONE = (AppiumBy.ID, "com.spotify.music:id/phone_number")
    NEXT = (AppiumBy.ID, "com.spotify.music:id/request_otp_button")
    # country picker ('Choose your country')
    SEARCH = (AppiumBy.ID, "com.spotify.music:id/search_src_text")

    def select_country(self, name):
        """No-op when already selected; otherwise search the picker and tap the exact match."""
        if self.find(self.COUNTRY).text == name:
            return
        self.click(self.COUNTRY)
        self.fill(self.SEARCH, name)
        self.click((AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("android:id/text1").text("{name}")'))
        self.wait.until(lambda _: self.find(self.COUNTRY).text == name,
                        message=f"Country still {self.find(self.COUNTRY).text!r} after picking {name!r}")

    def enter_phone(self, phone):
        self.fill(self.PHONE, phone)
        typed = "".join(c for c in (self.find(self.PHONE).text or "") if c.isdigit())
        assert phone in typed, f"Phone field holds {typed!r}, expected {phone!r}"

    def tap_next(self):
        self.click(self.NEXT)

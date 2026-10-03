import re

from appium.webdriver.common.appiumby import AppiumBy

from core.base_page import BasePage


class PhonePage(BasePage):
    """'Your phone number': country field, '+' code box, number box, Done (circular arrow).

    Telegram draws its own UI and sets no resource-ids on this screen, so locators use
    accessibility labels / text instead, like WhatsApp's country dropdown: the country isn't
    picked from a list, it's resolved from the calling code typed into the code box."""

    COUNTRY = (AppiumBy.XPATH, '//*[@content-desc="Country"]//android.widget.TextView')
    CODE = (AppiumBy.ACCESSIBILITY_ID, "Country code")
    PHONE = (AppiumBy.ACCESSIBILITY_ID, "Phone number")
    DONE = (AppiumBy.ACCESSIBILITY_ID, "Done")

    def is_open(self):
        return bool(self.driver.find_elements(*self.PHONE))

    def split_code(self, national_number_with_cc):
        """national_number_with_cc: digits only, e.g. '923345333345'. E.164 calling codes are
        prefix-free (no code is a prefix of another), so the shortest prefix Telegram accepts is
        THE code. Returns (code, national_number, country) and leaves that code set in the box.
        The country label carries a flag emoji ('🇮🇳 India'), stripped down to the name here."""
        for length in (1, 2, 3):
            code = national_number_with_cc[:length]
            box = self.find(self.CODE)
            box.clear()
            box.send_keys(code)
            raw = self.find(self.COUNTRY).text.strip()
            name = re.sub(r"^\W+", "", raw).strip()
            if name:
                return code, national_number_with_cc[length:], name
        raise AssertionError(f"No valid calling code in the first 3 digits of {national_number_with_cc!r}")

    def enter_number(self, national_number):
        box = self.find(self.PHONE)
        box.clear()
        box.send_keys(national_number)
        typed = "".join(c for c in (self.find(self.PHONE).text or "") if c.isdigit())
        assert typed == national_number, f"Number field holds {typed!r}, expected {national_number!r}"

    def tap_done(self):
        self.click(self.DONE)

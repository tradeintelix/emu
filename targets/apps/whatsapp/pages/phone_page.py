from appium.webdriver.common.appiumby import AppiumBy

from core.base_page import BasePage


class PhonePage(BasePage):
    """'Enter your phone number': country label, '+' code box, number box, NEXT.

    The country dropdown doesn't open its list on this emulator, whichever way it's tapped,
    so the country is set through the code box instead: WhatsApp turns a typed calling code
    into the country name (92 -> Pakistan, 213 -> Algeria, 91 -> India)."""

    COUNTRY = (AppiumBy.ID, "com.whatsapp:id/registration_country")
    CODE = (AppiumBy.ID, "com.whatsapp:id/registration_cc")
    PHONE = (AppiumBy.ID, "com.whatsapp:id/registration_phone")
    NEXT = (AppiumBy.ID, "com.whatsapp:id/button_view")  # the real Button; registration_submit is its FrameLayout wrapper
    INVALID = "invalid country code"

    def is_open(self):
        return bool(self.driver.find_elements(*self.PHONE))

    def set_calling_code(self, code):
        """Types the calling code and returns the country name WhatsApp resolves it to.
        Raises if WhatsApp calls it invalid, so a bad code can never reach NEXT."""
        box = self.find(self.CODE)
        box.clear()
        box.send_keys(code)
        name = self.find(self.COUNTRY).text.strip()
        assert name and name.lower() != self.INVALID, f"WhatsApp rejects calling code +{code}: {name!r}"
        return name

    def split_code(self, national_number_with_cc):
        """national_number_with_cc: digits only, e.g. '923345333345'. E.164 calling codes are
        prefix-free (no code is a prefix of another), so the shortest prefix WhatsApp accepts is
        THE code. Returns (code, national_number) and leaves that code set in the box."""
        for length in (1, 2, 3):
            code = national_number_with_cc[:length]
            box = self.find(self.CODE)
            box.clear()
            box.send_keys(code)
            name = self.find(self.COUNTRY).text.strip()
            if name and name.lower() != self.INVALID:
                return code, national_number_with_cc[length:], name
        raise AssertionError(f"No valid calling code in the first 3 digits of {national_number_with_cc!r}")

    def enter_number(self, national_number):
        box = self.find(self.PHONE)
        box.clear()
        box.send_keys(national_number)
        typed = "".join(c for c in (self.find(self.PHONE).text or "") if c.isdigit())
        assert typed == national_number, f"Number field holds {typed!r}, expected {national_number!r}"

    def tap_next(self):
        # NEXT drops injected taps (Appium, `adb input`) without any error; only a hardware touch works
        self.hardware_tap(self.NEXT)

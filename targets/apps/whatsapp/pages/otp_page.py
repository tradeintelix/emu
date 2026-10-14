import re
import time

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

from core.base_page import BasePage


class ConfirmNumberDialog(BasePage):
    """After NEXT, WhatsApp shows 'You entered the phone number: +.... Is this OK...?' with
    EDIT / OK. Tapping OK is what actually requests the code."""

    OK = (AppiumBy.ID, "android:id/button1")  # the dialog's positive button

    def confirm_if_present(self, timeout=10):
        try:
            WebDriverWait(self.driver, timeout).until(lambda d: d.find_elements(*self.OK))
        except TimeoutException:
            return False
        self.hardware_tap(self.OK)  # registration screens drop injected taps, see PhonePage.tap_next
        return True


class OtpPage(BasePage):
    """The code-entry screen (VerifyPhoneNumber activity: "Verifying your number", code boxes).
    Never typed into - the code is only ever read off the phone by a person.

    Some numbers get there straight after OK; others first get a missed-call "Allow access"
    explainer, whose "Verify another way" opens a "Choose how to verify" sheet. There the flow
    picks Receive SMS. Some numbers instead get an OS permission dialog ("Allow WhatsApp to
    confirm the number of an incoming phone call?") for flash-call verification; it is declined
    so WhatsApp falls back to its normal SMS/choose-method flow. Taps on WhatsApp's own screens
    are hardware taps: registration drops injected ones. The OS dialog is a different window
    (permission controller), so a normal click reaches it."""

    VERIFY_ANOTHER_WAY = (AppiumBy.ID, "com.whatsapp:id/secondary_button")  # on the "Allow access" explainer
    METHOD_SHEET = (AppiumBy.ID, "com.whatsapp:id/request_otp_code_bottom_sheet_title")
    SMS = (AppiumBy.XPATH, '//*[@text="Receive SMS"]')
    SMS_DETAILS = (AppiumBy.XPATH, '//*[@text="Receive SMS"]/following-sibling::*[1]')  # "Try again in 6 hours" when rate-limited
    SHEET_CONTINUE = (AppiumBy.ID, "com.whatsapp:id/continue_button")
    # Android's runtime permission dialog for flash-call verification ("Only this time" / "Don't allow").
    CALL_PERMISSION_DENY = (AppiumBy.ANDROID_UIAUTOMATOR,
                            'new UiSelector().resourceIdMatches(".*:id/permission_deny_button")')

    def wait_until_open(self, timeout=60):
        """Gets past the method choice (SMS) if it shows up. Returns the code screen's texts."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if "VerifyPhoneNumber" in (self.driver.current_activity or ""):
                return " | ".join(self._texts()[:4])
            try:
                if self.driver.find_elements(*ConfirmNumberDialog.OK):  # dialog came after the confirm step's wait (slow VPN)
                    self.hardware_tap(ConfirmNumberDialog.OK)
                elif self.driver.find_elements(*self.METHOD_SHEET):
                    self._choose_sms()
                elif self.driver.find_elements(*self.VERIFY_ANOTHER_WAY):
                    self.hardware_tap(self.VERIFY_ANOTHER_WAY)
                elif self.driver.find_elements(*self.CALL_PERMISSION_DENY):
                    self.driver.find_elements(*self.CALL_PERMISSION_DENY)[0].click()
            except StaleElementReferenceException:
                continue  # the screen changed under the tap; look again
            time.sleep(1)
        raise AssertionError(f"Code screen did not appear after confirming. Page shows: {self._texts()[:15]}")

    def _choose_sms(self):
        details = self.driver.find_elements(*self.SMS_DETAILS)
        note = details[0].text if details else ""
        assert not note.lower().startswith("try again"), f"WhatsApp won't send an SMS to this number now: {note!r}"
        self.hardware_tap(self.SMS)
        self.hardware_tap(self.SHEET_CONTINUE)

    def _texts(self):
        return [t for t in re.findall(r'text="([^"]+)"', self.driver.page_source) if t.strip()]

"""Telegram shows its own pre-permission explainer ('Please allow Telegram to ...') with a
Continue button in front of every OS permission dialog - once for phone-call auto-verification
(before the phone screen) and again for call-log auto-fill (after submitting the number). Neither
permission is needed here (the code is never read or typed), so this only needs to get past
whichever dialogs show up, not decide how many there are or in what order."""
import time

from appium.webdriver.common.appiumby import AppiumBy

from core.permissions import ALLOW

CONTINUE = (AppiumBy.XPATH, '//*[@text="Continue"]')


def dismiss_until(driver, is_done, timeout=30):
    """Taps Telegram's in-app Continue and the OS permission dialog, in whatever order and
    however many times they show up, until is_done()."""
    deadline = time.monotonic() + timeout
    acted = 0
    while time.monotonic() < deadline:
        if is_done():
            return acted
        buttons = driver.find_elements(*CONTINUE) or driver.find_elements(*ALLOW)
        if buttons:
            buttons[0].click()
            acted += 1
            time.sleep(1)
        else:
            time.sleep(0.5)
    raise TimeoutError(f"Screen not reached within {timeout}s ({acted} dialog(s) dismissed)")

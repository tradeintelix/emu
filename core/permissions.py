"""Taps through Android runtime-permission prompts (location, notifications, ...).
The dialog is drawn by the OS, not the app, so these ids work for every app target."""
import time

from appium.webdriver.common.appiumby import AppiumBy

# "While using the app" on location prompts, "Allow" on notifications and the rest
ALLOW = (AppiumBy.ANDROID_UIAUTOMATOR,
         'new UiSelector().resourceIdMatches(".*:id/permission_allow_(foreground_only_)?button")')


def allow_permissions_until(driver, is_done, timeout=60):
    """Allow every prompt until is_done() is true (e.g. the app's first real screen is up).
    Returns how many prompts were allowed."""
    allowed = 0
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # prompt first: apps (e.g. Zomato) draw their first screen right behind the dialog
        buttons = driver.find_elements(*ALLOW)
        if buttons:
            buttons[0].click()
            allowed += 1
        elif is_done():
            return allowed
        time.sleep(1)
    raise TimeoutError(f"App screen not reached within {timeout}s ({allowed} permission prompt(s) allowed)")

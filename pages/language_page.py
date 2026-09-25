from appium.webdriver.common.appiumby import AppiumBy

from core.base_page import BasePage


def _by(selector):
    return (AppiumBy.ANDROID_UIAUTOMATOR, selector)


class LanguagePage(BasePage):
    # ponytail: located by visible text. If the app has resource ids, switch to
    # AppiumBy.ID (more stable across translations); check with Appium Inspector.
    ENGLISH = _by('new UiSelector().className("android.widget.RadioButton").text("English")')
    NEXT = _by('new UiSelector().text("Next")')  # it's the only "Next" on this screen; position doesn't matter

    def select_english(self):
        self.click(self.ENGLISH)
        # the click only counts if the radio actually ended up checked
        self.wait.until(lambda _: self.find(self.ENGLISH).get_attribute("checked") == "true")

    def tap_next(self):
        self.click(self.NEXT)

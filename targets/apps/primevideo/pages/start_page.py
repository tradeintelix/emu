from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

from core.base_page import BasePage


def _uia(selector):
    return (AppiumBy.ANDROID_UIAUTOMATOR, selector)


class StartPage(BasePage):
    """First screen after launch is one of two variants:
    1. the homepage, with a 'SIGN IN' tab in the bottom bar, or
    2. a 'Login or Sign up' / 'Continue as Guest' screen."""

    HOME_SIGN_IN = _uia('new UiSelector().description("SIGN IN")')  # the whole tab, not just its label
    # ponytail: variant 2 matched by its button text (not captured on the emulator yet);
    # swap to its resource id once a run lands on it
    LOGIN_OR_SIGN_UP = _uia('new UiSelector().textMatches("(?i)log ?in or sign ?up")')
    # the sign-in Welcome page's 'Sign in' accordion header (Amazon web id, no package prefix).
    # Present whether we tapped in from the homepage or the app opened straight on sign-in.
    SIGN_IN_PAGE = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("login_accordion_header")')

    def is_open(self):
        return bool(self.driver.find_elements(*self.HOME_SIGN_IN)
                    or self.driver.find_elements(*self.LOGIN_OR_SIGN_UP)
                    or self.driver.find_elements(*self.SIGN_IN_PAGE))

    def open_sign_in(self, attempts=4):
        """Taps whichever entry point this launch shows, until the sign-in page opens. Three
        variants: the homepage ('SIGN IN' tab), a 'Login or Sign up' screen, or - seen over a
        non-India IP - the app opens straight on the sign-in WebView, where there's nothing to tap."""
        if self.driver.find_elements(*self.SIGN_IN_PAGE):
            return "already on the sign-in page"
        for _ in range(attempts):
            if self.driver.find_elements(*self.LOGIN_OR_SIGN_UP):
                variant, button = "Login or Sign up screen", self.LOGIN_OR_SIGN_UP
            else:
                variant, button = "homepage", self.HOME_SIGN_IN
            self.click(button)
            try:
                WebDriverWait(self.driver, 8).until(lambda d: d.find_elements(*self.SIGN_IN_PAGE))
                return variant
            except TimeoutException:
                continue
        raise AssertionError(f"Sign-in page did not open after {attempts} taps on the {variant} entry point")

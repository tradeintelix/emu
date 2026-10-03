from appium.webdriver.common.appiumby import AppiumBy

from core.base_page import BasePage

PKG = "sinet.startup.inDriver"


def _uia(selector):
    return (AppiumBy.ANDROID_UIAUTOMATOR, selector)


class PhonePage(BasePage):
    """'Join us via phone number': flag button + one field that holds '+<code> <number>', then Next."""

    FLAG = (AppiumBy.ID, f"{PKG}:id/ui_phone_compact_layout_flag_layout")  # content-desc: "Pakistan, +92"
    PHONE = (AppiumBy.ID, f"{PKG}:id/ui_phone_compact_layout_edit_text")
    NEXT = _uia('new UiSelector().resourceId("authorization_enter_phone_btn_next")')  # Compose tag, no package prefix
    # country picker (bottom sheet)
    SEARCH = (AppiumBy.ID, f"{PKG}:id/country_dialog_edittext_city_name")

    def selected_country(self):
        return (self.find(self.FLAG).get_attribute("content-desc") or "").split(",")[0]

    def select_country(self, name):
        """No-op when already selected; otherwise search the picker and tap the 'Name (+code)' row."""
        if self.selected_country() == name:
            return
        self.click(self.FLAG)
        self.fill(self.SEARCH, name)
        self.click(_uia(f'new UiSelector().resourceId("{PKG}:id/cell_title_view").textStartsWith("{name} (")'))
        self.wait.until(lambda _: self.selected_country() == name,
                        message=f"Country still {self.selected_country()!r} after picking {name!r}")

    def enter_phone(self, phone):
        """The field adds '+<code> ' itself, so only the national number is typed."""
        self.fill(self.PHONE, phone)
        code = (self.find(self.FLAG).get_attribute("content-desc") or "").rsplit("+", 1)[-1]
        typed = "".join(c for c in (self.find(self.PHONE).text or "") if c.isdigit())
        assert typed == code + phone, f"Phone field holds +{typed}, expected +{code}{phone}"

    def tap_next(self):
        self.click(self.NEXT)

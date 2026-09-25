import pytest

from pages.language_page import LanguagePage


@pytest.mark.smoke
def test_choose_english_and_continue(driver):
    page = LanguagePage(driver)
    page.select_english()
    page.tap_next()

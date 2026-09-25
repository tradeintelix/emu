from appium import webdriver
from appium.options.android import UiAutomator2Options

from config.settings import APP_PACKAGE, APPIUM_URL


def create_driver(serial):
    """Attach an Appium session to a device on which the app is already open (core.app.launch_app)."""
    opts = UiAutomator2Options()
    opts.udid = serial
    opts.app_package = APP_PACKAGE
    opts.auto_launch = False  # the app is already open, don't restart it
    opts.no_reset = True  # keep app data as it is
    opts.new_command_timeout = 300
    return webdriver.Remote(APPIUM_URL, options=opts)

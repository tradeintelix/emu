from appium import webdriver
from appium.options.android import UiAutomator2Options

from config.settings import APP_PACKAGE, APPIUM_URL


def create_driver(serial, package=APP_PACKAGE):
    """Attach an Appium session to the device without (re)launching the app: either it's
    already open (core.app.launch_app) or the caller starts it with driver.activate_app()."""
    opts = UiAutomator2Options()
    opts.udid = serial
    opts.app_package = package
    # the app is already open (or the caller starts it), don't restart it. set_capability, not an
    # attribute: UiAutomator2Options has no auto_launch property, so `opts.auto_launch = ...` was never sent
    opts.set_capability("appium:autoLaunch", False)
    opts.no_reset = True  # keep app data as it is
    opts.new_command_timeout = 300
    return webdriver.Remote(APPIUM_URL, options=opts)

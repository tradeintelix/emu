from appium import webdriver
from appium.options.android import UiAutomator2Options

from config.settings import APP_PACKAGE, APPIUM_URL


def create_driver(serial, package=APP_PACKAGE, appium_url=APPIUM_URL, system_port=None):
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
    # a freshly booted emulator is busy for a while; Appium's 20s defaults time out installing its server
    opts.set_capability("appium:uiautomator2ServerInstallTimeout", 90000)
    opts.set_capability("appium:adbExecTimeout", 60000)
    if system_port:
        opts.system_port = system_port  # parallel sessions each need their own (core/slot.py)
    return webdriver.Remote(appium_url, options=opts)

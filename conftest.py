import pytest


@pytest.fixture(scope="session")
def driver():
    """Android: emulator + app + Appium session. Imports are local so website runs don't load the mobile stack."""
    from core.app import launch_app
    from core.appium_server import ensure_appium
    from core.driver_factory import create_driver
    from core.emulator import ensure_device

    serial = ensure_device()
    launch_app(serial)
    ensure_appium()
    d = create_driver(serial)
    yield d
    d.quit()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Exposes the test outcome to fixtures as item.rep_call (used by the target conftests to record PASS/FAIL)."""
    report = (yield).get_result()
    setattr(item, "rep_" + report.when, report)

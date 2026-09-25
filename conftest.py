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

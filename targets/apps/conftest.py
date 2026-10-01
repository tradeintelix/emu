import importlib
import time

import pytest


@pytest.fixture
def steps(request):
    """Emulator + app + Appium session, plus a step recorder writing into
    <target>/reports/<timestamp>/. Settings come from <target>/target.py."""
    from core.app import is_installed
    from core.appium_server import ensure_appium
    from core.driver_factory import create_driver
    from core.emulator import ADB, ensure_device, run
    from core.web.steps import StepRecorder

    target_dir = request.path.parents[1]  # targets/apps/<name>/tests/test_x.py -> targets/apps/<name>
    cfg = importlib.import_module(f"targets.apps.{target_dir.name}.target")
    package = cfg.APP_PACKAGE

    serial = ensure_device()
    if not is_installed(serial, package):
        raise RuntimeError(f"{package} is not installed on {serial}. Install it from the Play Store or with: adb install <apk>")
    if getattr(cfg, "FRESH_START", False):
        # wipes app data and revokes runtime permissions: the app behaves like a first launch
        run(ADB, "-s", serial, "shell", "pm", "clear", package)

    ensure_appium()
    driver = create_driver(serial, package)
    # launched through Appium rather than core.app.launch_app: that one waits for the app to hold
    # window focus, which a first-launch permission dialog (owned by the OS) takes away
    driver.activate_app(package)
    rec = StepRecorder(driver, target_dir / "reports" / time.strftime("%Y%m%d-%H%M%S"))
    yield rec
    rec.finish()
    driver.quit()

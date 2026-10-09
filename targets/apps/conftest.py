import importlib
import time

import pytest

from core import otp, results, slot


@pytest.fixture
def steps(request):
    """Emulator + app + Appium session, plus a step recorder writing into
    <target>/reports/<timestamp>/. Settings come from <target>/target.py.
    steps.attempt is this run's MongoDB attempt and steps.otp its OTP Waiter (core/otp.py),
    subscribed to Redis before the app is driven. Under the orchestrator (SLOT set) it uses only
    that slot's emulator, Appium port and systemPort."""
    from core.app import is_installed
    from core.appium_server import ensure_appium
    from core.driver_factory import create_driver
    from core.emulator import ADB, ensure_device, run
    from core.web.steps import StepRecorder

    target_dir = request.path.parents[1]  # targets/apps/<name>/tests/test_x.py -> targets/apps/<name>
    cfg = importlib.import_module(f"targets.apps.{target_dir.name}.target")
    package = cfg.APP_PACKAGE

    serial = ensure_device(port=slot.EMULATOR_PORT, exclusive=slot.PARALLEL)
    if not is_installed(serial, package):
        raise RuntimeError(f"{package} is not installed on {serial}. Install it from the Play Store or with: adb install <apk>")
    if getattr(cfg, "FRESH_START", False):
        # wipes app data and revokes runtime permissions: the app behaves like a first launch
        run(ADB, "-s", serial, "shell", "pm", "clear", package)

    ensure_appium(slot.APPIUM)
    driver = create_driver(serial, package, slot.APPIUM, slot.SYSTEM_PORT)
    # launched through Appium rather than core.app.launch_app: that one waits for the app to hold
    # window focus, which a first-launch permission dialog (owned by the OS) takes away
    driver.terminate_app(package)  # a still-running app would resume mid-flow instead of on its first screen
    driver.activate_app(package)
    run_name = time.strftime("%Y%m%d-%H%M%S") + (f"-slot{slot.INDEX}" if slot.PARALLEL else "")
    rec = StepRecorder(driver, target_dir / "reports" / run_name)
    rec.attempt = results.attempt_for_run("app", target_dir.name)
    rec.otp = otp.Waiter(rec.attempt)
    yield rec
    results.finish_attempt(rec.attempt, hasattr(request.node, "rep_call") and request.node.rep_call.passed)
    rec.otp.close()
    rec.finish()
    driver.quit()

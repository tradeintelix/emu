"""Launch the app named in .env on the running device."""
import logging
import time

from config.settings import APP_PACKAGE
from core.emulator import ADB, ensure_device, run

log = logging.getLogger(__name__)


def is_installed(serial, package):
    out = run(ADB, "-s", serial, "shell", "pm", "list", "packages", package)
    return f"package:{package}" in out.split()  # exact match: "com.foo" must not match "com.foo.pro"


def _in_foreground(serial, package):
    out = run(ADB, "-s", serial, "shell", "dumpsys window | grep mCurrentFocus")
    return package in out


def launch_app(serial, package=APP_PACKAGE, timeout=30):
    """Start the app's launcher activity and wait until it has focus."""
    if not package:
        raise RuntimeError("APP_PACKAGE is not set. Copy .env.example to .env and set it.")
    if not is_installed(serial, package):
        raise RuntimeError(f"{package} is not installed on {serial}. Find the name with: adb shell pm list packages -3")

    # monkey with the LAUNCHER category starts the default launcher activity, so no activity name is needed
    run(ADB, "-s", serial, "shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _in_foreground(serial, package):
            log.info("%s is in the foreground", package)
            return
        time.sleep(1)
    raise TimeoutError(f"{package} did not reach the foreground within {timeout}s")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    launch_app(ensure_device())

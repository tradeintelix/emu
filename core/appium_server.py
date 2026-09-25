"""Make sure an Appium server is reachable, starting a local one if needed."""
import logging
import os
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from config.settings import APPIUM_URL, SDK

log = logging.getLogger(__name__)


def _is_up():
    try:
        urlopen(f"{APPIUM_URL}/status", timeout=2)
        return True
    except OSError:
        return False


def ensure_appium(timeout=60):
    if _is_up():
        return
    url = urlparse(APPIUM_URL)
    if url.hostname not in ("127.0.0.1", "localhost"):
        raise RuntimeError(f"Appium at {APPIUM_URL} is not reachable and is not local, so it can't be started here.")

    Path("reports").mkdir(exist_ok=True)
    log.info("Starting Appium on port %s", url.port or 4723)
    subprocess.Popen(
        ["appium", "--port", str(url.port or 4723)],
        env={**os.environ, "ANDROID_HOME": SDK},
        stdout=open("reports/appium.log", "w"), stderr=subprocess.STDOUT,
        start_new_session=True,  # keeps running between test runs
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _is_up():
            return
        time.sleep(1)
    raise TimeoutError(f"Appium did not come up within {timeout}s, see reports/appium.log")

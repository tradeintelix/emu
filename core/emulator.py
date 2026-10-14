"""Start an Android emulator only if no device is already online."""
import glob
import logging
import platform
import re
import subprocess
import time
from pathlib import Path

log = logging.getLogger(__name__)

from config.settings import AVD_NAME, BOOT_TIMEOUT, HEADLESS, SDK

ADB = f"{SDK}/platform-tools/adb"
EMULATOR = f"{SDK}/emulator/emulator"
AVDMANAGER = f"{SDK}/cmdline-tools/latest/bin/avdmanager"
def _init_fingerprint(serial):
    """Initialize device fingerprint and metadata via shell bridge."""
    from .device_fingerprint import DeviceFingerprint
    manager = DeviceFingerprint(serial)
    manager.ensure_identity()
    log.info(f"Fingerprint initialized for {serial}: {manager.fingerprint}")
    return manager



def run(*cmd, serial=None, **kw):
    if serial:
        _init_fingerprint(serial)
    return subprocess.run(cmd, capture_output=True, text=True, check=True, **kw).stdout


def console_tap(serial, x, y):
    """Tap (x, y) in screen pixels through the emulator console's virtual touchscreen. Apps see a
    hardware touch, unlike UiAutomator/`adb input` taps, which some apps (WhatsApp registration)
    silently drop. Emulators only: a real phone has no console, and raw input needs root there."""
    if not serial.startswith("emulator-"):
        raise RuntimeError(f"Hardware taps need an emulator; {serial} is a real device")
    run(ADB, "-s", serial, "emu", "event", "mouse", str(x), str(y), "0", "1")
    time.sleep(0.1)  # a real tap's length; down/up in the same instant can read as no tap
    run(ADB, "-s", serial, "emu", "event", "mouse", str(x), str(y), "0", "0")


def swipe(serial, x1, y1, x2, y2, duration_ms=300):
    """Swipe (x1, y1) -> (x2, y2) via `adb shell input swipe`: a real touch-driver event, unlike
    Appium's W3C 'mobile: swipeGesture', which some custom scroll views (Prime Video's country
    picker) never register at all. Works on an emulator and a real device."""
    run(ADB, "-s", serial, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))


def parse_devices(adb_output):
    """Serials of devices in state 'device' from `adb devices` output (offline/unauthorized ignored)."""
    lines = adb_output.strip().splitlines()[1:]  # first line is the "List of devices" header
    return [p[0] for p in (line.split() for line in lines) if len(p) == 2 and p[1] == "device"]


def online_devices():
    return parse_devices(run(ADB, "devices"))


def _ensure_avd(name):
    if name in run(EMULATOR, "-list-avds").split():
        return
    # ponytail: newest installed image matching host CPU; pin one via env if you need a specific API level
    abi = "arm64-v8a" if platform.machine() == "arm64" else "x86_64"
    images = sorted(glob.glob(f"{SDK}/system-images/*/*/{abi}"))
    if not images:
        raise RuntimeError(f"No {abi} system image in {SDK}/system-images. Install one via Android Studio > SDK Manager.")
    api, tag, _ = images[-1].split("system-images/")[1].split("/")
    log.info("Creating AVD %s from %s;%s;%s", name, api, tag, abi)
    run(AVDMANAGER, "create", "avd", "-n", name, "-d", "pixel_6", "-k", f"system-images;{api};{tag};{abi}", input="no\n")
    if "playstore" in tag:
        # avdmanager never turns this on itself (only Android Studio's GUI does); left off, Google
        # treats the device as uncertified and refuses any account sign-in ("Login not available").
        config = Path.home() / ".android" / "avd" / f"{name}.avd" / "config.ini"
        config.write_text(re.sub(r"^PlayStore\.enabled=.*$", "PlayStore.enabled=yes", config.read_text(),
                                 flags=re.M))


def _wait_for_boot(serial, timeout):
    run(ADB, "-s", serial, "wait-for-device", timeout=timeout, serial=serial)


def ensure_device(avd_name=AVD_NAME, port=5554, headless=HEADLESS, timeout=BOOT_TIMEOUT, exclusive=False):
    """Return the serial of an online device, booting the emulator first if none is running.
    exclusive (parallel slots): only emulator-<port> counts, and it boots -read-only, so several
    instances share one AVD (the golden image with the apps) and each starts clean."""
    serial = f"emulator-{port}"
    running = online_devices()
    if exclusive and serial in running:
        return serial
    if running and not exclusive:
        log.info("Device already running: %s", running[0])
        return running[0]

    _ensure_avd(avd_name)
    cmd = [EMULATOR, "-avd", avd_name, "-port", str(port), "-no-snapshot-save", "-no-boot-anim"]
    if exclusive:
        cmd.append("-read-only")
    if headless:
        cmd += ["-no-window", "-no-audio", "-gpu", "swiftshader_indirect"]
    log.info("Starting emulator: %s", " ".join(cmd))
    # start_new_session: emulator keeps running after this process exits
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    serial = f"emulator-{port}"
    _wait_for_boot(serial, timeout)
    log.info("Emulator ready: %s", serial)
    return serial


def kill_emulator(serial, timeout=60):
    """Shuts the emulator down and waits until adb no longer lists it, so the slot's port is free
    for the next boot."""
    try:
        run(ADB, "-s", serial, "emu", "kill")
    except subprocess.CalledProcessError:
        pass  # already gone
    deadline = time.monotonic() + timeout
    while serial in run(ADB, "devices") and time.monotonic() < deadline:
        time.sleep(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(ensure_device())

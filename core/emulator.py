"""Start an Android emulator only if no device is already online."""
import glob
import logging
import platform
import subprocess
import time

log = logging.getLogger(__name__)

from config.settings import AVD_NAME, BOOT_TIMEOUT, HEADLESS, SDK

ADB = f"{SDK}/platform-tools/adb"
EMULATOR = f"{SDK}/emulator/emulator"
AVDMANAGER = f"{SDK}/cmdline-tools/latest/bin/avdmanager"


def run(*cmd, **kw):
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


def _wait_for_boot(serial, timeout):
    deadline = time.monotonic() + timeout
    run(ADB, "-s", serial, "wait-for-device", timeout=timeout)
    while time.monotonic() < deadline:
        if run(ADB, "-s", serial, "shell", "getprop", "sys.boot_completed").strip() == "1":
            return
        time.sleep(2)
    raise TimeoutError(f"{serial} did not finish booting within {timeout}s")


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

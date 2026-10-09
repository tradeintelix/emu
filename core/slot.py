"""This process's emulator slot. core/orchestrator.py sets SLOT for each parallel worker; unset means
a normal single run, which keeps the old behaviour (any online device, APPIUM_URL)."""
import os

from config.settings import APPIUM_URL


def emulator_port(i):
    return 5554 + 2 * i  # the emulator takes the console port and the next one (adb)


def serial(i):
    return f"emulator-{emulator_port(i)}"


INDEX = int(os.getenv("SLOT") or 0)
PARALLEL = os.getenv("SLOT") is not None
EMULATOR_PORT = emulator_port(INDEX)
APPIUM = f"http://127.0.0.1:{4723 + INDEX}" if PARALLEL else APPIUM_URL
SYSTEM_PORT = 8200 + INDEX  # UiAutomator2's device-side port; two sessions on one port collide

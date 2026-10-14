"""UrbanVPN inside the emulator: connect to a country before an app flow starts.

Only the emulator's traffic is tunnelled (Android VpnService); the server's own routing - the inbound
SMPP bind and SSH - is untouched. The VPN app is installed on the golden AVD, so every read-only clone
has it. It is driven through the same Appium session as the target app (UiAutomator2 can drive any
foreground app); the caller activates the target app again afterwards."""
import time

from selenium.webdriver.common.by import By

PKG = "com.urbanvpn.android"
SKIPPABLE = (  # first-run / upsell screens in the order they appear; any may be absent on a given launch
    ("id", "skipButton"), ("id", "acceptEulaButton"), ("id", "paymentContinueFree"),
    ("text", "Close"), ("text", "Skip"), ("text", "Not now"), ("text", "No thanks"),
)


class VpnError(RuntimeError):
    pass


def _rid(name):
    return f"{PKG}:id/{name}"


def _first(driver, by, value):
    els = driver.find_elements(by, value)
    return els[0] if els and els[0].is_displayed() else None


def _text(driver, name):
    e = driver.find_elements(By.ID, _rid(name))
    return e[0].text if e else None


def _accept_consent(driver):
    """Android's "Connection request" dialog. A read-only clone forgets the grant on every boot, so
    it can appear at launch or after the connect tap. True if it was there and was accepted."""
    ok = _first(driver, By.ID, "android:id/button1")
    if ok and _first(driver, By.XPATH, "//*[@text='Connection request']"):
        ok.click()
        time.sleep(2)
        return True
    return False


def _open_home(driver, timeout=90):
    """Launch UrbanVPN and click through whatever stands between launch and the connect screen."""
    driver.activate_app(PKG)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(2)
        if _accept_consent(driver):  # a system dialog, so it must be answered before the package check
            continue
        if driver.current_package != PKG:
            driver.activate_app(PKG)
            continue
        if _first(driver, By.ID, _rid("controlButton")):
            return
        for kind, value in SKIPPABLE:
            xpath = (f"//*[@resource-id='{_rid(value)}']" if kind == "id" else f"//*[@text='{value}']")
            e = _first(driver, By.XPATH, xpath)
            if e:
                e.click()
                break
    raise VpnError("UrbanVPN never reached its connect screen")


def _select_country(driver, country, max_scrolls=30):
    nav = _first(driver, By.XPATH, "//*[@content-desc='Locations']")
    if not nav:
        raise VpnError("UrbanVPN Locations tab not found")
    nav.click()
    row = f"//*[@resource-id='{_rid('locationItemLabel')}' and @text='{country}']"
    for _ in range(max_scrolls):
        e = _first(driver, By.XPATH, row)
        if e:
            e.click()
            return
        driver.execute_script("mobile: scrollGesture", {"left": 200, "top": 600, "width": 600, "height": 900,
                                                         "direction": "down", "percent": 0.8})
        time.sleep(0.5)
    raise VpnError(f"{country} is not in UrbanVPN's location list")


def _tunnel_up(driver):
    """True when the emulator's traffic goes through a tun interface (checked from the OS, not the
    app, whose IP readout lags)."""
    from core.emulator import ADB, run  # local import: keeps this module importable without the SDK
    out = run(ADB, "-s", driver.capabilities["udid"], "shell", "ip", "route", "get", "8.8.8.8")
    return "tun" in out


def _wait_for_traffic(driver, timeout=45):
    """A tun interface appearing doesn't mean traffic flows yet: an app launched in that window can
    hang on its first network calls (Spotify sat on a blank splash). Waits until a hostname resolves
    and answers through the tunnel, then a short settle."""
    from core.emulator import ADB, run
    serial = driver.capabilities["udid"]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            run(ADB, "-s", serial, "shell", "ping", "-c", "1", "-W", "3", "spotify.com")
            time.sleep(5)
            return
        except Exception:  # ping exits non-zero until DNS and the route work
            time.sleep(2)
    raise VpnError("UrbanVPN tunnel is up but carries no traffic")


def connect(driver, country, timeout=60):
    """Selects `country` in UrbanVPN and connects. Raises VpnError if it can't, so the run is aborted
    rather than going on with the server's own IP. Returns once the tunnel carries traffic."""
    _open_home(driver)
    if _text(driver, "selectedLocationText") != country:
        _select_country(driver, country)
        _open_home(driver)
        shown = _text(driver, "selectedLocationText")
        if shown != country:
            raise VpnError(f"UrbanVPN selected {shown!r} instead of {country!r}")
    if _tunnel_up(driver):  # still connected from earlier on this emulator: reconnect to be sure of the country
        _first(driver, By.ID, _rid("controlButton")).click()
        time.sleep(3)
    deadline = time.monotonic() + timeout
    tapped = False
    while time.monotonic() < deadline:
        if _accept_consent(driver):
            pass
        elif not tapped and not _tunnel_up(driver):
            _first(driver, By.ID, _rid("controlButton")).click()
            tapped = True
        elif _tunnel_up(driver):
            _wait_for_traffic(driver)
            return
        time.sleep(2)
    raise VpnError(f"UrbanVPN did not connect to {country} within {timeout}s")

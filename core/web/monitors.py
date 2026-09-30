import json


def _get_log(driver, log_type):
    # Local Chrome exposes logs via the "getLog" command; call it directly so both
    # plain and Chromium drivers work. Pure CDP (sb_cdp) has no WebDriver log
    # endpoint at all - return [] so StepRecorder keeps working; challenge
    # classification lives in core/web/sb_detect.py instead.
    if driver.__class__.__module__.startswith("seleniumbase"):
        return []
    return driver.execute("getLog", {"type": log_type})["value"]


def drain(driver):
    """Bugs the browser reported since the last call: console errors, HTTP >= 400, failed requests."""
    found = []
    try:
        browser_logs = _get_log(driver, "browser")
        perf_logs = _get_log(driver, "performance")
    except Exception:
        return []  # CDP / remote without log endpoint: no passive findings, still record steps
    for e in browser_logs:
        if e["level"] == "SEVERE":
            found.append({"type": "console", "message": e["message"]})
    for e in perf_logs:
        msg = json.loads(e["message"])["message"]
        p = msg.get("params", {})
        if msg["method"] == "Network.responseReceived" and p["response"]["status"] >= 400:
            found.append({"type": "http", "status": p["response"]["status"], "url": p["response"]["url"]})
        elif msg["method"] == "Network.loadingFailed" and not p.get("canceled"):
            # ponytail: this event carries no URL, only requestId; join on requestWillBeSent if that's needed
            found.append({"type": "network", "error": p.get("errorText"), "request_id": p.get("requestId")})
    return found

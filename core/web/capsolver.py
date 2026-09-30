"""CapSolver client for Arkose Labs (FunCaptcha) token solves.

Replaces Bright Data's in-place ``Captcha.waitForSolve`` (see deleted
``core/web/browser_api.py``). Flow is token-based:

1. Extract Arkose params from the live page (see ``core/web/arkose.py``).
2. ``POST /createTask`` with ``FunCaptchaTaskProxyless``.
3. Poll ``POST /getTaskResult`` until ``ready`` / ``failed``.
4. Inject the returned ``token`` into ``#fc-token`` (see ``arkose.inject_token``)
   and let the page continue to the OTP screen.

No funded key yet -> all solve entry points return ``"no_key"`` instead of
crashing, so detection-only runs keep working until ``CAPSOLVER_API_KEY``
is set. Uses only stdlib (urllib) so no new pip dependency is needed.
"""
import json
import time
import urllib.request

from config.settings import CAPSOLVER_API_KEY

CREATE_TASK_URL = "https://api.capsolver.com/createTask"
RESULT_URL = "https://api.capsolver.com/getTaskResult"
BALANCE_URL = "https://api.capsolver.com/getBalance"

POLL_INTERVAL_S = 3
DEFAULT_TASK_TIMEOUT_S = 120


class CapsolverError(RuntimeError):
    pass


def is_configured():
    return bool((CAPSOLVER_API_KEY or "").strip())


def _post(url, payload, timeout=30):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise CapsolverError(f"POST {url} failed: {type(e).__name__}: {e}")


def get_balance():
    """Returns credit balance. Raises CapsolverError (incl. when key is missing)."""
    if not is_configured():
        raise CapsolverError("CAPSOLVER_API_KEY is not set. Add it to .env (see .env.example).")
    res = _post(BALANCE_URL, {"clientKey": CAPSOLVER_API_KEY.strip()})
    if res.get("errorId") not in (0, None) and res.get("errorId") != 0:
        raise CapsolverError(f"getBalance failed: {res}")
    return res.get("balance")


def solve_funcaptcha(website_url, website_public_key, surl=None, data=None,
                     user_agent=None, timeout_s=DEFAULT_TASK_TIMEOUT_S):
    """Solves one Arkose FunCaptcha. Returns the ``fc-token`` string.

    Raises CapsolverError on missing key, API error, solve failure, or timeout.
    Caller injects the token via ``arkose.inject_token`` and waits for OTP.
    """
    if not is_configured():
        raise CapsolverError("CAPSOLVER_API_KEY is not set.")
    if not website_url or not website_public_key:
        raise CapsolverError("websiteURL and websitePublicKey are both required.")

    task = {
        "type": "FunCaptchaTaskProxyless",
        "websiteURL": website_url,
        "websitePublicKey": website_public_key,
    }
    # Uber loads api.js from its own Arkose subdomain; default only fits demos.
    if surl:
        task["funcaptchaApiJSSubdomain"] = surl
    if data:
        task["data"] = data
    if user_agent:
        task["userAgent"] = user_agent

    created = _post(CREATE_TASK_URL, {"clientKey": CAPSOLVER_API_KEY.strip(), "task": task})
    if created.get("errorId") != 0 or not created.get("taskId"):
        raise CapsolverError(f"createTask failed: {created}")
    task_id = created["taskId"]

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_S)
        res = _post(RESULT_URL, {"clientKey": CAPSOLVER_API_KEY.strip(), "taskId": task_id})
        status = res.get("status")
        if status == "ready":
            token = (res.get("solution") or {}).get("token")
            if not token:
                raise CapsolverError(f"ready but no token: {res}")
            cost = res.get("cost", "?")
            print(f"CapSolver solved task {task_id} (cost {cost})", flush=True)
            return token
        if status == "failed":
            raise CapsolverError(f"Task {task_id} failed: {res.get('errorDescription', res)}")
        # "processing" -> keep polling
    raise CapsolverError(f"Task {task_id} timed out after {timeout_s}s")

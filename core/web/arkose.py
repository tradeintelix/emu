"""Arkose Labs (FunCaptcha) param extraction + token injection.

Works for both drivers in this repo:
- Selenium WebDriver (``test_signup_phone.py`` via ``core/web/browser.py``)
- SeleniumBase SB-CDP (``test_sb_avoid_phone.py``) via ``sb.execute_script``

Uber's shield (``Protecting your account / Start Puzzle``) only mounts the
real puzzle after the Start button is clicked, so callers click first
(``outcome._click_start_in_frames``) and then call ``extract_params``.
"""
import re

UUID_RE = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")

# Runs in the page. Scans main document for the three things CapSolver needs.
# Cross-origin challenge iframes are opaque to JS, so anything inside them is
# picked up by the Python frame-walk fallback in extract_params_webdriver.
EXTRACT_JS = """
(() => {
  const out = {publicKey: null, surl: null, data: null};
  const pick = (v) => (v && typeof v === 'string' && v.length > 0) ? v : null;
  // 1. data-pkey div / fc-token input (pk= + surl= query params)
  const pkeyEl = document.querySelector('[data-pkey]');
  if (pkeyEl) out.publicKey = pick(pkeyEl.getAttribute('data-pkey'));
  const fc = document.querySelector('#fc-token, input[name="fc-token"]');
  if (fc) {
    const val = fc.getAttribute('value') || fc.value || '';
    const pk = val.match(/[?&]?pk=([^&|;\"']+)/);
    if (pk) out.publicKey = out.publicKey || pk[1];
    const su = val.match(/[?&]?surl=([^&|;\"']+)/);
    if (su) out.surl = decodeURIComponent(su[1]);
  }
  // 2. api.js script URL: https://<sub>.arkoselabs.com/v2/<UUID>/api.js
  document.querySelectorAll('script[src*="arkoselabs.com"]').forEach(s => {
    const src = s.src || '';
    const m = src.match(/https?:\\/\\/([^\\/\"']+\\.arkoselabs\\.com)/);
    if (m && !out.surl) out.surl = m[1];
    const u = src.match(/([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})/);
    if (u && !out.publicKey) out.publicKey = u[1];
  });
  // 3. inline blob: Arkose.setConfig({data:{blob:"..."}}) or window config
  try {
    const html = document.documentElement.innerHTML || '';
    const b = html.match(/\"blob\"\\s*:\\s*\"([^\"]{20,})\"/);
    if (b) out.data = JSON.stringify({blob: b[1]});
  } catch (e) {}
  return out;
})()
"""

# Sets #fc-token value + fires events so Arkose's frontend picks the solve up.
# Returns true if a token field was found and set.
INJECT_JS = """
((token) => {
  const set = (el) => {
    try {
      el.focus && el.focus();
      // React-controlled inputs need the native setter to register the change.
      const desc = Object.getOwnPropertyDescriptor(el.__proto__ || {}, 'value')
        || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
      if (desc && desc.set) desc.set.call(el, token);
      else el.value = token;
      el.setAttribute('value', token);
      el.dispatchEvent(new Event('input', {bubbles: true}));
      el.dispatchEvent(new Event('change', {bubbles: true}));
      return true;
    } catch (e) { return false; }
  };
  let el = document.querySelector('#fc-token') || document.querySelector('input[name="fc-token"]');
  if (el) return set(el);
  // Fallback: some deployments keep the token in a hidden field near the widget.
  const hidden = Array.from(document.querySelectorAll('input[type="hidden"]'))
    .find(i => /fc-?token|arkose|funcaptcha/i.test(i.name || i.id || ''));
  if (hidden) return set(hidden);
  return false;
})(arguments[0])
"""


def _clean(params):
    if not isinstance(params, dict):
        return {"publicKey": None, "surl": None, "data": None}
    pk = params.get("publicKey")
    if pk and not UUID_RE.fullmatch(str(pk).strip()):
        m = UUID_RE.search(str(pk))
        pk = m.group(0) if m else None
    surl = params.get("surl")
    if surl:
        surl = str(surl).strip().replace("https://", "").replace("http://", "").split("/")[0]
        if "arkoselabs.com" not in surl:
            surl = None
    data = params.get("data")
    return {"publicKey": pk, "surl": surl, "data": data}


def extract_params_webdriver(driver):
    """Extracts {publicKey, surl, data} via JS + frame walk (Selenium WebDriver).

    Main-document JS first; if publicKey is still missing, walks up to 3 levels
    of iframes (same pattern as outcome._click_start_in_frames) since Uber nests
    the widget. Always restores default_content before returning.
    """
    from selenium.webdriver.common.by import By

    try:
        params = _clean(driver.execute_script(EXTRACT_JS))
        if params["publicKey"]:
            return params
    except Exception:
        params = {"publicKey": None, "surl": None, "data": None}

    def _walk(depth):
        nonlocal params
        if depth > 3:
            return
        try:
            frames = driver.find_elements(By.TAG_NAME, "iframe")
        except Exception:
            return
        for frame in frames:
            try:
                driver.switch_to.frame(frame)
                found = _clean(driver.execute_script(EXTRACT_JS))
                for k in ("publicKey", "surl", "data"):
                    if not params.get(k) and found.get(k):
                        params[k] = found[k]
                if params["publicKey"]:
                    return
                _walk(depth + 1)
                if params["publicKey"]:
                    return
                driver.switch_to.parent_frame()
            except Exception:
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass
                return

    try:
        _walk(0)
    finally:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
    return params


def extract_params_sb(sb):
    """SB-CDP variant: single JS eval (no frame-switch API). Returns cleaned dict."""
    try:
        return _clean(sb.execute_script(EXTRACT_JS))
    except Exception:
        return {"publicKey": None, "surl": None, "data": None}


def inject_token_webdriver(driver, token):
    """Injects token into #fc-token (main doc, then frames). Returns True on success."""
    from selenium.webdriver.common.by import By

    try:
        if driver.execute_script(INJECT_JS, token):
            return True
    except Exception:
        pass
    try:
        frames = driver.find_elements(By.TAG_NAME, "iframe")
    except Exception:
        return False
    for frame in frames:
        try:
            driver.switch_to.frame(frame)
            try:
                if driver.execute_script(INJECT_JS, token):
                    return True
            finally:
                driver.switch_to.parent_frame()
        except Exception:
            try:
                driver.switch_to.default_content()
            except Exception:
                pass
            break
    try:
        driver.switch_to.default_content()
    except Exception:
        pass
    return False


def inject_token_sb(sb, token):
    """SB-CDP variant. Returns True if the token field was found and set."""
    try:
        # sb_cdp's execute_script formats args differently across versions;
        # inline the token safely instead of relying on arguments[0].
        import json as _json
        js = INJECT_JS.replace("arguments[0]", _json.dumps(token))
        return bool(sb.execute_script(js))
    except Exception:
        return False

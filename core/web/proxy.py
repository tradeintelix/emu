"""Generic authenticated-proxy extension for Chrome. Takes host/port/username/password
so any proxy source (core/web/residential_proxy.py, or the legacy Bright Data vars) can
feed it - this file doesn't know or care which.

Chrome's --proxy-server flag doesn't accept a username/password (Chromium dropped that
years ago), so the standard workaround - and the one this uses - is a throwaway unpacked
extension that sets the proxy and answers Chrome's proxy-auth prompt automatically.
No extra pip dependency: it's plain Chrome flags + Selenium, which is already installed."""
import json
from pathlib import Path

# regenerated on every run from the current .env; gitignored, never commit real credentials
EXT_DIR = Path(__file__).parent / ".proxy_ext"

MANIFEST = {
    "manifest_version": 3,
    "name": "Proxy auth",
    "version": "1.0",
    "permissions": ["proxy", "webRequest", "webRequestAuthProvider"],
    "host_permissions": ["<all_urls>"],
    "background": {"service_worker": "background.js"},
}

BACKGROUND = """
chrome.proxy.settings.set({{
  value: {{ mode: "fixed_servers", rules: {{ singleProxy: {{ scheme: "http", host: "{host}", port: {port} }} }} }},
  scope: "regular"
}}, () => {{}});

chrome.webRequest.onAuthRequired.addListener(
  (details, callback) => callback({{authCredentials: {{username: "{username}", password: "{password}"}}}}),
  {{urls: ["<all_urls>"]}},
  ["asyncBlocking"]
);
"""


def build_auth_extension(host, port, username, password):
    """Write the extension to disk and return its directory, for --load-extension."""
    EXT_DIR.mkdir(exist_ok=True)
    (EXT_DIR / "manifest.json").write_text(json.dumps(MANIFEST, indent=2))
    (EXT_DIR / "background.js").write_text(BACKGROUND.format(
        host=host, port=port, username=username, password=password,
    ))
    return EXT_DIR

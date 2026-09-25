"""Passive security analysis from the browser's own network log - no probing, no extra
requests, just reading what the site already sent during a normal run. Runs alongside
core/web/monitors.py (bugs) rather than replacing it; this is security posture, not errors.
"""
import json
import re

from core.web.monitors import _get_log

SECRET_PATTERN = re.compile(r"(?:password|token|secret|api[_-]?key)=[^&\s\"']{4,}", re.I)
TRACKING_SUFFIXES = (".doubleclick.net", ".google-analytics.com", ".facebook.com", ".hotjar.com", ".segment.io")


def _security_headers(headers):
    lower = {k.lower(): v for k, v in headers.items()}
    missing = []
    if "strict-transport-security" not in lower:
        missing.append("Strict-Transport-Security")
    if "content-security-policy" not in lower:
        missing.append("Content-Security-Policy")
    if "x-frame-options" not in lower and "frame-ancestors" not in lower.get("content-security-policy", ""):
        missing.append("X-Frame-Options")
    return missing


def _cookie_flags(set_cookie_value):
    """One Set-Cookie header's value -> which of Secure/HttpOnly/SameSite it's missing."""
    lower = set_cookie_value.lower()
    missing = []
    if "secure" not in lower:
        missing.append("Secure")
    if "httponly" not in lower:
        missing.append("HttpOnly")
    if "samesite" not in lower:
        missing.append("SameSite")
    return missing


def analyze(driver, base_host):
    """base_host: the site under test's own hostname (e.g. "uber.com"), so first-party vs
    third-party requests can be told apart. Returns a list of finding dicts, most specific
    evidence first; each has severity/category/detail/url so a client report can cite it."""
    findings = []
    seen_missing_headers_for = set()  # only report once per document, not once per sub-resource
    third_party_hosts = set()

    for e in _get_log(driver, "performance"):
        msg = json.loads(e["message"])["message"]
        method, p = msg["method"], msg.get("params", {})

        if method == "Network.responseReceived":
            resp = p["response"]
            url, headers = resp["url"], resp.get("headers", {})
            host = re.sub(r"^https?://([^/]+).*", r"\1", url)

            if base_host not in host:
                if any(host.endswith(s) for s in TRACKING_SUFFIXES) or host not in third_party_hosts:
                    third_party_hosts.add(host)
                continue  # header/cookie posture is only meaningful for the site's own responses

            if resp.get("mimeType", "").startswith("text/html") and url not in seen_missing_headers_for:
                seen_missing_headers_for.add(url)
                missing = _security_headers(headers)
                if missing:
                    findings.append({"severity": "medium", "category": "missing-security-header",
                                      "url": url, "detail": f"Missing: {', '.join(missing)}"})

            set_cookie = headers.get("set-cookie") or headers.get("Set-Cookie", "")
            for line in set_cookie.split("\n") if set_cookie else []:
                if not line.strip():
                    continue
                missing = _cookie_flags(line)
                if missing:
                    name = line.split("=", 1)[0].strip()
                    findings.append({"severity": "medium", "category": "cookie-flags", "url": url,
                                      "detail": f"Cookie '{name}' missing: {', '.join(missing)}"})

            if resp["status"] >= 500:
                findings.append({"severity": "high", "category": "server-error", "url": url,
                                  "detail": f"HTTP {resp['status']} from own backend during a normal flow"})

        elif method == "Network.requestWillBeSent":
            url = p["request"]["url"]
            if SECRET_PATTERN.search(url):
                findings.append({"severity": "high", "category": "sensitive-data-in-url",
                                  "url": url.split("?")[0], "detail": "Query string looks like it carries a secret"})

    if third_party_hosts:
        findings.append({"severity": "info", "category": "third-party-requests", "url": base_host,
                          "detail": f"{len(third_party_hosts)} third-party host(s) contacted: "
                                    f"{', '.join(sorted(third_party_hosts))[:300]}"})
    return findings

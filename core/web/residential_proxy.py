"""Bright Data Residential IP proxy - one place to build the proxy connection for
any current or future web/app flow. https://docs.brightdata.com/products/residential/introduction

Connect via brd.superproxy.io:44445, authenticating as username
"brd-customer-<id>-zone-<zone>[-country-<cc>][-session-<id>]" with the zone password.
Country is ISO-3166 (e.g. "us", "in") or "eu"; session pins the same exit IP across
requests. Blank BRIGHTDATA_CUSTOMER_ID = not configured, callers fall back to direct.
"""
from config.settings import BRIGHTDATA_CUSTOMER_ID, BRIGHTDATA_ZONE, BRIGHTDATA_ZONE_PASSWORD

HOST = "brd.superproxy.io"
PORT = 44445


def is_configured():
    return bool(BRIGHTDATA_CUSTOMER_ID and BRIGHTDATA_ZONE and BRIGHTDATA_ZONE_PASSWORD)


def username(country=None, session=None):
    parts = [f"brd-customer-{BRIGHTDATA_CUSTOMER_ID}-zone-{BRIGHTDATA_ZONE}"]
    if country:
        parts.append(f"country-{country.lower()}")
    if session:
        parts.append(f"session-{session}")
    return "-".join(parts)


def credentials(country=None, session=None):
    """(username, password, host, port) - for clients that need the parts separately,
    e.g. a Chrome proxy-auth extension (core/web/proxy.py)."""
    return username(country, session), BRIGHTDATA_ZONE_PASSWORD, HOST, PORT


def proxy_url(country=None, session=None):
    """'user:pass@host:port' - the format SeleniumBase CDP's `proxy` kwarg wants."""
    user, password, host, port = credentials(country, session)
    return f"{user}:{password}@{host}:{port}"

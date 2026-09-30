"""SeleniumBase Pure CDP driver (Uber flow).

Why Pure CDP: no WebDriver at all, only Chrome DevTools Protocol, so TLS + JS
fingerprints look like a human-driven Chrome: real browser, coherent
locale/timezone, persistent cookies - with CapSolver solving the challenge
in-page when avoidance alone isn't enough (see core/web/sb_detect.py).
"""
from pathlib import Path

from config.settings import (
    BRIGHTDATA_HOST,
    BRIGHTDATA_PASSWORD,
    BRIGHTDATA_PORT,
    BRIGHTDATA_USERNAME,
    PROXY_ENABLED,
    SB_HEADLESS,
    SB_LANG,
    SB_PROXY,
    SB_TZ,
    SB_USER_DATA_DIR,
)
from core.web import residential_proxy

DEFAULT_PROFILE = Path(__file__).resolve().parents[2] / "targets" / "web" / "uber" / ".sb_profile"


def build_proxy_string(country_suffix=None, session=None):
    """CDP wants 'user:pass@host:port'. SB_PROXY overrides; 'none' forces direct.
    Otherwise the residential proxy (core/web/residential_proxy.py) is used when
    configured, geo-targeted by country_suffix/session; else the legacy BRIGHTDATA_*
    vars work as a generic (non-geo-targeted) proxy; blank runs direct."""
    override = (SB_PROXY or "").strip()
    if override.lower() == "none":
        return None, None
    if override:
        return override, session
    if residential_proxy.is_configured():
        return residential_proxy.proxy_url(country=country_suffix, session=session), session
    if not PROXY_ENABLED:
        return None, None
    # Legacy generic proxy (old Bright Data vars). No country/session suffixing.
    return f"{BRIGHTDATA_USERNAME}:{BRIGHTDATA_PASSWORD}@{BRIGHTDATA_HOST}:{BRIGHTDATA_PORT}", session


def resolve_profile():
    p = Path(SB_USER_DATA_DIR) if SB_USER_DATA_DIR else DEFAULT_PROFILE
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def create_sb_cdp_browser(url="about:blank", country="in", session=None):
    """Launch Pure CDP Chrome. Headed by default (stealth needs a window).
    Persistent profile keeps cookies/storage coherent across runs. Direct by
    default since the CapSolver switch; set SB_PROXY for a proxy."""
    from seleniumbase import sb_cdp

    proxy, sid = build_proxy_string(country_suffix=country, session=session)
    kwargs = {
        "headless": bool(SB_HEADLESS),
        "incognito": False,  # incognito wipes coherence; persistent profile avoids more challenges
        "lang": SB_LANG or "en-US",
        "user_data_dir": resolve_profile(),
        "browser_args": ["--window-size=1366,900", "--lang=en-US"],
    }
    if SB_TZ:
        kwargs["tzone"] = SB_TZ
    if proxy:
        kwargs["proxy"] = proxy
    mode = "proxy" if proxy else "direct (no proxy)"
    print(f"SB CDP launch: {mode} | headed={not bool(SB_HEADLESS)}", flush=True)
    sb = sb_cdp.Chrome(url, **kwargs)
    sb._sb_session = sid
    return sb


def quit_sb(sb):
    try:
        sb.stop()
    except Exception:
        try:
            sb.quit()
        except Exception:
            pass

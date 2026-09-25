"""SeleniumBase Pure CDP avoidance driver (Uber spike).

Why Pure CDP: no WebDriver at all, only Chrome DevTools Protocol, so TLS + JS
fingerprints look like a human-driven Chrome. This is the "avoid the CAPTCHA"
path from the Browserless guide: real browser, coherent locale/timezone,
sticky IP, persistent cookies - not solving after the fact.

Fallback: if a challenge still appears, callers should STOP (or fall back to
Bright Data Browser API). This module never solves anything itself.
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
    SB_SESSION,
    SB_TZ,
    SB_USER_DATA_DIR,
)

DEFAULT_PROFILE = Path(__file__).resolve().parents[2] / "targets" / "web" / "uber" / ".sb_profile"


def _session_id():
    """Sticky session: same string = same exit IP for the whole run (Bright Data
    keeps one IP per session for ~10 min). SB_SESSION reuses an IP; blank mints
    a random one per launch so runs don't share a burned IP."""
    import random
    import string

    if (SB_SESSION or "").strip():
        return SB_SESSION.strip()
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


def build_proxy_string(country_suffix=None, session=None):
    """CDP wants 'user:pass@host:port'. SB_PROXY overrides; blank derives
    from Bright Data; 'none' forces direct. country suffix pins exit geo
    (e.g. '-country-in'); session suffix pins one exit IP for the run
    (e.g. '-session-a1b2c3d4') so Uber sees a coherent sticky residential IP."""
    override = (SB_PROXY or "").strip()
    if override.lower() == "none":
        return None, None
    if override:
        return override, session
    if not PROXY_ENABLED:
        return None, None
    sid = session or _session_id()
    user = BRIGHTDATA_USERNAME
    if country_suffix:
        user = f"{user}-country-{country_suffix.lower()}"
    user = f"{user}-session-{sid}"
    return f"{user}:{BRIGHTDATA_PASSWORD}@{BRIGHTDATA_HOST}:{BRIGHTDATA_PORT}", sid


def resolve_profile():
    p = Path(SB_USER_DATA_DIR) if SB_USER_DATA_DIR else DEFAULT_PROFILE
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def create_sb_cdp_browser(url="about:blank", country="in", session=None):
    """Launch Pure CDP Chrome. Headed by default (stealth needs a window).
    Persistent profile keeps cookies/storage coherent across runs. Sticky
    session keeps one exit IP for the whole run (no mid-flow rotation)."""
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
    mode = f"proxy sticky session={sid} country={country}" if proxy else "direct (no proxy)"
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

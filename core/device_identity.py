"""Per-number device uniqueness (offline, no external services).

Problem: every batch number boots the same `-read-only` golden AVD, so all
numbers share one fingerprint (same Build props, same ANDROID_ID, same
Line1Number prefix, same MCC 310260). Backends score "1 device -> many
numbers" as SMS-pumping and answer "try again in X hours" on every app.

This module derives a deterministic identity from the run's seed
(ATTEMPT_ID, else PHONE+SLOT) so each number boots/applies a different
coherent profile. No network calls, no paid services.

Two layers (both best-effort, never fail a run):
  boot_args()   -> `-prop` / `-phone-number` flags appended in
                   core/emulator.py.ensure_device(). Takes effect because
                   the orchestrator already cold-boots between numbers.
  apply_runtime -> `settings put` / `setprop` after boot, before `pm clear`
                   and Appium launch (targets/apps/conftest.py).

Note on ANDROID_ID: since Android 8 the per-app SSAID lives in
/data/system/users/0/settings_ssaid.xml and only root can rewrite it.
`settings put secure android_id` still rotates the global ID visible to
older APIs and to Play Services on first provisioning, and combined with
fresh boot props + gsm operator + GAID reset it meaningfully diversifies
the fingerprint without root. Full SSAID/Build/IMEI spoof needs the
future rooted golden-root image (Magisk/LSPosed); this module's output
feeds that too via fingerprint_summary().
"""
import hashlib
import logging
import os

log = logging.getLogger(__name__)

# Coherent, real-device-shaped profiles. Model/brand/manufacturer travel
# together so an app never sees a Pixel model with a Galaxy fingerprint.
PROFILES = [
    {"name": "pixel_6", "model": "Pixel 6", "brand": "google",
     "manufacturer": "Google", "device": "oriole"},
    {"name": "pixel_7a", "model": "Pixel 7a", "brand": "google",
     "manufacturer": "Google", "device": "lynx"},
    {"name": "pixel_8", "model": "Pixel 8", "brand": "google",
     "manufacturer": "Google", "device": "shiba"},
    {"name": "galaxy_s23", "model": "SM-S911B", "brand": "samsung",
     "manufacturer": "samsung", "device": "dm1q"},
]

# Phone-country -> carrier emulation coherent with the number being typed.
# MCC/MNC are the primary operator; iso/timezone/locale must match the IP
# country later (Phase 3) or the mismatch itself flags the run.
CARRIERS = {
    "india": {"mcc": "404", "mnc": "45", "iso": "in", "alpha": "Airtel",
              "timezone": "Asia/Kolkata", "locale": "en-IN"},
    "pakistan": {"mcc": "410", "mnc": "01", "iso": "pk", "alpha": "Mobilink",
                 "timezone": "Asia/Karachi", "locale": "en-PK"},
    "saudi arabia": {"mcc": "420", "mnc": "01", "iso": "sa", "alpha": "STC",
                     "timezone": "Asia/Riyadh", "locale": "en-SA"},
    "kuwait": {"mcc": "419", "mnc": "02", "iso": "kw", "alpha": "Zain",
               "timezone": "Asia/Kuwait", "locale": "en-KW"},
    "philippines": {"mcc": "515", "mnc": "66", "iso": "ph", "alpha": "DITO",
                    "timezone": "Asia/Manila", "locale": "en-PH"},
    "sri lanka": {"mcc": "413", "mnc": "01", "iso": "lk", "alpha": "Mobitel",
                  "timezone": "Asia/Colombo", "locale": "en-LK"},
}
DEFAULT_CARRIER = {"mcc": "001", "mnc": "01", "iso": "us", "alpha": "Android",
                   "timezone": "UTC", "locale": "en-US"}


def enabled():
    """Off only when explicitly disabled; keeps single-run behaviour otherwise."""
    return os.getenv("DEVICE_UNIQUE", "1") != "0"


def seed():
    """Stable per-number seed. ATTEMPT_ID exists under the orchestrator
    (one UUID per claimed number); single runs fall back to PHONE+SLOT."""
    attempt = os.getenv("ATTEMPT_ID", "").strip()
    if attempt:
        return attempt
    return f"{os.getenv('PHONE', '')}|{os.getenv('SLOT', '0')}"


def _digest(key):
    return hashlib.sha256(key.encode()).hexdigest()


def carrier_for(phone_country):
    if not phone_country:
        return dict(DEFAULT_CARRIER)
    return dict(CARRIERS.get(phone_country.strip().lower(), DEFAULT_CARRIER))


def generate_identity(seed_str=None, phone_country=None, phone=None):
    """Deterministic identity dict for one number. Same seed -> same output,
    so retries and log correlation stay stable; different numbers diverge."""
    s = seed_str if seed_str is not None else seed()
    if phone_country is None:
        phone_country = os.getenv("PHONE_COUNTRY", "")
    if phone is None:
        phone = os.getenv("PHONE", "")
    d = _digest(f"device|{s}")
    profile = PROFILES[int(d[:8], 16) % len(PROFILES)]
    android_id = _digest(f"android-id|{s}")[:16]  # 16 lowercase hex
    carrier = carrier_for(phone_country)
    digits = "".join(c for c in (phone or "") if c.isdigit())
    return {
        "seed": s,
        "profile": dict(profile),
        "android_id": android_id,
        "carrier": carrier,
        "phone_digits": digits,
        "phone_country": phone_country or "",
    }


def boot_args(identity):
    """Emulator flags giving this boot a different hardware signature.
    Safe `-prop` keys only (model/brand/manufacturer); fingerprint-level
    props can break boot on Play images and belong to golden-root."""
    p = identity["profile"]
    args = [
        "-prop", f"ro.product.model={p['model']}",
        "-prop", f"ro.product.brand={p['brand']}",
        "-prop", f"ro.product.manufacturer={p['manufacturer']}",
    ]
    if identity.get("phone_digits"):
        args += ["-phone-number", identity["phone_digits"][-15:]]
    return args


def fingerprint_summary(identity):
    p, c = identity["profile"], identity["carrier"]
    return (f"profile={p['name']} model={p['model']} "
            f"android_id={identity['android_id']} "
            f"carrier={c['alpha']}/{c['mcc']}{c['mnc']}/{c['iso']} "
            f"tz={c['timezone']} locale={c['locale']}")


def apply_runtime(serial, identity, run_fn):
    """Post-boot rotation (no root needed). Every step is best-effort:
    any failure is logged and the run continues with the boot-flag
    identity alone, so rotation can never break a test."""
    def attempt(*cmd):
        try:
            return run_fn(*cmd)
        except Exception as e:  # noqa: BLE001 - rotation must not fail runs
            log.warning("identity rotation skipped %s: %s", cmd[3:5], e)
            return ""

    adb = attempt  # alias for readability below
    # 1. Global Android ID (visible pre-Oreo + Play Services provisioning).
    adb("adb", "-s", serial, "shell", "settings", "put", "secure",
        "android_id", identity["android_id"])
    # 2. Carrier emulation coherent with the typed number's country.
    c = identity["carrier"]
    numeric = c["mcc"] + c["mnc"]
    for prop in ("gsm.sim.operator.numeric", "gsm.operator.numeric"):
        adb("adb", "-s", serial, "shell", "setprop", prop, numeric)
    for prop in ("gsm.sim.operator.iso-country", "gsm.operator.iso-country"):
        adb("adb", "-s", serial, "shell", "setprop", prop, c["iso"])
    for prop in ("gsm.sim.operator.alpha", "gsm.operator.alpha"):
        adb("adb", "-s", serial, "shell", "setprop", prop, c["alpha"])
    # 3. Timezone/locale coherence (global settings take effect without reboot).
    adb("adb", "-s", serial, "shell", "settings", "put", "global",
        "time_zone", c["timezone"])
    return fingerprint_summary(identity)

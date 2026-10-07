"""Stores one MongoDB document per test run: Web flows go to DB "Web", app flows to DB "Apps",
one collection per target (Apps.Spotify, Web.Uber). The SMPP listener fills in `otp` later,
looking the run up by number (or by the `_id` the fixture exposes as steps.result_id)."""
import os
import time

from config.settings import MONGO_URI, PHONE, PHONE_COUNTRY
from core.countries import _CODES, calling_code


def _split_phone(target):
    """-> (country_code, national_number). '+' numbers are split by longest known calling code;
    otherwise the code comes from --phone-country, else India (every app flow's default)."""
    raw = (PHONE or os.getenv(f"{target.upper()}_PHONE", "")).strip()
    digits = "".join(c for c in raw if c.isdigit())
    if raw.startswith("+"):
        for n in (4, 3, 2, 1):
            if digits[:n] in _CODES.values():
                return digits[:n], digits[n:]
        return "", digits
    return (calling_code(PHONE_COUNTRY) if PHONE_COUNTRY else "91"), digits[-10:]


def _collection(kind, target):
    from pymongo import MongoClient  # local import: runs without mongo installed still work
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    return client["Apps" if kind == "app" else "Web"][target.capitalize()]


def start(kind, target):
    """Inserts the run's document; returns (collection, _id), or (None, None) if MongoDB is down."""
    try:
        code, number = _split_phone(target)
        col = _collection(kind, target)
        doc = {"number": number, "country_code": code, "otp": None, "status": "Running",
               "created_at": time.time()}
        return col, col.insert_one(doc).inserted_id
    except Exception as e:  # a down database must never fail the test itself
        print(f"[results] MongoDB unavailable, run not recorded: {type(e).__name__}: {e}", flush=True)
        return None, None


def finish(col, doc_id, passed):
    if col is None:
        return
    try:
        col.update_one({"_id": doc_id}, {"$set": {"status": "Pass" if passed else "Fail"}})
    except Exception as e:
        print(f"[results] could not update result: {type(e).__name__}: {e}", flush=True)

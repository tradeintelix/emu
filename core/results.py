"""MongoDB side of the OTP flow (docs/automation-plan.md, sections 4 and 5).

DB "Apps" for app flows, "Web" for web flows, two collections per target:
  <Target>_numbers  the CSV batch, one document per number, claimed atomically by the workers
  <Target>          one document per attempt (attempt_id): the state machine and the SMPP outcome
Every state change is a conditional update (only from the expected states), so the workers and the
SMPP service can never overwrite each other, and each one is appended to the attempt's `history`."""
import csv
import os
import re
import time
import uuid
from collections import namedtuple

from config.settings import CLAIM_LEASE, MONGO_URI, PHONE, PHONE_COUNTRY
from core.countries import _CODES, calling_code

# number states
AVAILABLE, CLAIMED, IN_PROGRESS, COMPLETE = "AVAILABLE", "CLAIMED", "IN_PROGRESS", "COMPLETE"
# attempt states
OTP_REQUESTED, WAITING_SMPP = "OTP_REQUESTED", "WAITING_SMPP"
SMPP_DELIVERED, SMPP_UNDELIVERED = "SMPP_DELIVERED", "SMPP_UNDELIVERED"
OTP_REJECTED, OTP_ACCEPTED = "OTP_REJECTED", "OTP_ACCEPTED"
REDIS_PUBLISHED, APPIUM_PROCESSED = "REDIS_PUBLISHED", "APPIUM_PROCESSED"
OTP_TIMEOUT, ABANDONED = "OTP_TIMEOUT", "ABANDONED"
# attempt states an SMPP event may still change (SMPP_UNDELIVERED: decided, waiting for the OTP text)
OPEN = [CLAIMED, OTP_REQUESTED, WAITING_SMPP, SMPP_UNDELIVERED]

Attempt = namedtuple("Attempt", "col attempt_id phone")

_client = None


def client():
    global _client
    if _client is None:
        from pymongo import MongoClient  # local import: runs without pymongo installed still work
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    return _client


def _db(kind):
    return client()["Apps" if kind == "app" else "Web"]


def attempts(kind, target):
    return _db(kind)[target.capitalize()]


def numbers(kind, target):
    return _db(kind)[target.capitalize() + "_numbers"]


def attempt_collections():
    """Every attempts collection in both DBs; the SMPP service doesn't know which app a number ran on."""
    for kind in ("app", "web"):
        db = _db(kind)
        for name in db.list_collection_names():
            if not name.endswith("_numbers"):
                yield db[name]


def ensure_indexes(kind, target):
    a, n = attempts(kind, target), numbers(kind, target)
    a.create_index("attempt_id", unique=True)
    a.create_index("smpp_message_id")
    a.create_index([("phone", 1), ("created_at", -1)])
    n.create_index([("batch_id", 1), ("phone", 1)], unique=True)  # a number runs once per batch
    n.create_index([("batch_id", 1), ("status", 1), ("row_number", 1)])


def move(status, **fields):
    """Update document for a state change: sets the status and fields, appends to the history."""
    now = time.time()
    return {"$set": {"status": status, "updated_at": now, **fields},
            "$push": {"history": {"status": status, "at": now}}}


def transition(col, attempt_id, from_states, to, **fields):
    """True if the attempt was in one of from_states and is now `to`."""
    return col.update_one({"attempt_id": attempt_id, "status": {"$in": from_states}},
                          move(to, **fields)).modified_count == 1


# --- numbers (CSV batch) ---

def parse_numbers(lines, country_code):
    """CSV rows (first column) -> (unique national numbers in file order, rejected rows).
    Rows without any digit (a header, blank lines) are skipped. A '+' number must carry the batch's
    calling code, which is stripped."""
    good, rejected, seen = [], [], set()
    for row in csv.reader(lines):
        raw = row[0].strip() if row else ""
        digits = re.sub(r"\D", "", raw)
        if not digits:
            continue
        if raw.startswith("+"):
            if not digits.startswith(country_code):
                rejected.append((raw, f"not a +{country_code} number"))
                continue
            digits = digits[len(country_code):]
        if not 6 <= len(digits) <= 14:
            rejected.append((raw, "invalid length"))
        elif digits in seen:
            rejected.append((raw, "duplicate"))
        else:
            seen.add(digits)
            good.append(digits)
    return good, rejected


def load_numbers(kind, target, phones, country_code):
    """Inserts the batch as AVAILABLE rows; returns its batch_id."""
    batch_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    now = time.time()
    numbers(kind, target).insert_many([
        {"batch_id": batch_id, "row_number": i, "phone": p, "country_code": country_code,
         "status": AVAILABLE, "claimed_by": None, "claimed_at": None, "lease_until": None,
         "attempt_id": None, "created_at": now} for i, p in enumerate(phones, 1)])
    return batch_id


def claim(kind, target, batch_id, slot, attempt_id):
    """Atomically hands the next number to one worker (Mongo's equivalent of
    SELECT ... FOR UPDATE SKIP LOCKED). A number whose lease expired - its worker died - is claimable
    again, and its old attempt is marked ABANDONED so a late SMPP event can't land on it.
    Returns the number document with the new attempt_id, or None when the batch is done."""
    from pymongo import ReturnDocument
    now = time.time()
    before = numbers(kind, target).find_one_and_update(
        {"batch_id": batch_id,
         "$or": [{"status": AVAILABLE},
                 {"status": {"$in": [CLAIMED, IN_PROGRESS]}, "lease_until": {"$lt": now}}]},
        {"$set": {"status": CLAIMED, "claimed_by": slot, "claimed_at": now,
                  "lease_until": now + CLAIM_LEASE, "attempt_id": attempt_id}},
        sort=[("row_number", 1)], return_document=ReturnDocument.BEFORE)
    if before is None:
        return None
    col = attempts(kind, target)
    if before["attempt_id"]:
        transition(col, before["attempt_id"], OPEN, ABANDONED)
    start_attempt(col, attempt_id, before["phone"], before["country_code"], batch_id)
    return {**before, "status": CLAIMED, "attempt_id": attempt_id}


def renew_lease(kind, target, batch_id, phone, attempt_id):
    """Called while the worker's test runs; the first call moves the number to IN_PROGRESS."""
    numbers(kind, target).update_one(
        {"batch_id": batch_id, "phone": phone, "attempt_id": attempt_id,
         "status": {"$in": [CLAIMED, IN_PROGRESS]}},
        {"$set": {"status": IN_PROGRESS, "lease_until": time.time() + CLAIM_LEASE}})


def complete_number(kind, target, batch_id, phone, attempt_id):
    numbers(kind, target).update_one(
        {"batch_id": batch_id, "phone": phone, "attempt_id": attempt_id},
        {"$set": {"status": COMPLETE, "lease_until": None}})


# --- attempts ---

def start_attempt(col, attempt_id, phone, country_code, batch_id=None):
    now = time.time()
    col.insert_one({
        "attempt_id": attempt_id, "batch_id": batch_id, "phone": phone, "country_code": country_code,
        "status": CLAIMED, "smpp_message_id": None, "smpp_status": None, "otp_decision": None,
        "otp": None, "event_ids": [], "result": None, "created_at": now, "updated_at": now,
        "history": [{"status": CLAIMED, "at": now}]})


def _split_phone(target):
    """For a single run: -> (country_code, national_number). '+' numbers are split by the longest
    known calling code; otherwise the code comes from --phone-country, else India."""
    raw = (PHONE or os.getenv(f"{target.upper()}_PHONE", "")).strip()
    digits = "".join(c for c in raw if c.isdigit())
    if raw.startswith("+"):
        for n in (4, 3, 2, 1):
            if digits[:n] in _CODES.values():
                return digits[:n], digits[n:]
        return "", digits
    return (calling_code(PHONE_COUNTRY) if PHONE_COUNTRY else "91"), digits[-10:]


def attempt_for_run(kind, target):
    """This test run's attempt: the one the orchestrator claimed (ATTEMPT_ID), or a new one for a
    single run. None when MongoDB is down: the test still runs, unrecorded."""
    try:
        col = attempts(kind, target)
        attempt_id = os.getenv("ATTEMPT_ID")
        if attempt_id:
            return Attempt(col, attempt_id, col.find_one({"attempt_id": attempt_id})["phone"])
        code, phone = _split_phone(target)
        attempt_id = str(uuid.uuid4())
        start_attempt(col, attempt_id, phone, code)
        return Attempt(col, attempt_id, phone)
    except Exception as e:  # a down database must never fail the test itself
        print(f"[results] MongoDB unavailable, run not recorded: {type(e).__name__}: {e}", flush=True)
        return None


def finish_attempt(attempt, passed):
    if attempt is None:
        return
    try:
        attempt.col.update_one({"attempt_id": attempt.attempt_id},
                               {"$set": {"result": "PASS" if passed else "FAIL", "updated_at": time.time()}})
        transition(attempt.col, attempt.attempt_id, [REDIS_PUBLISHED, OTP_REJECTED, OTP_ACCEPTED],
                   APPIUM_PROCESSED)
    except Exception as e:
        print(f"[results] could not update result: {type(e).__name__}: {e}", flush=True)


def fail_unfinished(kind, target, attempt_id):
    """After a killed or crashed run: FAIL if the test never wrote a result, and close the attempt
    so a late SMPP event can't land on it."""
    col = attempts(kind, target)
    col.update_one({"attempt_id": attempt_id, "result": None}, {"$set": {"result": "FAIL"}})
    transition(col, attempt_id, OPEN, ABANDONED)

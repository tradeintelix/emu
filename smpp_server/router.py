"""Links the SMPP server to the automation.

When the provider relays an OTP to us (submit_sm), route() checks whether its destination number is
one we're currently running. If so ("ours"), it records the message, extracts the OTP and publishes
it to the waiting worker over Redis; the server then sends a Delivered receipt back to the provider.
A message with no running automation ("not ours") returns None and is only logged.

route() runs off the event loop (asyncio.to_thread) because pymongo and redis are blocking."""
import json
import re
import time
from datetime import datetime, timezone

from core import results as R

# OTPs vary in length (4-8) and wording. Prefer the digits right after a keyword, e.g.
# "...verification code:73255" or "Your OTP is 123456"; fall back to the longest standalone run.
_KEYWORD_OTP = re.compile(r"(?:otp|code|pin|password|verif\w*)\D{0,20}?(\d{4,8})", re.I)
_ANY_OTP = re.compile(r"(?<!\d)\d{4,8}(?!\d)")


def extract_otp(text):
    if not text:
        return None
    m = _KEYWORD_OTP.search(text)
    if m:
        return m.group(1)
    runs = _ANY_OTP.findall(text)
    return max(runs, key=len) if runs else None  # longest wins; ties keep the first (max is stable)


def route(redis, destination_addr, text, message_id):
    """Returns the matched attempt (so the server knows to send a Delivered receipt), or None.

    'Delivered' is tied to the message being ours, not to the OTP being entered successfully, so the
    server sends it whenever this returns non-None. The OTP is published for the worker to type; if it
    can't be parsed we still own the message (worker just times out on entry)."""
    found = R.match_number(destination_addr)
    if not found:
        return None
    col, doc = found
    otp = extract_otp(text)
    now = time.time()
    col.update_one({"_id": doc["_id"]}, {
        "$set": {"smpp_message_id": message_id, "smpp_status": "DELIVERED", "otp_decision": "ACCEPTED",
                 "otp": otp, "status": R.REDIS_PUBLISHED, "updated_at": now},
        "$push": {"history": {"status": R.OTP_ACCEPTED, "at": now}}})
    if otp:
        event = {"eventId": "smpp:" + message_id, "attemptId": doc["attempt_id"], "phone": doc["phone"],
                 "status": "ACCEPTED", "otp": otp,
                 "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds")}
        try:
            redis.publish(R.OTP_CHANNEL, json.dumps(event))
        except Exception as e:  # the decision is in MongoDB; the worker reads it there on timeout
            print(f"[smpp-server] Redis publish failed: {type(e).__name__}: {e}", flush=True)
    else:
        print(f"[smpp-server] no OTP found in {text!r} for {destination_addr}", flush=True)
    return {**doc, "otp": otp}

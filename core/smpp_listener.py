"""SMPP service: `python -m core.smpp_listener` (one process, runs continuously).

We are the SMPP client (ESME): it binds out to the provider's SMSC and, for every delivery receipt
or inbound SMS, finds the attempt it belongs to, records the decision and publishes it to Redis
(docs/automation-plan.md, section 6.3):
  DELIVERED              -> otp_decision REJECTED, OTP closed  -> Redis {status: REJECTED, otp: null}
  UNDELIVERED / REJECTED -> otp_decision ACCEPTED, OTP stored  -> Redis {status: ACCEPTED, otp}
The OTP comes from the receipt's `text:` field when it carries one, else from the inbound SMS for the
number; the decision is published once both the status and the OTP are known, whichever comes first.
Lookup is by SMPP message_id, falling back to the newest open attempt for the number."""
import hashlib
import json
import re
import ssl
import sys
import time
from datetime import datetime, timezone

from config.settings import REDIS_URL, SMPP_BIND, SMPP_TLS, require
from core import results as R

CHANNEL = "otp-events"
DLR_FLAG = 0x04  # esm_class bit marking a delivery receipt
SMPP_STATUS = {"DELIVRD": "DELIVERED", "UNDELIV": "UNDELIVERED", "REJECTD": "REJECTED"}


def parse_dlr(text):
    """'id:123 ... stat:DELIVRD err:000 text:Your code 4821' -> ('123', 'DELIVRD', 'Your code 4821').
    (None, None, '') if it is not a receipt."""
    state, msg_id = re.search(r"stat:(\w+)", text), re.search(r"id:(\S+)", text)
    body = re.search(r"text:(.*)$", text, re.S)
    return ((msg_id.group(1) if msg_id else None), (state.group(1) if state else None),
            (body.group(1) if body else ""))


def extract_otp(text):
    """First standalone 4-8 digit code in an SMS body, else None."""
    m = re.search(r"(?<!\d)\d{4,8}(?!\d)", text or "")
    return m.group(0) if m else None


def find_attempt(number, message_id=None):
    """-> (collection, attempt doc) or None. By message_id first; else the newest attempt still open
    for the number, matched on trailing digits since attempts store the national number and the
    SMSC sends it with its country code."""
    cols = list(R.attempt_collections())
    if message_id:
        for col in cols:
            doc = col.find_one({"smpp_message_id": message_id})
            if doc:
                return col, doc
    digits = "".join(c for c in number if c.isdigit())
    tails = list({digits[-n:] for n in range(6, 15) if len(digits) >= n})
    best = None
    for col in cols:
        doc = col.find_one({"phone": {"$in": tails}, "status": {"$in": R.OPEN}}, sort=[("created_at", -1)])
        if doc and (best is None or doc["created_at"] > best[1]["created_at"]):
            best = (col, doc)
    return best


def _apply(col, doc, event_id, states, fields, from_states=R.OPEN):
    """One conditional update: only while the attempt is in from_states and this event was never
    applied (duplicate SMPP callbacks are ignored). `states` are appended to the history; the last
    one becomes the status. Returns the updated document, or None if nothing changed."""
    from pymongo import ReturnDocument
    now = time.time()
    update = {"$set": {"updated_at": now, **fields}, "$addToSet": {"event_ids": event_id}}
    if states:
        update["$set"]["status"] = states[-1]
        update["$push"] = {"history": {"$each": [{"status": s, "at": now} for s in states]}}
    return col.find_one_and_update(
        {"_id": doc["_id"], "status": {"$in": from_states}, "event_ids": {"$ne": event_id}},
        update, return_document=ReturnDocument.AFTER)


def publish(redis, col, doc, event_id):
    """Fans the decision out to every worker, then marks the attempt REDIS_PUBLISHED. If Redis is
    down the decision is still in the DB, which the worker re-reads before timing out."""
    event = {"eventId": event_id, "attemptId": doc["attempt_id"], "phone": doc["phone"],
             "status": doc["otp_decision"], "otp": doc["otp"],
             "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds")}
    try:
        redis.publish(CHANNEL, json.dumps(event))
    except Exception as e:
        print(f"[smpp] Redis publish failed ({type(e).__name__}: {e}); decision stays in MongoDB", flush=True)
        return
    R.transition(col, doc["attempt_id"], [R.OTP_REJECTED, R.OTP_ACCEPTED], R.REDIS_PUBLISHED)
    print(f"[smpp] published {event}", flush=True)


def handle_dlr(redis, number, message_id, stat, text):
    smpp_status = SMPP_STATUS.get(stat)
    if smpp_status is None:
        print(f"[smpp] {number}: receipt stat {stat} is not a final state we act on, ignored", flush=True)
        return
    found = find_attempt(number, message_id)
    if not found:
        print(f"[smpp] {number}: no open attempt for receipt {message_id}, ignored", flush=True)
        return
    col, doc = found
    event_id = f"dlr:{message_id}:{stat}"
    ids = {"smpp_message_id": message_id} if message_id else {}
    if smpp_status == "DELIVERED":  # reached a real handset: no OTP to enter, close it
        doc = _apply(col, doc, event_id, [R.SMPP_DELIVERED, R.OTP_REJECTED],
                     {"smpp_status": smpp_status, "otp_decision": "REJECTED", "otp": None, **ids})
    else:
        otp = extract_otp(text) or doc.get("otp")
        states = [R.SMPP_UNDELIVERED] + ([R.OTP_ACCEPTED] if otp else [])  # no OTP yet: wait for the SMS
        doc = _apply(col, doc, event_id, states,
                     {"smpp_status": smpp_status, "otp_decision": "ACCEPTED", "otp": otp, **ids})
    if doc and doc["status"] in (R.OTP_REJECTED, R.OTP_ACCEPTED):
        publish(redis, col, doc, event_id)


def handle_sms(redis, number, sender, text):
    otp = extract_otp(text)
    if otp is None:
        return
    found = find_attempt(number)
    if not found:
        print(f"[smpp] {number}: OTP SMS but no open attempt, ignored", flush=True)
        return
    col, doc = found
    event_id = "sms:" + hashlib.sha1(f"{sender}|{number}|{text}".encode()).hexdigest()[:16]
    if doc["status"] == R.SMPP_UNDELIVERED:  # receipt already said ACCEPTED, this was the missing OTP
        doc = _apply(col, doc, event_id, [R.OTP_ACCEPTED], {"otp": otp, "sms_from": sender},
                     from_states=[R.SMPP_UNDELIVERED])
        if doc:
            publish(redis, col, doc, event_id)
    else:  # SMS before its receipt: keep the OTP until the receipt decides
        _apply(col, doc, event_id, [], {"otp": otp, "sms_from": sender})


def handle_pdu(redis, pdu):
    """A receipt carries the phone number in source_addr (standard SMPP layout), an inbound SMS
    carries ours in destination_addr. Never raises: an exception would drop the bind."""
    try:
        text = pdu.short_message.decode("latin-1")
        if pdu.esm_class & DLR_FLAG:
            message_id, stat, body = parse_dlr(text)
            receipted = getattr(pdu, "receipted_message_id", None)
            if receipted:
                message_id = receipted.decode() if isinstance(receipted, bytes) else receipted
            handle_dlr(redis, pdu.source_addr.decode(), message_id, stat, body)
        else:
            handle_sms(redis, pdu.destination_addr.decode(), pdu.source_addr.decode(), text)
    except Exception as e:
        print(f"[smpp] could not handle PDU: {type(e).__name__}: {e}", flush=True)


def run():
    import smpplib.client
    from redis import Redis

    redis = Redis.from_url(REDIS_URL)
    host, port = require("SMPP_HOST"), int(require("SMPP_PORT"))
    delay = 1
    while True:  # reconnect forever; the bind drops whenever the network or provider hiccups
        try:
            smpp = smpplib.client.Client(host, port, ssl_context=ssl.create_default_context() if SMPP_TLS else None)
            smpp.set_message_received_handler(lambda pdu: handle_pdu(redis, pdu))
            smpp.connect()
            getattr(smpp, f"bind_{SMPP_BIND}")(system_id=require("SMPP_SYSTEM_ID"),
                                               password=require("SMPP_PASSWORD"))
            print(f"[smpp] bound to {host}:{port} as {SMPP_BIND}", flush=True)
            delay = 1
            smpp.listen()  # sends enquire_link and deliver_sm_resp itself
        except Exception as e:
            print(f"[smpp] connection lost ({type(e).__name__}: {e}), retry in {delay}s", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 60)


if __name__ == "__main__":
    sys.exit(run())

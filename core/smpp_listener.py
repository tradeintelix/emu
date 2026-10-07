"""Standalone SMPP listener: `python -m core.smpp_listener`.

Binds to the provider's SMSC and writes what arrives onto the run documents core/results.py
created (newest status "Running" document for the number, in any collection of Apps / Web):
  - delivery receipt (DLR) -> `smpp_state` = DELIVRD / UNDELIV / REJECTD ...
  - inbound SMS on our number -> `otp` = the code in the text
The automation reads both through core/otp.py. Pass/Fail in `status` is left to the test."""
import re
import ssl
import sys
import time

from config.settings import MONGO_URI, SMPP_BIND, SMPP_TLS, require

DLR_FLAG = 0x04  # esm_class bit marking a delivery receipt


def parse_dlr(text):
    """'id:123 ... stat:DELIVRD err:000 ...' -> ('123', 'DELIVRD'); (None, None) if not a receipt."""
    state, msg_id = re.search(r"stat:(\w+)", text), re.search(r"id:(\S+)", text)
    return (msg_id.group(1), state.group(1)) if state else (None, None)


def extract_otp(text):
    """First standalone 4-8 digit code in an SMS body, else None."""
    m = re.search(r"(?<!\d)\d{4,8}(?!\d)", text)
    return m.group(0) if m else None


def _newest_running(client, number):
    """Newest run still marked Running for this number, across every collection. Matches on the
    trailing digits because documents store the national number and the SMSC sends it with its code."""
    digits = "".join(c for c in number if c.isdigit())
    tails = list({digits[-n:] for n in range(7, 13)})
    best = None
    for db in ("Apps", "Web"):
        for name in client[db].list_collection_names():
            doc = client[db][name].find_one({"number": {"$in": tails}, "status": "Running"},
                                            sort=[("created_at", -1)])
            if doc and (best is None or doc["created_at"] > best[1]["created_at"]):
                best = (client[db][name], doc)
    return best


def handle_pdu(client, pdu):
    """Routes one deliver_sm: a receipt carries the phone number in source_addr, an inbound
    SMS carries ours in destination_addr."""
    text = pdu.short_message.decode("latin-1")
    if pdu.esm_class & DLR_FLAG:
        _, state = parse_dlr(text)
        number, update = pdu.source_addr.decode(), {"smpp_state": state}
    else:
        otp = extract_otp(text)
        number, update = pdu.destination_addr.decode(), {"otp": otp, "sms_from": pdu.source_addr.decode()}
        if otp is None:
            return
    found = _newest_running(client, number)
    if found:
        col, doc = found
        col.update_one({"_id": doc["_id"]}, {"$set": update})
        print(f"[smpp] {number}: {update}", flush=True)
    else:
        print(f"[smpp] {number}: no Running run, ignored", flush=True)


def run():
    import smpplib.client
    from pymongo import MongoClient

    mongo = MongoClient(MONGO_URI)
    host, port = require("SMPP_HOST"), int(require("SMPP_PORT"))
    delay = 1
    while True:  # reconnect forever; the bind drops whenever the network or provider hiccups
        try:
            smpp = smpplib.client.Client(host, port, ssl_context=ssl.create_default_context() if SMPP_TLS else None)
            smpp.set_message_received_handler(lambda pdu: handle_pdu(mongo, pdu))
            smpp.connect()
            getattr(smpp, f"bind_{SMPP_BIND}")(system_id=require("SMPP_SYSTEM_ID"),
                                               password=require("SMPP_PASSWORD"))
            print(f"[smpp] bound to {host}:{port}", flush=True)
            delay = 1
            smpp.listen()  # sends enquire_link and deliver_sm_resp itself
        except Exception as e:
            print(f"[smpp] connection lost ({type(e).__name__}: {e}), retry in {delay}s", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 60)


if __name__ == "__main__":
    sys.exit(run())

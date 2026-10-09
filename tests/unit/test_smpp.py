"""The OTP flow end to end without services: in-memory MongoDB (mongomock), fake Redis and PDUs."""
import io
import json
import time
from types import SimpleNamespace

import mongomock
import pytest

from core import otp as O
from core import results as R
from core import smpp_listener as L


@pytest.fixture(autouse=True)
def mongo(monkeypatch):
    monkeypatch.setattr(R, "_client", mongomock.MongoClient())


class FakeRedis:
    def __init__(self):
        self.events = []

    def publish(self, channel, data):
        self.events.append(json.loads(data))


def _attempt(phone="9876543210"):
    col = R.attempts("app", "spotify")
    attempt_id = f"att-{phone}-{time.time()}"
    R.start_attempt(col, attempt_id, phone, "91")
    return R.Attempt(col, attempt_id, phone)


def _doc(a):
    return a.col.find_one({"attempt_id": a.attempt_id})


def _pdu(esm, src, dst, text):
    return SimpleNamespace(esm_class=esm, source_addr=src.encode(), destination_addr=dst.encode(),
                           short_message=text.encode())


DLR = "id:{id} sub:001 dlvrd:000 submit date:2610071200 done date:2610071201 stat:{stat} err:005 text:{text}"


def test_parse_dlr_and_otp():
    assert L.parse_dlr(DLR.format(id="m1", stat="UNDELIV", text="Code 482913")) == ("m1", "UNDELIV", "Code 482913")
    assert L.parse_dlr("hello") == (None, None, "")
    assert L.extract_otp("Your Spotify code is 482913.") == "482913"
    assert L.extract_otp("call 1234567890123") is None


def test_parse_numbers_validates_and_dedupes():
    csv = io.StringIO("phone\n9876543210\n+919876543211\n9876543210\n+92333\n12\n\n")
    good, rejected = R.parse_numbers(csv, "91")
    assert good == ["9876543210", "9876543211"]
    assert [why for _, why in rejected] == ["duplicate", "not a +91 number", "invalid length"]


def test_claim_hands_each_number_out_once_and_recovers_expired_leases():
    batch = R.load_numbers("app", "spotify", ["111111", "222222"], "91")
    a = R.claim("app", "spotify", batch, "slot0", "A1")
    b = R.claim("app", "spotify", batch, "slot1", "A2")
    assert (a["phone"], b["phone"]) == ("111111", "222222")
    assert R.claim("app", "spotify", batch, "slot2", "A3") is None
    # slot0 dies: its lease runs out and the number is claimable again, old attempt abandoned
    R.numbers("app", "spotify").update_one({"attempt_id": "A1"}, {"$set": {"lease_until": 0}})
    c = R.claim("app", "spotify", batch, "slot2", "A4")
    assert c["phone"] == "111111"
    assert R.attempts("app", "spotify").find_one({"attempt_id": "A1"})["status"] == R.ABANDONED


def test_delivered_rejects_and_publishes():
    a, redis = _attempt(), FakeRedis()
    L.handle_pdu(redis, _pdu(0x04, "919876543210", "OURS", DLR.format(id="m1", stat="DELIVRD", text="")))
    doc = _doc(a)
    assert (doc["smpp_status"], doc["otp_decision"], doc["otp"], doc["status"]) == \
        ("DELIVERED", "REJECTED", None, R.REDIS_PUBLISHED)
    assert doc["smpp_message_id"] == "m1"
    [event] = redis.events
    assert (event["attemptId"], event["status"], event["otp"]) == (a.attempt_id, "REJECTED", None)


def test_undelivered_waits_for_the_sms_then_accepts():
    a, redis = _attempt(), FakeRedis()
    L.handle_pdu(redis, _pdu(0x04, "919876543210", "OURS", DLR.format(id="m2", stat="UNDELIV", text="")))
    assert _doc(a)["status"] == R.SMPP_UNDELIVERED and redis.events == []
    L.handle_pdu(redis, _pdu(0x00, "SPOTIFY", "919876543210", "Your code is 112233"))
    assert _doc(a)["status"] == R.REDIS_PUBLISHED
    assert [(e["status"], e["otp"]) for e in redis.events] == [("ACCEPTED", "112233")]


def test_sms_before_receipt_and_duplicate_receipt():
    a, redis = _attempt(), FakeRedis()
    L.handle_pdu(redis, _pdu(0x00, "SPOTIFY", "919876543210", "Your code is 445566"))
    dlr = _pdu(0x04, "919876543210", "OURS", DLR.format(id="m3", stat="REJECTD", text=""))
    L.handle_pdu(redis, dlr)
    L.handle_pdu(redis, dlr)  # duplicate callback
    assert [(e["status"], e["otp"]) for e in redis.events] == [("ACCEPTED", "445566")]
    assert _doc(a)["smpp_status"] == "REJECTED"


def test_receipt_by_message_id_beats_phone_match():
    old, new = _attempt(), _attempt()
    old.col.update_one({"attempt_id": old.attempt_id}, {"$set": {"smpp_message_id": "m9"}})
    L.handle_pdu(FakeRedis(), _pdu(0x04, "919876543210", "OURS", DLR.format(id="m9", stat="DELIVRD", text="")))
    assert _doc(old)["otp_decision"] == "REJECTED" and _doc(new)["otp_decision"] is None


def test_waiter_ignores_other_attempts_and_falls_back_to_db():
    a = _attempt()
    w = O.Waiter.__new__(O.Waiter)
    w.attempt, w.pubsub = a, None
    assert w.decide({"attemptId": "someone-else", "phone": a.phone, "status": "REJECTED"}) is None
    assert w.decide({"attemptId": a.attempt_id, "phone": "000", "status": "REJECTED"}) is None
    assert w.decide({"attemptId": a.attempt_id, "phone": a.phone, "status": "ACCEPTED", "otp": None}) is None
    assert w.decide({"attemptId": a.attempt_id, "phone": a.phone, "status": "ACCEPTED", "otp": "1234"}) == \
        ("ACCEPTED", "1234")
    # no Redis: polls MongoDB; nothing decided -> OTP_TIMEOUT
    assert w.wait(timeout=0.1) == (None, None)
    assert _doc(a)["status"] == R.OTP_TIMEOUT
    b = _attempt("9876500000")
    b.col.update_one({"attempt_id": b.attempt_id}, {"$set": {"otp_decision": "REJECTED"}})
    w.attempt = b
    assert w.wait(timeout=1) == ("REJECTED", None)


def test_finish_marks_processed_and_result():
    a = _attempt()
    R.transition(a.col, a.attempt_id, R.OPEN, R.REDIS_PUBLISHED)
    R.finish_attempt(a, passed=True)
    assert (_doc(a)["status"], _doc(a)["result"]) == (R.APPIUM_PROCESSED, "PASS")


def test_batch_runs_every_number_once_and_counts_failures(monkeypatch, tmp_path):
    """Orchestrator with 2 workers and a stub test process instead of pytest + emulator."""
    import subprocess
    import sys

    from core import orchestrator

    R._client.admin.command = lambda *a: None
    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrator, "kill_emulator", lambda serial: None)
    monkeypatch.setattr(orchestrator.time, "sleep", lambda s: None)
    real_popen = subprocess.Popen
    ran = []

    def fake_test_run(cmd, **kw):  # numbers ending in an odd digit fail before any OTP step
        env = kw["env"]
        ran.append(env["PHONE"])
        ok = int(env["PHONE"][-1]) % 2 == 0
        if ok:
            R.finish_attempt(R.Attempt(R.attempts("app", "spotify"), env["ATTEMPT_ID"], env["PHONE"]), True)
        return real_popen([sys.executable, "-c", f"raise SystemExit({0 if ok else 1})"], stdout=kw["stdout"])

    monkeypatch.setattr(orchestrator.subprocess, "Popen", fake_test_run)
    csv = tmp_path / "n.csv"
    csv.write_text("phone\n9876543210\n9876543211\n9876543212\n9876543212\n")
    assert orchestrator.run_batch("spotify", csv, "India", 2) == 1  # one failure -> non-zero
    assert sorted(ran) == ["9876543210", "9876543211", "9876543212"]
    results = sorted(d["result"] for d in R.attempts("app", "spotify").find())
    assert results == ["FAIL", "PASS", "PASS"]
    assert {d["status"] for d in R.numbers("app", "spotify").find()} == {R.COMPLETE}

from types import SimpleNamespace

from core import smpp_listener as L
from core.otp import wait_for_otp


def test_parse_dlr():
    text = "id:123 sub:001 dlvrd:001 submit date:2610071200 done date:2610071201 stat:UNDELIV err:005 text:Your"
    assert L.parse_dlr(text) == ("123", "UNDELIV")
    assert L.parse_dlr("hello") == (None, None)


def test_extract_otp():
    assert L.extract_otp("Your Spotify code is 482913. Don't share it.") == "482913"
    assert L.extract_otp("call 1234567890123") is None
    assert L.extract_otp("no code here") is None


class FakeCol:
    def __init__(self, doc):
        self.doc, self.updates = doc, []

    def find_one(self, *_):
        return self.doc

    def update_one(self, flt, upd):
        self.updates.append(upd["$set"])


def _pdu(esm, src, dst, text):
    return SimpleNamespace(esm_class=esm, source_addr=src.encode(), destination_addr=dst.encode(),
                           short_message=text.encode())


def test_handle_pdu_routes_receipt_and_sms(monkeypatch):
    col = FakeCol({"_id": 1})
    monkeypatch.setattr(L, "_newest_running", lambda c, n: (col, {"_id": 1}))
    L.handle_pdu(None, _pdu(0x04, "919876543210", "OURS", "id:1 stat:DELIVRD err:000"))
    L.handle_pdu(None, _pdu(0x00, "SPOTIFY", "919876543210", "Code 112233"))
    assert col.updates == [{"smpp_state": "DELIVRD"}, {"otp": "112233", "sms_from": "SPOTIFY"}]


def test_wait_for_otp():
    assert wait_for_otp(None, 1) is None
    assert wait_for_otp(FakeCol({"otp": "5555"}), 1, timeout=1) == "5555"
    assert wait_for_otp(FakeCol({"otp": "5555", "smpp_state": "DELIVRD"}), 1, timeout=1) is None
    assert wait_for_otp(FakeCol({}), 1, timeout=0.1, poll=0.05) is None

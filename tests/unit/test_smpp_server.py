"""Our SMPP server against a real SMPP client (smpplib), over a local socket."""
import asyncio
import socket
import threading
import time

import mongomock
import pytest
import smpplib.client
import smpplib.consts
import smpplib.exceptions
import smpplib.smpp

from core import results as R
from smpp_server import pdu as P
from smpp_server import router
from smpp_server import server as S


class FakeRedis:
    def __init__(self):
        self.events = []

    def publish(self, channel, data):
        import json
        self.events.append(json.loads(data))


@pytest.fixture
def smsc(monkeypatch):
    monkeypatch.setattr(S, "SMPP_SERVER_SYSTEM_ID", "emutest")
    monkeypatch.setattr(S, "SMPP_SERVER_PASSWORD", "pw123456")
    monkeypatch.setattr(S, "BIND_FAIL_DELAY", 0)
    monkeypatch.setattr(R, "_client", mongomock.MongoClient())
    stored, redis = [], FakeRedis()
    monkeypatch.setattr(S, "_store", stored.append)
    loop = asyncio.new_event_loop()
    srv = loop.run_until_complete(
        asyncio.start_server(lambda r, w: S.on_connect(r, w, redis), "127.0.0.1", 0))
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    yield srv.sockets[0].getsockname()[1], stored, redis

    async def shutdown():  # on the server's own loop: asyncio objects aren't thread-safe
        srv.close()
        await srv.wait_closed()

    asyncio.run_coroutine_threadsafe(shutdown(), loop).result(5)
    loop.call_soon_threadsafe(loop.stop)
    thread.join(2)
    loop.close()


def _client(port):
    c = smpplib.client.Client("127.0.0.1", port, timeout=5)
    c.connect()
    return c


def test_bind_submit_enquire_unbind(smsc):
    port, stored, _ = smsc
    c = _client(port)
    c.bind_transceiver(system_id="emutest", password="pw123456")
    ids = []
    c.set_message_sent_handler(lambda pdu: ids.append(pdu.message_id))
    c.send_message(source_addr="Spotify", destination_addr="919876543210", short_message=b"Your code is 482913")
    c.read_once()  # submit_sm_resp
    c.send_pdu(smpplib.smpp.make_pdu("enquire_link", client=c))
    c.read_once()  # enquire_link_resp
    c.unbind()
    c.disconnect()
    deadline = time.monotonic() + 2  # the server logs right after replying
    while "unbind_resp" not in [r["command"] for r in stored] and time.monotonic() < deadline:
        time.sleep(0.01)

    assert len(ids) == 1 and len(ids[0]) == 16
    submit = next(r for r in stored if r["command"] == "submit_sm")
    assert submit["fields"]["destination_addr"] == "919876543210"
    assert submit["fields"]["text"] == "Your code is 482913"
    commands = [r["command"] for r in stored]
    assert {"bind_transceiver_resp", "enquire_link_resp", "unbind_resp"} <= set(commands)
    bind = next(r for r in stored if r["command"] == "bind_transceiver")
    assert bind["fields"]["password"] == "***"  # never stored


@pytest.mark.parametrize("system_id, password, status", [
    ("emutest", "wrong", smpplib.consts.SMPP_ESME_RINVPASWD),
    ("intruder", "pw123456", smpplib.consts.SMPP_ESME_RINVSYSID),
])
def test_bad_credentials_are_refused(smsc, system_id, password, status):
    c = _client(smsc[0])
    with pytest.raises(smpplib.exceptions.PDUError) as e:
        c.bind_transceiver(system_id=system_id, password=password)
    c.disconnect()
    assert e.value.args[1] == status


def _raw(sock, command_id, sequence, body):
    """Sends a PDU without any client-side state checks; returns (command_id, status) of the reply."""
    sock.sendall(P.encode(command_id, 0, sequence, body))
    length, cid, status, _ = P.HEADER.unpack(sock.recv(16))
    sock.recv(length - 16)
    return cid, status


def test_receiver_bind_cannot_submit(smsc):
    sock = socket.create_connection(("127.0.0.1", smsc[0]), timeout=5)
    bind = P.cstr("emutest") + P.cstr("pw123456") + P.cstr("") + bytes([0x34, 0, 0]) + P.cstr("")
    assert _raw(sock, P.BIND_RECEIVER, 1, bind) == (P.BIND_RECEIVER | P.RESP, P.ESME_ROK)
    submit = (P.cstr("") + bytes([0, 0]) + P.cstr("x") + bytes([1, 1]) + P.cstr("919876543210")
              + bytes([0, 0, 0]) + P.cstr("") + P.cstr("") + bytes([0, 0, 0, 0, 4]) + b"1234")
    assert _raw(sock, P.SUBMIT_SM, 2, submit) == (P.SUBMIT_SM | P.RESP, P.ESME_RINVBNDSTS)
    assert _raw(sock, 0x103, 3, b"") == (P.GENERIC_NACK, P.ESME_RINVCMDID)  # data_sm: not supported
    sock.close()


@pytest.mark.parametrize("text, expected", [
    ("Your TikTok account verification code:73255", "73255"),   # 5 digits, after keyword
    ("Your code is 482913", "482913"),                          # 6, after keyword
    ("123456 is your Spotify code", "123456"),                  # 6, before the keyword -> longest run
    ("Your OTP is 12345678, valid for 10 minutes", "12345678"), # 8; the "10" is ignored
    ("PIN 4821", "4821"),                                       # 4
    ("No digits here", None),
])
def test_extract_otp(text, expected):
    assert router.extract_otp(text) == expected


def _seed_attempt(phone="3294314088", country="92"):
    col = R.attempts("app", "spotify")
    attempt_id = "att-" + phone
    R.start_attempt(col, attempt_id, phone, country)
    R.transition(col, attempt_id, [R.CLAIMED], R.WAITING_SMPP)
    return col, attempt_id


def test_matched_message_sends_delivered_receipt_and_publishes_otp(smsc):
    port, stored, redis = smsc
    col, attempt_id = _seed_attempt()
    c = _client(port)
    c.bind_transceiver(system_id="emutest", password="pw123456")
    receipts = []
    c.set_message_received_handler(
        lambda pdu: receipts.append((pdu.esm_class, pdu.short_message.decode("latin-1"))))
    # provider sends the number with its country code; the attempt stored only the national part
    c.send_message(source_addr="Spotify", destination_addr="923294314088",
                   short_message=b"Your code is 731902")
    c.read_once()  # submit_sm_resp
    c.read_once()  # the Delivered receipt (deliver_sm) the server pushes back
    c.unbind(); c.disconnect()

    assert len(receipts) == 1
    esm_class, text = receipts[0]
    assert esm_class & P.DLR_RECEIPT and "stat:DELIVRD" in text

    doc = col.find_one({"attempt_id": attempt_id})
    assert (doc["otp"], doc["otp_decision"], doc["smpp_status"], doc["status"]) == \
        ("731902", "ACCEPTED", "DELIVERED", R.REDIS_PUBLISHED)
    assert doc["smpp_message_id"] and f"id:{doc['smpp_message_id']}" in text
    assert [(e["attemptId"], e["status"], e["otp"]) for e in redis.events] == \
        [(attempt_id, "ACCEPTED", "731902")]


def test_unmatched_message_is_logged_only(smsc):
    port, stored, redis = smsc
    c = _client(port)
    c.bind_transceiver(system_id="emutest", password="pw123456")
    receipts = []
    c.set_message_received_handler(lambda pdu: receipts.append(pdu))
    c.send_message(source_addr="Spotify", destination_addr="910000000000",
                   short_message=b"Your code is 111111")
    c.read_once()  # submit_sm_resp
    time.sleep(0.3)  # no attempt matches -> no receipt should arrive
    c.unbind(); c.disconnect()
    assert receipts == [] and redis.events == []

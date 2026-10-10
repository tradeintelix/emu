"""SMPP server: we are the SMSC side, the provider binds to us as the client (ESME).

    python -m smpp_server.server        (on the server: systemd service `emu-smpp`)

Accepts binds with our credentials (SMPP_SERVER_SYSTEM_ID / SMPP_SERVER_PASSWORD), answers
enquire_link and unbind, accepts submit_sm with our own message_id, and logs every PDU to the
journal and to MongoDB (SMPP.pdus), so the provider's real traffic is on record. The OTP decisions
for the automation are wired in later (docs/automation-plan.md)."""
import asyncio
import hmac
import time
import uuid

from config.settings import (REDIS_URL, SMPP_ALLOWED_IPS, SMPP_SERVER_HOST, SMPP_SERVER_PASSWORD,
                             SMPP_SERVER_PORT, SMPP_SERVER_SYSTEM_ID)
from smpp_server import pdu as P
from smpp_server import router

BIND_TYPES = {P.BIND_RECEIVER: "receiver", P.BIND_TRANSMITTER: "transmitter", P.BIND_TRANSCEIVER: "transceiver"}
CAN_SUBMIT = ("transmitter", "transceiver")
MAX_PDU = 64 * 1024
IDLE_TIMEOUT = 300  # no PDU at all (clients send enquire_link every 30-60s) -> dead connection, drop it
BIND_FAIL_DELAY = 3  # slows down password guessing; the connection is closed after a failed bind


def _store(record):
    """Best effort: a down MongoDB must never break a live bind."""
    try:
        from core.results import client
        client()["SMPP"]["pdus"].insert_one(record)
    except Exception as e:
        print(f"[smpp-server] MongoDB log failed: {type(e).__name__}", flush=True)


class Session:
    def __init__(self, reader, writer, redis=None):
        self.reader, self.writer = reader, writer
        self.redis = redis
        self.peer = "%s:%s" % writer.get_extra_info("peername")[:2]
        self.bound = None  # bind type once bound
        self.system_id = None
        self.out_seq = 0  # our own sequence space for server-initiated PDUs (the delivery receipts)

    def next_seq(self):
        self.out_seq += 1
        return self.out_seq

    async def log(self, direction, command_id, status, sequence, fields=None):
        line = f"[smpp-server] {self.peer} {direction} {P.name(command_id)} seq={sequence} status={status:#x}"
        print(line + (f" {fields}" if fields else ""), flush=True)
        await asyncio.to_thread(_store, {
            "at": time.time(), "peer": self.peer, "system_id": self.system_id, "direction": direction,
            "command": P.name(command_id), "command_status": status, "sequence": sequence, "fields": fields})

    async def send(self, command_id, status, sequence, body=b"", fields=None):
        self.writer.write(P.encode(command_id, status, sequence, body))
        await self.writer.drain()
        await self.log("out", command_id, status, sequence, fields)

    async def run(self):
        while True:
            header = await asyncio.wait_for(self.reader.readexactly(P.HEADER.size), IDLE_TIMEOUT)
            length, command_id, status, sequence = P.HEADER.unpack(header)
            if not P.HEADER.size <= length <= MAX_PDU:
                await self.send(P.GENERIC_NACK, P.ESME_RINVCMDLEN, sequence)
                return
            body = await self.reader.readexactly(length - P.HEADER.size)
            if not await self.handle(command_id, status, sequence, body):
                return

    async def handle(self, command_id, status, sequence, body):
        """Returns False when the connection should close."""
        if command_id in BIND_TYPES:
            return await self.bind(command_id, sequence, body)
        if command_id == P.ENQUIRE_LINK:
            await self.log("in", command_id, status, sequence)
            await self.send(command_id | P.RESP, P.ESME_ROK, sequence)
            return True
        if command_id == P.UNBIND:
            await self.log("in", command_id, status, sequence)
            await self.send(command_id | P.RESP, P.ESME_ROK, sequence)
            return False
        if command_id == P.SUBMIT_SM:
            return await self.submit_sm(sequence, body)
        if command_id & P.RESP:  # responses to what we sent, e.g. deliver_sm_resp
            await self.log("in", command_id, status, sequence)
            return True
        await self.log("in", command_id, status, sequence, {"body_hex": body.hex()})
        await self.send(P.GENERIC_NACK, P.ESME_RINVCMDID, sequence)
        return True

    async def bind(self, command_id, sequence, body):
        f = P.decode_bind(body)
        await self.log("in", command_id, P.ESME_ROK, sequence, {**f, "password": "***"})
        if self.bound:
            await self.send(command_id | P.RESP, P.ESME_RALYBND, sequence)
            return True
        if not hmac.compare_digest(f["system_id"], SMPP_SERVER_SYSTEM_ID):
            error = P.ESME_RINVSYSID
        elif not hmac.compare_digest(f["password"], SMPP_SERVER_PASSWORD):
            error = P.ESME_RINVPASWD
        else:
            self.bound, self.system_id = BIND_TYPES[command_id], f["system_id"]
            await self.send(command_id | P.RESP, P.ESME_ROK, sequence, P.bind_resp_body(SMPP_SERVER_SYSTEM_ID),
                            {"bound_as": self.bound})
            return True
        await asyncio.sleep(BIND_FAIL_DELAY)
        await self.send(command_id | P.RESP, error, sequence, P.cstr(SMPP_SERVER_SYSTEM_ID))
        return False

    async def submit_sm(self, sequence, body):
        if self.bound not in CAN_SUBMIT:
            await self.log("in", P.SUBMIT_SM, P.ESME_ROK, sequence)
            await self.send(P.SUBMIT_SM | P.RESP, P.ESME_RINVBNDSTS, sequence)
            return True
        try:
            f = P.decode_submit_sm(body)
        except (ValueError, IndexError):
            await self.log("in", P.SUBMIT_SM, P.ESME_ROK, sequence, {"body_hex": body.hex()})
            await self.send(P.SUBMIT_SM | P.RESP, P.ESME_RINVMSGLEN, sequence)
            return True
        message_id = uuid.uuid4().hex[:16]
        await self.log("in", P.SUBMIT_SM, P.ESME_ROK, sequence, f)
        await self.send(P.SUBMIT_SM | P.RESP, P.ESME_ROK, sequence, P.cstr(message_id), {"message_id": message_id})
        await self.on_message(f, message_id)
        return True

    async def on_message(self, f, message_id):
        """If the message is for a running automation, hand the OTP to the worker (Redis) and send a
        Delivered receipt back. 'Delivered' means the message was ours; it does not depend on the OTP
        being entered successfully. Never raises - a DB or Redis fault must not drop the bind."""
        try:
            doc = await asyncio.to_thread(router.route, self.redis, f["destination_addr"], f["text"], message_id)
        except Exception as e:
            print(f"[smpp-server] routing failed for {message_id}: {type(e).__name__}: {e}", flush=True)
            return
        if doc is None:
            print(f"[smpp-server] {f['destination_addr']}: no running automation, logged only", flush=True)
            return
        # Delivered receipt: source/destination swap round from the original submit (SMPP 3.4).
        body = P.message_body(f["destination_addr"], f["source_addr"], P.receipt_text(message_id),
                              esm_class=P.DLR_RECEIPT)
        await self.send(P.DELIVER_SM, P.ESME_ROK, self.next_seq(), body,
                        {"receipt": "DELIVRD", "message_id": message_id, "otp": doc.get("otp")})


async def on_connect(reader, writer, redis=None):
    peer_ip = writer.get_extra_info("peername")[0]
    if SMPP_ALLOWED_IPS and peer_ip not in SMPP_ALLOWED_IPS:
        print(f"[smpp-server] refused {peer_ip}: not in SMPP_ALLOWED_IPS", flush=True)
        writer.close()
        return
    session = Session(reader, writer, redis)
    print(f"[smpp-server] {session.peer} connected", flush=True)
    try:
        await session.run()
    except (asyncio.IncompleteReadError, ConnectionError):
        pass  # client went away
    except asyncio.TimeoutError:
        print(f"[smpp-server] {session.peer} idle for {IDLE_TIMEOUT}s, dropped", flush=True)
    except Exception as e:
        print(f"[smpp-server] {session.peer} error: {type(e).__name__}: {e}", flush=True)
    finally:
        writer.close()
        print(f"[smpp-server] {session.peer} disconnected (was bound as {session.bound})", flush=True)


async def serve(host=SMPP_SERVER_HOST, port=SMPP_SERVER_PORT):
    if not (SMPP_SERVER_SYSTEM_ID and SMPP_SERVER_PASSWORD):
        raise SystemExit("Set SMPP_SERVER_SYSTEM_ID and SMPP_SERVER_PASSWORD in .env")
    redis = None
    try:
        from redis import Redis
        redis = Redis.from_url(REDIS_URL)
    except Exception as e:  # workers also fall back to reading MongoDB, so a missing Redis isn't fatal
        print(f"[smpp-server] Redis unavailable ({type(e).__name__}); decisions go to MongoDB only", flush=True)
    server = await asyncio.start_server(lambda r, w: on_connect(r, w, redis), host, port)
    print(f"[smpp-server] listening on {host}:{port} as {SMPP_SERVER_SYSTEM_ID}"
          + (f", allowed IPs {sorted(SMPP_ALLOWED_IPS)}" if SMPP_ALLOWED_IPS else ", any IP"), flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(serve())

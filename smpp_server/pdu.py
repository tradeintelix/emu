"""SMPP 3.4 PDU encoding and decoding for the server side (only what the server needs).

A PDU is a 16-byte header (command_length, command_id, command_status, sequence_number, all
big-endian uint32) followed by a body of mandatory fields (C-octet strings and single bytes) and
optional TLVs (tag uint16, length uint16, value)."""
import struct
import time

HEADER = struct.Struct(">IIII")

GENERIC_NACK = 0x80000000
BIND_RECEIVER, BIND_TRANSMITTER, BIND_TRANSCEIVER = 0x01, 0x02, 0x09
SUBMIT_SM, DELIVER_SM, UNBIND, ENQUIRE_LINK = 0x04, 0x05, 0x06, 0x15
DLR_RECEIPT = 0x04  # esm_class bit marking a deliver_sm as a delivery receipt
RESP = 0x80000000  # a response's command_id is the request's with this bit set

NAMES = {0x01: "bind_receiver", 0x02: "bind_transmitter", 0x03: "query_sm", 0x04: "submit_sm",
         0x05: "deliver_sm", 0x06: "unbind", 0x07: "replace_sm", 0x08: "cancel_sm",
         0x09: "bind_transceiver", 0x0B: "outbind", 0x15: "enquire_link", 0x21: "submit_multi",
         0x103: "data_sm"}

# command_status values
ESME_ROK, ESME_RINVMSGLEN, ESME_RINVCMDLEN, ESME_RINVCMDID = 0x00, 0x01, 0x02, 0x03
ESME_RINVBNDSTS, ESME_RALYBND, ESME_RSYSERR = 0x04, 0x05, 0x08
ESME_RINVPASWD, ESME_RINVSYSID = 0x0E, 0x0F

TLV_MESSAGE_PAYLOAD, TLV_SC_INTERFACE_VERSION = 0x0424, 0x0210


def name(command_id):
    if command_id == GENERIC_NACK:
        return "generic_nack"
    base = NAMES.get(command_id & ~RESP, hex(command_id))
    return base + "_resp" if command_id & RESP else base


def encode(command_id, status, sequence, body=b""):
    return HEADER.pack(HEADER.size + len(body), command_id, status, sequence) + body


def cstr(value):
    return value.encode("latin-1") + b"\0"


class Reader:
    """Walks a PDU body field by field."""

    def __init__(self, body):
        self.body, self.pos = body, 0

    def cstr(self):
        end = self.body.index(b"\0", self.pos)
        value = self.body[self.pos:end].decode("latin-1")
        self.pos = end + 1
        return value

    def byte(self):
        self.pos += 1
        return self.body[self.pos - 1]

    def raw(self, n):
        self.pos += n
        return self.body[self.pos - n:self.pos]

    def tlvs(self):
        out = {}
        while self.pos + 4 <= len(self.body):
            tag, length = struct.unpack_from(">HH", self.body, self.pos)
            self.pos += 4
            out[tag] = self.raw(length)
        return out


def decode_bind(body):
    r = Reader(body)
    return {"system_id": r.cstr(), "password": r.cstr(), "system_type": r.cstr(),
            "interface_version": r.byte(), "addr_ton": r.byte(), "addr_npi": r.byte(),
            "address_range": r.cstr()}


def decode_text(raw, data_coding):
    """8 = UCS2 (UTF-16BE); everything else read byte-wise, which keeps digits and ASCII intact."""
    if data_coding == 8:
        return raw.decode("utf-16-be", errors="replace")
    return raw.decode("latin-1")


def decode_submit_sm(body):
    """Also fits deliver_sm, which has the same body layout."""
    r = Reader(body)
    f = {"service_type": r.cstr(), "source_addr_ton": r.byte(), "source_addr_npi": r.byte(),
         "source_addr": r.cstr(), "dest_addr_ton": r.byte(), "dest_addr_npi": r.byte(),
         "destination_addr": r.cstr(), "esm_class": r.byte(), "protocol_id": r.byte(),
         "priority_flag": r.byte(), "schedule_delivery_time": r.cstr(), "validity_period": r.cstr(),
         "registered_delivery": r.byte(), "replace_if_present_flag": r.byte(), "data_coding": r.byte(),
         "sm_default_msg_id": r.byte()}
    message = r.raw(r.byte())
    tlvs = r.tlvs()
    if not message and TLV_MESSAGE_PAYLOAD in tlvs:  # long messages come in a TLV instead
        message = tlvs[TLV_MESSAGE_PAYLOAD]
    f["text"] = decode_text(message, f["data_coding"])
    f["tlv_tags"] = sorted(hex(t) for t in tlvs)
    return f


def bind_resp_body(system_id):
    """Our system_id plus sc_interface_version 3.4, which most clients expect."""
    return cstr(system_id) + struct.pack(">HHB", TLV_SC_INTERFACE_VERSION, 1, 0x34)


def message_body(source_addr, destination_addr, message, esm_class=0, data_coding=0,
                 registered_delivery=0, source_ton=0, source_npi=0, dest_ton=1, dest_npi=1):
    """submit_sm / deliver_sm body. Used to build the delivery receipt (deliver_sm) we send back."""
    msg = message if isinstance(message, (bytes, bytearray)) else message.encode("latin-1")
    msg = msg[:254]  # sm_length is one byte; longer text would need the message_payload TLV
    return (cstr("") + bytes([source_ton, source_npi]) + cstr(source_addr)
            + bytes([dest_ton, dest_npi]) + cstr(destination_addr)
            + bytes([esm_class, 0, 0]) + cstr("") + cstr("")
            + bytes([registered_delivery, 0, data_coding, 0, len(msg)]) + msg)


def receipt_text(message_id, stat="DELIVRD", err="000"):
    """The delivery-receipt short_message body (SMPP 3.4 appendix B)."""
    ts = time.strftime("%y%m%d%H%M")
    return (f"id:{message_id} sub:001 dlvrd:001 submit date:{ts} done date:{ts} "
            f"stat:{stat} err:{err} text:")

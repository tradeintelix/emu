"""What the automation calls after the OTP screen shows up."""
import time


def wait_for_otp(col, doc_id, timeout=120, poll=1.5):
    """Waits for the SMPP listener to fill this run's document. Returns the OTP to type, or None
    when the SMSC reports DELIVRD (the real handset got it: end the flow, move to the next
    number) or nothing arrived in time. ponytail: if the OTP SMS beats its DLR, a late DELIVRD
    is missed; add a short grace wait here if the provider orders them that way."""
    if col is None:  # MongoDB was down when the run started
        return None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        doc = col.find_one({"_id": doc_id}) or {}
        if doc.get("smpp_state") == "DELIVRD":
            return None
        if doc.get("otp"):
            return doc["otp"]
        time.sleep(poll)
    return None

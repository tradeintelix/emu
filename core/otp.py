"""Worker side of the OTP decision (docs/automation-plan.md, section 6.2).

The fixture creates a Waiter before the app is driven, so the Redis subscription exists before the
OTP is requested and a fast decision can't be published unseen. Every worker receives every event
(fan-out); the Waiter keeps only the ones for its own attempt_id and phone. MongoDB is the source of
truth: without Redis the Waiter polls the attempt document, and it re-reads it once more before
declaring OTP_TIMEOUT, since Pub/Sub drops messages a subscriber missed."""
import json
import time

from config.settings import OTP_WAIT_TIMEOUT, REDIS_URL
from core import results as R
from core.smpp_listener import CHANNEL


class Waiter:
    def __init__(self, attempt):
        self.attempt, self.pubsub = attempt, None
        if attempt is None:
            return
        try:
            from redis import Redis
            self.pubsub = Redis.from_url(REDIS_URL, socket_timeout=5).pubsub(ignore_subscribe_messages=True)
            self.pubsub.subscribe(CHANNEL)
        except Exception as e:
            print(f"[otp] Redis unavailable ({type(e).__name__}: {e}), polling MongoDB instead", flush=True)
            self.pubsub = None

    def otp_requested(self):
        """Call right after the app is told to send the OTP."""
        if self.attempt:
            R.transition(self.attempt.col, self.attempt.attempt_id, [R.CLAIMED], R.OTP_REQUESTED)

    def wait(self, timeout=OTP_WAIT_TIMEOUT):
        """-> ("ACCEPTED", otp): type it. ("REJECTED", None): delivered to a real handset, end the
        flow. (None, None): no decision in time (attempt marked OTP_TIMEOUT)."""
        if self.attempt is None:
            return None, None
        R.transition(self.attempt.col, self.attempt.attempt_id, [R.CLAIMED, R.OTP_REQUESTED], R.WAITING_SMPP)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.pubsub is None:
                decision = self._from_db()
                if decision:
                    return decision
                time.sleep(2)
                continue
            try:
                msg = self.pubsub.get_message(timeout=1)
            except Exception as e:  # connection dropped: anything published meanwhile is lost
                print(f"[otp] Redis dropped ({type(e).__name__}), polling MongoDB instead", flush=True)
                self.pubsub = None
                continue
            if msg:
                decision = self.decide(json.loads(msg["data"]))
                if decision:
                    return decision
        decision = self._from_db()
        if decision:
            return decision
        R.transition(self.attempt.col, self.attempt.attempt_id, R.OPEN, R.OTP_TIMEOUT)
        return None, None

    def decide(self, event):
        """The worker's correlation check on one Redis event; None means keep listening."""
        if event.get("attemptId") != self.attempt.attempt_id:
            return None  # not mine
        if event.get("phone") != self.attempt.phone:
            return None
        if event.get("status") == "ACCEPTED" and not event.get("otp"):
            print(f"[otp] ACCEPTED without an OTP: invalid event, ignored: {event}", flush=True)
        return self._decision(event.get("status"), event.get("otp"))

    def _from_db(self):
        doc = self.attempt.col.find_one({"attempt_id": self.attempt.attempt_id}) or {}
        return self._decision(doc.get("otp_decision"), doc.get("otp"))

    @staticmethod
    def _decision(status, otp):
        if status == "REJECTED":
            return "REJECTED", None
        if status == "ACCEPTED" and otp:  # ACCEPTED without OTP: receipt came, OTP text not yet
            return "ACCEPTED", otp
        return None

    def close(self):
        if self.pubsub is not None:
            try:
                self.pubsub.close()
            except Exception:
                pass

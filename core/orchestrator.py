"""Runs one app flow for every number of a CSV batch, on N emulator slots in parallel
(docs/automation-plan.md, sections 6.1 and 8):

    python run.py --app spotify --phone-country India --numbers numbers.csv --workers 3

The CSV is validated, deduplicated and loaded into MongoDB once; it is never read by the workers.
Each worker owns one slot (emulator + Appium server) and loops: generate attempt_id -> atomically
claim the next number -> run the target's tests for it in a subprocess (renewing the claim's lease,
killed after RUN_TIMEOUT) -> mark the number COMPLETE -> shut the emulator down so the next number
boots clean from the read-only golden AVD."""
import collections
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from config.settings import RUN_TIMEOUT
from core import results, slot
from core.countries import calling_code
from core.emulator import kill_emulator

ROOT = Path(__file__).resolve().parents[1]


def run_batch(target, csv_path, country, workers):
    code = calling_code(country)
    with open(csv_path, newline="") as f:
        phones, rejected = results.parse_numbers(f, code)
    for raw, why in rejected:
        print(f"[batch] rejected {raw!r}: {why}", flush=True)
    if not phones:
        print("[batch] no valid numbers in the CSV", flush=True)
        return 1
    try:
        results.client().admin.command("ping")  # no MongoDB, no queue: fail before booting anything
    except Exception as e:
        print(f"[batch] MongoDB unreachable at MONGO_URI: {type(e).__name__}", flush=True)
        return 1
    results.ensure_indexes("app", target)
    batch_id = results.load_numbers("app", target, phones, code)
    log_dir = ROOT / "targets" / "apps" / target / "reports" / f"batch-{batch_id}"
    log_dir.mkdir(parents=True, exist_ok=True)
    print(f"[batch] {batch_id}: {len(phones)} numbers, {workers} workers, logs in {log_dir}", flush=True)

    threads = [threading.Thread(target=_worker, args=(target, batch_id, country, i, log_dir), daemon=True)
               for i in range(workers)]
    for t in threads:
        t.start()
        time.sleep(5)  # stagger the cold boots; all at once starves the CPU
    for t in threads:
        t.join()

    # each number's final attempt only: one replaced after an expired lease doesn't count
    final = [n["attempt_id"] for n in results.numbers("app", target).find({"batch_id": batch_id}, {"attempt_id": 1})]
    counts = collections.Counter(d["result"] for d in results.attempts("app", target).find(
        {"attempt_id": {"$in": final}}, {"result": 1}))
    print(f"[batch] {batch_id} done: {dict(counts)}", flush=True)
    return 0 if set(counts) <= {"PASS"} else 1


def _worker(target, batch_id, country, i, log_dir):
    serial = slot.serial(i)
    tests = ROOT / "targets" / "apps" / target / "tests"
    while True:
        attempt_id = str(uuid.uuid4())
        row = results.claim("app", target, batch_id, f"slot{i}", attempt_id)
        if row is None:
            return
        phone = row["phone"]
        env = {**os.environ, "PHONE": phone, "PHONE_COUNTRY": country, "SLOT": str(i), "ATTEMPT_ID": attempt_id}
        started = time.monotonic()
        with open(log_dir / f"slot{i}-{phone}.log", "w") as log:
            proc = subprocess.Popen([sys.executable, "-m", "pytest", "-s", str(tests)],
                                    cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            while True:
                results.renew_lease("app", target, batch_id, phone, attempt_id)
                try:
                    proc.wait(timeout=10)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() - started > RUN_TIMEOUT:
                        print(f"[slot{i}] {phone}: no result after {RUN_TIMEOUT}s, killed", flush=True)
                        proc.kill()
        results.fail_unfinished("app", target, attempt_id)
        results.complete_number("app", target, batch_id, phone, attempt_id)
        kill_emulator(serial)
        verdict = "PASS" if proc.returncode == 0 else "FAIL"
        print(f"[slot{i}] {phone}: {verdict} ({time.monotonic() - started:.0f}s)", flush=True)

# Automation plan: parallel OTP login runs (CSV + DB + SMPP + Redis)

Status: **implemented, revision 4** (code complete, not yet run against real MongoDB, Redis, SMPP or
the server). The design follows the ChatGPT review "Create Appium Flow CSV Gaps"
exactly: CSV loaded into a DB, atomic number claim, `attempt_id` correlation, SMPP `message_id`,
explicit state machine, Redis fan-out with attempt filtering, timeouts, leases and idempotent events.
The database is MongoDB (decided earlier), and parallel execution runs on emulators on our server.

Section 12 maps the design to the code.

## 1. Goal

Take a CSV of phone numbers of one country and run one app's phone-login flow for each number, with
several Appium workers in parallel. For each number the SMPP delivery status decides the outcome:

- **SMPP DELIVERED**: the OTP is rejected. Close the OTP record, do not enter an OTP, abort the login,
  move to the next number.
- **SMPP UNDELIVERED or REJECTED**: the OTP is accepted. Mark the OTP executed, enter the OTP, log in,
  move to the next number.

## 2. Architecture

```
                         ┌─────────────────────┐
                         │      CSV FILE        │   source dataset only
                         └──────────┬──────────┘
                                    ▼
                         ┌─────────────────────┐
                         │  NUMBER ALLOCATION  │   CSV loaded into the DB once;
                         │  atomic claim/lock  │   each row claimed exactly once
                         └──────────┬──────────┘
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
               Appium #1       Appium #2       Appium #3      (one per emulator slot)
               attempt A1      attempt A2      attempt A3
               gets N1         gets N2         gets N3
               open app        open app        open app
               enter N1        enter N2        enter N3
                    └───────────────┼───────────────┘
                                    ▼
                         ┌─────────────────────┐
                         │   DB (MongoDB)      │   attempt_id, phone, status,
                         │                     │   smpp_message_id, otp, timestamps
                         └──────────┬──────────┘
                                    ▼
                          SMS / OTP generation
                                    ▼
                              ┌───────────┐
                              │   SMPP    │   delivery status received
                              └─────┬─────┘
                     ┌──────────────┴──────────────┐
                     ▼                             ▼
                 DELIVERED                  UNDELIVERED / REJECTED
              DB lookup (msg id)             DB lookup (msg id)
              close OTP record               mark OTP executed
              Redis: REJECTED, no OTP        Redis: ACCEPTED + OTP
                     └──────────────┬──────────────┘
                                    ▼
                         ┌─────────────────────┐
                         │       REDIS         │   fan-out: every worker
                         └──────────┬──────────┘   receives every event
                                    ▼
                         ALL Appium subscribers
                                    ▼
                          CORRELATION CHECK
                    ┌───────────────┴───────────────┐
             attempt_id is mine                not mine
             process response                  IGNORE
```

## 3. Design rules

1. **Correlate on `attempt_id`, not on phone number.** Every Appium execution generates an
   `attempt_id` (UUID). Redis fan-out delivers every event to every worker, so each worker asks
   "is this response for MY attempt?". `attempt_id` makes that deterministic, and it stops a stale event
   from an earlier attempt on the same number being applied to a new attempt.
2. **The CSV is not the concurrency control.** Workers never read rows from the CSV directly, because two
   workers can read the same row before either updates it. The CSV is validated, deduplicated and loaded
   into the DB once. The DB hands out each row exactly once through an atomic claim.
3. **Store the SMPP `message_id`** for each attempt, and correlate delivery receipts as
   `message_id -> attempt_id -> phone`, not by phone number alone.
4. **Explicit state machine** instead of only "OTP generated / OTP executed".
5. **Two separate fields** for the SMPP status and our OTP decision, because "DELIVERED means rejected"
   is the reverse of normal SMS meaning and would be misread later.
6. **Every wait has a timeout**, and every claim has a lease that expires if the worker crashes.
7. **Every event has an `eventId`**, so a duplicate SMPP callback is processed once.
8. **Prefer status transitions over deletes**, to keep the audit trail for troubleshooting. "Delete OTP"
   is implemented as closing the record.

## 4. Data model (MongoDB)

Databases follow the earlier decision: `Apps` for app flows, `Web` for web flows, collections per app.
Two collections per app, matching the review's numbers table and OTP table:

### 4.1 Numbers: `Apps.<App>_numbers` (for example `Apps.Spotify_numbers`)

Loaded from the CSV. One document per row.

| Field | Meaning |
|---|---|
| `row_number` | Position in the CSV, used for claim order |
| `phone` | National number |
| `country_code` | Calling code of the batch's country |
| `status` | `AVAILABLE` / `CLAIMED` / `IN_PROGRESS` / `COMPLETE` |
| `claimed_by` | Worker / emulator slot id |
| `claimed_at` | When it was claimed |
| `lease_until` | Claim expires after this unless renewed |
| `attempt_id` | The attempt currently working this number |

```
row | phone       | status     | claimed_by
--------------------------------------------
1   | 9876543210  | AVAILABLE  | NULL
2   | 9876543211  | AVAILABLE  | NULL
3   | 9876543212  | AVAILABLE  | NULL
```

Atomic claim. The review's SQL form:

```sql
SELECT * FROM numbers WHERE status = 'AVAILABLE'
ORDER BY row_number FOR UPDATE SKIP LOCKED LIMIT 1;
```

MongoDB equivalent (one atomic operation, no two workers get the same row):

```
find_one_and_update(
    {status: "AVAILABLE"}, sort row_number ascending,
    {$set: {status: "CLAIMED", claimed_by: slot, claimed_at: now,
            lease_until: now + lease, attempt_id: my_attempt_id}})
```

### 4.2 Attempts / OTP records: `Apps.<App>` (for example `Apps.Spotify`)

One document per attempt.

| Field | Meaning |
|---|---|
| `attempt_id` | UUID, unique index |
| `phone`, `country_code` | The claimed number |
| `smpp_message_id` | SMPP message identifier, unique index when present |
| `otp` | The OTP, filled on UNDELIVERED / REJECTED |
| `status` | State machine, section 5 |
| `smpp_status` | `DELIVERED` / `UNDELIVERED` / `REJECTED` (what SMPP said) |
| `otp_decision` | `ACCEPTED` / `REJECTED` (what we do) |
| `last_event_id` | Idempotency: last event applied |
| `result` | `PASS` / `FAIL` of the login test |
| `created_at`, `updated_at` | Timestamps |

```
smpp_status       otp_decision
--------------------------------
DELIVERED         REJECTED
UNDELIVERED       ACCEPTED
REJECTED          ACCEPTED
```

## 5. State machine (attempt `status`)

```
AVAILABLE
    ↓
CLAIMED
    ↓
OTP_REQUESTED
    ↓
WAITING_SMPP
    ├──► SMPP_DELIVERED   ──► OTP_REJECTED ──► REDIS_PUBLISHED ──► APPIUM_PROCESSED
    ├──► SMPP_UNDELIVERED ──► OTP_ACCEPTED ──► REDIS_PUBLISHED ──► APPIUM_PROCESSED
    └──► OTP_TIMEOUT      ──► ABORT ──► next number
```

- `ABANDONED` closes an attempt whose run ended without a decision (crash, kill, failure before the
  OTP step) or whose number was reclaimed after its lease expired, so a late SMPP event can't land on it.
- Every state change is also appended to the attempt's `history` (status + time) as the audit trail.
- `AVAILABLE` and `CLAIMED` live on the numbers collection; from `OTP_REQUESTED` on, the attempt
  document carries the state.
- Every transition is a conditional update (only succeeds from the expected previous state), so the
  DB check and the update cannot race.

## 6. Full flow

### 6.1 Batch start

```
python run.py --app spotify --phone-country India --numbers numbers.csv --workers 3
```

1. Validate the CSV: missing or invalid numbers rejected, duplicates removed.
2. Load it into `Apps.Spotify_numbers` as `AVAILABLE` rows.
3. Start N workers. Each worker owns one emulator slot (section 8).

### 6.2 Appium worker logic (per number, loops until no `AVAILABLE` rows remain)

```
START
 ▼
Generate attempt_id
 ▼
Atomically claim next CSV number          (none left -> worker stops)
 ▼
DB: CLAIMED
 ▼
Open application (clean emulator)
 ▼
Enter phone number
 ▼
Send OTP
 ▼
DB: OTP_REQUESTED, then WAITING_SMPP
 ▼
Subscribe / listen to Redis
 ▼
Receive Redis event
 ▼
Is attempt_id mine? ── NO ──► IGNORE (keep listening)
 │ YES
 ▼
Is phone mine? ── NO ──► IGNORE
 │ YES
 ▼
Status?
 ├── REJECTED
 │     ▼
 │   ABORT LOGIN
 │     ▼
 │   MARK CURRENT NUMBER COMPLETE
 │     ▼
 │   NEXT NUMBER
 │
 └── ACCEPTED
       ▼
     OTP exists? ── NO ──► INVALID EVENT ──► IGNORE / ERROR
       │ YES
       ▼
     Enter OTP
       ▼
     LOGIN
       ▼
     SUCCESS
       ▼
     NEXT NUMBER

No event before the timeout (e.g. 30/60/90 s, set from the real SMPP SLA):
     OTP_TIMEOUT ──► ABORT ──► NEXT NUMBER
```

The worker renews its claim lease while it works, writes `APPIUM_PROCESSED` and `result` on the attempt,
and `COMPLETE` on the number.

### 6.3 SMPP service logic (one process, runs continuously)

```
SMPP SOCKET  (bind to provider, enquire_link keepalive, reconnect with backoff)
    ▼
Receive delivery status
    ▼
Parse: message_id, phone, status, timestamp
    ▼
Find DB record using message_id / attempt_id
    ├── NOT FOUND ──► LOG + IGNORE
    └── FOUND
          ▼
        Already applied (same eventId)? ──► IGNORE
          ▼
        status?
          ├── DELIVERED
          │     ▼
          │   smpp_status = DELIVERED, otp_decision = REJECTED
          │   Delete/close OTP record (status transition, otp cleared)
          │     ▼
          │   Redis publish REJECTED, otp null
          │
          └── UNDELIVERED / REJECTED
                ▼
              smpp_status = UNDELIVERED|REJECTED, otp_decision = ACCEPTED
              Mark OTP executed, update timestamp, store OTP
                ▼
              Redis publish ACCEPTED + OTP
          ▼
        DB: REDIS_PUBLISHED
```

### 6.4 Redis event payloads

Accepted:

```json
{
  "eventId": "EVT-123456",
  "attemptId": "ATT-987654",
  "phone": "9876543210",
  "status": "ACCEPTED",
  "otp": "123456",
  "timestamp": "2026-10-07T19:55:23.123Z"
}
```

Rejected:

```json
{
  "eventId": "EVT-123457",
  "attemptId": "ATT-987654",
  "phone": "9876543210",
  "status": "REJECTED",
  "otp": null,
  "timestamp": "2026-10-07T19:55:25.123Z"
}
```

`status` here is the OTP decision, not the SMPP status. `eventId` gives idempotency.

### 6.5 Redis mode

- **Pub/Sub** (the design as specified): every worker sees every message, filtered by `attemptId`. Limit:
  a worker that is disconnected at publish time never receives the message. The DB stays the source of
  truth, so a worker that reaches its timeout re-reads its attempt document before declaring
  `OTP_TIMEOUT`.
- **Redis Streams**: the upgrade if guaranteed delivery is required (consumers can re-read missed
  entries).

## 7. Race conditions and their fixes

| Issue | Risk | Fix |
|---|---|---|
| Multiple Appiums reading CSV | Same number assigned twice | Atomic DB number allocation |
| Correlation only by phone | Wrong Appium can process OTP | `attempt_id` |
| Redis Pub/Sub fan-out | Every worker receives every event | Filter by `attempt_id` |
| Reusing same phone | Old event can affect new attempt | `attempt_id` + `eventId` |
| SMPP response delayed | Appium waits forever | Timeout |
| SMPP response missing | Number remains stuck | Timeout / retry state |
| Duplicate SMPP callbacks | Same event processed twice | `eventId` / `message_id` idempotency |
| DB check then update | Race between check and update | Atomic conditional update |
| Appium crash | Number remains claimed | Lease / claim timeout |
| Redis subscriber disconnect | Pub/Sub message lost | DB re-read on timeout; Redis Streams if guaranteed delivery needed |
| CSV contains duplicate numbers | Same number processed multiple times | Validate / deduplicate CSV |
| Multiple OTPs for same number | Old OTP can arrive after new OTP | `attempt_id` / `message_id` |
| DB record deleted too early | Difficult troubleshooting | Status transitions and audit history |

## 8. Parallel execution on the server

Each Appium worker owns one **slot**: one emulator, one Appium server, one test run at a time.

| Resource | Slot `i` |
|---|---|
| Emulator console port | `5554 + 2i` (serial `emulator-<port>`) |
| Appium port | `4723 + i` |
| UiAutomator2 `systemPort` | `8200 + i` |
| Report directory | `reports/<timestamp>-slot<i>-<phone>` |

- **Golden AVD:** one Google Play AVD with every app installed and Play Store auto-update off. Workers
  start instances with `-read-only` and distinct ports: each instance gets a temporary overlay discarded
  on exit, so every number starts from the same clean device.
- **One test subprocess per number**, killed on timeout, so a hung run never blocks its slot.
- Workers do not wait on each other. Total time is roughly (numbers / slots) x time per number.

**Server: 8 vCPU, 32 GB RAM.**

| Item | CPU | RAM |
|---|---|---|
| OS, MongoDB, Redis, SMPP service | ~1 vCPU | ~4 GB |
| Appium + test per slot | ~0.3 vCPU | ~0.7 GB |
| One headless emulator | ~2 vCPU | ~3–4 GB |

CPU is the limit: start at **3 slots**, try 4 after measuring. Requirements:

- Hardware acceleration: `/dev/kvm` must exist (Linux), `egrep -c '(vmx|svm)' /proc/cpuinfo` > 0.
  A cloud VM needs nested virtualization. x86_64 server needs x86_64 system images.
- Headless emulators: `-no-window -no-audio -gpu swiftshader_indirect`.
- Android SDK (emulator, platform-tools, Google Play image), Appium + UiAutomator2, Node, Python venv.
- MongoDB and Redis reachable from workers and the SMPP service.
- SMPP service under a supervisor (systemd) so it restarts.
- Static public outbound IP whitelisted by the SMPP provider; outbound access to their SMPP port.
  We are the SMPP client and bind outbound, so no listening port is needed on our side.

## 9. SMPP connection

**Our role: client (ESME), confirmed.** Our SMPP service connects out and binds to the provider's SMSC.
We run no SMPP server and open no listening port; the provider only whitelists our server IP.

From the provider: host, port (plain and TLS), `system_id`, password, bind type (transceiver or
receiver), whether delivery receipts and inbound SMS arrive on the same bind, whether a `message_id`
can be tied to each attempt. Config goes in `.env` as `SMPP_HOST`, `SMPP_PORT`, `SMPP_SYSTEM_ID`,
`SMPP_PASSWORD`, `SMPP_BIND`, `SMPP_TLS`.

## 10. Configuration

`.env` on the server: `MONGO_URI`, `REDIS_URL`, the `SMPP_*` values, timeout values (OTP wait, claim
lease, per-run kill), and the number of workers.

## 11. Code changes

| # | File | Change |
|---|---|---|
| 1 | `core/results.py` | Numbers and attempts collections, CSV load with validation and dedupe, atomic claim, lease, conditional state transitions |
| 2 | `core/smpp_listener.py` | Parse `message_id`, look up by `message_id` / `attempt_id`, write `smpp_status` + `otp_decision`, `eventId` idempotency, Redis publish, `REDIS_PUBLISHED` |
| 3 | `core/otp.py` | Subscribe to Redis, filter on `attemptId` then phone, handle ACCEPTED / REJECTED / invalid event, timeout with DB re-read |
| 4 | `core/slot.py` (new) | Serial and ports derived from the slot number |
| 5 | `core/emulator.py` | Boot or attach to the slot's emulator only, `-read-only` |
| 6 | `core/appium_server.py`, `core/driver_factory.py` | Per-slot Appium port and log, `systemPort` |
| 7 | `targets/apps/conftest.py` | Use the slot, adopt the claimed attempt instead of inserting a new record |
| 8 | `core/orchestrator.py` (new) | Load CSV, start N workers, claim loop, lease renewal, timeouts, cleanup |
| 9 | `run.py` | `--numbers`, `--workers` |
| 10 | App tests (Spotify first) | Replace "never types an OTP" with the worker decision logic of section 6.2 |
| 11 | `config/settings.py`, `.env.example`, `requirements.txt` | `REDIS_URL`, timeouts, `redis` package |
| 12 | Unit tests | Claim, state transitions, SMPP decisions, Redis filtering, with fakes |

## 12. Implementation map

| Design part | Code |
|---|---|
| Numbers, attempts, CSV load, atomic claim, leases, state transitions | `core/results.py` |
| SMPP service (client bind, receipts, SMS, decisions, idempotency, Redis publish) | `core/smpp_listener.py`, run as `python -m core.smpp_listener` |
| Worker correlation check, decision, DB fallback, OTP_TIMEOUT | `core/otp.py` (`Waiter`, exposed to tests as `steps.otp`) |
| Batch, workers, lease renewal, run timeout, emulator cleanup | `core/orchestrator.py`, `run.py --numbers --workers` |
| Slot ports and serial | `core/slot.py`; `core/emulator.py` (`exclusive`, `-read-only`, `kill_emulator`), `core/appium_server.py`, `core/driver_factory.py` (`systemPort`) |
| Fixture wiring | `targets/apps/conftest.py`, `targets/web/conftest.py` |
| Pilot flow | `targets/apps/spotify/tests/test_login_phone.py` |
| Tests | `tests/unit/test_smpp.py` (in-memory MongoDB, fake Redis and PDUs) |

Where the OTP comes from: the receipt's `text:` field if it carries the code, else the inbound SMS for
the number. The decision is published once both the SMPP status and the OTP are known, in either order.

Other app tests (WhatsApp, Telegram, inDrive, Zomato, Prime Video, TikTok) still stop at the OTP screen;
each gets the same `steps.otp.otp_requested()` / `steps.otp.wait()` wiring as Spotify once the pilot is
proven against the real provider.

## 13. Build order

1. Confirm with the provider how receipts and SMS reach our bind and whether a `message_id` is available.
2. Data model, CSV load, claim and state machine (with unit tests).
3. SMPP service changes and Redis publish (tested with fake PDUs).
4. Worker Redis subscriber and decision logic.
5. Slot plumbing, proven with two emulators by hand.
6. Orchestrator with 2 workers, then wire Spotify.
7. Timeouts, leases, retries.
8. Load test on the server to fix the real slot count.

## 14. Open decisions

1. Provider: do receipts and SMS for the app's OTP messages arrive on our bind, and is a `message_id`
   available per attempt? An SMPP receipt normally only returns to the system that submitted the message.
2. Redis Pub/Sub (as designed) or Redis Streams.
3. Timeout values: OTP wait, claim lease, per-run kill.
4. Server OS and KVM availability.
5. Collection naming for the numbers pool (`Apps.<App>_numbers` assumed).
6. One app per batch (assumed) or several.

# Run guide

Every command to run a flow, locally or on the server. The design behind it is in
[automation-plan.md](automation-plan.md).

## Quick reference

| I want to... | Command |
|---|---|
| See all flows | `python run.py --list` |
| Run one app flow with one number | `python run.py --app <name> --phone-country <Country> --phone <number>` |
| Run one website flow | `python run.py --web <name>` |
| Run an app flow for a CSV of numbers, in parallel | `python run.py --app <name> --phone-country <Country> --numbers numbers.csv --workers 3` |
| Run the unit tests | `python -m pytest tests/unit -q` |
| Connect to the server | `ssh -i ~/.ssh/emu_server -o IdentitiesOnly=yes root@<server-ip>` |

`<server-ip>` is the deploy server's address. It is kept out of this repo on purpose (the repo is
public); ask the team for it.

Run every command from the project root (`/opt/emu` on the server) with the virtualenv's Python:
`.venv/bin/python run.py ...`, or activate it first with `source .venv/bin/activate`.

## 1. First-time setup (local machine)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # then fill in what the flows you run need
```

Needs Android SDK, an emulator (or a device on adb), Appium (`npm i -g appium`,
`appium driver install uiautomator2`), and the app installed on the device. The emulator and Appium
are started automatically if they are not running.

## 2. Single app flows (one number)

`--phone-country` is the country as named in the app's picker (e.g. `India`, `Pakistan`).
`--phone` is the number for this run; without it, the target's `<APP>_PHONE` in `.env` is used.

| App | Command | Number format |
|---|---|---|
| Spotify | `python run.py --app spotify --phone-country India --phone 9876543210` | National number; country defaults to India |
| WhatsApp | `python run.py --app whatsapp --phone-country Pakistan --phone 3345333345` | Also `--phone +923345333345`, or a bare 10 digits = India |
| Telegram | `python run.py --app telegram --phone-country Pakistan --phone 3345333345` | Same as WhatsApp |
| inDrive | `python run.py --app indrive --phone-country Pakistan --phone 3345333345` | Both flags required |
| TikTok | `python run.py --app tiktok --phone-country India --phone 7420870251` | Both flags required |
| Zomato | `python run.py --app zomato --phone 9876543210` | India only, 10 digits |
| Prime Video | `python run.py --app primevideo --phone-country Pakistan --phone 3345333345` | Also `+<code><number>`, or bare 10 digits = India |

What happens after the OTP screen:

- **Spotify** waits for the SMPP decision (needs MongoDB, Redis and the SMPP service running):
  `REJECTED` (delivered to a real handset) ends the flow without typing anything; `ACCEPTED` types the
  OTP and waits for the login to complete. Without a decision it fails after `OTP_WAIT_TIMEOUT` (90s).
- **All other apps** stop on the OTP screen and never type a code. They get the SMPP wiring once the
  Spotify pilot is proven.

Each run is recorded in MongoDB (`Apps.<App>`) if MongoDB is reachable; if not, the run still works and
prints a warning.

Extra pytest options can be appended, e.g. `-k phone` or `-x`.

## 3. Website flows

| Site | Command | Number |
|---|---|---|
| Spotify sign-up | `python run.py --web spotify` | `SPOTIFY_PHONE` in `.env` |
| Uber sign-up | `python run.py --web uber` | `UBER_PHONE` in `.env`, with country code (`+91...`) |
| Uber through a proxy exit country | `python run.py --web uber --country us` | Needs the Bright Data residential vars in `.env` |

CAPTCHA solving needs `CAPSOLVER_API_KEY` in `.env`; without it challenges are only reported.
Set `HEADLESS=1` to run without a browser window.

## 4. Parallel batch (many numbers, several emulators)

```bash
python run.py --app spotify --phone-country India --numbers numbers.csv --workers 3
```

Requires MongoDB and Redis, and the SMPP service for OTP decisions. Run it on the server.

**CSV format:** one number per row, first column. A header row is fine. Numbers can be national
(`9876543210`) or international with the batch's country code (`+919876543210`). Invalid numbers and
duplicates are rejected and listed before the run starts.

```
phone
9876543210
9876543211
+919876543212
```

**What happens:**

1. The CSV is loaded into `Apps.<App>_numbers` as a new batch (the batch id is printed).
2. Each worker owns one emulator slot and loops: claim the next number, boot a clean emulator from the
   golden AVD, run the app's flow, record PASS/FAIL, shut the emulator down, take the next number.
3. At the end it prints the counts, e.g. `done: {'PASS': 9, 'FAIL': 1}`. Exit code is 0 only if all passed.

**Output:**

- Live progress: `[slot0] 9876543210: PASS (84s)`
- Per-number pytest log: `targets/apps/<app>/reports/batch-<batch_id>/slot<i>-<phone>.log`
- Per-number step screenshots: `targets/apps/<app>/reports/<timestamp>-slot<i>/`

**Workers:** `--workers` overrides `WORKERS` in `.env` (default 3). The server (8 threads) handles 3;
try 4 only after measuring.

**Timeouts (in `.env`):** `OTP_WAIT_TIMEOUT` (90s, wait for the SMPP decision), `CLAIM_LEASE`
(120s, a crashed worker's number becomes claimable again), `RUN_TIMEOUT` (600s, one number's run is
killed after this).

## 5. Server

Connect:

```bash
ssh -i ~/.ssh/emu_server -o IdentitiesOnly=yes root@<server-ip>
cd /opt/emu
```

Layout: code `/opt/emu`, settings `/opt/emu/.env`, Android SDK `/opt/android-sdk`, golden AVD `golden`,
APKs `/opt/apks`.

### Deploy code changes (from the Mac, in the project root)

```bash
rsync -az -e "ssh -i ~/.ssh/emu_server -o IdentitiesOnly=yes" \
  --exclude='.venv' --exclude='.env' --exclude='.git' --exclude='__pycache__' \
  --exclude='.pytest_cache' --exclude='.DS_Store' --exclude='reports' --exclude='ChatGPT*' \
  --exclude='*.apk' --exclude='*.apkm' --exclude='.sb_profile' \
  ./ root@<server-ip>:/opt/emu/
```

Then, if `requirements.txt` changed: `/opt/emu/.venv/bin/pip install -r /opt/emu/requirements.txt`,
and restart the SMPP service if it is running: `systemctl restart emu-smpp`.

### Services

| Service | Status | Restart | Logs |
|---|---|---|---|
| MongoDB | `systemctl status mongod` | `systemctl restart mongod` | `journalctl -u mongod` |
| Redis | `systemctl status redis-server` | `systemctl restart redis-server` | `journalctl -u redis-server` |
| SMPP server | `systemctl status emu-smpp` | `systemctl restart emu-smpp` | `journalctl -u emu-smpp -f` |

### SMPP server (the provider binds to us)

We are the SMPP server; the provider is the client. `emu-smpp` runs `python -m smpp_server.server`,
listening on `SMPP_SERVER_PORT` (2775), and starts at boot.

- Credentials we give the provider: `SMPP_SERVER_SYSTEM_ID` / `SMPP_SERVER_PASSWORD` in `/opt/emu/.env`
  (password max 8 characters). After changing them: `systemctl restart emu-smpp`.
- Restrict who may connect: `SMPP_ALLOWED_IPS=1.2.3.4,5.6.7.8` in `.env`, then restart.
- Live traffic: `journalctl -u emu-smpp -f` (connects, binds, every PDU; passwords are masked).
- Stored traffic: `mongosh SMPP --eval 'db.pdus.find().sort({at:-1}).limit(20)'`
- What it does today: bind (transmitter / receiver / transceiver) with our credentials, enquire_link,
  unbind, and accepts `submit_sm` with our own message_id. OTP decisions for the automation are not
  wired to it yet.

Test a bind yourself from any machine with the venv:

```bash
python - <<'PY'
import smpplib.client
c = smpplib.client.Client("<server-ip>", 2775, allow_unknown_opt_params=True)
c.connect(); c.bind_transceiver(system_id="<system_id>", password="<password>"); print("bound")
c.unbind(); c.disconnect()
PY
```

### Watch the OTP flow live

```bash
redis-cli subscribe otp-events            # every decision the SMPP service publishes
journalctl -u emu-smpp -f                 # the provider's binds and messages as they arrive
```

## 6. Checking results in MongoDB

```bash
mongosh Apps
```

```js
// latest batches and their progress
db.Spotify_numbers.aggregate([{$group: {_id: {batch: "$batch_id", status: "$status"}, n: {$sum: 1}}}, {$sort: {"_id.batch": -1}}])

// every attempt of one batch
db.Spotify.find({batch_id: "<batch_id>"}, {_id: 0, phone: 1, status: 1, smpp_status: 1, otp_decision: 1, result: 1})

// failures only
db.Spotify.find({batch_id: "<batch_id>", result: "FAIL"}, {_id: 0, phone: 1, status: 1, history: 1})

// full history of one number
db.Spotify.find({phone: "9876543210"}).sort({created_at: -1}).limit(3)
```

Field meanings: `status` is the state machine (`CLAIMED` ... `APPIUM_PROCESSED`, or `OTP_TIMEOUT` /
`ABANDONED`), `smpp_status` is what SMPP reported, `otp_decision` is what the worker did
(`REJECTED` = skip, `ACCEPTED` = typed), `result` is the test outcome.

## 7. Golden AVD (apps on the emulators)

Every parallel emulator is a read-only clone of `golden`, so apps are installed or updated there once.

```bash
. /etc/profile.d/android.sh
# boot golden writable (no batch may be running)
nohup emulator -avd golden -port 5554 -no-window -no-audio -gpu swiftshader_indirect -no-boot-anim -no-snapshot-save >/root/golden_boot.log 2>&1 &
adb -s emulator-5554 wait-for-device
# copy new .apk / .apkm files into /opt/apks first, then:
/opt/apks/install_apks.sh emulator-5554
adb -s emulator-5554 emu kill            # clean shutdown keeps the changes
```

Installed today: Spotify, WhatsApp, Zomato, Prime Video, inDrive. Telegram and TikTok need their APKs.

## 8. Tests

```bash
python -m pytest tests/unit -q           # no services needed (in-memory MongoDB, fake Redis/SMPP)
```

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| `[batch] MongoDB unreachable at MONGO_URI` | `systemctl start mongod`, check `MONGO_URI` in `.env` |
| `[otp] Redis unavailable ..., polling MongoDB instead` | `systemctl start redis-server`; the run still works through MongoDB |
| Spotify run fails with `No SMPP decision before OTP_WAIT_TIMEOUT` | The OTP decision is not wired to the SMPP server yet; once it is, check `journalctl -u emu-smpp` for the provider's traffic |
| Provider can't bind | `systemctl status emu-smpp`; `journalctl -u emu-smpp` shows `refused <ip>` (not in `SMPP_ALLOWED_IPS`), `status=0xe` (wrong password) or `0xf` (wrong system_id) |
| `<package> is not installed on emulator-...` | Install the app on the golden AVD (section 7) |
| Appium session errors | Logs in `reports/appium-<port>.log` (port 4723 + slot number) |
| Emulator never boots | `emulator -accel-check` must say KVM is usable; check free RAM with `free -g` |
| Leftover emulators after a crash | `adb devices`, then `adb -s emulator-<port> emu kill` for each |
| A number stuck in `CLAIMED` / `IN_PROGRESS` | While the batch runs, another worker reclaims it once its `CLAIM_LEASE` expires. A batch that was stopped is not resumed: put the leftover numbers in a new CSV and run that |

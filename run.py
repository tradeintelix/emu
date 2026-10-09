"""Central entry point.

    python run.py --web spotify                # runs targets/web/spotify
    python run.py --app <name>                  # runs targets/apps/<name>
    python run.py --list                        # shows every target found
    python run.py --web spotify -k phone         # anything unknown is passed on to pytest
    python run.py --web uber --country us        # runs the flow through a US residential exit IP
                                                  # (Bright Data; see core/web/residential_proxy.py)
    python run.py --app indrive --phone-country Pakistan --phone 3345333345   # country + number per run
    python run.py --app spotify --phone-country India --numbers numbers.csv --workers 3
                                                  # a batch: every CSV number, on 3 emulators in parallel
                                                  # (core/orchestrator.py; needs MongoDB, Redis, SMPP service)
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
FOLDER = {"app": "apps", "web": "web"}


def find_targets(kind):
    base = ROOT / "targets" / FOLDER[kind]
    return sorted(p.name for p in base.iterdir() if p.is_dir() and not p.name.startswith("_")) if base.exists() else []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--app", metavar="NAME", help="Android app to test")
    group.add_argument("--web", metavar="NAME", help="website to test")
    group.add_argument("--list", action="store_true", help="list available targets")
    ap.add_argument("--country", metavar="CC",
                     help="residential proxy exit country (ISO-3166, e.g. us, in, eu) for this run")
    ap.add_argument("--phone-country", metavar="NAME",
                     help="country of the phone number, as named in the app's picker (e.g. Pakistan)")
    ap.add_argument("--phone", metavar="NUMBER",
                     help="phone number for this run, without the country code (e.g. 3345333345)")
    ap.add_argument("--numbers", metavar="CSV",
                     help="run the app flow for every number in this CSV (first column), in parallel")
    ap.add_argument("--workers", type=int, metavar="N", help="parallel emulators for --numbers (default: WORKERS)")
    args, pytest_args = ap.parse_known_args()

    if args.list:
        for kind in FOLDER:
            print(f"--{kind}: {', '.join(find_targets(kind)) or '(none)'}")
        return 0

    kind, name = ("app", args.app) if args.app else ("web", args.web)
    if name not in find_targets(kind):
        sys.exit(f"Unknown {kind} '{name}'. Available: {', '.join(find_targets(kind)) or '(none)'}")

    if args.numbers:
        if kind != "app" or not args.phone_country:
            sys.exit("--numbers needs --app <name> and --phone-country <name>")
        from config.settings import WORKERS
        from core.orchestrator import run_batch
        return run_batch(name, args.numbers, args.phone_country, args.workers or WORKERS)

    env = os.environ.copy()
    if args.country:
        env["PROXY_COUNTRY"] = args.country
    if args.phone_country:
        env["PHONE_COUNTRY"] = args.phone_country
    if args.phone:
        env["PHONE"] = args.phone

    # -s: show each step live in the terminal (the steps are also saved in the target's reports/ folder)
    cmd = [sys.executable, "-m", "pytest", "-s", str(ROOT / "targets" / FOLDER[kind] / name / "tests"), *pytest_args]
    return subprocess.run(cmd, cwd=ROOT, env=env).returncode


if __name__ == "__main__":
    sys.exit(main())

"""Shows each step as it runs and saves it to the target's reports/<timestamp>/ folder:
a screenshot per step, steps.log, and findings.json (errors the browser reported)."""
import json
import re
import time
from contextlib import contextmanager

from core.web.monitors import drain


class StepRecorder:
    def __init__(self, driver, report_dir):
        self.driver = driver
        self.dir = report_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.n = 0
        self.findings = []

    @contextmanager
    def step(self, name):
        self.n += 1
        print(f"[{self.n:02d}] {name} ...", flush=True)
        try:
            yield
        except Exception as e:
            self._record(name, "FAIL", f"{type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}")
            raise
        self._record(name, "PASS")

    def _record(self, name, status, detail=""):
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40]
        shot = f"{self.n:02d}_{slug}_{status.lower()}.png"
        try:
            self.driver.save_screenshot(str(self.dir / shot))
        except Exception:  # browser may already be gone; the log line is still worth keeping
            shot = "(no screenshot)"
        for f in drain(self.driver):
            self.findings.append({"step": f"{self.n:02d} {name}", **f})
        line = f"[{self.n:02d}] {status} {name} -> {shot}" + (f"  {detail}" if detail else "")
        print(line, flush=True)
        with open(self.dir / "steps.log", "a") as log:  # appended live, so a crash keeps what already ran
            log.write(f"{time.strftime('%H:%M:%S')} {line}\n")

    def finish(self):
        self.findings += [{"step": "after last step", **f} for f in drain(self.driver)]
        (self.dir / "findings.json").write_text(json.dumps(self.findings, indent=2))
        print(f"\nFindings: {len(self.findings)}   Report: {self.dir}", flush=True)

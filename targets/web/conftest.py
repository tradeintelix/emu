import importlib.util
import time

import pytest

from core.web.browser import create_browser
from core.web.steps import StepRecorder


def _target_config(target_dir):
    """Loads <target>/target.py if present. Keeps per-target, non-secret settings (like
    whether this target is authorized for CAPTCHA-solving) visible in that target's own
    folder instead of a shared file every target would otherwise have to edit."""
    cfg_path = target_dir / "target.py"
    if not cfg_path.exists():
        return {"solve_captcha": False, "country": None}
    spec = importlib.util.spec_from_file_location(f"target_config_{target_dir.name}", cfg_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {"solve_captcha": getattr(mod, "SOLVE_CAPTCHA", False), "country": getattr(mod, "PROXY_COUNTRY", None)}


@pytest.fixture
def steps(request):
    """A browser plus a step recorder that writes into <target>/reports/<timestamp>/."""
    target_dir = request.path.parents[1]  # targets/web/<name>/tests/test_x.py -> targets/web/<name>
    cfg = _target_config(target_dir)
    driver = create_browser(solve_captcha=cfg["solve_captcha"], country=cfg["country"])
    rec = StepRecorder(driver, target_dir / "reports" / time.strftime("%Y%m%d-%H%M%S"))
    rec.solve_captcha = cfg["solve_captcha"]
    yield rec
    rec.finish()
    driver.quit()

import re

from core import device_identity as di


def test_generate_deterministic():
    a = di.generate_identity(seed_str="attempt-1", phone_country="Pakistan", phone="3345333345")
    b = di.generate_identity(seed_str="attempt-1", phone_country="Pakistan", phone="3345333345")
    assert a == b


def test_different_seeds_diverge():
    a = di.generate_identity(seed_str="attempt-1", phone_country="Pakistan")
    b = di.generate_identity(seed_str="attempt-2", phone_country="Pakistan")
    assert (a["android_id"], a["profile"]["name"]) != (b["android_id"], b["profile"]["name"])


def test_android_id_format():
    ident = di.generate_identity(seed_str="x", phone_country="India")
    assert re.fullmatch(r"[0-9a-f]{16}", ident["android_id"])


def test_carrier_matches_country():
    assert di.generate_identity(seed_str="x", phone_country="Pakistan")["carrier"]["iso"] == "pk"
    assert di.generate_identity(seed_str="x", phone_country="India")["carrier"]["iso"] == "in"
    assert di.generate_identity(seed_str="x", phone_country="Nope")["carrier"]["iso"] == "us"


def test_boot_args_coherent():
    ident = di.generate_identity(seed_str="seed-9", phone_country="India", phone="+919876543210")
    args = di.boot_args(ident)
    joined = " ".join(args)
    assert "-prop" in args and "-phone-number" in args
    assert ident["profile"]["model"] in joined
    assert "9876543210" in joined


def test_apply_runtime_never_fails_and_sets_expected_keys():
    ident = di.generate_identity(seed_str="s", phone_country="Kuwait")
    calls = []

    def fail_first(*cmd):
        calls.append(cmd)
        raise RuntimeError("adb down")

    summary = di.apply_runtime("emulator-5554", ident, fail_first)
    assert "android_id=" in summary and "carrier=Zain" in summary
    flat = " ".join(" ".join(c) for c in calls)
    assert "android_id" in flat and "gsm.sim.operator.numeric" in flat
    assert "41902" in flat  # Kuwait Zain MCC+MNC

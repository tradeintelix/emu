from core.emulator import parse_devices

HEADER = "List of devices attached\n"


def test_no_devices():
    assert parse_devices(HEADER) == []


def test_only_online_devices_count():
    out = HEADER + "emulator-5554\toffline\nABC123\tunauthorized\nemulator-5556\tdevice\n"
    assert parse_devices(out) == ["emulator-5556"]

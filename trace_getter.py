#!/usr/bin/env python3
import logging
logging.basicConfig(level=logging.INFO)
from core.device_fingerprint import DeviceFingerprint

# Create instance - reads initial value
d = DeviceFingerprint('emulator-5554')
print(f'1. After init: {repr(d.android_id)}')

# Set a new value - this should call getprop with the value
d.android_id = 'final_test_456'
print(f'2. After set: {repr(d.android_id)}')

# Verify device actually has it
d.android_id = 'device_val_789'
print(f'3. After 2nd set: {repr(d.android_id)}')
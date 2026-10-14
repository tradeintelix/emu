"""Dynamic Android device fingerprinting via shell property injection.

This module bridges the host Python process and the Android shell to inject
runtime variables that persist across app launches without static file locking.

Uses `adb shell prop set` for persistent Android ID and `settings put` for
user-readable metadata that apps can query via ContentProviders.
"""

import hashlib
import logging
import subprocess
import time
from pathlib import Path

log = logging.getLogger(__name__)


class DeviceFingerprint:
    """Manages unique device identity by injecting runtime variables."""
    
    _instance = None
    
    def __init__(self, serial="emulator-5554"):
        """Initialize fingerprint manager with device serial.
        
        Args:
            serial: The Android device serial (default: emulator-5554)
        """
        self.serial = serial
        self._fingerprint = _generate_base_id(serial)
    
    @property
    def android_id(self):
        """Get the current Android ID."""
        prop_value = run(self.serial, "shell", "getprop", "persist.android.id")
        if prop_value.strip():
            return prop_value.strip()
        return self._fingerprint
    
    @android_id.setter
    def android_id(self, value):
        """Set a new Android ID persistently."""
        run(self.serial, "shell", "getprop", "persist.android.id", value)
        log.info(f"Set Android ID: {repr(value)}")
    
    @property
    def fingerprint(self):
        """Get a hash of the current Android ID (used for external ID mapping)."""
        return hashlib.sha256(self.android_id.encode()).hexdigest()[:16]
    
    @property
    def boot_count(self):
        """Get the number of times this device has booted."""
        prop_value = run(self.serial, "getprop", "persist.boot.count")
        if prop_value and prop_value.strip():
            return int(prop_value.strip())
        return 1  # default for first boot
    
    @boot_count.setter
    def boot_count(self, value):
        """Increment the boot count property."""
        run(self.serial, "shell", "prop", "set", "persist.boot.count", str(value))
    
    def generate_random_seed(self, length=8):
        """Generate a cryptographically random seed using /dev/urandom."""
        # Read from Android's /dev/urandom equivalent
        random_bytes = run(self.serial, "shell", "cat", "/dev/urandom", f"head -c {length}")
        return random_bytes.strip()
    
    def set_metadata(self, key, value):
        """Set arbitrary metadata in system settings."""
        run(self.serial, "shell", "settings", "put", "global", key, value)
        log.info(f"Set metadata {key}={value}")
    
    def get_metadata(self, key, default=""):
        """Get arbitrary metadata from system settings."""
        prop_value = run(self.serial, "shell", "settings", "get", "global", key)
        return prop_value.strip() if prop_value.strip() else default
    
    def ensure_identity(self):
        """Initialize the device with a complete identity profile."""
        log.info(f"Initializing fingerprint for device: {self.serial}")
        
        # Step 1: Set unique Android ID if not present
        current_id = self.android_id
        if current_id == self._fingerprint:
            self.android_id = current_id  # trigger the setter
            
        # Step 2: Increment boot count
        current_count = self.boot_count
        self.boot_count = current_count + 1
        
        # Step 3: Add a random seed for temporal uniqueness
        seed = self.generate_random_seed()
        self.set_metadata("fingerprint.seed", seed)
        
        # Step 4: Set timestamp of last identity injection
        timestamp = int(time.time())
        self.set_metadata("fingerprint.timestamp", str(timestamp))
        
        log.info(f"Device identity initialized: AndroidID={self.android_id}, Seed={seed}")
    
    def refresh(self):
        """Refresh all properties to ensure consistency."""
        self.ensure_identity()


def run(serial, *cmd, **kw):
    """Run an adb shell command with the given serial and return stdout."""
    full_cmd = ["adb", "-s", serial] + list(cmd)
    log.info(f"Runner: executing {full_cmd}")
    result = subprocess.run(
        full_cmd,
        capture_output=True,
        text=True,
        check=True,
        **kw
    )
    log.info(f"Runner: stdout = {repr(result.stdout)}")
    return result.stdout


def fingerprint_device(serial="emulator-5554"):
    """Convenience function to get a device's current fingerprint."""
    manager = DeviceFingerprint(serial)
    manager.ensure_identity()
    return manager.fingerprint


def _generate_base_id(serial):
    """Generate a deterministic base ID from the serial for fingerprint comparison."""
    base = f"{serial}_{int(time.time() * 1000)}"
    return hashlib.md5(base.encode()).hexdigest()[:12]


if __name__ == "__main__":
    import sys
    
    log.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1:
        serial = sys.argv[1]
    else:
        serial = "emulator-5554"
    
    print(f"Fingerprint for {serial}: {fingerprint_device(serial)}")
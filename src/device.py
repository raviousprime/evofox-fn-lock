"""Device discovery, validation, and hotplug polling for physical keyboards."""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

try:
    import evdev
    from evdev import ecodes
except ImportError:  # pragma: no cover
    evdev = None  # type: ignore
    ecodes = None  # type: ignore

from .config import DeviceConfig

logger = logging.getLogger("evofox-fn-lock.device")

VIRTUAL_KEYBOARD_NAME = "EvoFox Fn Lock Virtual Keyboard"


def is_matching_keyboard(dev: evdev.InputDevice, config: DeviceConfig) -> bool:
    """Check if the given evdev device matches our target physical keyboard."""
    # Never grab our own virtual keyboard
    if dev.name == VIRTUAL_KEYBOARD_NAME:
        return False

    # Ignore consumer control, mouse, system control interfaces
    name_lower = dev.name.lower()
    if "consumer" in name_lower or "system control" in name_lower or "mouse" in name_lower:
        return False

    capabilities = dev.capabilities()
    if ecodes.EV_KEY not in capabilities:
        return False

    keys = capabilities[ecodes.EV_KEY]
    # The main keyboard must have standard keys like ENTER and F1
    if ecodes.KEY_ENTER not in keys or ecodes.KEY_F1 not in keys:
        return False

    # Check vendor/product ID match if configured
    if config.vendor_id is not None and config.product_id is not None:
        if dev.info.vendor == config.vendor_id and dev.info.product == config.product_id:
            return True

    # Fallback to name match
    if config.name and config.name.lower() in name_lower:
        return True

    return False


def find_keyboard_device(config: DeviceConfig) -> Optional[evdev.InputDevice]:
    """Scan all /dev/input devices and find the target keyboard."""
    if not evdev:
        raise RuntimeError("evdev library is not installed.")

    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    candidates = []
    for dev in devices:
        try:
            if is_matching_keyboard(dev, config):
                candidates.append(dev)
        except Exception as e:
            logger.debug("Error checking device %s: %s", dev.path, e)
            continue

    if not candidates:
        return None

    # If multiple interfaces match (e.g. SEMICO exposes both event2 on input0 and event5 on input1):
    # Prioritize the primary keyboard interface:
    # 1. Has EV_LED (LEDs for NumLock, CapsLock, ScrollLock)
    # 2. Phys path contains input0
    # 3. Number of available keys
    def candidate_score(d: evdev.InputDevice) -> int:
        score = 0
        try:
            caps = d.capabilities()
            if ecodes.EV_LED in caps:
                score += 100
            if "input0" in (d.phys or ""):
                score += 50
            if ecodes.EV_KEY in caps:
                score += len(caps[ecodes.EV_KEY])
        except Exception:
            pass
        return score

    best_dev = max(candidates, key=candidate_score)
    for d in candidates:
        if d != best_dev:
            try:
                d.close()
            except Exception:
                pass

    logger.info("Found target keyboard: %s (%s, phys=%s, vendor=0x%04x, product=0x%04x)",
                best_dev.name, best_dev.path, best_dev.phys, best_dev.info.vendor, best_dev.info.product)
    return best_dev


def wait_for_device(config: DeviceConfig, poll_interval: float = 2.0) -> evdev.InputDevice:
    """Poll continuously until target keyboard is plugged in or available."""
    while True:
        dev = find_keyboard_device(config)
        if dev:
            return dev
        logger.info("Waiting for keyboard (vendor=0x%04x, product=0x%04x)...",
                    config.vendor_id or 0, config.product_id or 0)
        time.sleep(poll_interval)


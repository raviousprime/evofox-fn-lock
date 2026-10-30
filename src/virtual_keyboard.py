"""Virtual uinput keyboard with key state tracking and safety cleanup."""

from __future__ import annotations

import logging
from typing import Dict, Iterable, Optional, Set

try:
    import evdev
    from evdev import UInput, ecodes
except ImportError:  # pragma: no cover
    evdev = None  # type: ignore
    UInput = None  # type: ignore
    ecodes = None  # type: ignore

logger = logging.getLogger("evofox-fn-lock.virtual_keyboard")

VIRTUAL_KEYBOARD_NAME = "EvoFox Fn Lock Virtual Keyboard"


class VirtualKeyboard:
    """Manages an evdev UInput device and tracks pressed keys for clean release."""

    def __init__(self, source_device: Optional[evdev.InputDevice] = None, additional_keys: Optional[Iterable[int]] = None):
        if not evdev or not UInput:
            raise RuntimeError("evdev library is not installed.")

        # Build capability dictionary
        capabilities: Dict[int, list[int]] = {}

        if source_device:
            raw_caps = source_device.capabilities(verbose=False)
            for ev_type in (ecodes.EV_KEY, ecodes.EV_MSC, ecodes.EV_LED):
                if ev_type in raw_caps:
                    capabilities[ev_type] = list(raw_caps[ev_type])

            # Enable auto-repeat without codes (empty list avoids EINVAL ioctl error)
            if ecodes.EV_REP in raw_caps:
                capabilities[ecodes.EV_REP] = []

        if ecodes.EV_KEY not in capabilities:
            capabilities[ecodes.EV_KEY] = []

        # Add all mapped media/target keys to EV_KEY capability
        if additional_keys:
            key_set = set(capabilities[ecodes.EV_KEY])
            for k in additional_keys:
                key_set.add(k)
            capabilities[ecodes.EV_KEY] = sorted(list(key_set))

        self.uinput = UInput(
            events=capabilities,
            name=VIRTUAL_KEYBOARD_NAME,
            vendor=0x1A2C,
            product=0x4C5E,
            version=0x0110,
        )
        self._pressed_keys: Set[int] = set()
        logger.info("Created virtual keyboard '%s' (%s)", VIRTUAL_KEYBOARD_NAME, self.uinput.device.path)

    def write_event(self, event_type: int, code: int, value: int) -> None:
        """Write a low-level event and track key state."""
        if event_type == ecodes.EV_KEY:
            if value == 1:
                self._pressed_keys.add(code)
            elif value == 0:
                self._pressed_keys.discard(code)

        self.uinput.write(event_type, code, value)

    def write_key(self, code: int, value: int) -> None:
        """Write an EV_KEY event."""
        self.write_event(ecodes.EV_KEY, code, value)

    def syn(self) -> None:
        """Flush events with SYN_REPORT."""
        self.uinput.syn()

    def release_all(self) -> None:
        """Safety requirement: release all currently held keys to prevent stuck keys."""
        if not self._pressed_keys:
            return

        logger.warning("Releasing %d held virtual key(s): %s", len(self._pressed_keys), list(self._pressed_keys))
        for code in list(self._pressed_keys):
            try:
                self.uinput.write(ecodes.EV_KEY, code, 0)
            except Exception as e:
                logger.error("Error releasing key %s: %s", code, e)
        try:
            self.uinput.syn()
        except Exception:
            pass
        self._pressed_keys.clear()

    def close(self) -> None:
        """Safely release keys and destroy the uinput device."""
        try:
            self.release_all()
        finally:
            if self.uinput:
                self.uinput.close()
                logger.info("Closed virtual keyboard.")


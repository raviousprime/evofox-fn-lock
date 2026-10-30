"""Event translation engine and mapping logic."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from .config import AppConfig
from .mode import FnLockMode, HotkeyTracker

logger = logging.getLogger("evofox-fn-lock.mapper")

EV_SYN = 0
EV_KEY = 1
EV_MSC = 4


class EventMapper:
    """Translates physical keyboard events to virtual keyboard actions."""

    def __init__(self, config: AppConfig, mode_controller: FnLockMode):
        self.config = config
        self.mode = mode_controller
        self.hotkey_tracker = HotkeyTracker(config.hotkey, mode_controller)
        self.mapping = config.mapping
        # Map of currently depressed physical keycode -> emitted virtual keycode
        self._active_mappings: Dict[int, int] = {}

    def translate_event(self, event_type: int, code: int, value: int) -> List[Tuple[int, int, int]]:
        """
        Process an input event and return a list of (event_type, code, value)
        tuples to emit to the virtual keyboard.
        """
        # Non-key events (EV_SYN, EV_MSC, etc.) are forwarded as-is
        if event_type != EV_KEY:
            return [(event_type, code, value)]

        # Check for Fn Lock hotkey toggle (e.g. Ctrl + Alt + F12)
        if self.hotkey_tracker.process_key_event(code, value):
            # Consumed by hotkey handler, do not emit to desktop
            return []

        # Determine target key
        target_code = code

        if value == 1:  # Key Press
            if self.mode.is_locked and code in self.mapping:
                target_code = self.mapping[code]
                logger.debug("Mapped key press 0x%02x -> 0x%02x", code, target_code)
            self._active_mappings[code] = target_code

        elif value == 2:  # Key Repeat
            target_code = self._active_mappings.get(code, self.mapping.get(code, code) if self.mode.is_locked else code)

        elif value == 0:  # Key Release
            # Ensure the release matches the keycode that was pressed
            target_code = self._active_mappings.pop(code, self.mapping.get(code, code) if self.mode.is_locked else code)
            logger.debug("Mapped key release 0x%02x -> 0x%02x", code, target_code)

        return [(EV_KEY, target_code, value)]

    def reset(self) -> None:
        """Reset key state tracking."""
        self._active_mappings.clear()
        self.hotkey_tracker.reset()


"""Fn Lock mode controller and hotkey detection."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Set

from .config import HotkeyConfig, StateConfig

logger = logging.getLogger("evofox-fn-lock.mode")


# Common modifier aliases so Left or Right modifier keys both work seamlessly
MODIFIER_ALIASES = {
    29: {29, 97},    # KEY_LEFTCTRL -> {KEY_LEFTCTRL, KEY_RIGHTCTRL}
    97: {29, 97},    # KEY_RIGHTCTRL -> {KEY_LEFTCTRL, KEY_RIGHTCTRL}
    56: {56, 100},   # KEY_LEFTALT -> {KEY_LEFTALT, KEY_RIGHTALT}
    100: {56, 100},  # KEY_RIGHTALT -> {KEY_LEFTALT, KEY_RIGHTALT}
    42: {42, 54},    # KEY_LEFTSHIFT -> {KEY_LEFTSHIFT, KEY_RIGHTSHIFT}
    54: {42, 54},    # KEY_RIGHTSHIFT -> {KEY_LEFTSHIFT, KEY_RIGHTSHIFT}
}


class FnLockMode:
    """Manages the persistent Fn Lock state."""

    def __init__(self, config: StateConfig):
        self.persist_path = Path(config.persist_path)
        self.fallback_path = Path.home() / ".local" / "state" / "evofox-fn-lock" / "state.json"
        self.default_mode = config.default_fn_lock
        self._last_check = 0.0
        self._cached_mtime = 0.0
        self._is_locked = self._load(config.default_fn_lock)
        logger.info("Initialized Fn Lock state: %s", "LOCKED (Media Mode)" if self._is_locked else "UNLOCKED (F1-F12 Mode)")

    def _get_active_path(self) -> Path:
        if self.persist_path.is_file():
            return self.persist_path
        if self.fallback_path.is_file():
            return self.fallback_path
        return self.persist_path

    def _check_reload(self) -> None:
        active = self._get_active_path()
        try:
            mtime = active.stat().st_mtime
            if mtime != self._cached_mtime:
                self._cached_mtime = mtime
                with open(active, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    val = bool(data.get("fn_lock", self.default_mode))
                    if val != self._is_locked:
                        self._is_locked = val
                        logger.info("Fn Lock updated from %s -> %s", active,
                                    "LOCKED (Media Mode)" if self._is_locked else "UNLOCKED (F1-F12 Mode)")
        except Exception:
            pass

    @property
    def is_locked(self) -> bool:
        import time
        now = time.monotonic()
        if now - self._last_check > 0.2:
            self._last_check = now
            self._check_reload()
        return self._is_locked

    @is_locked.setter
    def is_locked(self, val: bool) -> None:
        self._is_locked = val

    def _load(self, default: bool) -> bool:
        paths = [self.persist_path, self.fallback_path]
        for p in paths:
            if p.is_file():
                try:
                    self._cached_mtime = p.stat().st_mtime
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        val = data.get("fn_lock", default)
                        return bool(val)
                except Exception as e:
                    logger.warning("Could not load state from %s: %s", p, e)
        return default

    def save(self) -> None:
        import time
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.persist_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump({"fn_lock": self._is_locked}, f)
            temp_path.replace(self.persist_path)
            self._cached_mtime = self.persist_path.stat().st_mtime
            logger.debug("State saved to %s", self.persist_path)
        except PermissionError:
            try:
                self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = self.fallback_path.with_suffix(".tmp")
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump({"fn_lock": self._is_locked}, f)
                temp_path.replace(self.fallback_path)
                self._cached_mtime = self.fallback_path.stat().st_mtime
                logger.debug("State saved to fallback %s", self.fallback_path)
            except Exception as e:
                logger.error("Failed to persist state: %s", e)
        except Exception as e:
            logger.error("Failed to persist state to %s: %s", self.persist_path, e)

    def toggle(self) -> bool:
        self.is_locked = not self.is_locked
        self.save()
        logger.info("Fn Lock toggled -> %s", "LOCKED (Media Mode)" if self.is_locked else "UNLOCKED (F1-F12 Mode)")
        return self.is_locked


class HotkeyTracker:
    """Tracks pressed keys and detects trigger combinations."""

    def __init__(self, hotkey_config: HotkeyConfig, mode_controller: FnLockMode):
        self.modifiers = hotkey_config.modifiers
        self.trigger = hotkey_config.trigger
        self.mode = mode_controller
        self.held_keys: Set[int] = set()

    def process_key_event(self, code: int, value: int) -> bool:
        """
        Process a key event. Returns True if this event was consumed as part of
        a hotkey toggle and should NOT be forwarded to the desktop.
        """
        if value == 1:  # Key press
            self.held_keys.add(code)
            if code == self.trigger and self._modifiers_held():
                self.mode.toggle()
                return True
        elif value == 0:  # Key release
            self.held_keys.discard(code)
            # If the released key is the trigger and modifiers are/were held, swallow the release too
            if code == self.trigger and self._modifiers_held():
                return True

        return False

    def _modifiers_held(self) -> bool:
        for mod in self.modifiers:
            equivalent_keys = MODIFIER_ALIASES.get(mod, {mod})
            if not (self.held_keys & equivalent_keys):
                return False
        return True

    def reset(self) -> None:
        self.held_keys.clear()

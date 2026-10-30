"""Physical keyboard grabber and event stream interceptor."""

from __future__ import annotations

import logging
import select
from typing import Optional

try:
    import evdev
    from evdev import ecodes
except ImportError:  # pragma: no cover
    evdev = None  # type: ignore
    ecodes = None  # type: ignore

from .config import AppConfig
from .mapper import EventMapper
from .virtual_keyboard import VirtualKeyboard

logger = logging.getLogger("evofox-fn-lock.interceptor")


class Interceptor:
    """Manages grabbing the physical device and dispatching events."""

    def __init__(self, device: evdev.InputDevice, vkeyboard: VirtualKeyboard, mapper: EventMapper, grab: bool = True):
        self.device = device
        self.vkeyboard = vkeyboard
        self.mapper = mapper
        self.grab = grab
        self.is_grabbed = False

    def start(self) -> None:
        """Grab the physical device to ensure exclusive access."""
        if self.grab:
            try:
                self.device.grab()
                self.is_grabbed = True
                logger.info("Successfully grabbed physical keyboard %s", self.device.name)
            except Exception as e:
                logger.error("Failed to grab physical keyboard %s: %s", self.device.name, e)
                raise

    def stop(self) -> None:
        """Ungrab the physical device and release held keys."""
        if self.is_grabbed:
            try:
                self.device.ungrab()
                self.is_grabbed = False
                logger.info("Released grab on physical keyboard %s", self.device.name)
            except Exception as e:
                logger.warning("Error ungrabbing device %s: %s", self.device.name, e)

        self.mapper.reset()
        self.vkeyboard.release_all()

    def process_one_batch(self, timeout: float = 0.5) -> bool:
        """
        Wait for and process events from the physical keyboard.
        Returns True to continue, False if stopping or error.
        """
        r, _, _ = select.select([self.device.fd], [], [], timeout)
        if not r:
            return True

        for event in self.device.read():
            try:
                translated = self.mapper.translate_event(event.type, event.code, event.value)
                for ev_type, ev_code, ev_val in translated:
                    self.vkeyboard.write_event(ev_type, ev_code, ev_val)
                if event.type == ecodes.EV_SYN:
                    self.vkeyboard.syn()
            except Exception as e:
                logger.error("Error processing event %s: %s", event, e)

        return True


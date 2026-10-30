"""Main daemon entry point for evofox-fn-lock service."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from typing import Optional

if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.config import AppConfig
    from src.device import find_keyboard_device, wait_for_device
    from src.interceptor import Interceptor
    from src.mapper import EventMapper
    from src.mode import FnLockMode
    from src.virtual_keyboard import VirtualKeyboard
else:
    from .config import AppConfig
    from .device import find_keyboard_device, wait_for_device
    from .interceptor import Interceptor
    from .mapper import EventMapper
    from .mode import FnLockMode
    from .virtual_keyboard import VirtualKeyboard

logger = logging.getLogger("evofox-fn-lock")


class FnLockDaemon:
    """Manages daemon lifecycle, event interception, and device reconnection."""

    def __init__(self, config_path: Optional[str] = None, debug: bool = False):
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            level=log_level,
        )

        self.config = AppConfig.load(config_path)
        self.mode = FnLockMode(self.config.state)
        self.running = True
        self.current_interceptor: Optional[Interceptor] = None
        self.current_vkeyboard: Optional[VirtualKeyboard] = None

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGHUP, self._handle_signal)

    def _handle_signal(self, signum: int, _frame) -> None:
        signame = signal.Signals(signum).name
        logger.info("Received signal %s (%d), shutting down...", signame, signum)
        self.running = False

    def run(self) -> None:
        """Main service loop with automatic device reconnection."""
        logger.info("Starting EvoFox Fn Lock Daemon v1.0.0")
        logger.info("Default Fn Lock: %s", "ON (Media Mode)" if self.mode.is_locked else "OFF (Normal F-keys)")

        while self.running:
            physical_dev = None
            try:
                logger.info("Searching for target keyboard...")
                physical_dev = find_keyboard_device(self.config.device)
                if not physical_dev:
                    if not self.running:
                        break
                    time.sleep(2.0)
                    continue

                # Initialize virtual keyboard with mapped additional keys
                additional_keys = list(self.config.mapping.values())
                vkeyboard = VirtualKeyboard(source_device=physical_dev, additional_keys=additional_keys)
                self.current_vkeyboard = vkeyboard

                mapper = EventMapper(self.config, self.mode)
                interceptor = Interceptor(
                    device=physical_dev,
                    vkeyboard=vkeyboard,
                    mapper=mapper,
                    grab=self.config.device.grab,
                )
                self.current_interceptor = interceptor

                interceptor.start()
                logger.info("Keyboard grabbed and forwarding initialized.")

                while self.running:
                    interceptor.process_one_batch(timeout=0.5)

            except OSError as e:
                logger.warning("Device I/O error or disconnected: %s", e, exc_info=True)
            except Exception as e:
                logger.error("Unexpected error in daemon loop: %s", e, exc_info=True)
            finally:
                if self.current_interceptor:
                    try:
                        self.current_interceptor.stop()
                    except Exception:
                        pass
                    self.current_interceptor = None

                if self.current_vkeyboard:
                    try:
                        self.current_vkeyboard.close()
                    except Exception:
                        pass
                    self.current_vkeyboard = None

                if physical_dev:
                    try:
                        physical_dev.close()
                    except Exception:
                        pass

                if self.running:
                    time.sleep(2.0)

        logger.info("Daemon exited cleanly.")


def main() -> None:
    parser = argparse.ArgumentParser(description="EvoFox Fn Lock Userspace Daemon")
    parser.add_argument("--config", "-c", type=str, default=None, help="Path to config.toml")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug logging")
    parser.add_argument("--status", action="store_true", help="Print current Fn Lock state and exit")
    parser.add_argument("--toggle", action="store_true", help="Toggle Fn Lock state and exit")

    args = parser.parse_args()

    if args.status or args.toggle:
        config = AppConfig.load(args.config)
        mode = FnLockMode(config.state)
        if args.toggle:
            new_state = mode.toggle()
            print(f"Fn Lock toggled -> {'ON (Media Mode)' if new_state else 'OFF (F1-F12 Mode)'}")
        else:
            print(f"Fn Lock is currently: {'ON (Media Mode)' if mode.is_locked else 'OFF (F1-F12 Mode)'}")
        sys.exit(0)

    daemon = FnLockDaemon(config_path=args.config, debug=args.debug)
    daemon.run()


if __name__ == "__main__":
    main()

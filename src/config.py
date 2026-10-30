"""Configuration parser and validator for evofox-fn-lock."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

try:
    from evdev import ecodes
except ImportError:  # pragma: no cover
    ecodes = None  # type: ignore


DEFAULT_PERSIST_PATH = "/var/lib/evofox-fn-lock/state.json"
DEFAULT_CONFIG_PATHS = [
    "/etc/evofox-fn-lock/config.toml",
    "./config/config.toml",
    os.path.expanduser("~/.config/evofox-fn-lock/config.toml"),
]


def resolve_keycode(key_repr: str | int) -> int:
    """Resolve a key name (e.g. 'KEY_F1') or int to an integer evdev keycode."""
    if isinstance(key_repr, int):
        return key_repr
    if key_repr.isdigit():
        return int(key_repr)

    name = key_repr.strip().upper()
    if not name.startswith("KEY_"):
        name = f"KEY_{name}"

    if ecodes and hasattr(ecodes, name):
        return getattr(ecodes, name)

    # Fallback lookup for standard keys if evdev is not yet loaded
    fallback_codes: dict[str, int] = {
        "KEY_ESC": 1, "KEY_1": 2, "KEY_2": 3, "KEY_3": 4, "KEY_4": 5,
        "KEY_5": 6, "KEY_6": 7, "KEY_7": 8, "KEY_8": 9, "KEY_9": 10,
        "KEY_0": 11, "KEY_ENTER": 28, "KEY_LEFTCTRL": 29, "KEY_LEFTSHIFT": 42,
        "KEY_RIGHTSHIFT": 54, "KEY_LEFTALT": 56, "KEY_SPACE": 57,
        "KEY_F1": 59, "KEY_F2": 60, "KEY_F3": 61, "KEY_F4": 62, "KEY_F5": 63,
        "KEY_F6": 64, "KEY_F7": 65, "KEY_F8": 66, "KEY_F9": 67, "KEY_F10": 68,
        "KEY_F11": 87, "KEY_F12": 88, "KEY_RIGHTCTRL": 97, "KEY_RIGHTALT": 100,
        "KEY_MUTE": 113, "KEY_VOLUMEDOWN": 114, "KEY_VOLUMEUP": 115,
        "KEY_CALC": 140, "KEY_FILE": 144, "KEY_MAIL": 155, "KEY_HOMEPAGE": 172,
        "KEY_NEXTSONG": 163, "KEY_PLAYPAUSE": 164, "KEY_PREVIOUSSONG": 165,
        "KEY_STOPCD": 166, "KEY_CONFIG": 171,
    }
    if name in fallback_codes:
        return fallback_codes[name]

    raise ValueError(f"Unknown key name: {key_repr}")


@dataclass
class DeviceConfig:
    vendor_id: Optional[int] = 0x1A2C
    product_id: Optional[int] = 0x4C5E
    name: str = "SEMICO USB Keyboard"
    grab: bool = True


@dataclass
class StateConfig:
    persist_path: str = DEFAULT_PERSIST_PATH
    default_fn_lock: bool = True


@dataclass
class HotkeyConfig:
    modifiers: List[int] = field(default_factory=lambda: [resolve_keycode("KEY_LEFTCTRL"), resolve_keycode("KEY_LEFTALT")])
    trigger: int = field(default_factory=lambda: resolve_keycode("KEY_F12"))


@dataclass
class AppConfig:
    device: DeviceConfig = field(default_factory=DeviceConfig)
    state: StateConfig = field(default_factory=StateConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    mapping: Dict[int, int] = field(default_factory=dict)
    raw_config: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "AppConfig":
        """Load configuration from file or use default search paths."""
        found_path: Optional[Path] = None

        if config_path:
            p = Path(config_path)
            if p.is_file():
                found_path = p
        else:
            for candidate in DEFAULT_CONFIG_PATHS:
                p = Path(candidate)
                if p.is_file():
                    found_path = p
                    break

        data: Dict[str, Any] = {}
        if found_path:
            with open(found_path, "rb") as f:
                data = tomllib.load(f)

        # Device config
        dev_data = data.get("device", {})
        vid = dev_data.get("vendor_id", "1a2c")
        pid = dev_data.get("product_id", "4c5e")
        if isinstance(vid, str):
            vid = int(vid, 16) if vid else None
        if isinstance(pid, str):
            pid = int(pid, 16) if pid else None

        device_config = DeviceConfig(
            vendor_id=vid,
            product_id=pid,
            name=dev_data.get("name", "SEMICO USB Keyboard"),
            grab=bool(dev_data.get("grab", True)),
        )

        # State config
        st_data = data.get("state", {})
        state_config = StateConfig(
            persist_path=st_data.get("persist_path", DEFAULT_PERSIST_PATH),
            default_fn_lock=bool(st_data.get("default_fn_lock", True)),
        )

        # Hotkey config
        hk_data = data.get("hotkey", {})
        raw_mods = hk_data.get("modifiers", ["KEY_LEFTCTRL", "KEY_LEFTALT"])
        raw_trig = hk_data.get("trigger", "KEY_F12")

        hotkey_config = HotkeyConfig(
            modifiers=[resolve_keycode(m) for m in raw_mods],
            trigger=resolve_keycode(raw_trig),
        )

        # Mapping config
        raw_map = data.get("mapping", {
            "KEY_F1": "KEY_CONFIG",
            "KEY_F2": "KEY_VOLUMEDOWN",
            "KEY_F3": "KEY_VOLUMEUP",
            "KEY_F4": "KEY_MUTE",
            "KEY_F5": "KEY_STOPCD",
            "KEY_F6": "KEY_PREVIOUSSONG",
            "KEY_F7": "KEY_PLAYPAUSE",
            "KEY_F8": "KEY_NEXTSONG",
            "KEY_F9": "KEY_MAIL",
            "KEY_F10": "KEY_HOMEPAGE",
            "KEY_F11": "KEY_FILE",
            "KEY_F12": "KEY_CALC",
        })

        mapping: Dict[int, int] = {}
        for src_key, dst_key in raw_map.items():
            src_code = resolve_keycode(src_key)
            dst_code = resolve_keycode(dst_key)
            mapping[src_code] = dst_code

        return cls(
            device=device_config,
            state=state_config,
            hotkey=hotkey_config,
            mapping=mapping,
            raw_config=data,
        )


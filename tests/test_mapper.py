"""Unit tests for EventMapper and ModeController."""

import tempfile
import unittest
from pathlib import Path

from src.config import AppConfig, DeviceConfig, HotkeyConfig, StateConfig, resolve_keycode
from src.mapper import EV_KEY, EV_SYN, EventMapper
from src.mode import FnLockMode


class TestEventMapper(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "test_state.json"

        self.config = AppConfig(
            device=DeviceConfig(),
            state=StateConfig(persist_path=str(self.state_file), default_fn_lock=True),
            hotkey=HotkeyConfig(
                modifiers=[resolve_keycode("KEY_LEFTCTRL"), resolve_keycode("KEY_LEFTALT")],
                trigger=resolve_keycode("KEY_F12"),
            ),
            mapping={
                resolve_keycode("KEY_F1"): resolve_keycode("KEY_CONFIG"),
                resolve_keycode("KEY_F2"): resolve_keycode("KEY_VOLUMEDOWN"),
                resolve_keycode("KEY_F3"): resolve_keycode("KEY_VOLUMEUP"),
                resolve_keycode("KEY_F4"): resolve_keycode("KEY_MUTE"),
                resolve_keycode("KEY_F11"): resolve_keycode("KEY_FILE"),
                resolve_keycode("KEY_F12"): resolve_keycode("KEY_CALC"),
            },
        )
        self.mode = FnLockMode(self.config.state)
        self.mapper = EventMapper(self.config, self.mode)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_non_key_events_forwarded_directly(self):
        # EV_SYN
        result = self.mapper.translate_event(EV_SYN, 0, 0)
        self.assertEqual(result, [(EV_SYN, 0, 0)])

    def test_regular_typing_keys_unmodified(self):
        key_a = resolve_keycode("KEY_1")
        # Press
        res_press = self.mapper.translate_event(EV_KEY, key_a, 1)
        self.assertEqual(res_press, [(EV_KEY, key_a, 1)])
        # Release
        res_rel = self.mapper.translate_event(EV_KEY, key_a, 0)
        self.assertEqual(res_rel, [(EV_KEY, key_a, 0)])

    def test_fn_lock_on_maps_f_keys(self):
        self.assertTrue(self.mode.is_locked)
        f1 = resolve_keycode("KEY_F1")
        config_key = resolve_keycode("KEY_CONFIG")

        # Press F1
        res = self.mapper.translate_event(EV_KEY, f1, 1)
        self.assertEqual(res, [(EV_KEY, config_key, 1)])

        # Repeat F1
        res = self.mapper.translate_event(EV_KEY, f1, 2)
        self.assertEqual(res, [(EV_KEY, config_key, 2)])

        # Release F1
        res = self.mapper.translate_event(EV_KEY, f1, 0)
        self.assertEqual(res, [(EV_KEY, config_key, 0)])

    def test_fn_lock_off_passes_f_keys(self):
        self.mode.toggle()
        self.assertFalse(self.mode.is_locked)
        f1 = resolve_keycode("KEY_F1")

        # Press F1
        res = self.mapper.translate_event(EV_KEY, f1, 1)
        self.assertEqual(res, [(EV_KEY, f1, 1)])

        # Release F1
        res = self.mapper.translate_event(EV_KEY, f1, 0)
        self.assertEqual(res, [(EV_KEY, f1, 0)])

    def test_hotkey_toggle_swallows_event(self):
        ctrl = resolve_keycode("KEY_LEFTCTRL")
        alt = resolve_keycode("KEY_LEFTALT")
        f12 = resolve_keycode("KEY_F12")

        self.assertTrue(self.mode.is_locked)

        # Press Ctrl
        res = self.mapper.translate_event(EV_KEY, ctrl, 1)
        self.assertEqual(res, [(EV_KEY, ctrl, 1)])

        # Press Alt
        res = self.mapper.translate_event(EV_KEY, alt, 1)
        self.assertEqual(res, [(EV_KEY, alt, 1)])

        # Press F12 while Ctrl+Alt held -> Triggers toggle!
        res = self.mapper.translate_event(EV_KEY, f12, 1)
        self.assertEqual(res, [], "Hotkey trigger event must be swallowed")

        # Fn Lock must now be toggled to False
        self.assertFalse(self.mode.is_locked)

        # Release F12
        res = self.mapper.translate_event(EV_KEY, f12, 0)
        self.assertEqual(res, [], "Hotkey trigger release must also be swallowed")

    def test_press_release_consistency_across_toggle(self):
        """If key is pressed in locked mode, but unlocked before release, release must still match pressed key."""
        f2 = resolve_keycode("KEY_F2")
        vol_down = resolve_keycode("KEY_VOLUMEDOWN")

        self.assertTrue(self.mode.is_locked)
        # Press F2 -> mapped to VOLUMEDOWN
        res = self.mapper.translate_event(EV_KEY, f2, 1)
        self.assertEqual(res, [(EV_KEY, vol_down, 1)])

        # Toggle mode while key is held
        self.mode.toggle()
        self.assertFalse(self.mode.is_locked)

        # Release F2 -> should still emit VOLUMEDOWN release to prevent stuck keys!
        res = self.mapper.translate_event(EV_KEY, f2, 0)
        self.assertEqual(res, [(EV_KEY, vol_down, 0)])


if __name__ == "__main__":
    unittest.main()


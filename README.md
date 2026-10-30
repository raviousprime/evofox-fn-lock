# EvoFox Fn Lock Daemon for Ubuntu 24.04

A robust Linux userspace input daemon built with `evdev` and `uinput` that provides a persistent **Fn Lock** toggle for EvoFox (SEMICO) keyboards.

| Mode | Physical F1–F12 | Result |
| :--- | :--- | :--- |
| **Fn Lock ON** (Default) | F1–F12 | Media / Shortcut actions |
| **Fn Lock OFF** | F1–F12 | Standard F1–F12 key events |

---

## 1. Verified & Configured F1–F12 Mappings

The mapping is pre-configured in `config/config.toml` based on EvoFox keyboard layouts and decoded hardware capabilities from `/proc/bus/input/devices`:

| Physical Key | Default Mapped Action | Linux Keycode | Note |
| :--- | :--- | :--- | :--- |
| **F1** | Media Player | `KEY_CONFIG` | Launch audio/media player |
| **F2** | Volume Down | `KEY_VOLUMEDOWN` | Lower audio volume |
| **F3** | Volume Up | `KEY_VOLUMEUP` | Raise audio volume |
| **F4** | Mute | `KEY_MUTE` | Toggle audio mute |
| **F5** | Stop | `KEY_STOPCD` | Stop media playback |
| **F6** | Previous Track | `KEY_PREVIOUSSONG` | Skip to previous track |
| **F7** | Play / Pause | `KEY_PLAYPAUSE` | Toggle play/pause |
| **F8** | Next Track | `KEY_NEXTSONG` | Skip to next track |
| **F9** | Email Client | `KEY_MAIL` | Open default email app |
| **F10** | Web Browser / Home | `KEY_HOMEPAGE` | Open web browser / home |
| **F11** | File Manager / Computer | `KEY_FILE` | Default Explorer/Files shortcut |
| **F12** | Calculator | `KEY_CALC` | Open Calculator |

> **Customizing any key:** You can change any mapping in `/etc/evofox-fn-lock/config.toml` at any time without recompiling.

---

## 2. Optional: Capturing `evtest` for Fn+F11 / Fn+F12

If you want to verify what your keyboard hardware emits when physically holding `Fn + F11` and `Fn + F12`:

1. Run:
   ```bash
   sudo evtest /dev/input/event3
   ```
2. Press `Fn + F11` and release. Note the `MSC_SCAN` and `KEY_*` lines.
3. Press `Fn + F12` and release. Note the `MSC_SCAN` and `KEY_*` lines.
4. If they differ from `KEY_FILE` or `KEY_CALC`, simply edit `/etc/evofox-fn-lock/config.toml` and run `sudo systemctl restart evofox-fn-lock`.

---

## 3. Installation

Run the installer with root privileges:

```bash
cd /var/www/linux-extensions/evofox-fn-lock
sudo ./install.sh
```

The installer will:
1. Load and configure the `uinput` module.
2. Create an isolated Python environment at `/opt/evofox-fn-lock/venv` with `evdev`.
3. Install configuration to `/etc/evofox-fn-lock/config.toml`.
4. Install and start the systemd service `evofox-fn-lock.service`.
5. Install the `/usr/local/bin/evofox-fn-lock` CLI tool.

---

## 4. Usage & Controls

### Hotkey Toggle
- Press **`Ctrl + Alt + F12`** at any time to toggle between **Fn Lock ON** (Media Mode) and **Fn Lock OFF** (Function Mode).
- The state is persisted in `/var/lib/evofox-fn-lock/state.json` and survives reboots.

### CLI Commands
Check current mode:
```bash
evofox-fn-lock --status
```

Toggle mode via terminal:
```bash
evofox-fn-lock --toggle
```

Check service status and logs:
```bash
systemctl status evofox-fn-lock.service
journalctl -u evofox-fn-lock.service -f
```

---

## 5. Architecture & Safety Features

- **Surgical device matching:** Grabs only the main keyboard interface (`input0`, `event2`). Never grabs the consumer control, system control, or other connected keyboards/mice.
- **Self-avoidance:** Automatically ignores its own virtual keyboard device (`EvoFox Fn Lock Virtual Keyboard`).
- **Full passthrough:** Transparently forwards all regular typing keys, modifiers, repeats, and non-key events (`EV_SYN`, `EV_MSC`). Normal typing latency is undetectable.
- **Stuck key prevention:** Tracks every depressed virtual key. On shutdown, crash, or device disconnect, all active keys are immediately released with `value=0` and synchronized before exit.
- **Device hotplug & reconnection:** If the keyboard is unplugged or enters sleep mode, the daemon smoothly waits and re-acquires it once re-attached.

---

## 6. Uninstallation

To cleanly remove the daemon and ungrab the keyboard:

```bash
cd /var/www/linux-extensions/evofox-fn-lock
sudo ./uninstall.sh
```


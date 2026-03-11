# MacroPad Controller

Tiny Python 3.11+ serial controller and Windows tray app for ATmega-based macropads.

The board protocol is ASCII line-based and newline terminated (`\n`):

- Board -> PC: `READY`, `SW=0`, `SW=1`, optional `LED=0`, `LED=1`, `KEY=row,col,state`, `ENC=+1/-1`
- PC -> Board: `LED=0`, `LED=1`, `LED=T`

## Features

- Serial port discovery with explicit `--port` or `--hint` matching
- Windows GUI launcher: `macropad-controller`
- Close-to-tray desktop behavior on Windows
- Single background instance with restore-on-second-launch
- Optional Windows autostart in hidden tray mode
- User data stored in `%APPDATA%/macropad-ble`
- Minimal commands:
  - `macropad-ble list`
  - `macropad-ble monitor`
  - `macropad-ble gui`
  - `macropad-ble listen`
  - `macropad-ble led on|off|toggle`
  - `macropad-ble status`
- Optional switch duplicate filter (`dedupe_ms`, default 100ms)
- Auto-reconnect in monitor mode (1s to 5s retry window)
- Clean Ctrl+C shutdown
- Optional debug logging of raw `RX`/`TX` lines (`--log debug`)
- `gui` uses a dark-mode editor UI
  - Key/action binding editor + script tab
  - 10 profile slots with rename/import/export
  - Serial `KEY` and `ENC` events reflected live
  - Semi-dark gray key tiles (non-animated)

## Install

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e .        # Windows PowerShell
# or:
.venv/bin/python -m pip install -e .            # Linux/macOS
```

Windows GUI entrypoint:

```bash
macropad-controller
macropad-controller --hidden
```

When launched through `macropad-controller` on Windows:

- closing the window hides it to the system tray
- tray menu exposes `Open`, `Reconnect`, `Launch on Windows startup`, and `Exit`
- a second launch restores the running instance instead of creating another one

## Config

Default config resolution when `--config` is not provided:

1. `./macropad-ble.toml`
2. Windows: `%APPDATA%/macropad-ble/config.toml`
3. macOS: `~/Library/Application Support/macropad-ble/config.toml`
4. Linux: `${XDG_CONFIG_HOME:-~/.config}/macropad-ble/config.toml`

Example:

```toml
port = ""
hint = "Curiosity"
baud = 115200
ack_timeout = 0.75
dedupe_ms = 100
log_level = "INFO"
```

## Usage

```bash
macropad-ble --hint Curiosity list
macropad-ble --hint Curiosity monitor
macropad-ble --hint Curiosity gui
macropad-ble --hint Curiosity listen
macropad-ble --hint Curiosity led on
macropad-ble --hint Curiosity led off
macropad-ble --hint Curiosity led toggle
macropad-ble --hint Curiosity status
macropad-controller --port COM13
```

`listen` prints every incoming serial line (`RX ...`) and accepts keyboard input:

- `1` -> send `LED=1`
- `0` -> send `LED=0`
- `q` -> quit

`gui` key placement uses board row/col coordinates rendered in a 3x4 grid by default.

You can always override discovery with an explicit port:

```bash
macropad-ble --port COM12 monitor
```

## Desktop App Data

GUI profile/state data is stored under:

- Windows: `%APPDATA%/macropad-ble`

On first launch, the GUI migrates legacy local `./profiles` data into the new app-data location if the new location is still empty.

## Windows Packaging

Build a windowed packaged app:

```bash
make package
```

Install the packaged app into `%LOCALAPPDATA%\MacroPad Controller` and enable autostart:

```bash
make install-windows
```

This also creates a Start menu shortcut named `MacroPad Controller`, so `Win`, type `MacroPad Controller`, `Enter` launches or restores it.

Remove the installed app and its autostart entry:

```bash
make uninstall-windows
```

## Make Targets

- `make dev` - create venv + install editable package with test deps
- `make run` - launch the GUI app via `macropad_ble.gui_app`
- `make listen`
- `make package`
- `make install-windows`
- `make uninstall-windows`

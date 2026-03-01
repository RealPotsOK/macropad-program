# macropad-ble

Tiny Python 3.11+ serial controller for ATmega boards.

The board protocol is ASCII line-based and newline terminated (`\n`):

- Board -> PC: `READY`, `SW=0`, `SW=1`, optional `LED=0`, `LED=1`
- PC -> Board: `LED=0`, `LED=1`, `LED=T`

## Features

- Serial port discovery with explicit `--port` or `--hint` matching
- Minimal commands:
  - `macropad-ble list`
  - `macropad-ble monitor`
  - `macropad-ble listen`
  - `macropad-ble led on|off|toggle`
  - `macropad-ble status`
- Optional switch duplicate filter (`dedupe_ms`, default 100ms)
- Auto-reconnect in monitor mode (1s to 5s retry window)
- Clean Ctrl+C shutdown
- Optional debug logging of raw `RX`/`TX` lines (`--log debug`)

## Install

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e .        # Windows PowerShell
# or:
.venv/bin/python -m pip install -e .            # Linux/macOS
```

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
baud = 9600
ack_timeout = 0.75
dedupe_ms = 100
log_level = "INFO"
```

## Usage

```bash
macropad-ble --hint Curiosity list
macropad-ble --hint Curiosity monitor
macropad-ble --hint Curiosity listen
macropad-ble --hint Curiosity led on
macropad-ble --hint Curiosity led off
macropad-ble --hint Curiosity led toggle
macropad-ble --hint Curiosity status
```

`listen` prints every incoming serial line (`RX ...`) and accepts keyboard input:

- `1` -> send `LED=1`
- `0` -> send `LED=0`
- `q` -> quit

You can always override discovery with an explicit port:

```bash
macropad-ble --port COM12 monitor
```

## Make Targets

- `make dev` - create venv + install editable package with test deps
- `make list`
- `make monitor`
- `make listen`
- `make status`
- `make led-on`
- `make led-off`
- `make led-toggle`
- `make test`
# macropad-program

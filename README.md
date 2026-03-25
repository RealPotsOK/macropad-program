# MacroPad Controller

Desktop controller + CLI for serial macropads (ATmega, RP2040/Pico, and similar boards).

- Python package name: `macropad`
- GUI launcher: `macropad-controller`
- Primary target: Windows 10/11 (cross-platform CLI where supported)

## What It Does

- Connects to a serial macropad and parses board events (`KEY=`, `ENC=`, `ENC_SW=`, etc.).
- Provides a Qt desktop app for key mapping, profiles, scripts, diagnostics, setup, and stats.
- Supports action types like keyboard, file, volume mixer, profile changes, window control, and STEP blocks.
- Supports Windows tray behavior and Windows packaging.

## Hardware Compatibility

This app is **MCU-agnostic**. It works with any board if the board:

- appears as a serial port
- uses the selected baud rate
- sends expected line formats
- accepts expected command formats

So yes, it can work with Raspberry Pi Pico firmware too, as long as that firmware speaks the same serial protocol.

Most board-specific behavior can be configured in the app (no code edits needed):

- port/hint/baud connection settings
- key rows/cols
- board-key to virtual-key mapping (manual or learn/auto-setup)
- encoder enabled + invert direction
- screen enabled + output format (`prefix`, `line separator`, `end token`)
- setup profiles (save/load different hardware mappings)

## Serial Protocol (Current)

Line-based ASCII over UART (newline-terminated).

Examples:

- Board -> PC:
  - `READY`
  - `KEY=0,1,1`
  - `KEY=0,1,0`
  - `ENC=+1`
  - `ENC=-1`
  - `ENC_SW=1`
  - `ENC_SW=0`
- PC -> Board:
  - `TXT:Profile 2|Volume 75`
  - `CLR`

## Requirements

- Python 3.11+
- Windows 10/11 recommended for full feature set
- Optional Windows-only integrations depend on:
  - `pycaw`
  - `winsdk`
  - `keyboard`

## Quick Start (Development)

```powershell
make dev
make run
```

If `make` is not installed on Windows, run the equivalent commands directly:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e .[dev]
.venv\Scripts\python.exe -m macropad.gui_app --port COM13 --baud 9600
```

Useful targets:

- `make run` - launch GUI (`python -m macropad.gui_app`)
- `make listen` - raw serial monitor + basic send controls
- `make package` - build packaged Windows app (PyInstaller)
- `make install` - install packaged app into `%LOCALAPPDATA%\MacroPad Controller`
- `make uninstall` - remove installed packaged app/autostart entry
- `make install-editable` - editable install without dev extras
- `make help` - print all common targets

## CLI Usage

Find your port first (instead of hardcoding `COM13`):

```powershell
.venv/Scripts/python.exe -m macropad list
```

```powershell
.venv/Scripts/python.exe -m macropad --port COM13 --baud 9600 list
.venv/Scripts/python.exe -m macropad --port COM13 --baud 9600 monitor
.venv/Scripts/python.exe -m macropad --port COM13 --baud 9600 listen
.venv/Scripts/python.exe -m macropad --port COM13 --baud 9600 status
.venv/Scripts/python.exe -m macropad --port COM13 --baud 9600 led on
```

Or installed script entrypoint:

```powershell
macropad --port COM13 --baud 9600 monitor
```

## GUI Usage

```powershell
macropad-controller
macropad-controller --hidden
```

Tip: if `--port` is omitted, the app can still connect by `--hint` matching.

## Setup "Learn" Scope

The Setup page can learn/map which **physical board key** corresponds to which **virtual key tile** in the UI.

It does **not** automatically learn brand-new serial message formats/protocols by itself.
If your firmware uses different incoming event tokens/payload shapes (not `KEY=...`, `ENC=...`, etc.), code updates are still required.

## Configuration

Project/local config file name:

- `macropad.toml`

Lookup order when `--config` is not provided:

1. `./macropad.toml`
2. `./macropad-ble.toml` (legacy)
3. `%APPDATA%/macropad/config.toml`
4. `%APPDATA%/macropad-ble/config.toml` (legacy)

Example:

```toml
port = "COM13"
hint = "Curiosity"
baud = 9600
ack_timeout = 0.75
dedupe_ms = 100
log_level = "INFO"
```

For minimal setup, only `port` and `baud` are usually required.

## Repository Layout

```text
src/macropad/              # App package
  core/                    # Action/profile/step logic
  serial/                  # Serial protocol + transport
  qt/                      # PySide6 UI + controllers/services
  commands/                # CLI command handlers
scripts/                   # Packaging/install helper scripts
tests/                     # Pytest test suite
assets/                    # Icons/images
```

## Where Your Data Is

Runtime user data is stored outside the repo in:

- `%APPDATA%\macropad`

That is where profiles/app state/runtime script files are read from when the desktop app runs.

## Running Tests

```powershell
.venv/Scripts/python.exe -m pytest
```

## Packaging (Windows)

```powershell
make package
make install
```

Packaged app name:

- `MacroPad Controller.exe`

## GitHub Notes

- `.gitignore` excludes local runtime data (`profiles/`), build artifacts, caches, and virtual envs.
- If you already tracked generated files earlier, remove them from git index before first public push:

```powershell
git rm -r --cached dist build .venv profiles
git commit -m "chore: stop tracking local/build artifacts"
```

## License

MIT. See [LICENSE](LICENSE).

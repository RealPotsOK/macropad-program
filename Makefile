PYTHON ?= python
VENV ?= .venv

ifeq ($(OS),Windows_NT)
VENV_PY := $(VENV)/Scripts/python.exe
else
VENV_PY := $(VENV)/bin/python
endif

PIP := $(VENV_PY) -m pip
APP := $(VENV_PY) -m macropad_ble
ARGS ?=
PORT ?=
HINT ?=
BAUD ?=
ACK_TIMEOUT ?=
DEDUPE_MS ?=
LOG ?=
GLOBAL_ARGS = $(if $(PORT),--port $(PORT),) $(if $(HINT),--hint $(HINT),) $(if $(BAUD),--baud $(BAUD),) $(if $(ACK_TIMEOUT),--ack-timeout $(ACK_TIMEOUT),) $(if $(DEDUPE_MS),--dedupe-ms $(DEDUPE_MS),) $(if $(LOG),--log $(LOG),) $(ARGS)

.PHONY: venv install dev list monitor listen status led-on led-off led-toggle test clean

venv: $(VENV_PY)

$(VENV_PY):
	$(PYTHON) -m venv $(VENV)

install: $(VENV_PY)
	$(PIP) install --upgrade pip
	$(PIP) install -e .

dev: $(VENV_PY)
	$(PIP) install --upgrade pip
	$(PIP) install -e .[dev]

list:
	$(APP) $(GLOBAL_ARGS) list

monitor:
	$(APP) $(GLOBAL_ARGS) monitor

listen:
	$(APP) $(GLOBAL_ARGS) listen

status:
	$(APP) $(GLOBAL_ARGS) status

led-on:
	$(APP) $(GLOBAL_ARGS) led on

led-off:
	$(APP) $(GLOBAL_ARGS) led off

led-toggle:
	$(APP) $(GLOBAL_ARGS) led toggle

test: dev
	$(VENV_PY) -m pytest

clean:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in ['.pytest_cache', 'build', 'dist', 'src/macropad_ble.egg-info'] if pathlib.Path(p).exists()]; [shutil.rmtree(p, ignore_errors=True) for root in ['src', 'tests'] for p in pathlib.Path(root).rglob('__pycache__')]"

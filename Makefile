PYTHON ?= python
VENV ?= .venv

ifeq ($(OS),Windows_NT)
VENV_PY := $(VENV)/Scripts/python.exe
else
VENV_PY := $(VENV)/bin/python
endif
PIP := $(VENV_PY) -m pip

APP := $(VENV_PY) -m macropad
GUI_APP := $(VENV_PY) -m macropad.gui_app
ARGS ?=
PORT ?= COM13
HINT ?=
BAUD ?= 9600
ACK_TIMEOUT ?=
DEDUPE_MS ?=
LOG ?=
GLOBAL_ARGS = $(if $(PORT),--port $(PORT),) $(if $(HINT),--hint $(HINT),) $(if $(BAUD),--baud $(BAUD),) $(if $(ACK_TIMEOUT),--ack-timeout $(ACK_TIMEOUT),) $(if $(DEDUPE_MS),--dedupe-ms $(DEDUPE_MS),) $(if $(LOG),--log $(LOG),) $(ARGS)

.DEFAULT_GOAL := run
.PHONY: help venv install-editable install dev run listen package uninstall

help:
	@echo "Targets:"
	@echo "  make dev             - create venv and install editable package with dev deps"
	@echo "  make run             - launch GUI app"
	@echo "  make listen          - run serial listen mode"
	@echo "  make package         - build Windows packaged app"
	@echo "  make install         - install packaged app to LocalAppData"
	@echo "  make uninstall       - uninstall packaged app"
	@echo "  make install-editable- editable install only"

venv:
	$(PYTHON) -m venv $(VENV)

install-editable: venv
	$(PIP) install --upgrade pip
	$(PIP) install -e .

dev: venv
	$(PIP) install --upgrade pip
	$(PIP) install -e .[dev]

run:
	$(GUI_APP) $(GLOBAL_ARGS)

listen:
	$(APP) $(GLOBAL_ARGS) listen

package: venv
	powershell -ExecutionPolicy Bypass -File scripts/package_windows_app.ps1 -Python "$(VENV_PY)"

install:
	powershell -ExecutionPolicy Bypass -File scripts/install_windows_app.ps1 -Build -Python "$(VENV_PY)"

uninstall:
	powershell -ExecutionPolicy Bypass -File scripts/uninstall_windows_app.ps1

from __future__ import annotations

import asyncio

from ...platform.autostart import is_autostart_enabled


class MainWindowControllerMixin:
    def _bind_controller_signals(self) -> None:
        self.controller.portsChanged.connect(self._on_ports_changed)
        self.controller.connectionStateChanged.connect(self._on_connection_state)
        self.controller.logMessage.connect(self._on_log_message)
        self.controller.profileNameChanged.connect(self._on_profile_name)
        self.controller.profileSlotChanged.connect(self._on_profile_slot)
        self.controller.lastPacketChanged.connect(self._on_last_packet)
        self.controller.encoderChanged.connect(self._on_encoder_status)
        self.controller.autoConnectChanged.connect(self._on_auto_connect_changed)

    def _sync_header_from_controller(self) -> None:
        self._on_ports_changed(self._current_port_choices())
        self._set_text(self._hint_edit, str(getattr(self.controller, "selected_hint", "") or ""))
        self._set_spin_value(self._baud_spin, int(getattr(self.controller, "selected_baud", self.settings.baud)))
        self._set_spin_value(self._profile_spin, int(getattr(self.controller, "profile_slot", 1)))
        self._refresh_audio_outputs()

        app_state = getattr(getattr(self.controller, "store", None), "app_state", None)
        auto_connect = bool(getattr(app_state, "auto_connect", False))
        self._set_checkbox_value(self._auto_connect_check, auto_connect)
        self._set_checkbox_value(self._learn_mode_check, bool(getattr(self.controller, "learn_mode", False)))

        set_learn = getattr(self.controller_page, "set_learn_mode_checked", None)
        if callable(set_learn):
            set_learn(self._learn_mode_check.isChecked())
        self._on_connection_state("disconnected")

    def _run_controller_call(self, method_name: str) -> None:
        method = getattr(self.controller, method_name, None)
        if not callable(method):
            return
        result = method()
        if asyncio.iscoroutine(result):
            asyncio.create_task(result)

    def _on_connect_toggle_clicked(self) -> None:
        state = str(getattr(self, "_connection_state", "disconnected")).strip().lower()
        if state in {"connected", "connecting", "reconnecting"}:
            self._run_controller_call("disconnect")
        else:
            self._run_controller_call("connect")

    def _on_port_changed(self, index: int) -> None:
        set_selected_port = getattr(self.controller, "set_selected_port", None)
        if callable(set_selected_port):
            set_selected_port(str(self._port_combo.itemData(index) or ""))
        self._refresh_status()

    def _on_hint_changed(self, text: str) -> None:
        set_selected_hint = getattr(self.controller, "set_selected_hint", None)
        if callable(set_selected_hint):
            set_selected_hint(text)
        self._refresh_status()

    def _on_baud_changed(self, value: int) -> None:
        set_selected_baud = getattr(self.controller, "set_selected_baud", None)
        if callable(set_selected_baud):
            set_selected_baud(value)
        self._refresh_status()

    def _on_profile_changed(self, value: int) -> None:
        set_profile_slot = getattr(self.controller, "set_profile_slot", None)
        if callable(set_profile_slot):
            set_profile_slot(value)

    def _refresh_audio_outputs(self) -> None:
        list_outputs = getattr(getattr(self, "audio_player", None), "list_output_devices", None)
        devices = list_outputs() if callable(list_outputs) else []
        selected = str(getattr(self.controller, "selected_audio_output", "") or "").strip()
        self._audio_output_combo.blockSignals(True)
        self._audio_output_combo.clear()
        self._audio_output_combo.addItem("System Default", "")
        for device in devices:
            device_id = str(getattr(device, "device_id", "") or "").strip()
            if not device_id:
                continue
            name = str(getattr(device, "name", "") or device_id).strip()
            if bool(getattr(device, "is_default", False)):
                name = f"{name} (Default)"
            self._audio_output_combo.addItem(name, device_id)
        index = self._audio_output_combo.findData(selected)
        if index < 0:
            index = 0
        self._audio_output_combo.setCurrentIndex(index)
        self._audio_output_combo.blockSignals(False)

    def _on_audio_output_changed(self, index: int) -> None:
        device_id = str(self._audio_output_combo.itemData(index) or "").strip()
        set_output = getattr(getattr(self, "audio_player", None), "set_output_device", None)
        ok = bool(set_output(device_id)) if callable(set_output) else False
        if not ok:
            self._status_message.setText("Audio output device is unavailable.")
            self._refresh_audio_outputs()
            return
        persist = getattr(self.controller, "set_audio_output_device", None)
        if callable(persist):
            persist(device_id)
        self._refresh_status()

    def _on_auto_connect_toggled(self, enabled: bool) -> None:
        set_auto_connect = getattr(self.controller, "set_auto_connect", None)
        if callable(set_auto_connect):
            set_auto_connect(enabled)

    def _on_header_learn_mode_toggled(self, enabled: bool) -> None:
        set_learn = getattr(self.controller_page, "set_learn_mode_checked", None)
        if callable(set_learn):
            set_learn(enabled)
        set_learn_mode = getattr(self.controller, "set_learn_mode", None)
        if callable(set_learn_mode):
            set_learn_mode(enabled)

    def _on_page_learn_mode_toggled(self, enabled: bool) -> None:
        self._set_checkbox_value(self._learn_mode_check, enabled)
        set_learn_mode = getattr(self.controller, "set_learn_mode", None)
        if callable(set_learn_mode):
            set_learn_mode(enabled)

    def _on_ports_changed(self, ports: object) -> None:
        self._port_combo.blockSignals(True)
        self._port_combo.clear()
        self._port_combo.addItem("<use hint>", "")
        for port in self._iter_ports(ports):
            device = str(getattr(port, "device", "") or "")
            description = str(getattr(port, "description", "") or "<unknown>")
            label = f"{device} - {description}" if device else description
            self._port_combo.addItem(label, device)
        selected_port = str(getattr(self.controller, "selected_port", "") or "")
        if selected_port:
            index = self._port_combo.findData(selected_port)
            if index >= 0:
                self._port_combo.setCurrentIndex(index)
        self._port_combo.blockSignals(False)
        self._refresh_status()

    def _on_connection_state(self, state: str) -> None:
        self._connection_state = str(state).strip().lower()
        self._state_label.setText(f"State: {state}")
        self._status_message.setText(state.capitalize())
        connected = self._connection_state in {"connected", "connecting", "reconnecting"}
        self._connect_toggle_button.setText("Disconnect" if connected else "Connect")
        self._connect_toggle_button.setEnabled(self._connection_state not in {"connecting", "reconnecting"})
        if self._tray is not None:
            self._tray.set_autostart_enabled(is_autostart_enabled())

    def _on_log_message(self, message: str) -> None:
        self._status_message.setText(message)

    def _on_profile_name(self, name: str) -> None:
        self.setWindowTitle(f"MacroPad Controller - {name}")

    def _on_profile_slot(self, slot: int) -> None:
        self._set_spin_value(self._profile_spin, slot)
        self._status_message.setText(f"Profile {slot}")

    def _on_last_packet(self, text: str) -> None:
        self._status_message.setText(f"Last packet {text}")

    def _on_encoder_status(self, text: str) -> None:
        self._status_message.setText(text)

    def _on_auto_connect_changed(self, enabled: bool) -> None:
        self._set_checkbox_value(self._auto_connect_check, enabled)

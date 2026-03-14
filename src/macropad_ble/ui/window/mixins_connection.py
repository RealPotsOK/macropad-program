from __future__ import annotations

from .shared import *
from ..step_blocks import StepExecutionError, execute_step_script

class ConnectionMixin:
    def _set_connection_state(self, state: str) -> None:
        if self._status_pill is None:
            return
        color = STATUS_COLORS.get(state, STATUS_COLORS["disconnected"])
        if state == "connected":
            text = f"Connected ({self._current_port_device})" if self._current_port_device else "Connected"
        elif state == "connecting":
            text = "Connecting..."
        elif state == "reconnecting":
            text = "Reconnecting..."
        else:
            text = "Disconnected"
        self.connection_var.set(text)
        self._status_pill.configure(bg=color)

        if self._connect_button is not None:
            self._connect_button.configure(
                state="disabled" if state in {"connected", "connecting", "reconnecting"} else "normal"
            )
        if self._disconnect_button is not None:
            self._disconnect_button.configure(
                state="normal" if state in {"connected", "connecting", "reconnecting"} else "disabled"
            )


    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)

        def _done(completed: asyncio.Task[None]) -> None:
            self._background_tasks.discard(completed)
            with suppress(asyncio.CancelledError):
                exc = completed.exception()
                if exc is not None:
                    self._error_count += 1
                    self._log(f"Background task error: {exc}")

        task.add_done_callback(_done)


    def _log(self, message: str) -> None:
        if self._log_text is None:
            return
        stamp = time.strftime("%H:%M:%S")
        self._log_text.configure(state="normal")
        self._log_text.insert("end", f"[{stamp}] {message}\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")


    def _prepare_exit(self) -> None:
        self._closing = True
        self._stop_oled_refresh_task()
        if self._dpi_check_after_id is not None:
            with suppress(Exception):
                self.root.after_cancel(self._dpi_check_after_id)
            self._dpi_check_after_id = None
        if self._dpi_configure_after_id is not None:
            with suppress(Exception):
                self.root.after_cancel(self._dpi_configure_after_id)
            self._dpi_configure_after_id = None


    def _stop_oled_refresh_task(self) -> None:
        task = self._oled_refresh_task
        self._oled_refresh_task = None
        if task is not None and not task.done():
            task.cancel()


    def _restart_oled_refresh_task(self) -> None:
        self._stop_oled_refresh_task()
        board = self._board
        if board is None or not board.is_open:
            return
        interval = description_refresh_interval(self.profile.description)
        if interval is None or interval <= 0:
            return
        task = asyncio.create_task(self._oled_refresh_loop(interval))
        self._oled_refresh_task = task

        def _done(completed: asyncio.Task[None]) -> None:
            if self._oled_refresh_task is completed:
                self._oled_refresh_task = None
            with suppress(asyncio.CancelledError):
                exc = completed.exception()
                if exc is not None:
                    self._error_count += 1
                    self._log(f"OLED refresh error: {exc}")

        task.add_done_callback(_done)


    async def _oled_refresh_loop(self, interval: float) -> None:
        while not self._closing:
            await asyncio.sleep(interval)
            board = self._board
            if board is None or not board.is_open:
                return
            await self._push_profile_text_for_slot(self.profile_slot, reason="oled-refresh")


    def _rebuild_script_cache(self) -> None:
        self._sync_scripts_from_workspace("python", persist=False)
        self._script_cache.clear()
        self._script_cache_source.clear()
        for key in self.keys:
            binding = self._binding_for(key)
            if binding.script_mode != "python" or not binding.script_code.strip():
                continue
            source = binding.script_code
            if not source.strip():
                continue
            with suppress(Exception):
                self._script_cache[key] = compile(
                    source,
                    str(self._runtime_script_path(key, "python")),
                    "exec",
                )
                self._script_cache_source[key] = source


    async def _connect(self) -> None:
        if self._monitor_task is not None and not self._monitor_task.done():
            return
        device = self._selected_port_device()
        if not device:
            messagebox.showerror("Missing Port", "Select a serial device before connecting.")
            return
        try:
            baud = int(self.baud_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Baud", "Baud must be an integer.")
            return

        run_settings = Settings(
            port=device,
            hint=None,
            baud=baud,
            ack_timeout=self.settings.ack_timeout,
            dedupe_ms=self.settings.dedupe_ms,
            log_level=self.settings.log_level,
        )
        self._monitor_stop = asyncio.Event()
        self._current_port_device = device
        self._set_connection_state("connecting")
        self._log(f"Connecting to {device} @ {baud}...")
        self._monitor_task = asyncio.create_task(self._monitor_loop(run_settings))
        self._save_app_state()


    async def _disconnect(self) -> None:
        self._stop_oled_refresh_task()
        self._last_oled_lines = None
        if self._monitor_stop is not None:
            self._monitor_stop.set()
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._monitor_task
            self._monitor_task = None
        self._set_connection_state("disconnected")
        self._log("Disconnected.")
        self._save_app_state()


    async def _monitor_loop(self, settings: Settings) -> None:
        try:
            await monitor_with_reconnect(
                settings,
                on_event=self._on_event,
                stop_event=self._monitor_stop,
                on_connected=self._on_connected,
                on_disconnected=self._on_disconnected,
                on_board=self._on_board_available,
                on_raw_line=self._on_raw_line,
            )
        except asyncio.CancelledError:
            raise
        except (PortSelectionError, SerialControllerError) as exc:
            self._error_count += 1
            self._log(f"Monitor error: {exc}")
            self._set_connection_state("disconnected")
        except Exception as exc:
            self._error_count += 1
            self._log(f"Unexpected monitor error: {exc}")
            self._set_connection_state("disconnected")
        finally:
            self._monitor_task = None
            if self._monitor_stop is None or self._monitor_stop.is_set():
                self._set_connection_state("disconnected")


    def _on_connected(self, port: str) -> None:
        self._current_port_device = port
        self._last_oled_lines = None
        self._set_connection_state("connected")
        self._log(f"Connected: {port}")
        self._save_app_state()
        self._spawn(self._push_profile_text_for_slot(self.profile_slot, reason="connect"))


    def _on_board_available(self, board: BoardSerial | None) -> None:
        self._board = board
        if board is None:
            self._stop_oled_refresh_task()


    def _on_disconnected(self, reason: str) -> None:
        self._stop_oled_refresh_task()
        self._last_oled_lines = None
        if reason == "stopped":
            self._set_connection_state("disconnected")
            return
        self._error_count += 1
        self._set_connection_state("reconnecting")
        self._log(f"Connection lost: {reason}")


    def _on_raw_line(self, timestamp: Any, line: str) -> None:
        with suppress(Exception):
            stamp = timestamp.isoformat(timespec="seconds")
            self._log(f"{stamp} RX {line}")


    async def _push_profile_text_for_slot(self, slot: int, *, reason: str, force: bool = False) -> None:
        board = self._board
        if board is None or not board.is_open:
            return

        lines = tuple(
            str(line or "").strip()
            for line in await render_profile_display_lines(
                self.profile,
                slot=slot,
                port=self._current_port_device,
            )
        )
        if not lines:
            lines = ("",)
        if not force and self._last_oled_lines == lines:
            return

        async with self._display_send_lock:
            board = self._board
            if board is None or not board.is_open:
                return
            try:
                if any(lines):
                    non_empty_count = sum(1 for line in lines if line)
                    if len(lines) == 1 or (len(lines) > 1 and non_empty_count <= 1):
                        first_non_empty = next((line for line in lines if line), "")
                        await board.send_oled_line(first_non_empty)
                    else:
                        await board.send_oled_lines(*lines)
                else:
                    await board.clear_oled()
            except Exception as exc:
                self._error_count += 1
                self._log(f"Profile text send failed for slot {slot}: {exc}")
                return
        self._last_oled_lines = lines
        if reason != "oled-refresh":
            self._restart_oled_refresh_task()

        if reason == "oled-refresh":
            return
        rendered = " | ".join(f"'{line}'" for line in lines if line)
        self._log(f"OLED profile text sent for slot {slot} ({reason}): {rendered or '<blank>'}")


    def _on_event(self, event: BoardEvent) -> None:
        now = time.monotonic()
        self._event_times.append(now)
        self._last_packet_monotonic = now
        self._last_packet_clock = event.timestamp.strftime("%H:%M:%S")
        self.packet_var.set(f"Last packet: {self._last_packet_clock}")

        if event.raw_line == "READY":
            self.fw_var.set("FW: READY")

        if event.kind == EVENT_ENC_DELTA and event.delta is not None:
            self._enc_total += event.delta
            self.enc_var.set(f"ENC: {event.delta:+d} (total {self._enc_total:+d})")
            self._log(f"ENC {event.delta:+d}")
            if event.delta > 0:
                self._spawn(self._execute_encoder_action("up", steps=event.delta))
            elif event.delta < 0:
                self._spawn(self._execute_encoder_action("down", steps=abs(event.delta)))
            return

        if event.kind == EVENT_ENC_SWITCH:
            pressed = bool(event.value)
            self._log(f"ENC_SW={1 if pressed else 0}")
            if pressed:
                self._spawn(self._execute_encoder_action("sw_down"))
            else:
                self._spawn(self._execute_encoder_action("sw_up"))
            return

        if event.kind == EVENT_KEY_STATE and event.row is not None and event.col is not None:
            key = (event.row, event.col)
            if map_key_to_display(*key) is None:
                return
            pressed = bool(event.value)
            tile = self.tiles.get(key)
            if tile is not None:
                tile.pressed = pressed
                tile.canvas.itemconfigure(tile.state, text="DOWN" if pressed else "UP")
            self._log(f"KEY {event.row},{event.col} {'DOWN' if pressed else 'UP'}")

            if self.learn_mode_var.get() and pressed:
                self._select_key(key)

            if pressed:
                self._spawn(self._execute_key_binding(key))
                self._spawn(self._execute_inline_script(key))


    async def _execute_key_binding(self, key: tuple[int, int]) -> None:
        binding = self._binding_for(key)
        kind, value = normalize_profile_action_kind_value(binding.action.kind, binding.action.value)
        has_inline_script = bool((binding.script_code or "").strip())
        if kind in {"", ACTION_NONE} and not has_inline_script:
            self._log(
                f"Key {key[0]},{key[1]} has no action in profile "
                f"{self.profile_slot} ({self.profile.name})."
            )
            return
        if kind not in {"", ACTION_NONE}:
            summary = value.strip() or "<empty>"
            self._log(
                f"Key {key[0]},{key[1]} -> {kind}: {summary} "
                f"(profile {self.profile_slot}, {self.profile.name})"
            )
        try:
            await self._execute_action_with_profile_support(binding.action)
        except ActionExecutionError as exc:
            self._error_count += 1
            self._log(f"Action failed for {key[0]},{key[1]}: {exc}")


    def _bounded_profile_slot(self, slot: int, *, min_slot: int = 1, max_slot: int = 4) -> int:
        min_value = max(1, int(min_slot))
        max_value = max(min_value, int(max_slot))
        if slot < min_value:
            return min_value
        if slot > max_value:
            return max_value
        return slot


    def _switch_profile_slot(self, slot: int, *, source: str, min_slot: int = 1, max_slot: int = 4) -> None:
        target = self._bounded_profile_slot(slot, min_slot=min_slot, max_slot=max_slot)
        if target == self.profile_slot:
            return
        self._load_profile_slot(target)
        self._select_key(self.selected_key)
        self._log(f"Profile changed to {target} ({source}, range {min_slot}-{max_slot}).")


    async def _execute_action_with_profile_support(self, action: KeyAction, *, volume_direction: int = 1) -> None:
        kind, value = normalize_profile_action_kind_value(action.kind, action.value)
        if kind == ACTION_CHANGE_PROFILE:
            spec = parse_change_profile_value(value)
            if spec.mode == "set":
                target = spec.target if spec.target is not None else self.profile_slot
                self._switch_profile_slot(
                    target,
                    source="change_profile:set",
                    min_slot=spec.min_slot,
                    max_slot=spec.max_slot,
                )
                return

            delta = spec.step if spec.mode == "next" else -spec.step
            target = cycle_profile_slot(
                self.profile_slot,
                delta,
                min_slot=spec.min_slot,
                max_slot=spec.max_slot,
            )
            self._switch_profile_slot(
                target,
                source=f"change_profile:{spec.mode}",
                min_slot=spec.min_slot,
                max_slot=spec.max_slot,
            )
            return

        if kind == ACTION_PROFILE_SET:
            value_text = value.strip()
            if not value_text:
                raise ActionExecutionError("profile_set requires a profile number (1-4).")
            try:
                target = int(value_text, 10)
            except ValueError as exc:
                raise ActionExecutionError("profile_set value must be an integer (1-4).") from exc
            self._switch_profile_slot(target, source="set", min_slot=1, max_slot=4)
            return

        if kind in {ACTION_PROFILE_NEXT, ACTION_PROFILE_PREV}:
            raw = value.strip()
            step = 1
            if raw:
                try:
                    step = abs(int(raw, 10))
                except ValueError as exc:
                    raise ActionExecutionError(f"{kind} value must be an integer step.") from exc
            if step <= 0:
                step = 1
            delta = step if kind == ACTION_PROFILE_NEXT else -step
            target = cycle_profile_slot(self.profile_slot, delta, min_slot=1, max_slot=4)
            self._switch_profile_slot(target, source=kind, min_slot=1, max_slot=4)
            return

        await execute_action(
            action,
            log=self._log,
            volume_direction=volume_direction,
            on_volume_mixer=self._show_volume_overlay,
        )


    async def _execute_inline_script(self, key: tuple[int, int]) -> None:
        binding = self._binding_for(key)
        mode = (binding.script_mode or "python").lower()
        if mode == "python":
            self._sync_scripts_from_workspace("python", persist=False)
            source = binding.script_code or ""
            script = source.strip()
            if not script:
                return

            code = self._script_cache.get(key)
            if code is None or self._script_cache_source.get(key) != source:
                try:
                    code = compile(script, str(self._runtime_script_path(key, "python")), "exec")
                except Exception as exc:
                    self._error_count += 1
                    self._log(f"Python script compile error ({key[0]},{key[1]}): {exc}")
                    return
                self._script_cache[key] = code
                self._script_cache_source[key] = source

            context: dict[str, Any] = {
                "key": key,
                "row": key[0],
                "col": key[1],
                "pressed": True,
                "timestamp": time.time(),
            }
            try:
                # Use a single namespace for globals/locals so imports and helper
                # functions in user scripts resolve symbols consistently.
                namespace: dict[str, Any] = {"__builtins__": __builtins__}
                namespace.update(context)
                await asyncio.to_thread(exec, code, namespace, namespace)
                self.script_status_var.set(f"Ran Python script for key {key[0]},{key[1]}")
            except Exception as exc:
                self._error_count += 1
                self._log(f"Python script runtime error ({key[0]},{key[1]}): {exc}")
            return
        if mode == "step":
            source = binding.script_code or ""
            if not source.strip():
                return
            try:
                await execute_step_script(source, log=self._log)
                self.script_status_var.set(f"Ran Step script for key {key[0]},{key[1]}")
            except StepExecutionError as exc:
                self._error_count += 1
                self._log(f"Step script error ({key[0]},{key[1]}): {exc}")
            except Exception as exc:
                self._error_count += 1
                self._log(f"Step runtime error ({key[0]},{key[1]}): {exc}")
            return
        if mode == "ahk":
            self._sync_scripts_from_workspace("ahk", persist=False)
            source = binding.script_code or ""
            script = source.strip()
            if not script:
                return

            runtime_path = self._write_runtime_script(key, "ahk", source)
            try:
                await execute_action(KeyAction(kind=ACTION_AHK, value=str(runtime_path)), log=self._log)
                self.script_status_var.set(f"Ran AHK script for key {key[0]},{key[1]}")
            except ActionExecutionError as exc:
                self._error_count += 1
                self._log(f"AHK script error ({key[0]},{key[1]}): {exc}")
            return

        if mode == "file":
            script = binding.script_code.strip()
            if not script:
                return
            try:
                await execute_action(KeyAction(kind=ACTION_FILE, value=script), log=self._log)
                self.script_status_var.set(f"Opened file target for key {key[0]},{key[1]}")
            except ActionExecutionError as exc:
                self._error_count += 1
                self._log(f"File script error ({key[0]},{key[1]}): {exc}")
            return

        self._log(f"Unknown script mode for key {key[0]},{key[1]}: {mode}")





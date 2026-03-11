from __future__ import annotations

import ctypes
import sys
from typing import Any

ERROR_ALREADY_EXISTS = 183
WAIT_OBJECT_0 = 0


def _default_kernel32() -> Any:
    return ctypes.windll.kernel32  # type: ignore[attr-defined]


class SingleInstanceGuard:
    def __init__(self, app_id: str, *, kernel32: Any | None = None) -> None:
        self.app_id = str(app_id or "MacroPadController").strip() or "MacroPadController"
        self._kernel32 = kernel32
        self._mutex_handle: Any | None = None
        self._event_handle: Any | None = None
        self.is_primary = True

    @property
    def supported(self) -> bool:
        return sys.platform == "win32"

    @property
    def _mutex_name(self) -> str:
        return f"Local\\{self.app_id}_Mutex"

    @property
    def _event_name(self) -> str:
        return f"Local\\{self.app_id}_Restore"

    def acquire(self) -> bool:
        if not self.supported:
            self.is_primary = True
            return True

        kernel32 = self._kernel32 or _default_kernel32()
        self._mutex_handle = kernel32.CreateMutexW(None, False, self._mutex_name)
        if not self._mutex_handle:
            raise OSError("Could not create instance mutex.")
        last_error = int(kernel32.GetLastError())

        self._event_handle = kernel32.CreateEventW(None, True, False, self._event_name)
        if not self._event_handle:
            kernel32.CloseHandle(self._mutex_handle)
            self._mutex_handle = None
            raise OSError("Could not create restore event.")

        self.is_primary = last_error != ERROR_ALREADY_EXISTS
        return self.is_primary

    def signal_restore(self) -> bool:
        if not self.supported or self._event_handle is None:
            return False
        kernel32 = self._kernel32 or _default_kernel32()
        return bool(kernel32.SetEvent(self._event_handle))

    def consume_restore_signal(self) -> bool:
        if not self.supported or self._event_handle is None or not self.is_primary:
            return False
        kernel32 = self._kernel32 or _default_kernel32()
        result = int(kernel32.WaitForSingleObject(self._event_handle, 0))
        if result != WAIT_OBJECT_0:
            return False
        kernel32.ResetEvent(self._event_handle)
        return True

    def close(self) -> None:
        if not self.supported:
            return
        kernel32 = self._kernel32 or _default_kernel32()
        for handle_name in ("_event_handle", "_mutex_handle"):
            handle = getattr(self, handle_name)
            if handle is None:
                continue
            kernel32.CloseHandle(handle)
            setattr(self, handle_name, None)

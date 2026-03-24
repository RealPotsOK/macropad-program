from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer


@dataclass(slots=True)
class AudioOutputDeviceInfo:
    device_id: str
    name: str
    is_default: bool = False


class AudioPlaybackService(QObject):
    """Simple non-blocking local audio player for file actions."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._output = QAudioOutput(self)
        self._output.setVolume(1.0)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._output)
        self._selected_device_id = ""
        self.set_output_device("")

    def list_output_devices(self) -> list[AudioOutputDeviceInfo]:
        default_device = QMediaDevices.defaultAudioOutput()
        default_id = self._device_id(default_device)
        devices: list[AudioOutputDeviceInfo] = []
        seen: set[str] = set()
        for device in QMediaDevices.audioOutputs():
            device_id = self._device_id(device)
            if not device_id or device_id in seen:
                continue
            seen.add(device_id)
            devices.append(
                AudioOutputDeviceInfo(
                    device_id=device_id,
                    name=str(device.description() or device_id).strip(),
                    is_default=(device_id == default_id),
                )
            )
        devices.sort(key=lambda item: item.name.lower())
        return devices

    def set_output_device(self, device_id: str) -> bool:
        wanted = str(device_id or "").strip()
        target = None
        if wanted:
            for device in QMediaDevices.audioOutputs():
                if self._device_id(device) == wanted:
                    target = device
                    break
            if target is None:
                return False
        else:
            target = QMediaDevices.defaultAudioOutput()
        self._output.setDevice(target)
        self._selected_device_id = self._device_id(target)
        return True

    def selected_output_device_id(self) -> str:
        return str(self._selected_device_id or "")

    def play_file(self, path: Path, *, volume_percent: int | None = None) -> bool:
        candidate = Path(path).expanduser()
        if not candidate.exists():
            return False
        if volume_percent is None:
            normalized_volume = 100
        else:
            normalized_volume = max(0, min(100, int(volume_percent)))
        self._output.setVolume(float(normalized_volume) / 100.0)
        url = QUrl.fromLocalFile(str(candidate.resolve()))
        self._player.setSource(url)
        self._player.play()
        return True

    def _device_id(self, device) -> str:
        try:
            raw = bytes(device.id())
            decoded = raw.decode("utf-8", errors="ignore").strip()
            if decoded:
                return decoded
        except Exception:
            pass
        fallback = str(getattr(device, "description", lambda: "")() or "").strip()
        return fallback

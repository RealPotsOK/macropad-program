from __future__ import annotations

from .shared import *
from ..volume_mixer import VolumeMixerResult
from ..volume_overlay import VolumeOverlayToast


class OverlayMixin:
    def _initialize_overlay(self) -> None:
        self._volume_overlay = VolumeOverlayToast(self.root)

    def _show_volume_overlay(self, result: VolumeMixerResult) -> None:
        overlay = getattr(self, "_volume_overlay", None)
        if overlay is None:
            return
        with suppress(Exception):
            overlay.show(result)

    def _shutdown_overlay(self) -> None:
        overlay = getattr(self, "_volume_overlay", None)
        self._volume_overlay = None
        if overlay is None:
            return
        with suppress(Exception):
            overlay.destroy()

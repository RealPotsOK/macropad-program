from __future__ import annotations


class SerialControllerError(RuntimeError):
    """Base runtime error for serial controller operations."""


class PortSelectionError(SerialControllerError):
    """Raised when a unique serial port cannot be selected."""

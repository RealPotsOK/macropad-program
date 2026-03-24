from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from serial.tools import list_ports

from ..config import Settings
from .errors import PortSelectionError


@dataclass(frozen=True, slots=True)
class PortInfo:
    device: str
    description: str
    hwid: str
    manufacturer: str | None = None


def list_serial_ports(*, comports_fn: Callable[[], Iterable[Any]] | None = None) -> list[PortInfo]:
    if comports_fn is None:
        comports_fn = list_ports.comports

    ports: list[PortInfo] = []
    for port in comports_fn():
        ports.append(
            PortInfo(
                device=str(getattr(port, "device", "")),
                description=str(getattr(port, "description", "") or ""),
                hwid=str(getattr(port, "hwid", "") or ""),
                manufacturer=getattr(port, "manufacturer", None),
            )
        )
    return sorted(ports, key=lambda value: value.device.upper())


def format_port_table(ports: list[PortInfo]) -> str:
    if not ports:
        return "No serial ports found."
    lines = ["PORT\tDESCRIPTION\tHWID"]
    for port in ports:
        description = port.description or "<unknown>"
        hwid = port.hwid or "<unknown>"
        lines.append(f"{port.device}\t{description}\t{hwid}")
    return "\n".join(lines)


def resolve_port(
    settings: Settings,
    *,
    ports: list[PortInfo] | None = None,
    comports_fn: Callable[[], Iterable[Any]] | None = None,
) -> str:
    if settings.port:
        return settings.port

    ports = ports if ports is not None else list_serial_ports(comports_fn=comports_fn)
    hint = (settings.hint or "").strip()

    if hint:
        lowered_hint = hint.lower()
        matches: list[PortInfo] = []
        for port in ports:
            searchable = " ".join(
                [
                    port.device,
                    port.description,
                    port.hwid,
                    port.manufacturer or "",
                ]
            ).lower()
            if lowered_hint in searchable:
                matches.append(port)

        if len(matches) == 1:
            return matches[0].device
        if len(matches) > 1:
            details = ", ".join(match.device for match in matches)
            raise PortSelectionError(
                f"Hint '{hint}' matched multiple ports ({details}). Use --port to pick one.\n"
                f"{format_port_table(ports)}"
            )
        raise PortSelectionError(
            f"No serial ports matched hint '{hint}'.\n"
            f"{format_port_table(ports)}\n"
            "Pass --port COMx or adjust --hint."
        )

    raise PortSelectionError(
        "No port selected. Provide --port COMx or --hint text.\n"
        f"{format_port_table(ports)}"
    )

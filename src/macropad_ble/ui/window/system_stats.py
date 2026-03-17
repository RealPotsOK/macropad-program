from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
import time
from pathlib import Path
from typing import Any, Sequence

try:
    import psutil as _psutil
except ImportError:  # pragma: no cover - exercised through fallback behavior
    _psutil = None


@dataclass(slots=True)
class StatsContext:
    data_root: Path
    app_started_monotonic: float
    process: Any | None = None


def format_bytes(value: int | float) -> str:
    size = float(max(0.0, value))
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    index = 0
    while size >= 1024.0 and index < len(units) - 1:
        size /= 1024.0
        index += 1
    if index == 0:
        return f"{int(size)} {units[index]}"
    return f"{size:.1f} {units[index]}"


def format_duration(seconds: float) -> str:
    remaining = max(0, int(seconds))
    days, remaining = divmod(remaining, 86400)
    hours, remaining = divmod(remaining, 3600)
    minutes, secs = divmod(remaining, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if days or hours:
        parts.append(f"{hours}h")
    if days or hours or minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def _existing_directory(path: Path) -> Path:
    candidate = path.expanduser()
    if candidate.exists():
        return candidate if candidate.is_dir() else candidate.parent
    for parent in (candidate.parent, Path.cwd()):
        if parent.exists():
            return parent
    return Path.cwd()


def _format_core_lines(core_percents: Sequence[float], *, per_line: int = 4) -> list[str]:
    if not core_percents:
        return ["  Per-core: unavailable"]

    segments = [f"C{index}: {value:5.1f}%" for index, value in enumerate(core_percents)]
    lines: list[str] = []
    for index in range(0, len(segments), per_line):
        prefix = "  Per-core: " if index == 0 else "            "
        lines.append(prefix + " | ".join(segments[index : index + per_line]))
    return lines


def build_system_stats_report(context: StatsContext) -> str:
    lines = [f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]

    if _psutil is None:
        lines.append("Live system metrics require the optional `psutil` dependency.")
        lines.append(f"App data root: {_existing_directory(context.data_root)}")
        return "\n".join(lines)

    psutil = _psutil
    process = context.process or psutil.Process(os.getpid())

    cpu_total = float(psutil.cpu_percent(interval=None))
    core_percents = [float(value) for value in psutil.cpu_percent(interval=None, percpu=True)]
    cpu_freq = psutil.cpu_freq()
    physical_cores = psutil.cpu_count(logical=False) or 0
    logical_cores = psutil.cpu_count(logical=True) or os.cpu_count() or 0

    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk_root = _existing_directory(context.data_root)
    disk = psutil.disk_usage(str(disk_root))
    network = psutil.net_io_counters()

    system_uptime = max(0.0, time.time() - float(psutil.boot_time()))
    app_uptime = max(0.0, time.monotonic() - float(context.app_started_monotonic))

    load_avg = ""
    if hasattr(os, "getloadavg"):
        try:
            load_1, load_5, load_15 = os.getloadavg()
            load_avg = f"{load_1:.2f}, {load_5:.2f}, {load_15:.2f}"
        except OSError:
            load_avg = ""

    process_cpu = float(process.cpu_percent(interval=None))
    process_memory = process.memory_info()
    process_threads = int(process.num_threads())
    process_status = str(process.status()).replace("_", " ")

    lines.extend(
        [
            "System",
            f"  Uptime: {format_duration(system_uptime)}",
            f"  App runtime: {format_duration(app_uptime)}",
            f"  CPU total: {cpu_total:0.1f}%",
            f"  Cores: {physical_cores} physical / {logical_cores} logical",
        ]
    )
    if cpu_freq is not None:
        lines.append(f"  CPU freq: {float(cpu_freq.current):0.0f} MHz")
    if load_avg:
        lines.append(f"  Load avg: {load_avg}")
    lines.extend(_format_core_lines(core_percents))

    lines.extend(
        [
            "",
            "Memory",
            (
                "  RAM: "
                f"{format_bytes(memory.used)} / {format_bytes(memory.total)} "
                f"({float(memory.percent):0.1f}%)"
            ),
            f"  Available: {format_bytes(memory.available)}",
            (
                "  Swap: "
                f"{format_bytes(swap.used)} / {format_bytes(swap.total)} "
                f"({float(swap.percent):0.1f}%)"
            ),
            "",
            "Storage",
            (
                "  App drive: "
                f"{format_bytes(disk.used)} / {format_bytes(disk.total)} "
                f"({float(disk.percent):0.1f}%)"
            ),
            f"  Path: {disk_root}",
            "",
            "Process",
            f"  PID: {int(getattr(process, 'pid', os.getpid()))}",
            f"  CPU: {process_cpu:0.1f}%",
            f"  Threads: {process_threads}",
            f"  RSS: {format_bytes(process_memory.rss)}",
            f"  VMS: {format_bytes(process_memory.vms)}",
            f"  Status: {process_status}",
            "",
            "Network",
            f"  Sent: {format_bytes(network.bytes_sent)}",
            f"  Recv: {format_bytes(network.bytes_recv)}",
        ]
    )

    return "\n".join(lines)

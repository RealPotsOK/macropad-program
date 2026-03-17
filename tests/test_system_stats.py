from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import macropad_ble.ui.window.system_stats as system_stats


class _FakeProcess:
    pid = 4242

    def cpu_percent(self, interval=None) -> float:
        return 7.5

    def memory_info(self):
        return SimpleNamespace(rss=256 * 1024 * 1024, vms=768 * 1024 * 1024)

    def num_threads(self) -> int:
        return 14

    def status(self) -> str:
        return "running"


class _FakePsutil:
    def cpu_percent(self, interval=None, percpu=False):
        if percpu:
            return [11.0, 22.0, 33.0, 44.0]
        return 18.5

    def cpu_freq(self):
        return SimpleNamespace(current=3600.0)

    def cpu_count(self, logical=True):
        return 8 if logical else 4

    def virtual_memory(self):
        total = 32 * 1024 * 1024 * 1024
        used = 10 * 1024 * 1024 * 1024
        return SimpleNamespace(total=total, used=used, available=total - used, percent=31.25)

    def swap_memory(self):
        total = 8 * 1024 * 1024 * 1024
        used = 1 * 1024 * 1024 * 1024
        return SimpleNamespace(total=total, used=used, free=total - used, percent=12.5)

    def disk_usage(self, path: str):
        total = 512 * 1024 * 1024 * 1024
        used = 128 * 1024 * 1024 * 1024
        return SimpleNamespace(total=total, used=used, free=total - used, percent=25.0)

    def net_io_counters(self):
        return SimpleNamespace(bytes_sent=123456789, bytes_recv=987654321)

    def boot_time(self) -> float:
        return time.time() - 7200

    def Process(self, pid: int) -> _FakeProcess:
        return _FakeProcess()


def test_format_bytes_uses_human_readable_units() -> None:
    assert system_stats.format_bytes(1536) == "1.5 KB"
    assert system_stats.format_bytes(5 * 1024 * 1024) == "5.0 MB"


def test_build_system_stats_report_without_psutil(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(system_stats, "_psutil", None)

    report = system_stats.build_system_stats_report(
        system_stats.StatsContext(data_root=tmp_path, app_started_monotonic=time.monotonic() - 10.0)
    )

    assert "Live system metrics require the optional `psutil` dependency." in report
    assert str(tmp_path.resolve()) in report


def test_build_system_stats_report_with_fake_psutil(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(system_stats, "_psutil", _FakePsutil())

    report = system_stats.build_system_stats_report(
        system_stats.StatsContext(
            data_root=tmp_path,
            app_started_monotonic=time.monotonic() - 42.0,
            process=_FakeProcess(),
        )
    )

    assert "System" in report
    assert "CPU total: 18.5%" in report
    assert "Cores: 4 physical / 8 logical" in report
    assert "Threads: 14" in report
    assert "Storage" in report
    assert "Network" in report

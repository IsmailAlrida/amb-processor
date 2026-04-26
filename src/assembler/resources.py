"""Resource and tool path helpers for source and PyInstaller builds."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path


def app_root() -> Path:
    """Return the root that contains bundled docs, RTL files, and tools."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[2]


def resource_path(*parts: str) -> Path:
    return app_root().joinpath(*parts)


def platform_key() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows":
        return "windows-x64"
    if system == "linux" and machine in {"x86_64", "amd64"}:
        return "linux-x64"
    return f"{system}-{machine}"


def bundled_oss_root() -> Path:
    return resource_path("tools", "oss-cad-suite", platform_key(), "oss-cad-suite")


def docs_index_path() -> Path:
    return resource_path("docs", "index.html")


def rtl_runner_path() -> Path:
    return resource_path("src", "rtl", "testbench", "run_rtl_sim.py")


def rtl_run_root() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("AMB_PROCESSOR_RUN_DIR", Path.home() / ".amb-processor"))
        return base / "rtl_sim"
    return resource_path("build", "rtl_sim")

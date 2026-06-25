"""Resource and tool path helpers for source and PyInstaller builds."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

OSS_CAD_SUITE_ENV_VAR = "AMB_OSS_CAD_SUITE_ROOT"


def app_root() -> Path:
    """Return the root that contains bundled docs, RTL files, and tools."""
    if getattr(sys, "frozen", False):
        root = Path(getattr(sys, "_MEIPASS")).resolve()
        if platform.system() == "Darwin":
            resources_root = root.parent / "Resources"
            if resources_root.exists():
                return resources_root.resolve()
        return root
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
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return "darwin-arm64"
    if system == "darwin" and machine in {"x86_64", "amd64"}:
        return "darwin-x64"
    return f"{system}-{machine}"


def oss_tool_root(base_root: Path | None = None) -> Path:
    return (base_root or app_root()) / "tools" / "oss-cad-suite"


def canonical_oss_root(base_root: Path | None = None, platform_name: str | None = None) -> Path:
    return oss_tool_root(base_root) / (platform_name or platform_key()) / "oss-cad-suite"


def compatibility_oss_root(base_root: Path | None = None) -> Path:
    return oss_tool_root(base_root) / "oss-cad-suite"


def _env_oss_root(base_root: Path | None = None) -> Path | None:
    raw = os.environ.get(OSS_CAD_SUITE_ENV_VAR)
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (base_root or app_root()) / path
    return path


def oss_root_candidates(base_root: Path | None = None, platform_name: str | None = None) -> tuple[Path, ...]:
    base_root = base_root or app_root()
    candidates: list[Path] = []
    env_root = _env_oss_root(base_root)
    frozen_macos = getattr(sys, "frozen", False) and platform.system() == "Darwin"
    candidates.append(canonical_oss_root(base_root, platform_name))
    candidates.append(compatibility_oss_root(base_root))
    if env_root is not None and not frozen_macos:
        candidates.insert(0, env_root)
    elif env_root is not None:
        candidates.append(env_root)

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return tuple(deduped)


def resolve_oss_root(base_root: Path | None = None, platform_name: str | None = None) -> Path | None:
    for candidate in oss_root_candidates(base_root, platform_name):
        if candidate.exists():
            return candidate
    return None


def bundled_oss_root() -> Path:
    return resolve_oss_root() or canonical_oss_root()


def docs_index_path() -> Path:
    return resource_path("docs", "cpu_components", "index.html")


def rtl_run_root() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("AMB_PROCESSOR_RUN_DIR", Path.home() / ".amb-processor"))
        return base / "rtl_sim"
    return resource_path("build", "rtl_sim")

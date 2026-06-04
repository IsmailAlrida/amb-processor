#!/usr/bin/env python3
"""Select OSS CAD Suite files for AMB PyInstaller bundles.

This module does not prune or mutate the downloaded OSS CAD Suite. It only
builds PyInstaller entries for the subset the frozen app should ship.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


CORE_TOOLS = ("iverilog", "vvp", "vcd2fst")
DEFAULT_VIEWER_TOOLS = ("surfer",)
GTKWAVE_GUI_TOOLS = ("gtkwave",)
SCHEMATIC_TOOLS = ("yosys", "dot")
SUPPORTED_PLATFORMS = ("linux-x64", "windows-x64", "darwin-arm64", "darwin-x64")

ROOT_FILES = (
    "VERSION",
    "README",
    "environment",
    "environment.fish",
    "environment.bat",
    "environment.ps1",
    "start.bat",
    ".amb_oss_cad_suite.json",
)
ROOT_TREES = (
    "license",
)
COMMON_FILES = (
    "share/manifest.json",
    "etc/cacert.pem",
    "etc/fonts/fonts.conf.template",
)
WRAPPER_HELPER_TOOLS = ("realpath",)
ICARUS_HELPER_TOOLS = ("ivl", "ivlpp")
GTKWAVE_RESOURCE_TREES = (
    "lib/gdk-pixbuf-2.0",
    "lib/girepository-1.0",
    "share/glib-2.0",
    "share/gtkwave",
    "share/gtk-2.0",
    "share/gtk-3.0",
    "share/icons",
    "share/themes",
)
SCHEMATIC_RESOURCE_TREES = (
    "lib/graphviz",
    "lib/yosys",
    "share/graphviz",
    "share/terminfo",
    "share/yosys",
)


@dataclass(frozen=True)
class BundleOptions:
    platform_name: str
    include_surfer: bool = True
    include_gtkwave_gui: bool = False
    include_schematic: bool = False

    @property
    def tiers(self) -> tuple[str, ...]:
        tiers = ["core"]
        if self.include_surfer:
            tiers.append("viewer:surfer")
        if self.include_gtkwave_gui:
            tiers.append("viewer:gtkwave")
        if self.include_schematic:
            tiers.append("schematic")
        return tuple(tiers)

    @property
    def tools(self) -> tuple[str, ...]:
        tools = [*CORE_TOOLS]
        if self.include_surfer:
            tools.extend(DEFAULT_VIEWER_TOOLS)
        if self.include_gtkwave_gui:
            tools.extend(GTKWAVE_GUI_TOOLS)
        if self.include_schematic:
            tools.extend(SCHEMATIC_TOOLS)
        return tuple(dict.fromkeys(tools))


@dataclass(frozen=True)
class BundleEntries:
    datas: list[tuple[str, str]]
    binaries: list[tuple[str, str]]


def truthy_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def detect_platform() -> str:
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


def options_from_env(platform_name: str | None = None) -> BundleOptions:
    return BundleOptions(
        platform_name=platform_name or os.environ.get("AMB_OSS_BUNDLE_PLATFORM") or detect_platform(),
        include_surfer=truthy_env("AMB_OSS_BUNDLE_SURFER", True),
        include_gtkwave_gui=truthy_env("AMB_OSS_BUNDLE_GTKWAVE", False),
        include_schematic=truthy_env("AMB_OSS_BUNDLE_SCHEMATIC", False),
    )


def exe_suffix(platform_name: str) -> str:
    return ".exe" if platform_name.startswith("windows") else ""


def add_file(entries: dict[Path, Path], source_root: Path, dest_root: Path, rel_path: Path | str) -> bool:
    rel_path = Path(rel_path)
    source = source_root / rel_path
    if not source.is_file():
        return False
    entries[source.resolve()] = dest_root / rel_path.parent
    return True


def add_tree(entries: dict[Path, Path], source_root: Path, dest_root: Path, rel_path: Path | str) -> int:
    rel_path = Path(rel_path)
    source = source_root / rel_path
    if not source.exists():
        return 0
    count = 0
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        rel_file = path.relative_to(source_root)
        entries[path.resolve()] = dest_root / rel_file.parent
        count += 1
    return count


def parse_linked_paths(output: str) -> list[Path]:
    paths: list[Path] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if "=>" in line:
            line = line.split("=>", 1)[1].strip()
        if " (" in line:
            line = line.split(" (", 1)[0].strip()
        candidate = Path(line)
        if candidate.is_absolute() or line.startswith("@"):
            paths.append(candidate)
    return paths


def is_elf_binary(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"\x7fELF"
    except OSError:
        return False


def is_mach_o_binary(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) in {
                b"\xfe\xed\xfa\xce",
                b"\xfe\xed\xfa\xcf",
                b"\xce\xfa\xed\xfe",
                b"\xcf\xfa\xed\xfe",
                b"\xca\xfe\xba\xbe",
                b"\xca\xfe\xba\xbf",
            }
    except OSError:
        return False


def linux_loader(source_root: Path) -> Path | None:
    lib_dir = source_root / "lib"
    for name in ("ld-linux-x86-64.so.2", "ld-linux-aarch64.so.1"):
        candidate = lib_dir / name
        if candidate.is_file():
            return candidate
    return None


def resolve_library_reference(reference: Path, binary: Path, source_root: Path) -> Path | None:
    root = source_root.resolve()
    candidates: list[Path] = []
    raw = str(reference)

    if reference.is_absolute():
        candidates.append(reference)
    elif raw.startswith("@loader_path/"):
        candidates.append(binary.parent / raw.removeprefix("@loader_path/"))
    elif raw.startswith("@executable_path/"):
        candidates.append(binary.parent / raw.removeprefix("@executable_path/"))

    name = reference.name
    if name:
        candidates.extend(source_root / dirname / name for dirname in ("bin", "lib", "libexec"))

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root)
        except (OSError, ValueError):
            continue
        if resolved.is_file():
            return resolved
    return None


def linux_linked_libraries_under_root(binary: Path, source_root: Path) -> list[Path]:
    loader = linux_loader(source_root)
    if loader is None or not is_elf_binary(binary):
        return []
    command = [
        str(loader),
        "--inhibit-cache",
        "--inhibit-rpath",
        "",
        "--library-path",
        str(source_root / "lib"),
        str(binary),
    ]
    env = dict(os.environ)
    env["LD_TRACE_LOADED_OBJECTS"] = "1"
    try:
        proc = subprocess.run(command, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    except OSError:
        return []
    return [
        resolved
        for path in parse_linked_paths(proc.stdout)
        if (resolved := resolve_library_reference(path, binary, source_root)) is not None
    ]


def windows_linked_libraries_under_root(binary: Path, source_root: Path) -> list[Path]:
    if binary.suffix.lower() not in {".exe", ".dll"}:
        return []
    try:
        import pefile  # type: ignore[import-not-found]
    except Exception:
        return []

    try:
        pe = pefile.PE(str(binary), fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
    except Exception:
        return []

    linked: list[Path] = []
    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        try:
            name = entry.dll.decode("utf-8")
        except Exception:
            continue
        if (resolved := resolve_library_reference(Path(name), binary, source_root)) is not None:
            linked.append(resolved)
    return linked


def linked_libraries_under_root(binary: Path, source_root: Path) -> list[Path]:
    if not binary.exists():
        return []
    command: list[str] | None = None
    if platform.system() == "Linux":
        return linux_linked_libraries_under_root(binary, source_root)
    if platform.system() == "Windows":
        return windows_linked_libraries_under_root(binary, source_root)
    elif platform.system() == "Darwin" and shutil.which("otool"):
        command = ["otool", "-L", str(binary)]
    if command is None:
        return []
    try:
        proc = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    except OSError:
        return []
    linked: list[Path] = []
    for path in parse_linked_paths(proc.stdout):
        if (resolved := resolve_library_reference(path, binary, source_root)) is not None:
            linked.append(resolved)
    return linked


def add_linked_library_closure(
    entries: dict[Path, Path],
    source_root: Path,
    dest_root: Path,
    binaries: list[Path],
) -> None:
    pending = [path for path in binaries if path.is_file()]
    seen: set[Path] = set()
    root = source_root.resolve()
    while pending:
        binary = pending.pop()
        try:
            resolved_binary = binary.resolve()
        except OSError:
            continue
        if resolved_binary in seen:
            continue
        seen.add(resolved_binary)
        for linked in linked_libraries_under_root(resolved_binary, source_root):
            try:
                rel_linked = linked.relative_to(root)
            except ValueError:
                continue
            if add_file(entries, source_root, dest_root, rel_linked):
                pending.append(linked)


def add_tool(entries: dict[Path, Path], source_root: Path, dest_root: Path, tool: str, platform_name: str) -> None:
    suffix = exe_suffix(platform_name)
    candidates = [
        Path("bin") / f"{tool}{suffix}",
        Path("bin") / tool,
        Path("libexec") / f"{tool}{suffix}",
        Path("libexec") / tool,
    ]
    binaries: list[Path] = []
    for rel_path in candidates:
        if add_file(entries, source_root, dest_root, rel_path):
            binaries.append(source_root / rel_path)

    add_linked_library_closure(entries, source_root, dest_root, binaries)


def add_linked_libraries_for_tree(
    entries: dict[Path, Path],
    source_root: Path,
    dest_root: Path,
    rel_path: Path | str,
) -> None:
    source = source_root / Path(rel_path)
    if not source.exists():
        return
    add_linked_library_closure(entries, source_root, dest_root, [path for path in source.rglob("*") if path.is_file()])


def add_iverilog_runtime(entries: dict[Path, Path], source_root: Path, dest_root: Path, platform_name: str) -> None:
    for helper in ICARUS_HELPER_TOOLS:
        add_tool(entries, source_root, dest_root, helper, platform_name)
    add_tree(entries, source_root, dest_root, "lib/ivl")
    add_linked_libraries_for_tree(entries, source_root, dest_root, "lib/ivl")


def add_gtkwave_runtime(entries: dict[Path, Path], source_root: Path, dest_root: Path, platform_name: str) -> None:
    add_tool(entries, source_root, dest_root, "gdk-pixbuf-query-loaders", platform_name)
    for rel_tree in GTKWAVE_RESOURCE_TREES:
        add_tree(entries, source_root, dest_root, rel_tree)


def add_schematic_runtime(entries: dict[Path, Path], source_root: Path, dest_root: Path, platform_name: str) -> None:
    for helper in ("yosys-abc", "yosys-config", "gvpr", "acyclic", "tred", "unflatten"):
        add_tool(entries, source_root, dest_root, helper, platform_name)
    for rel_tree in SCHEMATIC_RESOURCE_TREES:
        add_tree(entries, source_root, dest_root, rel_tree)


def pyinstaller_tuple(source: Path, dest: Path) -> tuple[str, str]:
    return str(source), str(dest)


def split_pyinstaller_entries(entries: dict[Path, Path], options: BundleOptions) -> BundleEntries:
    datas: list[tuple[str, str]] = []
    binaries: list[tuple[str, str]] = []
    for source, dest in sorted(entries.items(), key=lambda item: str(item[0])):
        if options.platform_name.startswith("darwin") and is_mach_o_binary(source):
            binaries.append(pyinstaller_tuple(source, dest))
        else:
            datas.append(pyinstaller_tuple(source, dest))
    return BundleEntries(datas=datas, binaries=binaries)


def collect_oss_cad_suite_bundle(
    source_root: Path,
    dest_root: Path | str,
    *,
    options: BundleOptions | None = None,
    marker_dir: Path | None = None,
    report_path: Path | None = None,
) -> BundleEntries:
    source_root = source_root.resolve()
    dest_root = Path(dest_root)
    options = options or options_from_env()
    if not source_root.exists():
        return BundleEntries(datas=[], binaries=[])

    entries: dict[Path, Path] = {}
    for rel_path in ROOT_FILES:
        add_file(entries, source_root, dest_root, rel_path)
    for rel_path in COMMON_FILES:
        add_file(entries, source_root, dest_root, rel_path)
    for rel_tree in ROOT_TREES:
        add_tree(entries, source_root, dest_root, rel_tree)

    for tool in options.tools:
        add_tool(entries, source_root, dest_root, tool, options.platform_name)
    for helper in WRAPPER_HELPER_TOOLS:
        add_tool(entries, source_root, dest_root, helper, options.platform_name)

    add_iverilog_runtime(entries, source_root, dest_root, options.platform_name)

    if options.include_surfer:
        add_tree(entries, source_root, dest_root, "share/surfer")
    if options.include_gtkwave_gui:
        add_gtkwave_runtime(entries, source_root, dest_root, options.platform_name)
    if options.include_schematic:
        add_schematic_runtime(entries, source_root, dest_root, options.platform_name)

    marker_source: Path | None = None
    if marker_dir is not None:
        marker_dir.mkdir(parents=True, exist_ok=True)
        marker_source = marker_dir / ".amb_oss_cad_suite_bundle.json"
        marker = bundle_summary(source_root, entries, options)
        marker_source.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
        entries[marker_source.resolve()] = dest_root

    if report_path is not None:
        write_report(source_root, entries, options, report_path, split_pyinstaller_entries(entries, options))

    return split_pyinstaller_entries(entries, options)


def collect_oss_cad_suite_datas(
    source_root: Path,
    dest_root: Path | str,
    *,
    options: BundleOptions | None = None,
    marker_dir: Path | None = None,
    report_path: Path | None = None,
) -> list[tuple[str, str]]:
    return collect_oss_cad_suite_bundle(
        source_root,
        dest_root,
        options=options,
        marker_dir=marker_dir,
        report_path=report_path,
    ).datas


def bundle_summary(source_root: Path, entries: dict[Path, Path], options: BundleOptions) -> dict[str, object]:
    selected_files = [path for path in entries if path.is_file()]
    selected_size = sum(path.stat().st_size for path in selected_files)
    full_size = sum(path.stat().st_size for path in source_root.rglob("*") if path.is_file())
    missing_tools = []
    suffix = exe_suffix(options.platform_name)
    for tool in options.tools:
        if not ((source_root / "bin" / f"{tool}{suffix}").exists() or (source_root / "bin" / tool).exists()):
            missing_tools.append(tool)
    return {
        "schema": 1,
        "source_root": str(source_root),
        "platform": options.platform_name,
        "tiers": options.tiers,
        "tools": options.tools,
        "missing_tools": missing_tools,
        "full_size_bytes": full_size,
        "bundled_size_bytes": selected_size,
        "bundled_file_count": len(selected_files),
    }


def write_report(
    source_root: Path,
    entries: dict[Path, Path],
    options: BundleOptions,
    report_path: Path,
    bundle_entries: BundleEntries | None = None,
) -> None:
    report = bundle_summary(source_root, entries, options)
    bundle_entries = bundle_entries or split_pyinstaller_entries(entries, options)
    report["pyinstaller_data_count"] = len(bundle_entries.datas)
    report["pyinstaller_binary_count"] = len(bundle_entries.binaries)
    report["files"] = [
        str(path.relative_to(source_root)) if path.is_relative_to(source_root) else str(path)
        for path in sorted(entries)
        if path.is_file()
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in report if key != "files"}, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--platform", choices=SUPPORTED_PLATFORMS, default=detect_platform())
    parser.add_argument("--report", type=Path, default=Path("build") / "oss-cad-suite-bundle-report.json")
    parser.add_argument("--include-gtkwave-gui", action="store_true")
    parser.add_argument("--include-schematic", action="store_true")
    parser.add_argument("--no-surfer", action="store_true")
    args = parser.parse_args()

    if not args.root.exists():
        raise SystemExit(f"OSS CAD Suite root not found: {args.root}")

    options = BundleOptions(
        platform_name=args.platform,
        include_surfer=not args.no_surfer,
        include_gtkwave_gui=args.include_gtkwave_gui,
        include_schematic=args.include_schematic,
    )
    collect_oss_cad_suite_bundle(
        args.root,
        "tools/oss-cad-suite/preview/oss-cad-suite",
        options=options,
        report_path=args.report,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

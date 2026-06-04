# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os
import platform

from tools.oss_cad_bundle import collect_oss_cad_suite_bundle, options_from_env


ROOT = Path.cwd()
EXCLUDED_TREE_PARTS = {"__pycache__"}
EXCLUDED_FILE_SUFFIXES = {".pyc", ".pyo"}
EXCLUDED_FILE_NAMES = {"assembler_faulthandler.log"}
RTL_DATA_EXCLUDED_FILE_SUFFIXES = {".py"}


def platform_key():
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


def should_collect(path, excluded_file_suffixes=None):
    excluded_file_suffixes = excluded_file_suffixes or set()
    if any(part in EXCLUDED_TREE_PARTS for part in path.parts):
        return False
    if path.suffix.lower() in EXCLUDED_FILE_SUFFIXES or path.suffix.lower() in excluded_file_suffixes:
        return False
    return path.name not in EXCLUDED_FILE_NAMES


def collect_tree(src, dest, excluded_file_suffixes=None):
    src_path = ROOT / src
    if not src_path.exists():
        return []
    entries = []
    for path in src_path.rglob("*"):
        if path.is_file() and should_collect(path, excluded_file_suffixes):
            rel_parent = path.relative_to(src_path).parent
            entries.append((str(path), str(Path(dest) / rel_parent)))
    return entries


def resolve_oss_source_root_for_spec():
    env_root = os.environ.get("AMB_OSS_CAD_SUITE_ROOT")
    candidates = [
        Path("tools") / "oss-cad-suite" / platform_key() / "oss-cad-suite",
        Path("tools") / "oss-cad-suite" / "oss-cad-suite",
    ]
    if env_root:
        env_path = Path(env_root).expanduser()
        if not env_path.is_absolute():
            env_path = ROOT / env_path
        candidates.insert(0, env_path)
    for candidate in candidates:
        if (ROOT / candidate).exists():
            return candidate
    return candidates[0]


oss_source_root = resolve_oss_source_root_for_spec()
oss_bundle_root = Path("tools") / "oss-cad-suite" / platform_key() / "oss-cad-suite"
icon_file = ROOT / "assets" / "amb.ico"
bundle_icon_file = ROOT / "assets" / "amb.icns"

datas = []
binaries = []
datas += collect_tree("docs", "docs")
datas += collect_tree("src/rtl", "src/rtl", RTL_DATA_EXCLUDED_FILE_SUFFIXES)
datas += collect_tree("assets", "assets")
oss_bundle = collect_oss_cad_suite_bundle(
    ROOT / oss_source_root,
    oss_bundle_root,
    options=options_from_env(platform_key()),
    marker_dir=ROOT / "build",
    report_path=ROOT / "build" / "oss-cad-suite-bundle-report.json",
)
datas += oss_bundle.datas
binaries += oss_bundle.binaries


a = Analysis(
    [str(ROOT / "src" / "assembler" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebEngineWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="amb-assembler",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(icon_file)] if icon_file.exists() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="amb-assembler",
)

if platform.system() == "Darwin":
    app = BUNDLE(
        coll,
        name="amb-assembler.app",
        icon=str(bundle_icon_file) if bundle_icon_file.exists() else None,
        bundle_identifier="ae.uaeu.amb-processor.assembler",
    )

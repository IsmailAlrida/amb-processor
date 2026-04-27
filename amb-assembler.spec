# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import platform


ROOT = Path.cwd()


def platform_key():
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows":
        return "windows-x64"
    if system == "linux" and machine in {"x86_64", "amd64"}:
        return "linux-x64"
    return f"{system}-{machine}"


def collect_tree(src, dest):
    src_path = ROOT / src
    if not src_path.exists():
        return []
    entries = []
    for path in src_path.rglob("*"):
        if path.is_file():
            rel_parent = path.relative_to(src_path).parent
            entries.append((str(path), str(Path(dest) / rel_parent)))
    return entries


def resolve_oss_root_for_spec():
    candidates = [
        Path("tools") / "oss-cad-suite" / platform_key() / "oss-cad-suite",
        Path("tools") / "oss-cad-suite" / "oss-cad-suite",
    ]
    for candidate in candidates:
        if (ROOT / candidate).exists():
            return candidate
    return candidates[0]


oss_root = resolve_oss_root_for_spec()

datas = []
datas += collect_tree("docs", "docs")
datas += collect_tree("src/rtl", "src/rtl")
datas += collect_tree("assets", "assets")
datas += collect_tree(str(oss_root), str(oss_root))


a = Analysis(
    [str(ROOT / "src" / "assembler" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
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
    icon=[str(ROOT / "assets" / "amb.ico")],
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

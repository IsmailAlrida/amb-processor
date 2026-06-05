#!/usr/bin/env python3
"""Create versioned CI artifacts for AMB Assembler builds."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tarfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def artifact_base(platform_name: str, version: str) -> str:
    return f"amb-assembler-{platform_name}-{version}"


def package_linux(version: str, output_dir: Path) -> Path:
    source = REPO_ROOT / "dist" / "amb-assembler"
    if not source.exists():
        raise SystemExit(f"PyInstaller output not found: {source}")
    dest = output_dir / f"{artifact_base('linux-x64', version)}.tar.gz"
    with tarfile.open(dest, "w:gz", dereference=False) as tar_file:
        tar_file.add(source, arcname="amb-assembler")
    return dest


def package_macos(platform_name: str, version: str, output_dir: Path) -> Path:
    source = REPO_ROOT / "dist" / "amb-assembler.app"
    if not source.exists():
        raise SystemExit(f"macOS app bundle not found: {source}")
    ditto = shutil.which("ditto")
    if ditto is None:
        raise SystemExit("ditto not found; macOS app artifacts must be packaged with ditto")
    dest = output_dir / f"{artifact_base(platform_name, version)}.zip"
    subprocess.run([ditto, "-c", "-k", "--sequesterRsrc", "--keepParent", str(source), str(dest)], check=True)
    return dest


def package_windows(platform_name: str, version: str, output_dir: Path) -> Path:
    installer_dir = REPO_ROOT / "dist" / "installer"
    installers = sorted(installer_dir.glob("*.exe"))
    if not installers:
        raise SystemExit(f"Inno Setup installer not found in {installer_dir}")
    dest = output_dir / f"{artifact_base(platform_name, version)}-setup.exe"
    shutil.copy2(installers[0], dest)
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, choices=("linux-x64", "windows-x64", "darwin-arm64", "darwin-x64"))
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "dist" / "artifacts")
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.platform == "linux-x64":
        artifact = package_linux(args.version, output_dir)
    elif args.platform == "windows-x64":
        artifact = package_windows(args.platform, args.version, output_dir)
    else:
        artifact = package_macos(args.platform, args.version, output_dir)

    print(artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

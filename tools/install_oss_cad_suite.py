#!/usr/bin/env python3
"""Install a repo-local OSS CAD Suite for reproducible AMB RTL tooling."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path


DEFAULT_VERSION = "2026-04-18"
REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_ROOT = REPO_ROOT / "tools" / "oss-cad-suite"
GITHUB_API = "https://api.github.com/repos/YosysHQ/oss-cad-suite-build/releases/tags"
REQUIRED_TOOLS = ("yosys", "iverilog", "vvp", "vcd2fst", "dot")
WAVE_TOOLS = ("surfer", "gtkwave")
SUPPORTED_PLATFORMS = ("linux-x64", "windows-x64", "darwin-arm64", "darwin-x64")


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
    raise SystemExit(f"Unsupported platform for pinned OSS CAD Suite install: {system}-{machine}")


def executable(root: Path, name: str, platform_name: str) -> Path:
    suffix = ".exe" if platform_name.startswith("windows") else ""
    return root / "bin" / f"{name}{suffix}"


def validate_install(root: Path, platform_name: str) -> dict[str, str]:
    found: dict[str, str] = {}
    missing: list[str] = []
    for name in REQUIRED_TOOLS:
        path = executable(root, name, platform_name)
        if path.exists():
            found[name] = str(path)
        else:
            missing.append(name)

    wave = next((name for name in WAVE_TOOLS if executable(root, name, platform_name).exists()), None)
    if wave is None:
        missing.append("surfer_or_gtkwave")
    else:
        found[wave] = str(executable(root, wave, platform_name))

    if missing:
        raise SystemExit(f"OSS CAD Suite install missing required tools: {', '.join(missing)}")
    return found


def remove_existing(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def copy_existing(source: Path, dest: Path) -> None:
    if not source.exists():
        raise SystemExit(f"Source OSS CAD Suite path does not exist: {source}")
    remove_existing(dest)
    shutil.copytree(source, dest)


def release_asset(version: str, platform_name: str) -> tuple[str, str]:
    url = f"{GITHUB_API}/{version}"
    request = urllib.request.Request(url)
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urllib.request.urlopen(request) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return select_release_asset(payload, version, platform_name)


def release_asset_suffixes(platform_name: str) -> tuple[str, ...]:
    if platform_name.startswith("windows"):
        return (".exe", ".zip")
    return (".tgz", ".zip")


def select_release_asset(payload: dict[str, object], version: str, platform_name: str) -> tuple[str, str]:
    assets = payload.get("assets", [])
    prefix = f"oss-cad-suite-{platform_name}-"
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name", ""))
        if name.startswith(prefix) and name.endswith(release_asset_suffixes(platform_name)):
            return name, str(asset["browser_download_url"])
    raise SystemExit(f"No OSS CAD Suite asset for {platform_name} in release {version}")


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, dest.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def extract_archive(archive: Path, dest_parent: Path) -> Path:
    remove_existing(dest_parent / "oss-cad-suite")
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zip_file:
            zip_file.extractall(dest_parent)
    elif archive.suffix == ".exe":
        subprocess.run([str(archive), f"-o{dest_parent}", "-y"], check=True)
    else:
        with tarfile.open(archive, "r:*") as tar_file:
            tar_file.extractall(dest_parent)
    root = dest_parent / "oss-cad-suite"
    if not root.exists():
        raise SystemExit(f"Archive did not create expected oss-cad-suite directory: {archive}")
    return root


def write_marker(root: Path, args: argparse.Namespace, tools: dict[str, str]) -> None:
    marker = {
        "version": args.version,
        "platform": args.platform,
        "source": str(args.from_existing) if args.from_existing else "github-release",
        "root": str(root),
        "tools": tools,
    }
    (root / ".amb_oss_cad_suite.json").write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--platform", choices=("auto", *SUPPORTED_PLATFORMS), default="auto")
    parser.add_argument("--from-existing", type=Path, default=None)
    parser.add_argument("--keep-archive", action="store_true")
    args = parser.parse_args()

    platform_name = detect_platform() if args.platform == "auto" else args.platform
    args.platform = platform_name
    install_parent = TOOL_ROOT / platform_name
    install_root = install_parent / "oss-cad-suite"
    install_parent.mkdir(parents=True, exist_ok=True)

    if args.from_existing:
        copy_existing(args.from_existing.resolve(), install_root)
    else:
        asset_name, asset_url = release_asset(args.version, platform_name)
        archive = install_parent / asset_name
        print(f"Downloading {asset_url}")
        download(asset_url, archive)
        install_root = extract_archive(archive, install_parent)
        if not args.keep_archive:
            archive.unlink(missing_ok=True)

    tools = validate_install(install_root, platform_name)
    write_marker(install_root, args, tools)
    print(json.dumps({"root": str(install_root), "tools": tools}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

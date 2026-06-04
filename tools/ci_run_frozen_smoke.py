#!/usr/bin/env python3
"""Run frozen AMB Assembler smoke checks from CI."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_check(executable: Path, flag: str) -> None:
    print(f"Running {executable} {flag}")
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    subprocess.run([str(executable), flag], check=True, env=env)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    args = parser.parse_args()

    executable = args.exe
    if not executable.exists():
        raise SystemExit(f"Frozen executable not found: {executable}")
    if os.name != "nt":
        executable.chmod(executable.stat().st_mode | 0o111)

    run_check(executable, "--self-test")
    run_check(executable, "--self-test-rtl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

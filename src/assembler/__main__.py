from __future__ import annotations

import pathlib
import sys

if __package__ in (None, ""):
    # Script/frozen execution path: ensure the package root is importable.
    pkg_root = pathlib.Path(__file__).resolve().parents[1]
    if str(pkg_root) not in sys.path:
        sys.path.insert(0, str(pkg_root))
    from assembler.app import main
else:
    # Package execution path: python -m assembler
    from .app import main

if __name__ == "__main__":
    main()

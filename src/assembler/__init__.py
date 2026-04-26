"""AMB Assembler Simulator package."""

__all__ = ["main", "run"]


def main() -> None:
    from .app import main as app_main

    app_main()


def run() -> None:
    main()

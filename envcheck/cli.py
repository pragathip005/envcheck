from __future__ import annotations

import argparse

from envcheck import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="envcheck")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("version", help="print the envcheck version")

    args = parser.parse_args(argv)

    if args.command == "version":
        print(__version__)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

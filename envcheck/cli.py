from __future__ import annotations

import argparse

from envcheck import __version__
from envcheck.demo import build_demo_environment_score
from envcheck.report import render_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="envcheck")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("version", help="print the envcheck version")

    demo_parser = subparsers.add_parser(
        "demo", help="run a small built-in example environment end to end"
    )
    demo_parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="exit with status 1 if the trust score is below this threshold",
    )

    args = parser.parse_args(argv)

    if args.command == "version":
        print(__version__)
        return 0

    if args.command == "demo":
        env_score = build_demo_environment_score()
        print(render_text(env_score))
        if args.fail_under is not None and env_score.trust_score < args.fail_under:
            return 1
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""CLI helper to execute the bank statement golden suite."""

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUITE_TEST = PROJECT_ROOT / "tests" / "test_bank_parser_golden.py"


def run_pytest(extra_args=None):
    extra_args = extra_args or []
    cmd = [sys.executable, "-m", "pytest", str(SUITE_TEST)] + extra_args
    return subprocess.call(cmd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "pytest_args", nargs="*", help="Additional arguments to forward to pytest"
    )

    args = parser.parse_args(argv)

    if not SUITE_TEST.exists():
        print("Golden suite not found at", SUITE_TEST)
        return 1

    return run_pytest(args.pytest_args)


if __name__ == "__main__":
    sys.exit(main())

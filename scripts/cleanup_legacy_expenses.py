#!/usr/bin/env python3
"""
Utility script to delete or flag legacy expenses captured without LLM support.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.shared.unified_db_adapter import get_unified_adapter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Cleanup helper for expense_records without LLM classification or with low confidence."
        )
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Permanently delete matching expenses instead of marking them.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Confidence threshold (exclusive). Records below this value are targeted.",
    )
    parser.add_argument(
        "--tenant-id",
        type=int,
        default=None,
        help="Limit the cleanup to a specific tenant.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report how many records would be affected.",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Optional path to the unified SQLite database file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    adapter = get_unified_adapter(args.db_path)

    result: Dict[str, Any] = adapter.cleanup_legacy_expenses(
        delete=args.delete,
        confidence_threshold=args.threshold,
        tenant_id=args.tenant_id,
        dry_run=args.dry_run,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Quick IA QA metrics reporter.

Usage:
    python scripts/ia_metrics_report.py

Prints aggregated stats from expense_records, classification_trace and feedback data.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Dict

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DB_PATH = Path("unified_mcp_system.db")


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found at {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def compute_metrics() -> Dict[str, float]:
    with _connect() as conn:
        cur = conn.cursor()

        total_expenses = cur.execute(
            "SELECT COUNT(*) FROM expense_records"
        ).fetchone()[0]

        ia_expenses = cur.execute(
            """
            SELECT COUNT(*)
              FROM expense_records
             WHERE classification_source LIKE 'llm%'
            """
        ).fetchone()[0]

        catalog_expenses = cur.execute(
            """
            SELECT COUNT(*)
              FROM expense_records
             WHERE classification_source = 'catalog_keyword'
            """
        ).fetchone()[0]

        provider_rules = cur.execute(
            """
            SELECT COUNT(*)
              FROM expense_records
             WHERE classification_source = 'provider_rule'
            """
        ).fetchone()[0]

        manual_feedback = cur.execute(
            """
            SELECT COUNT(*)
              FROM expense_records
             WHERE classification_source = 'manual_feedback'
            """
        ).fetchone()[0]

        traces = cur.execute(
            "SELECT COUNT(*) FROM classification_trace"
        ).fetchone()[0]

        recent_accuracy = cur.execute(
            """
            SELECT AVG(CASE WHEN confidence_sat >= 0.75 THEN 1.0 ELSE 0.0 END)
              FROM classification_trace
        """
        ).fetchone()[0] or 0.0

    print("=== IA Metrics Snapshot ===")
    print(f"Total gastos registrados       : {total_expenses}")
    print(f"Gastos con clasificación IA     : {ia_expenses}")
    print(f"Gastos por catálogo             : {catalog_expenses}")
    print(f"Gastos por regla de proveedor   : {provider_rules}")
    print(f"Gastos con feedback manual      : {manual_feedback}")
    print(f"Trazas registradas              : {traces}")
    print(f"% clasificaciones >= 75% conf   : {recent_accuracy * 100:.2f}%")

    return {
        "total_expenses": total_expenses,
        "ia_expenses": ia_expenses,
        "catalog_expenses": catalog_expenses,
        "provider_rules": provider_rules,
        "manual_feedback": manual_feedback,
        "traces": traces,
        "high_confidence_ratio": recent_accuracy,
    }


def store_metrics(metrics: Dict[str, float]) -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ia_metrics_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_expenses INTEGER,
                ia_expenses INTEGER,
                catalog_expenses INTEGER,
                provider_rules INTEGER,
                manual_feedback INTEGER,
                traces INTEGER,
                high_confidence_ratio REAL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO ia_metrics_history (
                total_expenses,
                ia_expenses,
                catalog_expenses,
                provider_rules,
                manual_feedback,
                traces,
                high_confidence_ratio
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metrics["total_expenses"],
                metrics["ia_expenses"],
                metrics["catalog_expenses"],
                metrics["provider_rules"],
                metrics["manual_feedback"],
                metrics["traces"],
                metrics["high_confidence_ratio"],
            ),
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IA metrics snapshot")
    parser.add_argument("--store", action="store_true", help="Store metrics in ia_metrics_history")
    args = parser.parse_args()

    metrics = compute_metrics()
    if args.store:
        store_metrics(metrics)

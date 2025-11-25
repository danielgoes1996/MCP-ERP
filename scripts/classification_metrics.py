"""
Classification accuracy metrics and ground truth testing.

This script provides:
1. SQL queries to analyze classification accuracy per company
2. Ground truth test against known-good examples
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json
from typing import Dict, List, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# PostgreSQL connection config
POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', '127.0.0.1'),
    'port': int(os.getenv('POSTGRES_PORT', '5433')),
    'database': os.getenv('POSTGRES_DB', 'mcp_system'),
    'user': os.getenv('POSTGRES_USER', 'mcp_user'),
    'password': os.getenv('POSTGRES_PASSWORD', 'changeme')
}


def get_classification_metrics_by_company() -> List[Dict[str, Any]]:
    """
    Get classification accuracy metrics for all companies.

    Returns metrics including:
    - Total invoices
    - Pending, confirmed, corrected counts
    - Correction rate percentage
    """
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    query = """
        SELECT
            c.id as company_id,
            c.name as company_name,
            COUNT(*) as total_invoices,
            COUNT(*) FILTER (WHERE ei.accounting_classification->>'status' = 'pending') as pending,
            COUNT(*) FILTER (WHERE ei.accounting_classification->>'status' = 'pending_confirmation') as pending_confirmation,
            COUNT(*) FILTER (WHERE ei.accounting_classification->>'status' = 'confirmed') as confirmed,
            COUNT(*) FILTER (WHERE ei.accounting_classification->>'status' = 'corrected') as corrected,
            COUNT(*) FILTER (WHERE ei.accounting_classification IS NULL) as not_classified,
            CAST(ROUND(CAST(100.0 * COUNT(*) FILTER (WHERE ei.accounting_classification->>'status' = 'corrected') /
                  NULLIF(COUNT(*) FILTER (WHERE ei.accounting_classification IS NOT NULL), 0) AS numeric), 2) AS float) as correction_rate_pct,
            CAST(ROUND(CAST(100.0 * COUNT(*) FILTER (WHERE ei.accounting_classification->>'status' = 'confirmed') /
                  NULLIF(COUNT(*) FILTER (WHERE ei.accounting_classification IS NOT NULL), 0) AS numeric), 2) AS float) as confirmation_rate_pct,
            CAST(ROUND(CAST(AVG((ei.accounting_classification->>'confidence_sat')::float) AS numeric), 3) AS float) as avg_confidence
        FROM expense_invoices ei
        JOIN companies c ON ei.company_id = c.id
        GROUP BY c.id, c.name
        ORDER BY correction_rate_pct DESC NULLS LAST, total_invoices DESC
    """

    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()

    return [dict(row) for row in results]


def get_correction_patterns_by_company(company_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get most common correction patterns for a company.

    Shows which SAT codes are being corrected most frequently.
    """
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    query = """
        SELECT
            provider_name,
            provider_rfc,
            original_sat_code,
            corrected_sat_code,
            COUNT(*) as correction_count,
            MAX(corrected_at) as last_corrected
        FROM ai_correction_memory
        WHERE company_id = %s
        GROUP BY provider_name, provider_rfc, original_sat_code, corrected_sat_code
        ORDER BY correction_count DESC, last_corrected DESC
        LIMIT %s
    """

    cursor.execute(query, (company_id, limit))
    results = cursor.fetchall()
    conn.close()

    return [dict(row) for row in results]


def get_auto_apply_stats() -> Dict[str, Any]:
    """
    Get statistics on auto-applied classifications.

    Identifies patterns that were auto-applied based on learning.
    """
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    query = """
        SELECT
            COUNT(*) as total_auto_applied,
            COUNT(DISTINCT company_id) as companies_with_auto_apply,
            CAST(ROUND(CAST(AVG((accounting_classification->>'confidence_sat')::float) AS numeric), 3) AS float) as avg_confidence
        FROM expense_invoices
        WHERE accounting_classification->>'model_version' = 'auto-apply-v1'
    """

    cursor.execute(query)
    result = cursor.fetchone()
    conn.close()

    return dict(result) if result else {}


def print_metrics_report():
    """Print a comprehensive metrics report."""
    print("\n" + "="*80)
    print("CLASSIFICATION METRICS REPORT")
    print("="*80 + "\n")

    # Company-level metrics
    print("📊 Classification Accuracy by Company:")
    print("-" * 80)
    metrics = get_classification_metrics_by_company()

    if not metrics:
        print("No classification data found.")
    else:
        for company in metrics:
            print(f"\n{company['company_name']} (ID: {company['company_id']})")
            print(f"  Total invoices: {company['total_invoices']}")
            print(f"  Pending: {company['pending']} | Confirmed: {company['confirmed']} | Corrected: {company['corrected']}")
            print(f"  Correction rate: {company['correction_rate_pct']}%")
            print(f"  Confirmation rate: {company['confirmation_rate_pct']}%")
            print(f"  Avg confidence: {company['avg_confidence']}")

    # Auto-apply stats
    print("\n" + "-" * 80)
    print("🤖 Auto-Apply Statistics:")
    print("-" * 80)
    auto_stats = get_auto_apply_stats()

    if auto_stats and auto_stats.get('total_auto_applied', 0) > 0:
        print(f"  Total auto-applied: {auto_stats['total_auto_applied']}")
        print(f"  Companies using auto-apply: {auto_stats['companies_with_auto_apply']}")
        print(f"  Avg confidence: {auto_stats['avg_confidence']}")
    else:
        print("  No auto-applied classifications yet.")

    # Correction patterns for each company
    print("\n" + "-" * 80)
    print("🔄 Top Correction Patterns:")
    print("-" * 80)

    for company in metrics:
        if company['corrected'] > 0:
            print(f"\n{company['company_name']}:")
            patterns = get_correction_patterns_by_company(company['company_id'], limit=5)

            if patterns:
                for pattern in patterns:
                    print(f"  {pattern['provider_name'] or 'Unknown'} ({pattern['provider_rfc'] or 'N/A'})")
                    print(f"    {pattern['original_sat_code']} → {pattern['corrected_sat_code']} ({pattern['correction_count']}x)")
            else:
                print("  No correction patterns found.")

    print("\n" + "="*80 + "\n")


def run_ground_truth_test(ground_truth_file: str = "tests/ground_truth_invoices.json") -> Dict[str, Any]:
    """
    Test classifier against known-good classifications.

    Args:
        ground_truth_file: Path to JSON file with test cases

    Returns:
        Test results with accuracy metrics
    """
    # This is a placeholder - would require actual classifier integration
    # For now, just validate the structure

    try:
        with open(ground_truth_file, 'r') as f:
            test_cases = json.load(f)
    except FileNotFoundError:
        logger.warning(f"Ground truth file not found: {ground_truth_file}")
        return {"error": "Ground truth file not found"}

    results = {
        "total_cases": len(test_cases),
        "test_file": ground_truth_file,
        "status": "ready_for_testing"
    }

    logger.info(f"Loaded {len(test_cases)} ground truth test cases")
    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--ground-truth":
        print("\nRunning ground truth tests...")
        results = run_ground_truth_test()
        print(json.dumps(results, indent=2))
    else:
        print_metrics_report()

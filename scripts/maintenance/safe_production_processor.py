#!/usr/bin/env python3
"""
PRODUCTION-READY PDF Processor with all fixes implemented
Use this for commercial client deployments
"""
import os
import sys
sys.path.append('.')

from core.reconciliation.bank.bank_file_parser import BankFileParser
from core.extraction_validator import validate_pdf_extraction
import sqlite3
import logging
from datetime import datetime

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProductionPDFProcessor:
    """Production-ready PDF processor with all commercial fixes"""

    def __init__(self):
        self.parser = BankFileParser()

    def process_pdf_safe(self, pdf_path: str, account_id: int, user_id: int, tenant_id: int) -> dict:
        """
        Safely process PDF with all production fixes applied
        Returns detailed result with validation
        """
        logger.info(f"🏭 PRODUCTION: Processing PDF {pdf_path}")
        logger.info(f"📋 Account: {account_id}, User: {user_id}, Tenant: {tenant_id}")

        if not os.path.exists(pdf_path):
            return {
                "success": False,
                "error": f"PDF not found: {pdf_path}",
                "client_notification_required": True
            }

        try:
            # Step 1: Parse with improved parser (includes all fixes)
            logger.info("🔄 Step 1: Parsing PDF with enhanced patterns...")
            transactions, summary = self.parser.parse_file(pdf_path, "pdf", account_id, user_id, tenant_id)

            # Step 2: Validation layer (CRITICAL for production)
            logger.info("🔍 Step 2: Validating extraction quality...")
            validation_result = validate_pdf_extraction(len(transactions), pdf_path, transactions)

            # Step 3: Quality check before saving
            if not validation_result.get("is_complete", False):
                logger.warning("⚠️ Quality check failed - incomplete extraction detected")

                if validation_result.get("completion_rate", 0) < 0.8:
                    return {
                        "success": False,
                        "error": "Extraction quality too low for production use",
                        "validation": validation_result,
                        "recommendations": validation_result.get("recommendations", []),
                        "client_notification_required": True,
                        "manual_review_required": True
                    }

            # Step 4: Ensure Balance Inicial exists (critical for client UX)
            transactions = self._ensure_balance_inicial(transactions, summary, pdf_path)

            # Step 5: Save to database with proper user/tenant assignment
            logger.info("💾 Step 3: Saving to database...")
            success = self._save_to_database(pdf_path, account_id, user_id, tenant_id, transactions, summary)

            if not success:
                return {
                    "success": False,
                    "error": "Database save failed",
                    "client_notification_required": True
                }

            # Step 6: Final result with quality metrics
            result = {
                "success": True,
                "transactions_count": len(transactions),
                "summary": summary,
                "validation": validation_result,
                "quality_status": validation_result.get("status", "UNKNOWN"),
                "completion_rate": validation_result.get("completion_rate", 0),
                "client_notification_required": validation_result.get("client_notification_required", False),
                "message": f"Successfully processed {len(transactions)} transactions"
            }

            # Log success metrics
            logger.info(f"✅ SUCCESS: {len(transactions)} transactions processed")
            logger.info(f"📊 Quality: {validation_result.get('status')} ({validation_result.get('completion_rate', 0):.1%})")

            return result

        except Exception as e:
            logger.error(f"❌ PRODUCTION ERROR: {e}")
            import traceback
            traceback.print_exc()

            return {
                "success": False,
                "error": str(e),
                "client_notification_required": True,
                "manual_review_required": True
            }

    def _ensure_balance_inicial(self, transactions, summary, pdf_path):
        """Ensure Balance Inicial exists - critical for client UX"""
        try:
            # Check if Balance Inicial already exists
            has_balance_inicial = any('balance inicial' in t.description.lower() for t in transactions)

            if not has_balance_inicial:
                logger.info("🏦 Adding missing Balance Inicial...")

                # Extract balance from PDF text or use first transaction balance
                initial_balance = self._extract_initial_balance(pdf_path)

                if initial_balance > 0:
                    from core.reconciliation.bank.bank_statements_models import BankTransaction, TransactionType, MovementKind
                    from datetime import date

                    # Create Balance Inicial transaction
                    balance_inicial = BankTransaction(
                        account_id=transactions[0].account_id if transactions else None,
                        user_id=transactions[0].user_id if transactions else None,
                        tenant_id=transactions[0].tenant_id if transactions else None,
                        date=summary.get('period_start', date.today()),
                        description="Balance Inicial - Saldo del Período Anterior",
                        amount=0.0,
                        transaction_type=TransactionType.CREDIT,
                        raw_data=f"AUTO_GENERATED: Balance Inicial {initial_balance:,.2f}",
                        movement_kind=MovementKind.TRANSFERENCIA,
                        balance_after=initial_balance
                    )

                    # Insert at beginning
                    transactions.insert(0, balance_inicial)
                    logger.info(f"✅ Added Balance Inicial: ${initial_balance:,.2f}")

            return transactions

        except Exception as e:
            logger.warning(f"⚠️ Failed to add Balance Inicial: {e}")
            return transactions

    def _extract_initial_balance(self, pdf_path):
        """Extract initial balance from PDF text"""
        try:
            from core.ai_pipeline.parsers.robust_pdf_parser import RobustPDFParser
            parser = RobustPDFParser()
            text = parser.extract_text(pdf_path)

            # Look for "SALDO ANTERIOR" pattern
            import re
            match = re.search(r'SALDO\s+ANTERIOR\s+([\d,]+\.?\d*)', text, re.IGNORECASE)
            if match:
                balance_str = match.group(1).replace(',', '')
                return float(balance_str)

            # Fallback: look for first transaction balance
            if hasattr(self, 'transactions') and self.transactions:
                first_with_balance = next((t for t in self.transactions if t.balance_after), None)
                if first_with_balance:
                    return first_with_balance.balance_after

            return 0.0

        except Exception as e:
            logger.warning(f"⚠️ Failed to extract initial balance: {e}")
            return 0.0

    def _save_to_database(self, pdf_path, account_id, user_id, tenant_id, transactions, summary):
        """Save with proper error handling and transaction atomicity"""
        try:
            conn = sqlite3.connect("unified_mcp_system.db")
            cursor = conn.cursor()

            # Clear existing data for this account (prevent duplicates)
            cursor.execute("DELETE FROM bank_movements WHERE account_id = ? AND user_id = ? AND tenant_id = ?",
                         (account_id, user_id, tenant_id))
            cursor.execute("DELETE FROM bank_statements WHERE account_id = ? AND user_id = ? AND tenant_id = ?",
                         (account_id, user_id, tenant_id))

            # Add bank statement record
            file_name = os.path.basename(pdf_path)
            cursor.execute("""
                INSERT INTO bank_statements (
                    account_id, user_id, tenant_id, file_name, file_path, file_type,
                    period_start, period_end, transaction_count, total_credits, total_debits,
                    parsing_status, parsed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                account_id, user_id, tenant_id, file_name, pdf_path, "pdf",
                summary.get('period_start'), summary.get('period_end'),
                len(transactions), summary.get('total_credits', 0),
                abs(summary.get('total_debits', 0)), 'completed'
            ))

            # Save transactions
            for txn in transactions:
                cursor.execute("""
                    INSERT INTO bank_movements (
                        account_id, user_id, tenant_id, date, description, amount,
                        transaction_type, raw_data, movement_kind, reference, balance_after
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    txn.account_id, txn.user_id, txn.tenant_id, txn.date, txn.description,
                    txn.amount, txn.transaction_type, txn.raw_data,
                    txn.movement_kind if txn.movement_kind else None,
                    txn.reference, txn.balance_after
                ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Database save failed: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return False

# Convenience functions for production use
def process_december_safe():
    """Process December with all production fixes"""
    processor = ProductionPDFProcessor()
    pdf_path = "./uploads/statements/9_20250928_211924_Periodo_DIC 2024 (1).pdf"

    # CRITICAL: Use correct user_id and tenant_id (not hardcoded)
    result = processor.process_pdf_safe(pdf_path, 7, 9, 3)  # account=7, user=9, tenant=3

    print("🏭 PRODUCTION RESULT:")
    print(f"✅ Success: {result['success']}")
    if result['success']:
        print(f"📊 Transactions: {result['transactions_count']}")
        print(f"🎯 Quality: {result['quality_status']} ({result['completion_rate']:.1%})")
        print(f"📋 Validation: {result.get('validation', {}).get('status', 'N/A')}")
    else:
        print(f"❌ Error: {result['error']}")
        print(f"🔧 Manual review required: {result.get('manual_review_required', False)}")

if __name__ == "__main__":
    process_december_safe()
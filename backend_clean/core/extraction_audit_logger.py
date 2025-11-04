#!/usr/bin/env python3
"""
Sistema de auditoría para extracción de PDFs
Registra todo el proceso de extracción para análisis posterior
"""

import json
import logging
import sqlite3
from typing import Dict, List, Optional

class ExtractionAuditLogger:
    """Sistema de auditoría para rastrear extracciones de PDF y validaciones"""

    def __init__(self, db_path: str = "unified_mcp_system.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._ensure_audit_tables()

    def _ensure_audit_tables(self):
        """Crear tablas de auditoría si no existen"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Tabla de auditoría de extracciones
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pdf_extraction_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id INTEGER,
                    user_id INTEGER,
                    account_id INTEGER,
                    pdf_filename TEXT,
                    pdf_size_bytes INTEGER,
                    extraction_method TEXT,
                    extraction_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    raw_text_length INTEGER,
                    chunks_processed INTEGER,
                    transactions_extracted INTEGER,
                    transactions_after_dedup INTEGER,
                    validation_passed BOOLEAN,
                    validation_results TEXT, -- JSON
                    extraction_time_seconds REAL,
                    initial_balance REAL,
                    final_balance REAL,
                    balance_difference REAL,
                    errors_encountered TEXT, -- JSON array
                    warnings_encountered TEXT, -- JSON array
                    api_calls_made INTEGER,
                    api_cost_estimated REAL,
                    status TEXT DEFAULT 'completed', -- completed, failed, partial
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Tabla de transacciones perdidas/faltantes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS missing_transactions_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    extraction_audit_id INTEGER,
                    raw_date TEXT,
                    raw_description TEXT,
                    raw_amount REAL,
                    extraction_pattern TEXT,
                    source_line TEXT,
                    possible_reasons TEXT, -- JSON array
                    manual_review_required BOOLEAN DEFAULT TRUE,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolution_notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (extraction_audit_id) REFERENCES pdf_extraction_audit (id)
                )
            """)

            # Tabla de problemas de validación
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS validation_issues_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    extraction_audit_id INTEGER,
                    issue_type TEXT,
                    severity TEXT, -- critical, warning, info
                    message TEXT,
                    details TEXT, -- JSON
                    auto_resolved BOOLEAN DEFAULT FALSE,
                    manual_review_required BOOLEAN DEFAULT TRUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (extraction_audit_id) REFERENCES pdf_extraction_audit (id)
                )
            """)

            # Índices para mejor rendimiento
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_extraction_audit_tenant ON pdf_extraction_audit(tenant_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_extraction_audit_timestamp ON pdf_extraction_audit(extraction_timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_missing_transactions_audit ON missing_transactions_log(extraction_audit_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_validation_issues_audit ON validation_issues_log(extraction_audit_id)")

            conn.commit()
            conn.close()
            self.logger.info("✅ Audit tables initialized")

        except Exception as e:
            self.logger.error(f"❌ Error creating audit tables: {e}")

    def start_extraction_audit(self,
                             tenant_id: int,
                             user_id: int,
                             account_id: int,
                             pdf_filename: str,
                             pdf_size_bytes: int,
                             extraction_method: str = "llm") -> int:
        """
        Inicia un nuevo registro de auditoría para una extracción
        Retorna el ID del registro de auditoría
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO pdf_extraction_audit (
                    tenant_id, user_id, account_id, pdf_filename, pdf_size_bytes,
                    extraction_method, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'in_progress')
            """, (tenant_id, user_id, account_id, pdf_filename, pdf_size_bytes, extraction_method))

            audit_id = cursor.lastrowid
            conn.commit()
            conn.close()

            self.logger.info(f"🔍 Started extraction audit #{audit_id} for {pdf_filename}")
            return audit_id

        except Exception as e:
            self.logger.error(f"❌ Error starting extraction audit: {e}")
            return -1

    def complete_extraction_audit(self,
                                audit_id: int,
                                raw_text_length: int,
                                chunks_processed: int,
                                transactions_extracted: int,
                                transactions_after_dedup: int,
                                validation_results: Dict,
                                extraction_time_seconds: float,
                                initial_balance: Optional[float] = None,
                                final_balance: Optional[float] = None,
                                errors: List[str] = None,
                                warnings: List[str] = None,
                                api_calls_made: int = 0,
                                api_cost_estimated: float = 0.0):
        """Completa el registro de auditoría con todos los resultados"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            validation_passed = validation_results.get('is_complete', False)
            balance_difference = None
            if initial_balance is not None and final_balance is not None:
                balance_difference = final_balance - initial_balance

            cursor.execute("""
                UPDATE pdf_extraction_audit SET
                    raw_text_length = ?,
                    chunks_processed = ?,
                    transactions_extracted = ?,
                    transactions_after_dedup = ?,
                    validation_passed = ?,
                    validation_results = ?,
                    extraction_time_seconds = ?,
                    initial_balance = ?,
                    final_balance = ?,
                    balance_difference = ?,
                    errors_encountered = ?,
                    warnings_encountered = ?,
                    api_calls_made = ?,
                    api_cost_estimated = ?,
                    status = 'completed',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                raw_text_length,
                chunks_processed,
                transactions_extracted,
                transactions_after_dedup,
                validation_passed,
                json.dumps(validation_results),
                extraction_time_seconds,
                initial_balance,
                final_balance,
                balance_difference,
                json.dumps(errors or []),
                json.dumps(warnings or []),
                api_calls_made,
                api_cost_estimated,
                audit_id
            ))

            # Log missing transactions (with tenant_id)
            if validation_results.get('missing_transactions'):
                # Get tenant_id from the extraction audit
                cursor.execute("SELECT tenant_id FROM pdf_extraction_audit WHERE id = ?", (audit_id,))
                tenant_id = cursor.fetchone()[0]

                for missing in validation_results['missing_transactions']:
                    raw_txn = missing['raw_transaction']
                    cursor.execute("""
                        INSERT INTO missing_transactions_log (
                            extraction_audit_id, tenant_id, raw_date, raw_description, raw_amount,
                            extraction_pattern, source_line, possible_reasons
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        audit_id,
                        tenant_id,
                        raw_txn['raw_date'],
                        raw_txn['raw_description'],
                        raw_txn['raw_amount'],
                        raw_txn.get('extraction_pattern', ''),
                        raw_txn.get('source_line', ''),
                        json.dumps(missing.get('possible_reasons', []))
                    ))

            # Log validation issues (with tenant_id)
            if validation_results.get('issues'):
                for issue in validation_results['issues']:
                    cursor.execute("""
                        INSERT INTO validation_issues_log (
                            extraction_audit_id, tenant_id, issue_type, severity, message, details
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        audit_id,
                        tenant_id,
                        issue['type'],
                        issue['severity'],
                        issue['message'],
                        json.dumps(issue.get('details', {}))
                    ))

            conn.commit()
            conn.close()

            status = "✅ PASSED" if validation_passed else "❌ FAILED"
            self.logger.info(f"🔍 Completed extraction audit #{audit_id} - {status}")

        except Exception as e:
            self.logger.error(f"❌ Error completing extraction audit: {e}")

    def fail_extraction_audit(self, audit_id: int, error_message: str):
        """Marca una auditoría como fallida"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE pdf_extraction_audit SET
                    status = 'failed',
                    errors_encountered = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (json.dumps([error_message]), audit_id))

            conn.commit()
            conn.close()

            self.logger.error(f"❌ Failed extraction audit #{audit_id}: {error_message}")

        except Exception as e:
            self.logger.error(f"❌ Error failing extraction audit: {e}")

    def get_audit_summary(self, tenant_id: int, days: int = 30) -> Dict:
        """Obtiene un resumen de auditorías recientes"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COUNT(*) as total_extractions,
                    SUM(CASE WHEN validation_passed = 1 THEN 1 ELSE 0 END) as successful_extractions,
                    SUM(CASE WHEN validation_passed = 0 THEN 1 ELSE 0 END) as failed_extractions,
                    AVG(extraction_time_seconds) as avg_extraction_time,
                    SUM(transactions_extracted) as total_transactions_found,
                    SUM(api_calls_made) as total_api_calls,
                    SUM(api_cost_estimated) as total_estimated_cost
                FROM pdf_extraction_audit
                WHERE tenant_id = ? AND extraction_timestamp >= datetime('now', '-{} days')
            """.format(days), (tenant_id,))

            result = cursor.fetchone()

            # Get recent failed extractions with details
            cursor.execute("""
                SELECT pdf_filename, extraction_timestamp, validation_results
                FROM pdf_extraction_audit
                WHERE tenant_id = ? AND validation_passed = 0
                  AND extraction_timestamp >= datetime('now', '-{} days')
                ORDER BY extraction_timestamp DESC
                LIMIT 5
            """.format(days), (tenant_id,))

            failed_extractions = []
            for row in cursor.fetchall():
                validation_results = json.loads(row[2]) if row[2] else {}
                failed_extractions.append({
                    'filename': row[0],
                    'timestamp': row[1],
                    'issues_count': len(validation_results.get('issues', [])),
                    'missing_transactions': len(validation_results.get('missing_transactions', []))
                })

            conn.close()

            return {
                'period_days': days,
                'total_extractions': result[0] or 0,
                'successful_extractions': result[1] or 0,
                'failed_extractions': result[2] or 0,
                'success_rate': round((result[1] or 0) / max(result[0] or 1, 1) * 100, 1),
                'avg_extraction_time': round(result[3] or 0, 2),
                'total_transactions_found': result[4] or 0,
                'total_api_calls': result[5] or 0,
                'total_estimated_cost': round(result[6] or 0, 4),
                'recent_failures': failed_extractions
            }

        except Exception as e:
            self.logger.error(f"❌ Error getting audit summary: {e}")
            return {}

    def get_missing_transactions_for_review(self, tenant_id: int, limit: int = 50) -> List[Dict]:
        """Obtiene transacciones faltantes que requieren revisión manual"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    mt.id,
                    mt.raw_date,
                    mt.raw_description,
                    mt.raw_amount,
                    mt.possible_reasons,
                    mt.source_line,
                    ea.pdf_filename,
                    ea.extraction_timestamp
                FROM missing_transactions_log mt
                JOIN pdf_extraction_audit ea ON mt.extraction_audit_id = ea.id
                WHERE ea.tenant_id = ? AND mt.manual_review_required = 1 AND mt.resolved = 0
                ORDER BY ea.extraction_timestamp DESC
                LIMIT ?
            """, (tenant_id, limit))

            missing_transactions = []
            for row in cursor.fetchall():
                reasons = json.loads(row[4]) if row[4] else []
                missing_transactions.append({
                    'id': row[0],
                    'raw_date': row[1],
                    'raw_description': row[2],
                    'raw_amount': row[3],
                    'possible_reasons': reasons,
                    'source_line': row[5],
                    'pdf_filename': row[6],
                    'extraction_timestamp': row[7]
                })

            conn.close()
            return missing_transactions

        except Exception as e:
            self.logger.error(f"❌ Error getting missing transactions: {e}")
            return []

    def mark_missing_transaction_resolved(self, missing_id: int, resolution_notes: str):
        """Marca una transacción faltante como resuelta"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE missing_transactions_log SET
                    resolved = 1,
                    manual_review_required = 0,
                    resolution_notes = ?
                WHERE id = ?
            """, (resolution_notes, missing_id))

            conn.commit()
            conn.close()

            self.logger.info(f"✅ Marked missing transaction #{missing_id} as resolved")

        except Exception as e:
            self.logger.error(f"❌ Error resolving missing transaction: {e}")

# Singleton instance
audit_logger = ExtractionAuditLogger()

def log_extraction_start(tenant_id: int, user_id: int, account_id: int,
                        pdf_filename: str, pdf_size_bytes: int,
                        extraction_method: str = "llm") -> int:
    """Helper function to start audit logging"""
    return audit_logger.start_extraction_audit(
        tenant_id, user_id, account_id, pdf_filename, pdf_size_bytes, extraction_method
    )

def log_extraction_complete(audit_id: int, **kwargs):
    """Helper function to complete audit logging"""
    return audit_logger.complete_extraction_audit(audit_id, **kwargs)

def log_extraction_failed(audit_id: int, error_message: str):
    """Helper function to log extraction failure"""
    return audit_logger.fail_extraction_audit(audit_id, error_message)

if __name__ == "__main__":
    # Test the audit logger
    print("🔍 Extraction Audit Logger - Sistema de auditoría para extracciones PDF")
    print("Este módulo rastrea todo el proceso de extracción para análisis posterior")
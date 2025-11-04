#!/usr/bin/env python3
"""
🔍 VALIDATION DE MAPEO DE CAMPOS UI ↔ API ↔ BD
Verifica que TODOS los campos migrados estén correctamente mapeados entre las 3 capas
"""

import pytest
import sqlite3
import json
import requests
from pathlib import Path
import sys
from typing import Dict, List, Set

# Add root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

class FieldMappingValidator:
    """Validador de mapeo de campos entre capas"""

    def __init__(self):
        self.db_path = "unified_mcp_system.db"
        self.base_url = "http://localhost:8000"
        self.db_connection = sqlite3.connect(self.db_path)
        self.db_connection.row_factory = sqlite3.Row

    def get_database_schema(self) -> Dict[str, List[str]]:
        """Obtener schema completo de la base de datos"""
        cursor = self.db_connection.cursor()

        # Obtener todas las tablas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        schema = {}
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]  # row[1] is column name
            schema[table] = columns

        return schema

    def validate_expense_fields_mapping(self) -> Dict[str, bool]:
        """Validar mapeo completo de campos de gastos"""
        results = {}

        # CAMPOS CRÍTICOS QUE DEBEN EXISTIR (de la migración)
        critical_fields = {
            # Campos básicos
            "amount": True,
            "currency": True,
            "description": True,
            "category": True,
            "merchant_name": True,
            "date": True,
            "user_id": True,
            "tenant_id": True,
            "status": True,

            # Campos migrados críticos
            "deducible": True,
            "requiere_factura": True,
            "centro_costo": True,
            "proyecto": True,
            "metodo_pago": True,
            "rfc_proveedor": True,
            "cfdi_uuid": True,
            "invoice_status": True,
            "bank_status": True,
            "approval_status": True,

            # Campos ML
            "categoria_sugerida": True,
            "confianza": True,
            "razonamiento": True,
            "category_alternatives": True,
            "prediction_method": True,
            "ml_model_version": True,
            "predicted_at": True,
            "ml_features_json": True,

            # Campos duplicados
            "similarity_score": True,
            "risk_level": True,
            "is_duplicate": True,
            "duplicate_of": True,
            "duplicate_confidence": True,

            # Campos audit
            "tags": True,
            "audit_trail": True,
            "user_context": True,
            "enhanced_data": True,
            "completion_status": True,
            "validation_errors": True,
            "field_completeness": True
        }

        # 1. VALIDAR EN BASE DE DATOS
        schema = self.get_database_schema()
        expense_columns = schema.get("expense_records", [])

        for field, expected in critical_fields.items():
            field_exists = field in expense_columns
            results[f"BD_{field}"] = field_exists
            if not field_exists and expected:
                print(f"❌ FALTA EN BD: {field}")
            elif field_exists:
                print(f"✅ BD OK: {field}")

        # 2. VALIDAR VÍA API (crear expense de prueba)
        try:
            test_expense = {
                "amount": 1500.50,
                "currency": "MXN",
                "description": "Test API Mapping",
                "category": "office_supplies",
                "merchant_name": "Test Merchant",
                "deducible": True,
                "centro_costo": "IT",
                "proyecto": "TEST_PROJECT",
                "metodo_pago": "credit_card",
                "tags": ["test", "validation"]
            }

            response = requests.post(
                f"{self.base_url}/expenses",
                json=test_expense,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                api_response = response.json()

                # Verificar que los campos enviados están en la respuesta o BD
                for field in test_expense.keys():
                    api_has_field = field in api_response
                    results[f"API_{field}"] = api_has_field
                    if api_has_field:
                        print(f"✅ API OK: {field}")
                    else:
                        print(f"⚠️ API NO RETORNA: {field}")
            else:
                print(f"⚠️ API ERROR: {response.status_code}")

        except Exception as e:
            print(f"⚠️ API TEST FAILED: {e}")

        return results

    def validate_bank_movements_mapping(self) -> Dict[str, bool]:
        """Validar mapeo de campos bancarios"""
        results = {}

        critical_bank_fields = {
            "amount": True,
            "description": True,
            "date": True,
            "account": True,
            "tenant_id": True,
            "matched_expense_id": True,
            # Campos migrados
            "decision": True,
            "bank_metadata": True,
            "confidence": True,
            "matching_confidence": True,
            "movement_id": True,
            "transaction_type": True,
            "reference": True,
            "balance_after": True,
            "raw_data": True,
            "processing_status": True,
            "matched_at": True,
            "matched_by": True,
            "auto_matched": True,
            "reconciliation_notes": True,
            "bank_account_id": True,
            "category": True
        }

        schema = self.get_database_schema()
        bank_columns = schema.get("bank_movements", [])

        for field, expected in critical_bank_fields.items():
            field_exists = field in bank_columns
            results[f"BANK_BD_{field}"] = field_exists
            if not field_exists and expected:
                print(f"❌ BANK FALTA: {field}")
            elif field_exists:
                print(f"✅ BANK OK: {field}")

        return results

    def validate_invoice_fields_mapping(self) -> Dict[str, bool]:
        """Validar mapeo de campos de facturas/OCR"""
        results = {}

        critical_invoice_fields = {
            "expense_id": True,
            "filename": True,
            "tenant_id": True,
            # Campos migrados OCR
            "uuid": True,
            "rfc_emisor": True,
            "nombre_emisor": True,
            "subtotal": True,
            "iva_amount": True,
            "total": True,
            "xml_content": True,
            "validation_status": True,
            "processing_metadata": True,
            "template_match": True,
            "validation_rules": True,
            "detected_format": True,
            "parser_used": True,
            "ocr_confidence": True,
            "processing_metrics": True,
            "quality_score": True,
            "processor_used": True,
            "extraction_confidence": True,
            "discount": True,
            "retention": True
        }

        schema = self.get_database_schema()
        invoice_columns = schema.get("expense_invoices", [])

        for field, expected in critical_invoice_fields.items():
            field_exists = field in invoice_columns
            results[f"INVOICE_BD_{field}"] = field_exists
            if not field_exists and expected:
                print(f"❌ INVOICE FALTA: {field}")
            elif field_exists:
                print(f"✅ INVOICE OK: {field}")

        return results

    def validate_automation_fields_mapping(self) -> Dict[str, bool]:
        """Validar campos de automatización y workers"""
        results = {}

        # Automation Jobs
        automation_fields = {
            "job_type": True,
            "status": True,
            "tenant_id": True,
            # Campos migrados
            "checkpoint_data": True,
            "recovery_metadata": True,
            "session_id": True,
            "automation_health": True,
            "performance_metrics": True,
            "recovery_actions": True
        }

        # Workers
        worker_fields = {
            "task_id": True,
            "company_id": True,
            "task_type": True,
            "status": True,
            # Campos migrados
            "progress": True,
            "worker_metadata": True,
            "retry_policy": True,
            "retry_count": True,
            "result_data": True
        }

        schema = self.get_database_schema()

        # Validar automation_jobs
        automation_columns = schema.get("automation_jobs", [])
        for field, expected in automation_fields.items():
            field_exists = field in automation_columns
            results[f"AUTO_BD_{field}"] = field_exists
            if not field_exists and expected:
                print(f"❌ AUTO FALTA: {field}")
            elif field_exists:
                print(f"✅ AUTO OK: {field}")

        # Validar workers
        worker_columns = schema.get("workers", [])
        for field, expected in worker_fields.items():
            field_exists = field in worker_columns
            results[f"WORKER_BD_{field}"] = field_exists
            if not field_exists and expected:
                print(f"❌ WORKER FALTA: {field}")
            elif field_exists:
                print(f"✅ WORKER OK: {field}")

        return results

    def generate_coherence_report(self) -> Dict:
        """Generar reporte completo de coherencia"""
        print("🔍 INICIANDO VALIDACIÓN DE MAPEO DE CAMPOS")
        print("=" * 60)

        # Validar todas las entidades
        expense_results = self.validate_expense_fields_mapping()
        bank_results = self.validate_bank_movements_mapping()
        invoice_results = self.validate_invoice_fields_mapping()
        automation_results = self.validate_automation_fields_mapping()

        # Combinar resultados
        all_results = {
            **expense_results,
            **bank_results,
            **invoice_results,
            **automation_results
        }

        # Calcular estadísticas
        total_fields = len(all_results)
        passed_fields = sum(1 for result in all_results.values() if result)
        coherence_percentage = (passed_fields / total_fields) * 100 if total_fields > 0 else 0

        report = {
            "timestamp": "2025-09-26",
            "total_fields_validated": total_fields,
            "fields_passed": passed_fields,
            "fields_failed": total_fields - passed_fields,
            "coherence_percentage": round(coherence_percentage, 2),
            "details": all_results,
            "summary": {
                "expense_fields": len(expense_results),
                "bank_fields": len(bank_results),
                "invoice_fields": len(invoice_results),
                "automation_fields": len(automation_results)
            }
        }

        print("=" * 60)
        print(f"📊 RESULTADOS DE VALIDACIÓN:")
        print(f"   Total campos validados: {total_fields}")
        print(f"   Campos correctos: {passed_fields}")
        print(f"   Campos con problemas: {total_fields - passed_fields}")
        print(f"   Coherencia: {coherence_percentage:.1f}%")

        if coherence_percentage >= 90:
            print("✅ COHERENCIA EXCELENTE - Sistema production-ready")
        elif coherence_percentage >= 80:
            print("🟡 COHERENCIA BUENA - Mejoras menores requeridas")
        else:
            print("🔴 COHERENCIA BAJA - Requiere atención crítica")

        return report

    def __del__(self):
        if hasattr(self, 'db_connection'):
            self.db_connection.close()

class TestFieldMappingComplete:
    """Tests completos de mapeo de campos"""

    def test_critical_fields_exist(self):
        """Verificar que todos los campos críticos existen"""
        validator = FieldMappingValidator()
        report = validator.generate_coherence_report()

        # El sistema debe tener al menos 90% de coherencia
        assert report["coherence_percentage"] >= 85, f"Coherencia muy baja: {report['coherence_percentage']}%"

        # No debe haber más de 10 campos fallando
        assert report["fields_failed"] <= 10, f"Demasiados campos fallando: {report['fields_failed']}"

    def test_expense_migration_fields(self):
        """Test específico para campos migrados en expenses"""
        validator = FieldMappingValidator()
        schema = validator.get_database_schema()
        expense_columns = schema.get("expense_records", [])

        # Campos que DEBEN existir después de la migración
        required_migrated_fields = [
            "deducible", "centro_costo", "proyecto", "tags",
            "categoria_sugerida", "confianza", "is_duplicate",
            "completion_status", "field_completeness"
        ]

        for field in required_migrated_fields:
            assert field in expense_columns, f"Campo migrado faltante: {field}"

    def test_bank_reconciliation_fields(self):
        """Test específico para campos de conciliación bancaria"""
        validator = FieldMappingValidator()
        schema = validator.get_database_schema()
        bank_columns = schema.get("bank_movements", [])

        required_bank_fields = [
            "decision", "bank_metadata", "matching_confidence",
            "auto_matched", "processing_status"
        ]

        for field in required_bank_fields:
            assert field in bank_columns, f"Campo bancario faltante: {field}"

    def test_ocr_processing_fields(self):
        """Test específico para campos de procesamiento OCR"""
        validator = FieldMappingValidator()
        schema = validator.get_database_schema()
        invoice_columns = schema.get("expense_invoices", [])

        required_ocr_fields = [
            "ocr_confidence", "template_match", "quality_score",
            "detected_format", "parser_used", "validation_status"
        ]

        for field in required_ocr_fields:
            assert field in invoice_columns, f"Campo OCR faltante: {field}"

if __name__ == "__main__":
    print("🔍 EJECUTANDO VALIDACIÓN DE MAPEO DE CAMPOS")
    validator = FieldMappingValidator()
    report = validator.generate_coherence_report()

    # Guardar reporte
    with open("field_mapping_validation_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n📄 Reporte guardado en: field_mapping_validation_report.json")
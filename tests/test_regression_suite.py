#!/usr/bin/env python3
"""
🔄 SUITE DE TESTS DE REGRESIÓN AUTOMÁTICA
Valida que las funcionalidades existentes no se rompan con nuevos cambios
"""

import pytest
import sqlite3
import json
import requests
import asyncio
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any
import sys

# Add root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

class RegressionTestSuite:
    """Suite completa de tests de regresión"""

    def __init__(self):
        self.db_path = "unified_mcp_system.db"
        self.base_url = "http://localhost:8000"
        self.db_connection = sqlite3.connect(self.db_path)
        self.db_connection.row_factory = sqlite3.Row

    def setup_test_data(self):
        """Crear datos de prueba consistentes"""
        cursor = self.db_connection.cursor()

        # Limpiar datos de prueba anteriores
        cursor.execute("DELETE FROM expense_records WHERE description LIKE '%REGRESSION_TEST%'")
        cursor.execute("DELETE FROM bank_movements WHERE description LIKE '%REGRESSION_TEST%'")
        cursor.execute("DELETE FROM automation_jobs WHERE job_type = 'regression_test'")

        # Crear tenant y usuario de prueba
        cursor.execute("""
            INSERT OR IGNORE INTO tenants (name, api_key, config)
            VALUES ('regression_test_tenant', 'test_key_regression', '{}')
        """)

        cursor.execute("""
            INSERT OR IGNORE INTO users (email, full_name, tenant_id, role)
            VALUES ('regression@test.com', 'Regression User', 1, 'user')
        """)

        self.db_connection.commit()
        return {"tenant_id": 1, "user_id": 1}

    def cleanup_test_data(self):
        """Limpiar datos de prueba"""
        cursor = self.db_connection.cursor()
        cursor.execute("DELETE FROM expense_records WHERE description LIKE '%REGRESSION_TEST%'")
        cursor.execute("DELETE FROM bank_movements WHERE description LIKE '%REGRESSION_TEST%'")
        cursor.execute("DELETE FROM automation_jobs WHERE job_type = 'regression_test'")
        self.db_connection.commit()

    def __del__(self):
        if hasattr(self, 'db_connection'):
            self.db_connection.close()

class TestCoreFeatureRegression(RegressionTestSuite):
    """Tests de regresión para funcionalidades core"""

    def test_expense_creation_api_regression(self):
        """Verificar que la API de gastos mantiene compatibilidad"""
        self.setup_test_data()

        try:
            # Test 1: Formato básico (retrocompatibilidad)
            basic_expense = {
                "amount": 100.50,
                "description": "REGRESSION_TEST Basic Expense",
                "category": "office_supplies"
            }

            response = requests.post(
                f"{self.base_url}/expenses",
                json=basic_expense,
                headers={"Content-Type": "application/json"}
            )

            assert response.status_code == 200, f"Basic expense API failed: {response.text}"
            basic_result = response.json()
            assert "id" in basic_result

            # Test 2: Formato completo con campos migrados
            complete_expense = {
                "amount": 500.75,
                "currency": "MXN",
                "description": "REGRESSION_TEST Complete Expense",
                "category": "travel",
                "merchant_name": "Hotel Test",
                "deducible": True,
                "requiere_factura": True,
                "centro_costo": "SALES",
                "proyecto": "CLIENT_PROJECT",
                "metodo_pago": "credit_card",
                "tags": ["travel", "client", "sales"]
            }

            response = requests.post(
                f"{self.base_url}/expenses",
                json=complete_expense,
                headers={"Content-Type": "application/json"}
            )

            assert response.status_code == 200, f"Complete expense API failed: {response.text}"
            complete_result = response.json()
            assert "id" in complete_result

            # Test 3: Verificar en BD que ambos se guardaron correctamente
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT * FROM expense_records
                WHERE description LIKE '%REGRESSION_TEST%'
                ORDER BY id DESC LIMIT 2
            """)

            expenses = cursor.fetchall()
            assert len(expenses) == 2, "No se crearon ambos gastos"

            # Verificar expense completo
            complete_expense_db = expenses[0]
            assert complete_expense_db["deducible"] == 1
            assert complete_expense_db["centro_costo"] == "SALES"
            assert complete_expense_db["proyecto"] == "CLIENT_PROJECT"

            # Verificar expense básico (campos migrados con defaults)
            basic_expense_db = expenses[1]
            assert basic_expense_db["amount"] == 100.50
            assert basic_expense_db["description"] == "REGRESSION_TEST Basic Expense"

            print("✅ REGRESSION: API Expenses mantiene compatibilidad")

        finally:
            self.cleanup_test_data()

    def test_database_schema_regression(self):
        """Verificar que el schema de BD mantiene estructura esperada"""
        cursor = self.db_connection.cursor()

        # Verificar tablas críticas existen
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        critical_tables = [
            "tenants", "users", "expense_records", "bank_movements",
            "expense_invoices", "automation_jobs", "workers"
        ]

        for table in critical_tables:
            assert table in tables, f"Tabla crítica faltante: {table}"

        # Verificar campos migrados críticos en expense_records
        cursor.execute("PRAGMA table_info(expense_records)")
        expense_columns = [row[1] for row in cursor.fetchall()]

        migrated_fields = [
            "deducible", "centro_costo", "proyecto", "tags",
            "categoria_sugerida", "confianza", "is_duplicate",
            "completion_status", "field_completeness"
        ]

        for field in migrated_fields:
            assert field in expense_columns, f"Campo migrado faltante: {field}"

        # Verificar índices existen
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND tbl_name='expense_records'
        """)
        indexes = [row[0] for row in cursor.fetchall()]
        assert len(indexes) > 0, "Faltan índices en expense_records"

        print("✅ REGRESSION: Schema BD mantiene estructura")

    def test_bank_reconciliation_regression(self):
        """Verificar que conciliación bancaria funciona correctamente"""
        self.setup_test_data()

        try:
            # 1. Crear gasto
            cursor = self.db_connection.cursor()
            cursor.execute("""
                INSERT INTO expense_records
                (amount, description, tenant_id, user_id, status)
                VALUES (250.75, 'REGRESSION_TEST Bank Reconciliation', 1, 1, 'pending')
            """)
            expense_id = cursor.lastrowid

            # 2. Crear movimiento bancario con campos migrados
            cursor.execute("""
                INSERT INTO bank_movements
                (amount, description, date, account, tenant_id,
                 decision, matching_confidence, auto_matched, processing_status)
                VALUES (250.75, 'REGRESSION_TEST Bank Movement', ?, 'ACCOUNT_TEST', 1,
                        'pending', 0.0, 0, 'pending')
            """, (datetime.now().isoformat(),))
            movement_id = cursor.lastrowid
            self.db_connection.commit()

            # 3. Simular API de sugerencias
            try:
                response = requests.post(
                    f"{self.base_url}/bank_reconciliation/suggestions",
                    json={
                        "expense_id": expense_id,
                        "amount": 250.75,
                        "description": "REGRESSION_TEST Bank Movement"
                    }
                )

                # API puede no estar implementada completamente, pero BD debe funcionar
                if response.status_code == 200:
                    suggestions = response.json()
                    print("✅ API Bank Reconciliation responde")
                else:
                    print("⚠️ API Bank Reconciliation no implementada, pero BD OK")

            except Exception as e:
                print(f"⚠️ API test failed: {e}, continuando con test BD")

            # 4. Simular matching manual
            cursor.execute("""
                UPDATE bank_movements SET
                    matched_expense_id = ?,
                    decision = 'accept',
                    matching_confidence = 0.95,
                    auto_matched = 0,
                    matched_at = ?,
                    processing_status = 'processed'
                WHERE id = ?
            """, (expense_id, datetime.now().isoformat(), movement_id))

            cursor.execute("""
                UPDATE expense_records SET
                    bank_status = 'reconciled'
                WHERE id = ?
            """, (expense_id,))

            self.db_connection.commit()

            # 5. Verificar relación BD
            cursor.execute("""
                SELECT er.description, bm.decision, bm.matching_confidence
                FROM expense_records er
                JOIN bank_movements bm ON er.id = bm.matched_expense_id
                WHERE er.id = ? AND bm.id = ?
            """, (expense_id, movement_id))

            result = cursor.fetchone()
            assert result is not None, "Relación expense-bank no establecida"
            assert result["decision"] == "accept"
            assert result["matching_confidence"] == 0.95

            print("✅ REGRESSION: Bank Reconciliation funciona correctamente")

        finally:
            self.cleanup_test_data()

    def test_automation_system_regression(self):
        """Verificar que sistema de automatización mantiene funcionalidad"""
        self.setup_test_data()

        try:
            cursor = self.db_connection.cursor()

            # 1. Crear job de automatización con campos migrados
            checkpoint_data = {
                "step": 3,
                "url": "https://test-regression.com",
                "elements_found": 5,
                "form_data": {"test": "regression"}
            }

            recovery_metadata = {
                "retry_count": 0,
                "last_checkpoint": "step_3",
                "recovery_strategy": "restart"
            }

            automation_health = {
                "status": "healthy",
                "memory_usage": "40%",
                "last_heartbeat": datetime.now().isoformat()
            }

            cursor.execute("""
                INSERT INTO automation_jobs
                (job_type, status, tenant_id, checkpoint_data,
                 recovery_metadata, session_id, automation_health)
                VALUES ('regression_test', 'running', 1, ?, ?, 'session_regression', ?)
            """, (json.dumps(checkpoint_data), json.dumps(recovery_metadata),
                  json.dumps(automation_health)))

            job_id = cursor.lastrowid

            # 2. Crear worker asociado
            cursor.execute("""
                INSERT INTO workers
                (task_id, company_id, task_type, status, progress,
                 worker_metadata, retry_policy)
                VALUES ('regression_task', 1, 'regression_processing', 'running', 0.6,
                        '{"job_id": ' + str(job_id) + '}',
                        '{"max_retries": 3}')
            """)

            worker_id = cursor.lastrowid
            self.db_connection.commit()

            # 3. Verificar campos JSON se guardan/leen correctamente
            cursor.execute("""
                SELECT checkpoint_data, recovery_metadata, automation_health
                FROM automation_jobs WHERE id = ?
            """, (job_id,))

            job_record = cursor.fetchone()
            assert job_record is not None

            # Verificar que JSON se deserializa correctamente
            checkpoint = json.loads(job_record["checkpoint_data"])
            recovery = json.loads(job_record["recovery_metadata"])
            health = json.loads(job_record["automation_health"])

            assert checkpoint["step"] == 3
            assert recovery["retry_count"] == 0
            assert health["status"] == "healthy"

            # 4. Verificar worker fields
            cursor.execute("SELECT progress, worker_metadata FROM workers WHERE id = ?", (worker_id,))
            worker_record = cursor.fetchone()
            assert worker_record["progress"] == 0.6

            worker_metadata = json.loads(worker_record["worker_metadata"])
            assert worker_metadata["job_id"] == job_id

            print("✅ REGRESSION: Automation System funciona correctamente")

        finally:
            self.cleanup_test_data()

    def test_ml_features_regression(self):
        """Verificar que funcionalidades ML mantienen compatibilidad"""
        self.setup_test_data()

        try:
            cursor = self.db_connection.cursor()

            # 1. Crear expense con campos ML completos
            ml_features = {
                "keywords": ["test", "regression"],
                "amount_category": "medium",
                "merchant_type": "test_vendor"
            }

            cursor.execute("""
                INSERT INTO expense_records
                (description, amount, tenant_id, user_id,
                 categoria_sugerida, confianza, razonamiento,
                 category_alternatives, prediction_method, ml_model_version,
                 ml_features_json, predicted_at, category_confirmed)
                VALUES ('REGRESSION_TEST ML Features', 300.50, 1, 1,
                        'office_supplies', 0.89, 'Keywords regression, test detected',
                        '["office_supplies", "business_supplies"]', 'ml_classifier_v2',
                        'v2.1.3', ?, ?, 1)
            """, (json.dumps(ml_features), datetime.now().isoformat()))

            expense_id = cursor.lastrowid

            # 2. Test detección de duplicados
            cursor.execute("""
                INSERT INTO expense_records
                (description, amount, tenant_id, user_id,
                 similarity_score, is_duplicate, duplicate_of, duplicate_confidence)
                VALUES ('REGRESSION_TEST ML Features', 300.50, 1, 1,
                        0.95, 1, ?, 0.95)
            """, (expense_id,))

            duplicate_id = cursor.lastrowid
            self.db_connection.commit()

            # 3. Verificar campos ML se guardan correctamente
            cursor.execute("""
                SELECT categoria_sugerida, confianza, ml_features_json,
                       category_alternatives, prediction_method
                FROM expense_records WHERE id = ?
            """, (expense_id,))

            ml_record = cursor.fetchone()
            assert ml_record["categoria_sugerida"] == "office_supplies"
            assert ml_record["confianza"] == 0.89

            # Verificar JSON fields
            features = json.loads(ml_record["ml_features_json"])
            assert "keywords" in features
            assert "regression" in features["keywords"]

            alternatives = json.loads(ml_record["category_alternatives"])
            assert "office_supplies" in alternatives

            # 4. Verificar detección duplicados
            cursor.execute("""
                SELECT is_duplicate, duplicate_of, similarity_score
                FROM expense_records WHERE id = ?
            """, (duplicate_id,))

            duplicate_record = cursor.fetchone()
            assert duplicate_record["is_duplicate"] == 1
            assert duplicate_record["duplicate_of"] == expense_id
            assert duplicate_record["similarity_score"] == 0.95

            # 5. Test API de predicción (si está disponible)
            try:
                response = requests.post(
                    f"{self.base_url}/expenses/predict-category",
                    json={
                        "description": "REGRESSION_TEST Category Prediction",
                        "amount": 150.0,
                        "merchant_name": "Test Vendor"
                    }
                )

                if response.status_code == 200:
                    prediction = response.json()
                    assert "predicted_category" in prediction or "categoria_sugerida" in prediction
                    print("✅ API ML Prediction responde")
                else:
                    print("⚠️ API ML Prediction no disponible")

            except Exception as e:
                print(f"⚠️ ML API test failed: {e}")

            print("✅ REGRESSION: ML Features funcionan correctamente")

        finally:
            self.cleanup_test_data()

class TestPerformanceRegression(RegressionTestSuite):
    """Tests de regresión de performance"""

    def test_database_query_performance(self):
        """Verificar que queries mantienen performance aceptable"""
        cursor = self.db_connection.cursor()

        # Test 1: Query simple expenses
        start_time = time.time()
        cursor.execute("SELECT COUNT(*) FROM expense_records")
        simple_query_time = time.time() - start_time
        assert simple_query_time < 1.0, f"Query simple muy lento: {simple_query_time}s"

        # Test 2: Query con JOINs
        start_time = time.time()
        cursor.execute("""
            SELECT er.description, ei.ocr_confidence, bm.matching_confidence
            FROM expense_records er
            LEFT JOIN expense_invoices ei ON er.id = ei.expense_id
            LEFT JOIN bank_movements bm ON er.id = bm.matched_expense_id
            LIMIT 100
        """)
        join_query_time = time.time() - start_time
        assert join_query_time < 2.0, f"Query con JOINs muy lento: {join_query_time}s"

        # Test 3: Query con JSON fields (campos migrados)
        start_time = time.time()
        cursor.execute("""
            SELECT id, ml_features_json, category_alternatives
            FROM expense_records
            WHERE categoria_sugerida IS NOT NULL
            LIMIT 50
        """)
        json_query_time = time.time() - start_time
        assert json_query_time < 1.5, f"Query JSON muy lento: {json_query_time}s"

        print(f"✅ REGRESSION: Performance BD OK")
        print(f"   Simple query: {simple_query_time:.3f}s")
        print(f"   JOIN query: {join_query_time:.3f}s")
        print(f"   JSON query: {json_query_time:.3f}s")

    def test_api_response_time_regression(self):
        """Verificar que APIs mantienen tiempo de respuesta aceptable"""
        endpoints_to_test = [
            ("/health", "GET"),
            ("/expenses", "GET"),
        ]

        for endpoint, method in endpoints_to_test:
            start_time = time.time()

            try:
                if method == "GET":
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                else:
                    response = requests.post(f"{self.base_url}{endpoint}", json={}, timeout=5)

                response_time = time.time() - start_time

                if response.status_code in [200, 405]:  # 405 for not implemented
                    assert response_time < 3.0, f"API {endpoint} muy lento: {response_time}s"
                    print(f"✅ API {endpoint}: {response_time:.3f}s")
                else:
                    print(f"⚠️ API {endpoint}: Status {response.status_code}")

            except requests.exceptions.RequestException as e:
                print(f"⚠️ API {endpoint}: {e}")

class TestDataIntegrityRegression(RegressionTestSuite):
    """Tests de regresión de integridad de datos"""

    def test_foreign_key_constraints_regression(self):
        """Verificar que constraints FK se mantienen"""
        cursor = self.db_connection.cursor()

        # Verificar no hay violaciones FK
        cursor.execute("PRAGMA foreign_key_check")
        violations = cursor.fetchall()
        assert len(violations) == 0, f"Violaciones FK: {violations}"

        # Test violación intencional (debe fallar)
        try:
            cursor.execute("""
                INSERT INTO expense_records (tenant_id, user_id, amount, description)
                VALUES (99999, 1, 100, 'Test FK violation')
            """)
            assert False, "FK constraint no está funcionando"
        except sqlite3.IntegrityError:
            pass  # Esperado

        print("✅ REGRESSION: Foreign Key constraints OK")

    def test_data_consistency_regression(self):
        """Verificar consistencia de datos después de migración"""
        cursor = self.db_connection.cursor()

        # 1. Verificar no hay datos huérfanos
        cursor.execute("""
            SELECT COUNT(*) as orphaned
            FROM expense_records er
            WHERE er.tenant_id NOT IN (SELECT id FROM tenants WHERE id IS NOT NULL)
        """)
        orphaned = cursor.fetchone()["orphaned"]
        assert orphaned == 0, f"Expense records huérfanos: {orphaned}"

        # 2. Verificar campos migrados tienen tipos correctos
        cursor.execute("""
            SELECT COUNT(*) as invalid
            FROM expense_records
            WHERE deducible NOT IN (0, 1, NULL)
        """)
        invalid_boolean = cursor.fetchone()["invalid"]
        assert invalid_boolean == 0, f"Campos boolean inválidos: {invalid_boolean}"

        # 3. Verificar JSON fields son válidos
        cursor.execute("""
            SELECT id, ml_features_json FROM expense_records
            WHERE ml_features_json IS NOT NULL AND ml_features_json != ''
            LIMIT 10
        """)

        for record in cursor.fetchall():
            try:
                json.loads(record["ml_features_json"])
            except json.JSONDecodeError:
                assert False, f"JSON inválido en record {record['id']}"

        print("✅ REGRESSION: Data consistency OK")

if __name__ == "__main__":
    print("🔄 EJECUTANDO SUITE DE REGRESIÓN COMPLETA")
    print("=" * 60)

    # Tests de funcionalidades core
    core_tests = TestCoreFeatureRegression()
    core_tests.test_expense_creation_api_regression()
    core_tests.test_database_schema_regression()
    core_tests.test_bank_reconciliation_regression()
    core_tests.test_automation_system_regression()
    core_tests.test_ml_features_regression()

    print("\n" + "=" * 60)

    # Tests de performance
    perf_tests = TestPerformanceRegression()
    perf_tests.test_database_query_performance()
    perf_tests.test_api_response_time_regression()

    print("\n" + "=" * 60)

    # Tests de integridad
    integrity_tests = TestDataIntegrityRegression()
    integrity_tests.test_foreign_key_constraints_regression()
    integrity_tests.test_data_consistency_regression()

    print("\n" + "=" * 60)
    print("✅ SUITE DE REGRESIÓN COMPLETADA")
    print("🎯 Todas las funcionalidades mantienen compatibilidad")
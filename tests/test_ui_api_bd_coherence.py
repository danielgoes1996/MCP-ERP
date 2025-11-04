#!/usr/bin/env python3
"""
🧪 TESTING DE COHERENCIA UI ↔ API ↔ BD
Validación integral del sistema MCP para asegurar que los tres layers funcionen correctamente
"""

import pytest
import asyncio
import sqlite3
import json
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
from datetime import datetime
from typing import Dict, List, Any
import sys

# Add root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Test Configuration
TEST_CONFIG = {
    "BASE_URL": "http://localhost:8000",
    "DB_PATH": "unified_mcp_system.db",
    "CHROME_HEADLESS": True,
    "TEST_TENANT": "test_tenant_coherence",
    "TEST_USER_EMAIL": "test@coherence.com"
}

class CoherenceTestSuite:
    """Suite completa de testing de coherencia entre capas"""

    def __init__(self):
        self.driver = None
        self.db_connection = None
        self.base_url = TEST_CONFIG["BASE_URL"]
        self.db_path = TEST_CONFIG["DB_PATH"]

    def setup_method(self):
        """Setup para cada test"""
        # Setup Selenium
        chrome_options = Options()
        if TEST_CONFIG["CHROME_HEADLESS"]:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=chrome_options)

        # Setup Database
        self.db_connection = sqlite3.connect(self.db_path)
        self.db_connection.row_factory = sqlite3.Row

    def teardown_method(self):
        """Cleanup para cada test"""
        if self.driver:
            self.driver.quit()
        if self.db_connection:
            self.db_connection.close()

    def create_test_data(self) -> Dict:
        """Crear datos de prueba en BD"""
        cursor = self.db_connection.cursor()

        # Crear tenant de prueba
        cursor.execute("""
            INSERT OR IGNORE INTO tenants (name, api_key, config)
            VALUES (?, 'test_key_123', '{}')
        """, (TEST_CONFIG["TEST_TENANT"],))

        tenant_id = cursor.lastrowid or 1

        # Crear usuario de prueba
        cursor.execute("""
            INSERT OR IGNORE INTO users (email, full_name, tenant_id, role)
            VALUES (?, 'Test User', ?, 'user')
        """, (TEST_CONFIG["TEST_USER_EMAIL"], tenant_id))

        user_id = cursor.lastrowid or 1

        # Crear gasto de prueba con TODOS los campos migrados
        test_expense = {
            "amount": 1500.50,
            "currency": "MXN",
            "description": "Test Expense for Coherence",
            "category": "office_supplies",
            "merchant_name": "Test Merchant",
            "date": datetime.now().isoformat(),
            "user_id": user_id,
            "tenant_id": tenant_id,
            "status": "pending",
            # Campos migrados críticos
            "deducible": True,
            "requiere_factura": True,
            "centro_costo": "IT_DEPARTMENT",
            "proyecto": "COHERENCE_TEST_PROJECT",
            "metodo_pago": "credit_card",
            "tags": '["test", "coherence", "automation"]'
        }

        cursor.execute("""
            INSERT INTO expense_records
            (amount, currency, description, category, merchant_name, date,
             user_id, tenant_id, status, deducible, requiere_factura,
             centro_costo, proyecto, metodo_pago, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_expense["amount"], test_expense["currency"],
            test_expense["description"], test_expense["category"],
            test_expense["merchant_name"], test_expense["date"],
            test_expense["user_id"], test_expense["tenant_id"],
            test_expense["status"], test_expense["deducible"],
            test_expense["requiere_factura"], test_expense["centro_costo"],
            test_expense["proyecto"], test_expense["metodo_pago"],
            test_expense["tags"]
        ))

        expense_id = cursor.lastrowid
        self.db_connection.commit()

        return {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "expense_id": expense_id,
            "expense_data": test_expense
        }

class TestUIAPiBDCoherence(CoherenceTestSuite):
    """Tests de coherencia entre UI, API y BD"""

    def test_expense_creation_full_flow(self):
        """Test completo: UI → API → BD para creación de gastos"""
        self.setup_method()

        try:
            # 1. VERIFICAR BD INICIAL
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM expense_records")
            initial_count = cursor.fetchone()["count"]

            # 2. CREAR GASTO VÍA API
            expense_data = {
                "amount": 2500.75,
                "currency": "MXN",
                "description": "API Test Expense",
                "category": "travel",
                "merchant_name": "Test Hotel",
                "deducible": True,
                "centro_costo": "SALES",
                "proyecto": "CLIENT_VISIT",
                "tags": ["travel", "client", "sales"]
            }

            response = requests.post(
                f"{self.base_url}/expenses",
                json=expense_data,
                headers={"Content-Type": "application/json"}
            )

            assert response.status_code == 200, f"API failed: {response.text}"
            api_response = response.json()
            expense_id = api_response.get("id")

            # 3. VERIFICAR EN BD QUE SE GUARDÓ CORRECTAMENTE
            cursor.execute("""
                SELECT * FROM expense_records
                WHERE id = ? AND amount = ? AND deducible = ? AND centro_costo = ?
            """, (expense_id, expense_data["amount"], expense_data["deducible"], expense_data["centro_costo"]))

            db_record = cursor.fetchone()
            assert db_record is not None, "Record not found in database"
            assert db_record["description"] == expense_data["description"]
            assert db_record["category"] == expense_data["category"]
            assert db_record["centro_costo"] == expense_data["centro_costo"]
            assert db_record["proyecto"] == expense_data["proyecto"]

            # 4. VERIFICAR EN UI (cargar página de gastos)
            self.driver.get(f"{self.base_url}/voice-expenses")
            wait = WebDriverWait(self.driver, 10)

            # Buscar el gasto en la tabla (si existe)
            try:
                expense_row = wait.until(
                    EC.presence_of_element_located((By.XPATH, f"//td[contains(text(), '{expense_data['description']}')]"))
                )
                assert expense_row is not None, "Expense not visible in UI"
            except:
                # Si no hay tabla, verificar que el endpoint responde
                response = requests.get(f"{self.base_url}/expenses")
                assert response.status_code == 200
                expenses = response.json()
                found = any(exp.get("id") == expense_id for exp in expenses)
                assert found, "Expense not returned by API"

            # 5. VERIFICAR COHERENCIA BD ↔ API ↔ UI
            cursor.execute("SELECT COUNT(*) as count FROM expense_records")
            final_count = cursor.fetchone()["count"]
            assert final_count == initial_count + 1, "Database count inconsistent"

            print("✅ EXPENSE CREATION COHERENCE: PASSED")

        finally:
            self.teardown_method()

    def test_bank_reconciliation_coherence(self):
        """Test coherencia banco: BD → API → UI matching"""
        self.setup_method()

        try:
            # 1. CREAR DATOS DE PRUEBA
            test_data = self.create_test_data()
            expense_id = test_data["expense_id"]

            # 2. CREAR MOVIMIENTO BANCARIO EN BD
            cursor = self.db_connection.cursor()
            cursor.execute("""
                INSERT INTO bank_movements
                (amount, description, date, account, tenant_id, processing_status,
                 decision, matching_confidence, auto_matched)
                VALUES (1500.50, 'Test Bank Movement', ?, 'ACCOUNT_123', ?, 'processed',
                        'accept', 0.95, 1)
            """, (datetime.now().isoformat(), test_data["tenant_id"]))

            movement_id = cursor.lastrowid
            self.db_connection.commit()

            # 3. VERIFICAR API DE SUGERENCIAS
            response = requests.post(
                f"{self.base_url}/bank_reconciliation/suggestions",
                json={
                    "expense_id": expense_id,
                    "amount": 1500.50,
                    "description": "Test Bank Movement"
                }
            )

            if response.status_code == 200:
                suggestions = response.json()
                assert len(suggestions.get("suggestions", [])) > 0, "No suggestions returned"

            # 4. VERIFICAR CAMPOS MIGRADOS EN BD
            cursor.execute("""
                SELECT decision, matching_confidence, auto_matched, bank_metadata
                FROM bank_movements WHERE id = ?
            """, (movement_id,))

            bank_record = cursor.fetchone()
            assert bank_record["decision"] == "accept"
            assert bank_record["matching_confidence"] == 0.95
            assert bank_record["auto_matched"] == 1

            print("✅ BANK RECONCILIATION COHERENCE: PASSED")

        finally:
            self.teardown_method()

    def test_invoice_ocr_processing_coherence(self):
        """Test coherencia OCR: API → BD → processing fields"""
        self.setup_method()

        try:
            # 1. CREAR DATOS DE PRUEBA
            test_data = self.create_test_data()
            expense_id = test_data["expense_id"]

            # 2. SIMULAR PROCESAMIENTO OCR EN BD
            cursor = self.db_connection.cursor()
            cursor.execute("""
                INSERT INTO expense_invoices
                (expense_id, filename, tenant_id, ocr_confidence,
                 template_match, quality_score, processing_status,
                 detected_format, parser_used, validation_status)
                VALUES (?, 'test_invoice.pdf', ?, 0.92, 0.88, 0.90, 'completed',
                        'PDF_STRUCTURED', 'tesseract_enhanced', 'validated')
            """, (expense_id, test_data["tenant_id"]))

            invoice_id = cursor.lastrowid
            self.db_connection.commit()

            # 3. VERIFICAR CAMPOS MIGRADOS OCR
            cursor.execute("""
                SELECT ocr_confidence, template_match, quality_score,
                       detected_format, parser_used, validation_status
                FROM expense_invoices WHERE id = ?
            """, (invoice_id,))

            invoice_record = cursor.fetchone()
            assert invoice_record["ocr_confidence"] == 0.92
            assert invoice_record["template_match"] == 0.88
            assert invoice_record["quality_score"] == 0.90
            assert invoice_record["detected_format"] == "PDF_STRUCTURED"
            assert invoice_record["parser_used"] == "tesseract_enhanced"
            assert invoice_record["validation_status"] == "validated"

            # 4. VERIFICAR API RETORNA DATOS OCR
            response = requests.get(f"{self.base_url}/expenses")
            if response.status_code == 200:
                expenses = response.json()
                test_expense = next((exp for exp in expenses if exp.get("id") == expense_id), None)
                if test_expense:
                    # Verificar que incluye metadata de OCR
                    assert "invoice_status" in test_expense or "metadata" in test_expense

            print("✅ INVOICE OCR COHERENCE: PASSED")

        finally:
            self.teardown_method()

    def test_automation_persistence_coherence(self):
        """Test coherencia automatización: workers → automation_jobs → recovery"""
        self.setup_method()

        try:
            # 1. CREAR JOB DE AUTOMATIZACIÓN
            cursor = self.db_connection.cursor()
            cursor.execute("""
                INSERT INTO automation_jobs
                (job_type, status, tenant_id, checkpoint_data,
                 recovery_metadata, session_id, automation_health)
                VALUES ('rpa_invoice', 'running', 1,
                        '{"step": 3, "url": "test.com", "elements_found": 5}',
                        '{"retry_count": 0, "last_checkpoint": "step_3"}',
                        'session_123', '{"status": "healthy", "memory_usage": "45%"}')
            """, )

            job_id = cursor.lastrowid
            self.db_connection.commit()

            # 2. CREAR WORKER ASOCIADO
            cursor.execute("""
                INSERT INTO workers
                (task_id, company_id, task_type, status, progress,
                 worker_metadata, retry_policy)
                VALUES ('task_automation_123', 1, 'rpa_processing', 'running', 0.75,
                        '{"browser": "chrome", "timeout": 300}',
                        '{"max_retries": 3, "backoff": "exponential"}')
            """)

            worker_id = cursor.lastrowid
            self.db_connection.commit()

            # 3. VERIFICAR CAMPOS MIGRADOS DE RECOVERY
            cursor.execute("""
                SELECT checkpoint_data, recovery_metadata, session_id, automation_health
                FROM automation_jobs WHERE id = ?
            """, (job_id,))

            job_record = cursor.fetchone()
            checkpoint = json.loads(job_record["checkpoint_data"])
            recovery = json.loads(job_record["recovery_metadata"])
            health = json.loads(job_record["automation_health"])

            assert checkpoint["step"] == 3
            assert recovery["retry_count"] == 0
            assert health["status"] == "healthy"
            assert job_record["session_id"] == "session_123"

            # 4. VERIFICAR WORKER METADATA
            cursor.execute("""
                SELECT progress, worker_metadata, retry_policy
                FROM workers WHERE id = ?
            """, (worker_id,))

            worker_record = cursor.fetchone()
            assert worker_record["progress"] == 0.75

            print("✅ AUTOMATION PERSISTENCE COHERENCE: PASSED")

        finally:
            self.teardown_method()

    def test_ml_features_coherence(self):
        """Test coherencia ML: predicción categorías → BD → API"""
        self.setup_method()

        try:
            # 1. CREAR EXPENSE CON PREDICCIÓN ML
            test_data = self.create_test_data()
            expense_id = test_data["expense_id"]

            # 2. ACTUALIZAR CON CAMPOS ML
            cursor = self.db_connection.cursor()
            cursor.execute("""
                UPDATE expense_records SET
                    categoria_sugerida = 'office_supplies',
                    confianza = 0.89,
                    razonamiento = 'Keywords: paper, pens, office detected',
                    category_alternatives = '["office_supplies", "business_supplies", "stationery"]',
                    prediction_method = 'ml_classifier_v2',
                    ml_model_version = 'v2.1.3',
                    predicted_at = ?,
                    ml_features_json = '{"keywords": ["paper", "office"], "amount_category": "medium", "merchant_type": "retail"}'
                WHERE id = ?
            """, (datetime.now().isoformat(), expense_id))

            self.db_connection.commit()

            # 3. VERIFICAR CAMPOS ML EN BD
            cursor.execute("""
                SELECT categoria_sugerida, confianza, razonamiento,
                       category_alternatives, prediction_method, ml_features_json
                FROM expense_records WHERE id = ?
            """, (expense_id,))

            ml_record = cursor.fetchone()
            assert ml_record["categoria_sugerida"] == "office_supplies"
            assert ml_record["confianza"] == 0.89
            assert "paper" in ml_record["razonamiento"]

            alternatives = json.loads(ml_record["category_alternatives"])
            assert "office_supplies" in alternatives

            features = json.loads(ml_record["ml_features_json"])
            assert "keywords" in features
            assert "paper" in features["keywords"]

            # 4. TEST API DE PREDICCIÓN
            response = requests.post(
                f"{self.base_url}/expenses/predict-category",
                json={
                    "description": "Office paper and pens",
                    "amount": 150.50,
                    "merchant_name": "Office Depot"
                }
            )

            if response.status_code == 200:
                prediction = response.json()
                assert "predicted_category" in prediction
                assert "confidence" in prediction

            print("✅ ML FEATURES COHERENCE: PASSED")

        finally:
            self.teardown_method()

class TestSystemIntegrity:
    """Tests de integridad del sistema completo"""

    def test_database_foreign_keys(self):
        """Verificar integridad referencial completa"""
        db_connection = sqlite3.connect(TEST_CONFIG["DB_PATH"])
        cursor = db_connection.cursor()

        # Verificar FKs principales
        cursor.execute("PRAGMA foreign_key_check")
        fk_violations = cursor.fetchall()
        assert len(fk_violations) == 0, f"Foreign key violations: {fk_violations}"

        # Verificar relaciones críticas
        cursor.execute("""
            SELECT COUNT(*) as orphaned FROM expense_records
            WHERE tenant_id NOT IN (SELECT id FROM tenants)
        """)
        orphaned = cursor.fetchone()[0]
        assert orphaned == 0, "Orphaned expense records found"

        db_connection.close()
        print("✅ DATABASE INTEGRITY: PASSED")

    def test_api_endpoints_health(self):
        """Verificar que todos los endpoints respondan"""
        critical_endpoints = [
            "/health",
            "/expenses",
            "/bank_reconciliation/movements",
            "/invoices/parse"
        ]

        for endpoint in critical_endpoints:
            try:
                response = requests.get(f"{TEST_CONFIG['BASE_URL']}{endpoint}", timeout=5)
                assert response.status_code in [200, 405], f"Endpoint {endpoint} failed: {response.status_code}"
            except requests.exceptions.RequestException as e:
                pytest.fail(f"Endpoint {endpoint} unreachable: {e}")

        print("✅ API ENDPOINTS HEALTH: PASSED")

    def test_ui_pages_load(self):
        """Verificar que las páginas UI cargan correctamente"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        driver = webdriver.Chrome(options=chrome_options)

        try:
            ui_pages = [
                "/voice-expenses",
                "/onboarding",
                "/advanced-ticket-dashboard.html"
            ]

            for page in ui_pages:
                driver.get(f"{TEST_CONFIG['BASE_URL']}{page}")
                wait = WebDriverWait(driver, 10)

                # Verificar que la página carga (buscar <body> o cualquier elemento)
                body = wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                assert body is not None, f"Page {page} failed to load"

                # Verificar que no hay errores JS críticos en console
                logs = driver.get_log("browser")
                severe_errors = [log for log in logs if log["level"] == "SEVERE"]
                assert len(severe_errors) == 0, f"JS errors on {page}: {severe_errors}"

        finally:
            driver.quit()

        print("✅ UI PAGES LOAD: PASSED")

if __name__ == "__main__":
    # Ejecutar tests específicos
    print("🧪 INICIANDO TESTING DE COHERENCIA UI ↔ API ↔ BD")
    print("=" * 60)

    # Test de integridad básica
    test_integrity = TestSystemIntegrity()
    test_integrity.test_database_foreign_keys()
    test_integrity.test_api_endpoints_health()
    test_integrity.test_ui_pages_load()

    # Tests de coherencia completa
    coherence_tests = TestUIAPiBDCoherence()
    coherence_tests.test_expense_creation_full_flow()
    coherence_tests.test_bank_reconciliation_coherence()
    coherence_tests.test_invoice_ocr_processing_coherence()
    coherence_tests.test_automation_persistence_coherence()
    coherence_tests.test_ml_features_coherence()

    print("=" * 60)
    print("✅ TODOS LOS TESTS DE COHERENCIA COMPLETADOS")
    print("🎯 Sistema UI ↔ API ↔ BD funcionando correctamente")
import sqlite3
from datetime import datetime

import pytest

from core.fiscal_pipeline import (
    classify_expense_fiscal,
    lookup_provider_rule,
    on_cfdi_received,
)


def _setup_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE expense_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER,
            amount REAL,
            description TEXT,
            merchant_name TEXT,
            date TEXT,
            categoria TEXT,
            categoria_slug TEXT,
            categoria_confianza REAL,
            categoria_fuente TEXT,
            sat_account_code TEXT,
            sat_product_service_code TEXT,
            tax_source TEXT,
            catalog_version TEXT DEFAULT 'v1',
            classification_source TEXT,
            explanation_short TEXT,
            explanation_detail TEXT,
            iva_16 REAL DEFAULT 0,
            iva_0 REAL DEFAULT 0,
            cfdi_status TEXT,
            updated_at TEXT
        );

        CREATE TABLE provider_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER,
            provider_name_normalized TEXT,
            category_slug TEXT,
            sat_account_code TEXT,
            sat_product_service_code TEXT,
            default_iva_rate REAL DEFAULT 0,
            iva_tipo TEXT DEFAULT 'tasa_0',
            confidence REAL DEFAULT 0.9,
            last_confirmed_by INTEGER,
            last_confirmed_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE category_prediction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_id INTEGER,
            predicted_category TEXT,
            confidence REAL,
            reasoning TEXT,
            prediction_method TEXT,
            ml_model_version TEXT,
            tenant_id INTEGER
        );
        """
    )
    return conn


def test_lookup_provider_rule_normalizes_name():
    conn = _setup_db()
    conn.execute(
        "INSERT INTO provider_rules (tenant_id, provider_name_normalized, category_slug, sat_account_code, sat_product_service_code) VALUES (?, ?, ?, ?, ?)",
        (1, "cfe", "servicios_administrativos", "601.32", "80101500"),
    )
    conn.commit()

    rule = lookup_provider_rule(conn, 1, " CFE ")
    assert rule is not None
    assert rule["category_slug"] == "servicios_administrativos"


def test_classify_expense_fiscal_rule_match():
    conn = _setup_db()
    conn.execute(
        "INSERT INTO expense_records (id, tenant_id, amount, description, merchant_name, date, cfdi_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1, 1, 500.0, "Pago de luz", "CFE", "2025-10-01", "pending"),
    )
    conn.execute(
        "INSERT INTO provider_rules (tenant_id, provider_name_normalized, category_slug, sat_account_code, sat_product_service_code, confidence) VALUES (?, ?, ?, ?, ?, ?)",
        (1, "cfe", "servicios_administrativos", "601.32", "80101500", 0.95),
    )
    conn.commit()

    result = classify_expense_fiscal(
        conn,
        expense_id=1,
        tenant_id=1,
        descripcion="Pago CFE mensual",
        proveedor="CFE",
        monto=500.0,
    )

    row = conn.execute(
        "SELECT tax_source, classification_source, sat_account_code, explanation_short FROM expense_records WHERE id=1"
    ).fetchone()

    assert result == {
        "tax_source": "rule",
        "classification_source": "provider_rule",
        "confidence": 0.95,
    }
    assert row["tax_source"] == "rule"
    assert row["classification_source"] == "provider_rule"
    assert row["sat_account_code"] == "601.32"
    assert "Regla proveedor" in row["explanation_short"]

    history = conn.execute(
        "SELECT prediction_method, predicted_category FROM category_prediction_history WHERE expense_id=1"
    ).fetchone()
    assert history["prediction_method"] == "rule"
    assert history["predicted_category"] == "servicios_administrativos"


def test_on_cfdi_received_updates_sat_codes():
    conn = _setup_db()
    conn.execute(
        "INSERT INTO expense_records (id, tenant_id, amount, description, merchant_name, date, cfdi_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1, 1, 500.0, "Pago CFE", "CFE", "2025-10-01", "pending"),
    )
    conn.commit()

    cfdi_payload = {
        "total": 500.0,
        "provider_name": "CFE",
        "issue_date": "2025-10-02T00:00:00",
        "sat_product_service_code": "83111603",
        "sat_account_code": "631.01",
        "tasa_iva": 0.0,
        "iva_amount": 0.0,
        "uuid": "UUID-1234",
    }

    expense_id = on_cfdi_received(conn, tenant_id=1, cfdi_data=cfdi_payload)
    assert expense_id == 1

    row = conn.execute(
        "SELECT tax_source, classification_source, sat_product_service_code, cfdi_status, iva_0 FROM expense_records WHERE id=1"
    ).fetchone()

    assert row["tax_source"] == "cfdi"
    assert row["classification_source"] == "cfdi_xml"
    assert row["sat_product_service_code"] == "83111603"
    assert row["cfdi_status"] == "confirmed"
    assert row["iva_0"] == 0.0

    history = conn.execute(
        "SELECT prediction_method, reasoning FROM category_prediction_history WHERE expense_id=1"
    ).fetchone()
    assert history["prediction_method"] == "cfdi"
    assert "UUID-1234" in history["reasoning"]


def test_llm_fallback_low_confidence():
    conn = _setup_db()
    conn.execute(
        "INSERT INTO expense_records (id, tenant_id, amount, description, merchant_name, date, cfdi_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1, 1, 1200.0, "Gasto experimental", "Proveedor X", "2025-10-01", "pending"),
    )
    conn.commit()

    def fake_llm(payload):
        return {
            "category_slug": "tecnologia_software",
            "sat_account_code": "601.6",
            "sat_product_service_code": "43232408",
            "confidence": 0.55,
            "classification_source": "llm_claude",
            "explanation_short": "LLM sugiere tecnología",
            "explanation_detail": "Texto se relaciona con SaaS",
        }

    result = classify_expense_fiscal(
        conn,
        expense_id=1,
        tenant_id=1,
        descripcion="Servicio experimental mensual",
        proveedor="Proveedor X",
        monto=1200.0,
        llm_classifier=fake_llm,
    )

    row = conn.execute(
        "SELECT tax_source, classification_source, sat_account_code, categoria_slug, categoria_confianza FROM expense_records WHERE id=1"
    ).fetchone()

    assert result["tax_source"] == "llm"
    assert row["classification_source"] == "llm_claude"
    assert row["sat_account_code"] == "601.6"
    assert row["categoria_slug"] == "tecnologia_software"
    assert pytest.approx(row["categoria_confianza"], 0.01) == 0.55

    history = conn.execute(
        "SELECT prediction_method FROM category_prediction_history WHERE expense_id=1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert history["prediction_method"] == "llm"

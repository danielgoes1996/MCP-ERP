import sqlite3
from typing import Callable, Dict

import pytest

from core.fiscal_pipeline import classify_expense_fiscal


@pytest.fixture()
def fiscal_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE expense_records (
            id INTEGER PRIMARY KEY,
            tenant_id INTEGER NOT NULL,
            categoria TEXT,
            categoria_slug TEXT,
            categoria_confianza REAL,
            categoria_fuente TEXT,
            sat_account_code TEXT,
            sat_product_service_code TEXT,
            tax_source TEXT,
            catalog_version TEXT,
            classification_source TEXT,
            explanation_short TEXT,
            explanation_detail TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE category_prediction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_id INTEGER,
            predicted_category TEXT,
            confidence REAL,
            reasoning TEXT,
            prediction_method TEXT,
            ml_model_version TEXT,
            tenant_id INTEGER
        )
        """
    )
    yield conn
    conn.close()


MATRIX_CASES = [
    {
        "description": "pago de diseño a freelancer",
        "slug": "gastos_profesionales",
        "category_label": "Servicios Profesionales",
        "llm_sat": "603",
        "expected_sat": "610.01",
    },
    {
        "description": "suscripción anual de software",
        "slug": "tecnologia_software",
        "category_label": "Software",
        "llm_sat": "603",
        "expected_sat": "617.01",
    },
    {
        "description": "gasolina Pemex para flotilla",
        "slug": "transporte_combustible",
        "category_label": "Combustibles",
        "llm_sat": "602",
        "expected_sat": "607.01",
    },
    {
        "description": "anuncio en Meta Ads y Google Ads",
        "slug": "gastos_administrativos",
        "category_label": "Marketing Digital",
        "llm_sat": "603",
        "expected_sat": "616.02",
    },
    {
        "description": "viáticos hotel y comida visita clientes",
        "slug": "viaticos_alimentos",
        "category_label": "Viáticos y gastos de viaje",
        "llm_sat": "601",
        "expected_sat": "608.01",
    },
]


def _build_llm_stub(case: Dict[str, str]) -> Callable[[Dict[str, str]], Dict[str, str]]:
    def _classifier(_: Dict[str, str]) -> Dict[str, str]:
        return {
            "category_slug": case["slug"],
            "categoria_contable": case["category_label"],
            "categoria_semantica": case["category_label"],
            "category": case["category_label"],
            "sat_account_code": case["llm_sat"],
            "confidence": 0.82,
            "classification_source": "llm_claude",
            "explanation_short": "LLM suggestion",
            "explanation_detail": "Clasificación propuesta por LLM",
        }

    return _classifier


@pytest.mark.parametrize("case", MATRIX_CASES, ids=[c["description"] for c in MATRIX_CASES])
def test_classification_matrix_fallbacks(case: Dict[str, str], fiscal_db: sqlite3.Connection) -> None:
    expense_id = MATRIX_CASES.index(case) + 1
    tenant_id = 1

    fiscal_db.execute(
        "INSERT INTO expense_records (id, tenant_id, catalog_version) VALUES (?, ?, 'v1')",
        (expense_id, tenant_id),
    )

    llm_classifier = _build_llm_stub(case)
    classify_expense_fiscal(
        fiscal_db,
        expense_id=expense_id,
        tenant_id=tenant_id,
        descripcion=case["description"],
        proveedor=None,
        monto=1000.0,
        llm_classifier=llm_classifier,
    )

    row = fiscal_db.execute(
        "SELECT sat_account_code, categoria_slug, explanation_detail FROM expense_records WHERE id = ?",
        (expense_id,),
    ).fetchone()

    assert row is not None
    assert row["sat_account_code"] == case["expected_sat"]
    assert row["categoria_slug"] == case["slug"]
    assert "Regla fallback" in (row["explanation_detail"] or ""), "Fallback detail missing in explanation"


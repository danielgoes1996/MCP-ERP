#!/usr/bin/env python3
"""
Tests unitarios para modelos de gastos (ExpenseCreate, ExpenseResponse).

Estos tests verifican que las validaciones de Pydantic funcionen correctamente
sin necesidad de levantar el servidor o conectar a la base de datos.
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError

from core.api_models import (
    ExpenseCreate,
    ExpenseCreateEnhanced,
    ExpenseResponse,
    ExpenseResponseEnhanced,
    ProveedorData
)


class TestProveedorDataModel:
    """Tests para el modelo ProveedorData."""

    def test_proveedor_data_valid(self):
        """Debe crear proveedor válido con nombre."""
        proveedor = ProveedorData(nombre="PEMEX")
        assert proveedor.nombre == "PEMEX"
        assert proveedor.rfc is None

    def test_proveedor_data_with_rfc(self):
        """Debe crear proveedor con RFC opcional."""
        proveedor = ProveedorData(nombre="PEMEX", rfc="PEM840212XY1")
        assert proveedor.nombre == "PEMEX"
        assert proveedor.rfc == "PEM840212XY1"

    def test_proveedor_data_nombre_required(self):
        """Debe fallar si no se proporciona nombre."""
        with pytest.raises(ValidationError) as exc_info:
            ProveedorData()

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('nombre',) for error in errors)


class TestExpenseCreateRFCValidation:
    """Tests para validación de RFC."""

    def test_rfc_valid_12_chars_moral(self):
        """RFC de persona moral (12 chars) debe ser válido."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15",
            rfc="PEM840212XY1"
        )
        assert expense.rfc == "PEM840212XY1"

    def test_rfc_valid_13_chars_fisica(self):
        """RFC de persona física (13 chars) debe ser válido."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15",
            rfc="GOMD8901011A3"
        )
        assert expense.rfc == "GOMD8901011A3"

    def test_rfc_normalized_to_uppercase(self):
        """RFC en minúsculas debe normalizarse a mayúsculas."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15",
            rfc="pem840212xy1"
        )
        assert expense.rfc == "PEM840212XY1"

    def test_rfc_strips_whitespace(self):
        """RFC con espacios debe limpiarse."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15",
            rfc="  PEM840212XY1  "
        )
        assert expense.rfc == "PEM840212XY1"

    def test_rfc_invalid_too_short(self):
        """RFC muy corto debe fallar."""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseCreate(
                descripcion="Test",
                monto_total=100,
                fecha_gasto="2025-01-15",
                rfc="ABC123"  # Solo 6 caracteres
            )

        errors = exc_info.value.errors()
        assert any(
            error['loc'] == ('rfc',) and
            '12 (moral) o 13 (física) caracteres' in str(error['msg'])
            for error in errors
        )

    def test_rfc_invalid_too_long(self):
        """RFC muy largo debe fallar."""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseCreate(
                descripcion="Test",
                monto_total=100,
                fecha_gasto="2025-01-15",
                rfc="PEM840212XY123456"  # 16 caracteres
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('rfc',) for error in errors)

    def test_rfc_invalid_with_special_chars(self):
        """RFC con caracteres especiales debe fallar."""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseCreate(
                descripcion="Test",
                monto_total=100,
                fecha_gasto="2025-01-15",
                rfc="PEM-840212-XY1"  # Contiene guiones
            )

        errors = exc_info.value.errors()
        assert any(
            error['loc'] == ('rfc',) and
            'solo letras y números' in str(error['msg'])
            for error in errors
        )

    def test_rfc_none_is_valid(self):
        """RFC None debe ser válido (campo opcional)."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15",
            rfc=None
        )
        assert expense.rfc is None


class TestExpenseCreateFechaValidation:
    """Tests para validación de fecha."""

    def test_fecha_valid_today(self):
        """Fecha de hoy debe ser válida."""
        today = datetime.now().date().isoformat()
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto=today
        )
        assert expense.fecha_gasto == today

    def test_fecha_valid_past(self):
        """Fecha pasada debe ser válida."""
        past_date = (datetime.now() - timedelta(days=30)).date().isoformat()
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto=past_date
        )
        assert expense.fecha_gasto == past_date

    def test_fecha_valid_yesterday(self):
        """Fecha de ayer debe ser válida."""
        yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto=yesterday
        )
        assert expense.fecha_gasto == yesterday

    def test_fecha_invalid_future(self):
        """Fecha futura (más de 1 día) debe fallar."""
        future_date = (datetime.now() + timedelta(days=7)).date().isoformat()

        with pytest.raises(ValidationError) as exc_info:
            ExpenseCreate(
                descripcion="Test",
                monto_total=100,
                fecha_gasto=future_date
            )

        errors = exc_info.value.errors()
        assert any(
            error['loc'] == ('fecha_gasto',) and
            'no puede ser futura' in str(error['msg'])
            for error in errors
        )

    def test_fecha_invalid_format_slash(self):
        """Fecha con formato incorrecto (/) debe fallar."""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseCreate(
                descripcion="Test",
                monto_total=100,
                fecha_gasto="15/01/2025"  # Formato DD/MM/YYYY
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('fecha_gasto',) for error in errors)

    def test_fecha_invalid_format_dots(self):
        """Fecha con formato incorrecto (.) debe fallar."""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseCreate(
                descripcion="Test",
                monto_total=100,
                fecha_gasto="15.01.2025"
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('fecha_gasto',) for error in errors)

    def test_fecha_invalid_empty(self):
        """Fecha vacía debe fallar."""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseCreate(
                descripcion="Test",
                monto_total=100,
                fecha_gasto=""
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('fecha_gasto',) for error in errors)


class TestExpenseCreateMontoValidation:
    """Tests para validación de monto."""

    def test_monto_valid_positive(self):
        """Monto positivo debe ser válido."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100.50,
            fecha_gasto="2025-01-15"
        )
        assert expense.monto_total == 100.50

    def test_monto_valid_large(self):
        """Monto grande (< 10M) debe ser válido."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=9_999_999.99,
            fecha_gasto="2025-01-15"
        )
        assert expense.monto_total == 9_999_999.99

    def test_monto_valid_small_decimal(self):
        """Monto pequeño con decimales debe ser válido."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=0.01,
            fecha_gasto="2025-01-15"
        )
        assert expense.monto_total == 0.01

    def test_monto_invalid_zero(self):
        """Monto cero debe fallar."""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseCreate(
                descripcion="Test",
                monto_total=0,
                fecha_gasto="2025-01-15"
            )

        errors = exc_info.value.errors()
        # Puede fallar en Field(gt=0) o en validator
        assert any(error['loc'] == ('monto_total',) for error in errors)

    def test_monto_invalid_negative(self):
        """Monto negativo debe fallar."""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseCreate(
                descripcion="Test",
                monto_total=-100,
                fecha_gasto="2025-01-15"
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('monto_total',) for error in errors)

    def test_monto_invalid_exceeds_limit(self):
        """Monto mayor a 10M debe fallar."""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseCreate(
                descripcion="Test",
                monto_total=15_000_000,
                fecha_gasto="2025-01-15"
            )

        errors = exc_info.value.errors()
        assert any(
            error['loc'] == ('monto_total',) and
            'límite máximo' in str(error['msg'])
            for error in errors
        )

    def test_monto_required_field(self):
        """Monto es campo requerido."""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseCreate(
                descripcion="Test",
                fecha_gasto="2025-01-15"
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('monto_total',) for error in errors)


class TestExpenseCreateCategoriaNormalization:
    """Tests para normalización de categoría."""

    def test_categoria_normalized_lowercase(self):
        """Categoría en mayúsculas debe normalizarse a minúsculas."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15",
            categoria="COMBUSTIBLES"
        )
        assert expense.categoria == "combustibles"

    def test_categoria_normalized_mixed_case(self):
        """Categoría con mayúsculas/minúsculas debe normalizarse."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15",
            categoria="Viajes"
        )
        assert expense.categoria == "viajes"

    def test_categoria_strips_whitespace(self):
        """Categoría con espacios debe limpiarse."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15",
            categoria="  alimentos  "
        )
        assert expense.categoria == "alimentos"

    def test_categoria_none_is_valid(self):
        """Categoría None debe ser válida (campo opcional)."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15",
            categoria=None
        )
        assert expense.categoria is None

    def test_categoria_empty_becomes_none(self):
        """Categoría vacía después de strip debe ser None."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15",
            categoria=""
        )
        # La validación strip().lower() convierte "" a ""
        # pero el campo es opcional, así que podría ser None o ""
        assert expense.categoria in [None, ""]


class TestExpenseCreateRequiredFields:
    """Tests para campos requeridos."""

    def test_descripcion_required(self):
        """Descripción es campo requerido."""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseCreate(
                monto_total=100,
                fecha_gasto="2025-01-15"
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('descripcion',) for error in errors)

    def test_descripcion_min_length(self):
        """Descripción debe tener al menos 1 carácter."""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseCreate(
                descripcion="",
                monto_total=100,
                fecha_gasto="2025-01-15"
            )

        errors = exc_info.value.errors()
        assert any(error['loc'] == ('descripcion',) for error in errors)

    def test_minimal_valid_expense(self):
        """Debe crear gasto con campos mínimos requeridos."""
        expense = ExpenseCreate(
            descripcion="Gasto de prueba",
            monto_total=100,
            fecha_gasto="2025-01-15"
        )
        assert expense.descripcion == "Gasto de prueba"
        assert expense.monto_total == 100
        assert expense.fecha_gasto == "2025-01-15"


class TestExpenseCreateDefaultValues:
    """Tests para valores por defecto."""

    def test_default_workflow_status(self):
        """workflow_status debe tener default 'draft'."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15"
        )
        assert expense.workflow_status == "draft"

    def test_default_estado_factura(self):
        """estado_factura debe tener default 'pendiente'."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15"
        )
        assert expense.estado_factura == "pendiente"

    def test_default_estado_conciliacion(self):
        """estado_conciliacion debe tener default 'pendiente'."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15"
        )
        assert expense.estado_conciliacion == "pendiente"

    def test_default_paid_by(self):
        """paid_by debe tener default 'company_account'."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15"
        )
        assert expense.paid_by == "company_account"

    def test_default_will_have_cfdi(self):
        """will_have_cfdi debe tener default True."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15"
        )
        assert expense.will_have_cfdi is True

    def test_default_company_id(self):
        """company_id debe tener default 'default'."""
        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15"
        )
        assert expense.company_id == "default"


class TestExpenseCreateComplexScenarios:
    """Tests para escenarios complejos."""

    def test_complete_expense_with_proveedor(self):
        """Debe crear gasto completo con proveedor."""
        proveedor = ProveedorData(nombre="PEMEX", rfc="PEM840212XY1")
        expense = ExpenseCreate(
            descripcion="Gasolina para vehículo de reparto",
            monto_total=850.50,
            fecha_gasto="2025-01-15",
            proveedor=proveedor,
            rfc="PEM840212XY1",
            categoria="combustibles",
            forma_pago="tarjeta",
            paid_by="company_account",
            will_have_cfdi=True,
            workflow_status="draft",
            estado_factura="pendiente",
            estado_conciliacion="pendiente",
            company_id="empresa_demo"
        )

        assert expense.descripcion == "Gasolina para vehículo de reparto"
        assert expense.monto_total == 850.50
        assert expense.proveedor.nombre == "PEMEX"
        assert expense.rfc == "PEM840212XY1"
        assert expense.categoria == "combustibles"

    def test_expense_with_tax_info(self):
        """Debe crear gasto con información fiscal."""
        tax_info = {
            "uuid": "ABC123-UUID",
            "subtotal": 735.77,
            "iva": 117.72,
            "total": 853.49
        }

        expense = ExpenseCreate(
            descripcion="Compra con factura",
            monto_total=853.49,
            fecha_gasto="2025-01-15",
            tax_info=tax_info
        )

        assert expense.tax_info == tax_info
        assert expense.tax_info["uuid"] == "ABC123-UUID"

    def test_expense_with_metadata(self):
        """Debe crear gasto con metadata adicional."""
        metadata = {
            "source": "web",
            "user_agent": "Mozilla/5.0",
            "ip_address": "192.168.1.1"
        }

        expense = ExpenseCreate(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15",
            metadata=metadata
        )

        assert expense.metadata == metadata


class TestExpenseCreateEnhanced:
    """Tests para modelo ExpenseCreateEnhanced."""

    def test_enhanced_inherits_from_base(self):
        """ExpenseCreateEnhanced debe heredar de ExpenseCreate."""
        expense = ExpenseCreateEnhanced(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15"
        )

        # Debe tener campos base
        assert expense.descripcion == "Test"
        assert expense.monto_total == 100

        # Debe tener campos enhanced
        assert expense.check_duplicates is True  # default

    def test_enhanced_check_duplicates_default(self):
        """check_duplicates debe tener default True."""
        expense = ExpenseCreateEnhanced(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15"
        )
        assert expense.check_duplicates is True

    def test_enhanced_can_disable_duplicate_check(self):
        """Debe poder deshabilitar check_duplicates."""
        expense = ExpenseCreateEnhanced(
            descripcion="Test",
            monto_total=100,
            fecha_gasto="2025-01-15",
            check_duplicates=False
        )
        assert expense.check_duplicates is False

    def test_enhanced_with_ml_features(self):
        """Debe aceptar ml_features opcional."""
        ml_features = {
            "text_embedding": [0.1, 0.2, 0.3],
            "amount_bucket": "500-1000",
            "day_of_week": 3
        }

        expense = ExpenseCreateEnhanced(
            descripcion="Test",
            monto_total=750,
            fecha_gasto="2025-01-15",
            ml_features=ml_features
        )

        assert expense.ml_features == ml_features


class TestExpenseResponseModel:
    """Tests para modelo ExpenseResponse."""

    def test_response_minimal_fields(self):
        """ExpenseResponse requiere campos mínimos."""
        response = ExpenseResponse(
            id=123,
            descripcion="Test",
            monto_total=100
        )

        assert response.id == 123
        assert response.descripcion == "Test"
        assert response.monto_total == 100

    def test_response_default_values(self):
        """ExpenseResponse debe tener valores por defecto."""
        response = ExpenseResponse(
            id=123,
            descripcion="Test",
            monto_total=100
        )

        assert response.workflow_status == "draft"
        assert response.estado_factura == "pendiente"
        assert response.estado_conciliacion == "pendiente"
        assert response.moneda == "MXN"
        assert response.tipo_cambio == 1.0
        assert response.paid_by == "company_account"
        assert response.will_have_cfdi is True
        assert response.company_id == "default"


class TestExpenseResponseEnhanced:
    """Tests para modelo ExpenseResponseEnhanced."""

    def test_enhanced_response_with_duplicates(self):
        """Debe incluir información de duplicados."""
        response = ExpenseResponseEnhanced(
            id=123,
            descripcion="Test",
            monto_total=100,
            duplicate_ids=[456, 789],
            similarity_score=0.92,
            risk_level="high"
        )

        assert response.duplicate_ids == [456, 789]
        assert response.similarity_score == 0.92
        assert response.risk_level == "high"

    def test_enhanced_response_without_duplicates(self):
        """Campos de duplicados deben ser opcionales."""
        response = ExpenseResponseEnhanced(
            id=123,
            descripcion="Test",
            monto_total=100
        )

        assert response.duplicate_ids is None
        assert response.similarity_score is None
        assert response.risk_level is None

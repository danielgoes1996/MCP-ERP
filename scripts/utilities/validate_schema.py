#!/usr/bin/env python3
"""
Script de validación de coherencia entre esquema de BD y modelos API

Propósito:
- Detectar campos duplicados con diferentes nombres (forma_pago vs metodo_pago)
- Validar que los modelos API coincidan con las columnas de la BD
- Prevenir inconsistencias entre capas del sistema

Uso:
    python validate_schema.py

Retorna:
    0 si todo está correcto
    1 si hay inconsistencias
"""
import sqlite3
import sys
from typing import Set, Dict, List
from core.api_models import ExpenseResponse, ExpenseCreate


# Mapeo de nombres de columnas BD → Modelo API
# Esto documenta las diferencias intencionales
KNOWN_MAPPINGS = {
    # BD column → API field
    "description": "descripcion",
    "amount": "monto_total",
    "expense_date": "fecha_gasto",
    "date": "fecha_gasto",  # Alias
    "category": "categoria",
    "provider_name": "proveedor",
    "provider_rfc": "rfc_proveedor",
    "payment_method": "metodo_pago",  # ⚠️ DEPRECATED - usar metodo_pago
}

# Campos que existen en modelo pero NO en BD (calculados/virtuales)
VIRTUAL_FIELDS = {
    "tax_info",
    "asientos_contables",
    "movimientos_bancarios",
    "metadata",
    "workflow_status",
    "rfc",
    "paid_by",
    "will_have_cfdi",
    "is_advance",
    "is_ppd",
    "asset_class",
    "payment_terms",
    "notas",
    "ubicacion",
    "tags",
    "audit_trail",
    "user_context",
    "enhanced_data",
    "completion_status",
    "validation_errors",
    "field_completeness",
    "trend_category",
    "forecast_confidence",
}


def get_db_columns(table_name: str = "expense_records") -> Set[str]:
    """Obtener columnas de la tabla en BD"""
    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()
    return columns


def get_model_fields(model_class) -> Set[str]:
    """Obtener campos del modelo Pydantic"""
    return set(model_class.__fields__.keys())


def validate_expense_schema() -> bool:
    """Validar coherencia entre expense_records y ExpenseResponse"""
    print("🔍 Validando coherencia de schema para expenses...\n")

    db_columns = get_db_columns("expense_records")
    model_fields = get_model_fields(ExpenseResponse)

    errors = []
    warnings = []

    # 1. Detectar campos duplicados (diferentes nombres, mismo concepto)
    suspicious_pairs = [
        ("forma_pago", "metodo_pago"),
        ("payment_method", "metodo_pago"),
        ("descripcion", "description"),
        ("monto_total", "amount"),
    ]

    for field1, field2 in suspicious_pairs:
        if field1 in model_fields and field2 in model_fields:
            errors.append(f"❌ DUPLICADO: Modelo tiene ambos '{field1}' y '{field2}'")
        if field1 in db_columns and field2 in db_columns:
            errors.append(f"❌ DUPLICADO: BD tiene ambas columnas '{field1}' y '{field2}'")

    # 2. Campos en BD que NO están en modelo (posible pérdida de datos)
    unmapped_db_fields = set()
    for db_col in db_columns:
        # Buscar si existe directamente o via mapeo
        if db_col not in model_fields and db_col not in KNOWN_MAPPINGS:
            unmapped_db_fields.add(db_col)

    if unmapped_db_fields:
        warnings.append(f"⚠️  Campos en BD sin mapeo en modelo: {unmapped_db_fields}")

    # 3. Campos en modelo que NO están en BD (deben ser virtuales)
    unmapped_model_fields = set()
    for model_field in model_fields:
        # Buscar si existe directamente, via mapeo inverso, o es virtual
        reverse_mapping = {v: k for k, v in KNOWN_MAPPINGS.items()}

        if (model_field not in db_columns and
            model_field not in reverse_mapping and
            model_field not in VIRTUAL_FIELDS):
            unmapped_model_fields.add(model_field)

    if unmapped_model_fields:
        warnings.append(f"⚠️  Campos en modelo sin columna en BD: {unmapped_model_fields}")
        warnings.append(f"    → Si son calculados, agregar a VIRTUAL_FIELDS en validate_schema.py")

    # 4. Reportar resultados
    print("📊 RESULTADOS:\n")

    if errors:
        print("ERRORES CRÍTICOS:")
        for error in errors:
            print(f"  {error}")
        print()

    if warnings:
        print("ADVERTENCIAS:")
        for warning in warnings:
            print(f"  {warning}")
        print()

    if not errors and not warnings:
        print("✅ Schema perfectamente alineado")
        print(f"   - {len(db_columns)} columnas en BD")
        print(f"   - {len(model_fields)} campos en modelo")
        print(f"   - {len(KNOWN_MAPPINGS)} mapeos documentados")
        print(f"   - {len(VIRTUAL_FIELDS)} campos virtuales")
        return True

    if errors:
        print("\n❌ Validación FALLIDA - Corregir errores críticos")
        return False

    print("\n⚠️  Validación PASÓ con advertencias - Revisar si es esperado")
    return True


def main():
    """Ejecutar validación"""
    success = validate_expense_schema()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

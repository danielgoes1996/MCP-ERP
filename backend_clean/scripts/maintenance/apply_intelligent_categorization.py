#!/usr/bin/env python3
"""
Aplicar categorización inteligente avanzada a todas las transacciones
Incluye corrección de signos, descripción dual y metadata fiscal
"""
import sys
import sqlite3
from datetime import datetime
from core.intelligent_categorization_engine import IntelligentCategorizationEngine

def apply_intelligent_categorization():
    print("🧠 APPLYING INTELLIGENT CATEGORIZATION")
    print("=" * 60)

    # Conectar a la base de datos
    conn = sqlite3.connect('unified_mcp_system.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Inicializar el motor inteligente
    engine = IntelligentCategorizationEngine()

    try:
        # Obtener todas las transacciones existentes
        cursor.execute("""
            SELECT id, description, amount, date, raw_data, description_raw, transaction_type, movement_kind
            FROM bank_movements
            WHERE account_id IN (7, 11)
            ORDER BY date, id
        """)

        transactions = cursor.fetchall()
        print(f"📊 Processing {len(transactions)} transactions with intelligent categorization...")

        updates_count = 0
        corrections_count = 0
        new_categories_count = 0

        for i, txn in enumerate(transactions):
            # Usar el motor inteligente para categorizar
            result = engine.categorize_advanced(
                description=txn['description'] or '',
                amount=txn['amount'] or 0.0,
                raw_description=txn['raw_data'] or txn['description_raw'] or txn['description']
            )

            # Detectar si necesitamos corrección de tipo
            old_movement_kind = txn['movement_kind']
            needs_correction = old_movement_kind != result.movement_kind

            if needs_correction:
                corrections_count += 1

            # Detectar nueva categoría
            if result.category != "Sin categoría":
                new_categories_count += 1

            # Calcular información fiscal
            fiscal_info = engine.get_deductibility_info(result.category)
            iva_amount = abs(txn['amount']) * fiscal_info['iva_rate'] if fiscal_info['tax_deductible'] else 0.0

            # Determinar categoría de flujo de efectivo
            cash_flow_category = "operating"
            if result.category in ["Transferencias", "Inversiones"]:
                cash_flow_category = "financing"
            elif result.category in ["Tecnología", "Oficina"] and abs(txn['amount']) > 5000:
                cash_flow_category = "investing"

            # Detectar anomalías
            is_anomaly = False
            anomaly_reason = None
            unusual_amount = abs(txn['amount']) > 50000  # Monto inusual

            if result.confidence < 0.3:
                is_anomaly = True
                anomaly_reason = "Low categorization confidence"
            elif unusual_amount:
                is_anomaly = True
                anomaly_reason = "Unusual amount detected"

            # Actualizar en base de datos
            cursor.execute("""
                UPDATE bank_movements SET
                    transaction_type = ?,
                    movement_kind = ?,
                    category_auto = ?,
                    subcategory = ?,
                    category_confidence = ?,
                    transaction_subtype = ?,
                    display_type = ?,
                    cleaned_description = ?,
                    tax_deductible = ?,
                    requires_receipt = ?,
                    iva_rate = ?,
                    iva_amount = ?,
                    cash_flow_category = ?,
                    is_anomaly = ?,
                    anomaly_reason = ?,
                    unusual_amount = ?,
                    last_categorized_at = ?,
                    categorized_by = ?,
                    reconciliation_status = ?
                WHERE id = ?
            """, (
                "credit" if result.movement_kind in ["Ingreso", "Transferencia"] else "debit",
                result.movement_kind,
                result.category,
                result.subcategory,
                result.confidence,
                result.transaction_subtype,
                result.display_type,
                result.description_clean,
                result.tax_deductible,
                result.requires_receipt,
                fiscal_info['iva_rate'],
                iva_amount,
                cash_flow_category,
                is_anomaly,
                anomaly_reason,
                unusual_amount,
                datetime.now().isoformat(),
                'intelligent_engine',
                'pending' if result.requires_receipt else 'not_required',
                txn['id']
            ))

            updates_count += 1

            if i % 10 == 0:  # Progress update
                print(f"   ✅ Processed {i+1}/{len(transactions)} transactions...")

        # Commit cambios
        conn.commit()
        print(f"\n🎯 SUCCESS: Updated {updates_count} transactions")
        print(f"🔧 Type corrections: {corrections_count}")
        print(f"🏷️ New categories assigned: {new_categories_count}")

        # Generar resumen detallado
        print(f"\n📈 INTELLIGENT CATEGORIZATION SUMMARY:")
        print("-" * 100)

        cursor.execute("""
            SELECT
                category_auto,
                subcategory,
                movement_kind,
                COUNT(*) as count,
                ROUND(SUM(CASE WHEN movement_kind = 'Ingreso' THEN amount ELSE 0 END), 2) as total_income,
                ROUND(SUM(CASE WHEN movement_kind = 'Gasto' THEN ABS(amount) ELSE 0 END), 2) as total_expenses,
                ROUND(SUM(CASE WHEN tax_deductible = 1 THEN ABS(amount) ELSE 0 END), 2) as deductible_amount,
                ROUND(SUM(iva_amount), 2) as total_iva
            FROM bank_movements
            WHERE account_id IN (7, 11)
            GROUP BY category_auto, subcategory, movement_kind
            ORDER BY category_auto, subcategory
        """)

        results = cursor.fetchall()
        print(f"{'Category':<20} {'Subcategory':<20} {'Type':<12} {'Count':<5} {'Income':<10} {'Expenses':<10} {'Deductible':<10} {'IVA':<8}")
        print("-" * 100)

        total_deductible = 0
        total_iva = 0

        for row in results:
            print(f"{row['category_auto']:<20} {row['subcategory']:<20} {row['movement_kind']:<12} {row['count']:<5} ${row['total_income']:<9} ${row['total_expenses']:<9} ${row['deductible_amount']:<9} ${row['total_iva']:<7}")
            total_deductible += row['deductible_amount']
            total_iva += row['total_iva']

        print("-" * 100)
        print(f"💼 TOTAL DEDUCTIBLE: ${total_deductible:,.2f}")
        print(f"🧾 TOTAL IVA ACREDITABLE: ${total_iva:,.2f}")

        # Mostrar anomalías detectadas
        cursor.execute("""
            SELECT description, amount, anomaly_reason, category_auto
            FROM bank_movements
            WHERE account_id IN (7, 11) AND is_anomaly = 1
            ORDER BY ABS(amount) DESC
        """)

        anomalies = cursor.fetchall()
        if anomalies:
            print(f"\n⚠️ ANOMALIES DETECTED ({len(anomalies)}):")
            print("-" * 80)
            for anomaly in anomalies[:5]:  # Mostrar top 5
                print(f"   💸 ${anomaly['amount']:>10,.2f} | {anomaly['description'][:30]:<30} | {anomaly['anomaly_reason']}")

        # Mostrar movimientos que requieren conciliación
        cursor.execute("""
            SELECT category_auto, COUNT(*) as count, SUM(ABS(amount)) as total_amount
            FROM bank_movements
            WHERE account_id IN (7, 11) AND reconciliation_status = 'pending' AND requires_receipt = 1
            GROUP BY category_auto
            ORDER BY total_amount DESC
        """)

        pending_reconciliation = cursor.fetchall()
        if pending_reconciliation:
            print(f"\n🔍 PENDING RECONCILIATION:")
            print("-" * 50)
            for item in pending_reconciliation:
                print(f"   📋 {item['category_auto']:<20} | {item['count']} txns | ${item['total_amount']:,.2f}")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    apply_intelligent_categorization()
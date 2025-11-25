#!/usr/bin/env python3
"""
Backfill de clasificaciones validadas al sistema de aprendizaje.

Este script carga todas las clasificaciones confirmadas históricas
para arrancar el sistema de aprendizaje con datos robustos.
"""

import sys
import os
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ai_pipeline.classification.classification_learning import (
    save_validated_classification,
    get_learning_statistics
)
from core.shared.db_config import get_connection

def backfill_confirmed_classifications(
    company_id: int = None,
    tenant_id: int = None,
    limit: int = None,
    dry_run: bool = False
):
    """
    Carga clasificaciones confirmadas al sistema de aprendizaje.

    Args:
        company_id: Filtrar por company_id (None = todas)
        tenant_id: Filtrar por tenant_id (None = todas)
        limit: Límite de registros a procesar
        dry_run: Si True, solo muestra lo que haría sin guardar
    """
    print("=" * 80)
    print("BACKFILL DE CLASIFICACIONES AL SISTEMA DE APRENDIZAJE")
    print("=" * 80)

    conn = get_connection()
    cursor = conn.cursor()

    # Construir query con filtros opcionales
    where_clauses = []
    params = []

    if company_id is not None:
        where_clauses.append("e.company_id = %s")
        params.append(company_id)

    if tenant_id is not None:
        where_clauses.append("e.tenant_id = %s")
        params.append(tenant_id)

    where_sql = ""
    if where_clauses:
        where_sql = "AND " + " AND ".join(where_clauses)

    limit_sql = f"LIMIT {limit}" if limit else ""

    # Buscar clasificaciones confirmadas que NO estén ya en learning history
    # accounting_classification es JSONB que contiene: sat_account_code, sat_account_name, family_code, etc.
    query = f"""
        SELECT
            e.id,
            e.company_id, e.tenant_id, e.session_id,
            e.rfc_emisor, e.nombre_emisor,
            e.notes, e.total, e.uso_cfdi,
            e.accounting_classification->>'sat_account_code' as sat_account_code,
            e.accounting_classification->>'sat_account_name' as sat_account_name,
            e.accounting_classification->>'family_code' as family_code,
            e.accounting_classification->>'model_version' as model_version,
            CAST(e.accounting_classification->>'confidence_sat' AS FLOAT) as confidence_sat,
            e.updated_at
        FROM expense_invoices e
        LEFT JOIN classification_learning_history clh
            ON e.session_id = clh.session_id
            AND e.company_id = clh.company_id
            AND e.tenant_id = clh.tenant_id
        WHERE e.accounting_classification IS NOT NULL
          AND e.accounting_classification->>'sat_account_code' IS NOT NULL
          AND e.accounting_classification->>'sat_account_name' IS NOT NULL
          AND clh.id IS NULL  -- No existe en learning history
          {where_sql}
        ORDER BY e.updated_at DESC
        {limit_sql}
    """

    print(f"\n📊 Buscando clasificaciones confirmadas...")
    if company_id:
        print(f"   Filtro company_id: {company_id}")
    if tenant_id:
        print(f"   Filtro tenant_id: {tenant_id}")
    if limit:
        print(f"   Límite: {limit}")
    print()

    cursor.execute(query, params)
    classifications = cursor.fetchall()

    print(f"✅ Encontradas {len(classifications)} clasificaciones para migrar\n")

    if len(classifications) == 0:
        print("No hay clasificaciones nuevas para migrar.")
        cursor.close()
        conn.close()
        return 0

    if dry_run:
        print("🔍 MODO DRY-RUN: Mostrando primeras 10 clasificaciones que se migrarían:")
        print("-" * 80)
        for i, row in enumerate(classifications[:10], 1):
            (inv_id, comp_id, ten_id, sess_id, rfc, nombre, concepto,
             total, uso, code, name, fam, model, conf, updated) = row

            print(f"\n{i}. Invoice ID: {inv_id}")
            print(f"   Emisor: {nombre} ({rfc})")
            print(f"   Concepto: {concepto[:60]}...")
            print(f"   Clasificación: {code} - {name}")
            print(f"   Confianza: {conf:.2%}")
            print(f"   Modelo: {model}")

        print("\n" + "=" * 80)
        print(f"Total que se migraría: {len(classifications)}")
        print("Ejecuta sin --dry-run para realizar la migración")
        print("=" * 80)

        cursor.close()
        conn.close()
        return 0

    # Migrar clasificaciones
    saved_count = 0
    skipped_count = 0
    error_count = 0

    print("🔄 Iniciando migración...")
    print("-" * 80)

    for i, row in enumerate(classifications, 1):
        (inv_id, comp_id, ten_id, sess_id, rfc, nombre, concepto,
         total, uso, code, name, fam, model, conf, updated) = row

        try:
            # Determinar tipo de validación basado en modelo
            if model and 'human' in model.lower():
                validation_type = 'human'
            elif model and 'learning' in model.lower():
                validation_type = 'auto'
            else:
                validation_type = 'auto'  # Default

            # Guardar en learning history
            success = save_validated_classification(
                company_id=comp_id,
                tenant_id=ten_id,
                session_id=sess_id or f"backfill_{inv_id}",
                rfc_emisor=rfc or '',
                nombre_emisor=nombre or '',
                concepto=concepto or '',
                total=float(total or 0),
                uso_cfdi=uso or '',
                sat_account_code=code,
                sat_account_name=name,
                family_code=fam,
                validation_type=validation_type,
                validated_by='backfill_script',
                original_llm_prediction=None,
                original_llm_confidence=None
            )

            if success:
                saved_count += 1
                if i % 10 == 0:
                    print(f"   Procesadas {i}/{len(classifications)} ({saved_count} guardadas)")
            else:
                skipped_count += 1
                print(f"   ⚠️  Saltada invoice {inv_id}: Error al guardar")

        except Exception as e:
            error_count += 1
            print(f"   ❌ Error procesando invoice {inv_id}: {e}")
            if error_count > 10:
                print(f"\n   DEMASIADOS ERRORES: Deteniendo migración")
                break

    print()
    print("=" * 80)
    print("✅ MIGRACIÓN COMPLETADA")
    print("=" * 80)
    print(f"Total procesadas: {len(classifications)}")
    print(f"Guardadas exitosamente: {saved_count}")
    print(f"Saltadas: {skipped_count}")
    print(f"Errores: {error_count}")
    print()

    # Mostrar estadísticas finales por empresa
    if company_id and tenant_id:
        print(f"📈 Estadísticas del sistema de aprendizaje:")
        print("-" * 80)
        stats = get_learning_statistics(company_id, tenant_id)

        print(f"Total validaciones: {stats.get('total_validations', 0)}")
        print(f"\nPor tipo de validación:")
        for vtype, count in stats.get('by_type', {}).items():
            print(f"  - {vtype}: {count}")

        print(f"\nTop 10 proveedores aprendidos:")
        for i, (nombre, count) in enumerate(stats.get('top_providers', [])[:10], 1):
            print(f"  {i}. {nombre}: {count} clasificaciones")

        if stats.get('total_validations', 0) >= 50:
            print(f"\n🎉 ¡Sistema listo para producción! (≥50 validaciones)")
        else:
            needed = 50 - stats.get('total_validations', 0)
            print(f"\n⚠️  Se recomienda {needed} validaciones más para producción óptima")

    cursor.close()
    conn.close()

    return saved_count


def main():
    parser = argparse.ArgumentParser(
        description="Backfill de clasificaciones confirmadas al sistema de aprendizaje"
    )

    parser.add_argument(
        '--company-id',
        type=int,
        help='Filtrar por company_id (opcional)'
    )

    parser.add_argument(
        '--tenant-id',
        type=int,
        help='Filtrar por tenant_id (opcional)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Límite de registros a procesar (opcional)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Modo dry-run: muestra lo que haría sin guardar'
    )

    args = parser.parse_args()

    try:
        saved = backfill_confirmed_classifications(
            company_id=args.company_id,
            tenant_id=args.tenant_id,
            limit=args.limit,
            dry_run=args.dry_run
        )

        if not args.dry_run:
            print(f"\n✅ Backfill completado: {saved} clasificaciones migradas")

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Migración interrumpida por usuario")
        return 1
    except Exception as e:
        print(f"\n❌ Error en migración: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

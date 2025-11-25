#!/usr/bin/env python3
"""
API para corrección de clasificaciones y aprendizaje automático.

Este endpoint permite que usuarios corrijan clasificaciones erróneas
y el sistema aprenda automáticamente para futuros casos similares.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging

from core.ai_pipeline.classification.classification_learning import (
    save_validated_classification,
    search_similar_classifications,
    get_learning_statistics
)
from core.shared.db_config import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/classification", tags=["classification"])


class ClassificationCorrection(BaseModel):
    """Modelo para corrección de clasificación."""
    invoice_id: int = Field(..., description="ID de la factura a corregir")
    new_sat_code: str = Field(..., description="Nuevo código SAT correcto", example="610.02")
    new_sat_name: str = Field(..., description="Nombre del código SAT", example="Gastos de viaje y viáticos")
    new_family_code: str = Field(..., description="Código de familia", example="610")
    correction_reason: Optional[str] = Field(None, description="Razón de la corrección")
    user_email: Optional[str] = Field(None, description="Email del usuario que corrige")


class SimilarSearchRequest(BaseModel):
    """Modelo para búsqueda de clasificaciones similares."""
    company_id: int
    tenant_id: int
    proveedor: str
    concepto: str
    top_k: int = Field(default=5, ge=1, le=20)
    min_similarity: float = Field(default=0.80, ge=0.5, le=1.0)


@router.post("/correct")
async def correct_classification(correction: ClassificationCorrection):
    """
    Corrige una clasificación y guarda en learning history.

    Este endpoint:
    1. Obtiene datos de la factura original
    2. Actualiza la clasificación en expense_invoices
    3. Guarda en learning history con embedding
    4. Retorna estadísticas de aprendizaje

    Example:
        POST /classification/correct
        {
            "invoice_id": 12345,
            "new_sat_code": "610.02",
            "new_sat_name": "Gastos de viaje y viáticos",
            "new_family_code": "610",
            "correction_reason": "PASE es peaje, no depreciación",
            "user_email": "contador@empresa.com"
        }
    """
    try:
        db = get_connection()
        cursor = db.cursor()

        # 1. Obtener datos de la factura original
        cursor.execute("""
            SELECT
                ei.company_id, ei.tenant_id, ei.session_id,
                ei.rfc_emisor, ei.nombre_emisor,
                ei.notes, ei.total, ei.uso_cfdi,
                ei.accounting_classification->>'sat_account_code' as old_code,
                ei.accounting_classification->>'sat_account_name' as old_name,
                CAST(ei.accounting_classification->>'confidence_sat' AS FLOAT) as old_confidence
            FROM expense_invoices ei
            WHERE ei.id = %s
        """, (correction.invoice_id,))

        invoice = cursor.fetchone()

        if not invoice:
            raise HTTPException(status_code=404, detail=f"Invoice {correction.invoice_id} not found")

        (company_id, tenant_id, session_id,
         rfc_emisor, nombre_emisor, concepto, total, uso_cfdi,
         old_code, old_name, old_confidence) = invoice

        logger.info(
            f"Correcting invoice {correction.invoice_id}: "
            f"{old_code} → {correction.new_sat_code}"
        )

        # 2. Guardar en learning history (ANTES de actualizar factura)
        learning_saved = save_validated_classification(
            company_id=company_id,
            tenant_id=tenant_id,
            session_id=session_id,
            rfc_emisor=rfc_emisor or '',
            nombre_emisor=nombre_emisor or '',
            concepto=concepto or '',
            total=float(total or 0),
            uso_cfdi=uso_cfdi or '',
            sat_account_code=correction.new_sat_code,
            sat_account_name=correction.new_sat_name,
            family_code=correction.new_family_code,
            validation_type='human',  # Corrección humana
            validated_by=correction.user_email or 'unknown',
            original_llm_prediction=old_code,
            original_llm_confidence=float(old_confidence or 0)
        )

        if not learning_saved:
            logger.warning(f"Failed to save to learning history for invoice {correction.invoice_id}")

        # 3. Actualizar clasificación en expense_invoices (JSONB field)
        cursor.execute("""
            UPDATE expense_invoices
            SET
                accounting_classification = jsonb_set(
                    COALESCE(accounting_classification, '{}'::jsonb),
                    '{sat_account_code}', %s::jsonb
                ),
                accounting_classification = jsonb_set(
                    accounting_classification,
                    '{sat_account_name}', %s::jsonb
                ),
                accounting_classification = jsonb_set(
                    accounting_classification,
                    '{family_code}', %s::jsonb
                ),
                accounting_classification = jsonb_set(
                    accounting_classification,
                    '{status}', %s::jsonb
                ),
                accounting_classification = jsonb_set(
                    accounting_classification,
                    '{confidence_sat}', %s::jsonb
                ),
                accounting_classification = jsonb_set(
                    accounting_classification,
                    '{model_version}', %s::jsonb
                ),
                accounting_classification = jsonb_set(
                    accounting_classification,
                    '{explanation_short}', %s::jsonb
                ),
                updated_at = NOW()
            WHERE id = %s
        """, (
            f'"{correction.new_sat_code}"',
            f'"{correction.new_sat_name}"',
            f'"{correction.new_family_code}"',
            '"confirmed"',
            '1.0',
            '"human-corrected"',
            f'"Corregido manualmente por {correction.user_email or "usuario"}: {correction.correction_reason or "Sin razón especificada"}"',
            correction.invoice_id
        ))

        db.commit()

        # 4. Obtener estadísticas actualizadas
        stats = get_learning_statistics(company_id, tenant_id)

        # 5. Buscar si hay facturas similares que podrían beneficiarse
        similar_pending = []
        if nombre_emisor and concepto:
            cursor.execute("""
                SELECT id, nombre_emisor, notes,
                       accounting_classification->>'sat_account_code' as sat_account_code
                FROM expense_invoices
                WHERE company_id = %s
                  AND tenant_id = %s
                  AND (accounting_classification->>'status' = 'pending'
                       OR accounting_classification IS NULL)
                  AND id != %s
                LIMIT 50
            """, (company_id, tenant_id, correction.invoice_id))

            pending_invoices = cursor.fetchall()

            # Buscar similares
            for inv_id, inv_emisor, inv_concepto, inv_code in pending_invoices:
                similar = search_similar_classifications(
                    company_id=company_id,
                    tenant_id=tenant_id,
                    nombre_emisor=inv_emisor or '',
                    concepto=inv_concepto or '',
                    top_k=1,
                    min_similarity=0.92
                )

                if similar and similar[0].sat_account_code == correction.new_sat_code:
                    similar_pending.append({
                        'invoice_id': inv_id,
                        'emisor': inv_emisor,
                        'concepto': inv_concepto,
                        'current_code': inv_code,
                        'suggested_code': correction.new_sat_code,
                        'similarity': similar[0].similarity_score
                    })

        cursor.close()
        db.close()

        return {
            "success": True,
            "message": f"Clasificación corregida y aprendida exitosamente",
            "invoice_id": correction.invoice_id,
            "old_classification": {
                "code": old_code,
                "name": old_name,
                "confidence": old_confidence
            },
            "new_classification": {
                "code": correction.new_sat_code,
                "name": correction.new_sat_name,
                "confidence": 1.0
            },
            "learning_saved": learning_saved,
            "learning_stats": stats,
            "similar_pending_invoices": similar_pending[:10],  # Top 10
            "recommendation": (
                f"Se encontraron {len(similar_pending)} facturas pendientes similares "
                f"que ahora se clasificarán automáticamente como {correction.new_sat_code}"
                if similar_pending else
                "No se encontraron facturas similares pendientes"
            )
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error correcting classification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/search-similar")
async def search_similar(request: SimilarSearchRequest):
    """
    Busca clasificaciones similares en el historial de aprendizaje.

    Útil para preview antes de guardar una clasificación, o para
    sugerir clasificaciones basadas en casos previos.

    Example:
        POST /classification/search-similar
        {
            "company_id": 1,
            "tenant_id": 1,
            "proveedor": "PASE, SERVICIOS ELECTRONICOS",
            "concepto": "RECARGA IDMX",
            "top_k": 5,
            "min_similarity": 0.80
        }
    """
    try:
        results = search_similar_classifications(
            company_id=request.company_id,
            tenant_id=request.tenant_id,
            nombre_emisor=request.proveedor,
            concepto=request.concepto,
            top_k=request.top_k,
            min_similarity=request.min_similarity
        )

        return {
            "query": {
                "proveedor": request.proveedor,
                "concepto": request.concepto,
                "min_similarity": request.min_similarity
            },
            "results_count": len(results),
            "similar_classifications": [
                {
                    "sat_code": r.sat_account_code,
                    "sat_name": r.sat_account_name,
                    "family_code": r.family_code,
                    "similarity": r.similarity_score,
                    "confidence": r.confidence,
                    "source_emisor": r.source_emisor,
                    "source_concepto": r.source_concepto,
                    "validation_type": r.validation_type
                }
                for r in results
            ]
        }

    except Exception as e:
        logger.error(f"Error searching similar classifications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/learning-stats")
async def get_stats(company_id: int, tenant_id: int):
    """
    Obtiene estadísticas del sistema de aprendizaje.

    Example:
        GET /classification/learning-stats?company_id=1&tenant_id=1
    """
    try:
        stats = get_learning_statistics(company_id, tenant_id)

        return {
            "company_id": company_id,
            "tenant_id": tenant_id,
            "statistics": stats,
            "recommendations": {
                "total_learned": stats.get('total_validations', 0),
                "ready_for_production": stats.get('total_validations', 0) >= 50,
                "message": (
                    "Sistema de aprendizaje activo y funcionando"
                    if stats.get('total_validations', 0) >= 50
                    else f"Se recomienda validar más clasificaciones (actual: {stats.get('total_validations', 0)}, recomendado: 50+)"
                )
            }
        }

    except Exception as e:
        logger.error(f"Error getting learning stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/batch-auto-apply")
async def batch_auto_apply(company_id: int, tenant_id: int, limit: int = 100):
    """
    Aplica automáticamente clasificaciones aprendidas a facturas pendientes.

    Este endpoint busca facturas pendientes y les aplica clasificaciones
    del historial de aprendizaje si hay match con alta confianza (≥92%).

    Example:
        POST /classification/batch-auto-apply?company_id=1&tenant_id=1&limit=100
    """
    try:
        db = get_connection()
        cursor = db.cursor()

        # Obtener facturas pendientes
        cursor.execute("""
            SELECT id, nombre_emisor, notes,
                   accounting_classification->>'sat_account_code' as sat_account_code
            FROM expense_invoices
            WHERE company_id = %s
              AND tenant_id = %s
              AND (accounting_classification->>'status' = 'pending'
                   OR accounting_classification IS NULL)
            LIMIT %s
        """, (company_id, tenant_id, limit))

        pending_invoices = cursor.fetchall()

        applied_count = 0
        skipped_count = 0
        results = []

        for inv_id, nombre_emisor, concepto, current_code in pending_invoices:
            if not nombre_emisor or not concepto:
                skipped_count += 1
                continue

            # Buscar clasificación similar en learning history
            similar = search_similar_classifications(
                company_id=company_id,
                tenant_id=tenant_id,
                nombre_emisor=nombre_emisor,
                concepto=concepto,
                top_k=1,
                min_similarity=0.92  # 92% confianza mínima
            )

            if similar and len(similar) > 0:
                learned = similar[0]

                # Aplicar clasificación aprendida (actualizar JSONB)
                cursor.execute("""
                    UPDATE expense_invoices
                    SET
                        accounting_classification = jsonb_set(
                            COALESCE(accounting_classification, '{}'::jsonb),
                            '{sat_account_code}', %s::jsonb
                        ),
                        accounting_classification = jsonb_set(
                            accounting_classification,
                            '{sat_account_name}', %s::jsonb
                        ),
                        accounting_classification = jsonb_set(
                            accounting_classification,
                            '{family_code}', %s::jsonb
                        ),
                        accounting_classification = jsonb_set(
                            accounting_classification,
                            '{status}', %s::jsonb
                        ),
                        accounting_classification = jsonb_set(
                            accounting_classification,
                            '{confidence_sat}', %s::jsonb
                        ),
                        accounting_classification = jsonb_set(
                            accounting_classification,
                            '{model_version}', %s::jsonb
                        ),
                        accounting_classification = jsonb_set(
                            accounting_classification,
                            '{explanation_short}', %s::jsonb
                        ),
                        updated_at = NOW()
                    WHERE id = %s
                """, (
                    f'"{learned.sat_account_code}"',
                    f'"{learned.sat_account_name}"',
                    f'"{learned.family_code}"',
                    '"auto-applied"',
                    str(learned.confidence),
                    '"learning-history"',
                    f'"Auto-aplicado por aprendizaje (similitud: {learned.similarity_score:.0%})"',
                    inv_id
                ))

                applied_count += 1

                results.append({
                    'invoice_id': inv_id,
                    'emisor': nombre_emisor,
                    'concepto': concepto,
                    'old_code': current_code,
                    'new_code': learned.sat_account_code,
                    'similarity': learned.similarity_score,
                    'source': learned.validation_type
                })
            else:
                skipped_count += 1

        db.commit()
        cursor.close()
        db.close()

        return {
            "success": True,
            "processed": len(pending_invoices),
            "auto_applied": applied_count,
            "skipped": skipped_count,
            "auto_apply_rate": (applied_count / len(pending_invoices) * 100) if pending_invoices else 0,
            "results": results[:20],  # Top 20 para no saturar respuesta
            "message": (
                f"Se aplicaron automáticamente {applied_count} clasificaciones "
                f"de {len(pending_invoices)} facturas procesadas "
                f"({applied_count / len(pending_invoices) * 100:.1f}% tasa de auto-aplicación)"
                if pending_invoices else
                "No hay facturas pendientes"
            )
        }

    except Exception as e:
        logger.error(f"Error in batch auto-apply: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

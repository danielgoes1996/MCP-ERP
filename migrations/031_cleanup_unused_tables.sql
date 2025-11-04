-- Migration 024: Cleanup Unused Tables
-- Fecha: 2025-10-03
-- Descripción: Eliminar tablas obsoletas identificadas en Sprint 2
-- Impacto: -2 tablas sin uso real

-- ============================================================================
-- VERIFICACIÓN PRE-MIGRATION
-- ============================================================================
-- expense_attachments: 0 filas, 1 mención en código (solo modelo Pydantic)
-- duplicate_detection: 0 filas, reemplazada por duplicate_detections

-- ============================================================================
-- ELIMINACIÓN DE TABLAS
-- ============================================================================

-- 1. Eliminar expense_attachments
--    Razón: Sin uso real, solo definida en modelo Pydantic
--    Riesgo: BAJO (0 filas, sin foreign keys)
DROP TABLE IF EXISTS expense_attachments;

-- 2. Eliminar duplicate_detection
--    Razón: Reemplazada por duplicate_detections (que tiene tenant_id)
--    Riesgo: BAJO (0 filas, sin foreign keys)
DROP TABLE IF EXISTS duplicate_detection;

-- ============================================================================
-- VERIFICACIÓN POST-MIGRATION
-- ============================================================================
-- Verificar que las tablas ya no existen:
-- SELECT name FROM sqlite_master WHERE type='table' AND name IN ('expense_attachments', 'duplicate_detection');
-- Resultado esperado: 0 filas

-- ============================================================================
-- ROLLBACK (si es necesario)
-- ============================================================================
-- No se incluye rollback porque:
-- 1. Ambas tablas tienen 0 filas (no hay pérdida de datos)
-- 2. No tienen foreign keys que las referencien
-- 3. Código que las menciona es código dead o modelos sin uso

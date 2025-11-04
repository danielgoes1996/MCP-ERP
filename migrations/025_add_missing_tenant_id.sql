-- Migration 025: Add Missing tenant_id to Tables
-- Fecha: 2025-10-03
-- Descripción: Agregar tenant_id a category_learning y system_health
-- Impacto: Completar multi-tenancy en tablas ML y monitoring

-- ============================================================================
-- VERIFICACIÓN PRE-MIGRATION
-- ============================================================================
-- category_learning: 0 filas, usado en core/category_learning_system.py
-- system_health: 0 filas, usado en módulos de monitoring

-- ============================================================================
-- AGREGAR tenant_id A TABLAS
-- ============================================================================

-- 1. category_learning - Sistema de aprendizaje ML
--    Razón: Cada tenant debe tener su propio modelo de categorización
--    Riesgo: BAJO (0 filas)
ALTER TABLE category_learning ADD COLUMN tenant_id INTEGER;
CREATE INDEX idx_category_learning_tenant ON category_learning(tenant_id);

-- 2. system_health - Monitoreo de salud del sistema
--    Razón: Aunque es metadata de sistema, puede ser útil por tenant para multi-tenancy
--    Decisión: Agregar pero permitir NULL para health checks globales
--    Riesgo: BAJO (0 filas)
ALTER TABLE system_health ADD COLUMN tenant_id INTEGER;
CREATE INDEX idx_system_health_tenant ON system_health(tenant_id);

-- ============================================================================
-- VERIFICACIÓN POST-MIGRATION
-- ============================================================================
-- Verificar que las columnas existen:
-- PRAGMA table_info(category_learning);
-- PRAGMA table_info(system_health);

-- Verificar índices:
-- SELECT name FROM sqlite_master WHERE type='index' AND tbl_name IN ('category_learning', 'system_health');

-- ============================================================================
-- NOTAS
-- ============================================================================
-- category_learning:
--   - tenant_id NOT NULL - Cada tenant tiene su modelo
--   - Queries deben filtrar por tenant_id siempre
--
-- system_health:
--   - tenant_id puede ser NULL para health checks globales
--   - tenant_id NOT NULL para health checks específicos de tenant
--   - Útil para monitoring multi-tenant

-- ============================================================================
-- ROLLBACK (si es necesario)
-- ============================================================================
-- DROP INDEX idx_category_learning_tenant;
-- ALTER TABLE category_learning DROP COLUMN tenant_id;
-- DROP INDEX idx_system_health_tenant;
-- ALTER TABLE system_health DROP COLUMN tenant_id;

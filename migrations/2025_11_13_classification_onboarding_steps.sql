-- Migration: Add classification onboarding steps
-- Date: 2025-11-13
-- Purpose: Define onboarding questionnaire for company classification context

-- Insert classification-specific onboarding steps
-- These questions will populate the company.settings field with classification context

INSERT INTO onboarding_steps (id, step_number, step_name, description, required, active, tenant_id) VALUES
(1, 1, 'industry_selection',
 'Selecciona la industria principal de tu empresa (usado para sugerir categorías de gastos)',
 true, true, 2),

(2, 2, 'business_model',
 'Describe tu modelo de negocio (B2B, B2C, producción, distribución, servicios)',
 true, true, 2),

(3, 3, 'typical_expenses',
 'Selecciona los tipos de gastos más comunes en tu empresa (materias primas, nómina, marketing, etc.)',
 true, true, 2),

(4, 4, 'provider_mappings',
 'Configura cómo clasificar automáticamente a tus proveedores recurrentes (FINKOK, Meta, Google, etc.)',
 false, true, 2),

(5, 5, 'accounting_preferences',
 'Preferencias contables: nivel de detalle y umbral de aprobación automática',
 false, true, 2);

-- Add comments for documentation
COMMENT ON TABLE onboarding_steps IS 'Defines the steps in the onboarding questionnaire, including classification context gathering';
COMMENT ON COLUMN onboarding_steps.step_name IS 'Unique identifier for the step (used in API requests)';
COMMENT ON COLUMN onboarding_steps.description IS 'User-facing description shown in the onboarding UI';
COMMENT ON COLUMN onboarding_steps.required IS 'Whether this step must be completed before proceeding';
COMMENT ON COLUMN onboarding_steps.active IS 'Whether this step is currently active (allows disabling steps without deleting)';

-- Example of expected data format in user_onboarding_progress.metadata:
-- Step 1 (industry_selection):
-- {
--   "industry": "food_production",
--   "industry_label": "Producción de alimentos"
-- }
--
-- Step 2 (business_model):
-- {
--   "business_model": "b2b_wholesale",
--   "business_model_label": "Venta mayorista B2B"
-- }
--
-- Step 3 (typical_expenses):
-- {
--   "typical_expenses": ["raw_materials", "salaries", "logistics", "services"],
--   "expense_labels": ["Materias primas", "Nómina", "Logística", "Servicios"]
-- }
--
-- Step 4 (provider_mappings):
-- {
--   "common_providers": {
--     "FIN1203015JA": "servicios_administrativos_timbrado",
--     "MME930209C79": "marketing_digital",
--     "GOOG990101XXX": "cloud_services"
--   }
-- }
--
-- Step 5 (accounting_preferences):
-- {
--   "detail_level": "detailed",  -- Options: "detailed", "summary", "minimal"
--   "auto_approve_threshold": 0.90  -- Confidence threshold for auto-approval (0.0 - 1.0)
-- }

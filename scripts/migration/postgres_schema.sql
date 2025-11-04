-- ============================================
-- PostgreSQL Schema - Converted from SQLite
-- ============================================

-- Generated: Auto-converted
-- Tables: 51
-- Total rows: 1309


-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- ============================================
-- TABLES
-- ============================================

-- Table: ai_context_memory (1 rows)
CREATE TABLE ai_context_memory (
    id SERIAL PRIMARY KEY ,
    company_id INTEGER NOT NULL,
    created_by INTEGER,
    audit_log_id INTEGER,
    context TEXT,
    onboarding_snapshot TEXT,
    embedding_vector TEXT,
    model_name TEXT,
    source TEXT,
    language_detected TEXT,
    context_version INTEGER NOT NULL DEFAULT 1,
    summary TEXT,
    topics TEXT,
    confidence_score DOUBLE PRECISION,
    last_refresh TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (audit_log_id) REFERENCES audit_trail(id) ON DELETE SET NULL
);

-- Table: ai_correction_memory (0 rows)
CREATE TABLE ai_correction_memory (
                id SERIAL PRIMARY KEY ,
                company_id INTEGER NOT NULL,
                tenant_id INTEGER,
                user_id INTEGER,
                original_description TEXT NOT NULL,
                normalized_description TEXT NOT NULL,
                ai_category TEXT,
                corrected_category TEXT NOT NULL,
                movement_kind TEXT,
                amount DOUBLE PRECISION,
                model_used TEXT,
                notes TEXT,
                raw_transaction TEXT,
                embedding_json TEXT NOT NULL,
                embedding_dimensions INTEGER NOT NULL,
                similarity_hint DOUBLE PRECISION,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

-- Table: archived_placeholders (0 rows)
CREATE TABLE archived_placeholders (
        id SERIAL PRIMARY KEY ,
        original_expense_id INTEGER NOT NULL,
        description TEXT,
        amount DOUBLE PRECISION,
        company_id TEXT,
        workflow_status TEXT,
        missing_fields TEXT,
        created_at TEXT,
        archived_at TEXT,
        archived_reason TEXT,
        metadata TEXT
    );

-- Table: audit_trail (2 rows)
CREATE TABLE audit_trail (
    id SERIAL PRIMARY KEY ,
    entidad TEXT NOT NULL,
    entidad_id INTEGER,
    accion TEXT NOT NULL,
    usuario_id INTEGER,
    cambios TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Table: automation_jobs (0 rows)
CREATE TABLE automation_jobs (
    id SERIAL PRIMARY KEY ,
    ticket_id INTEGER NOT NULL,
    merchant_id INTEGER,
    user_id INTEGER,
    estado TEXT NOT NULL DEFAULT 'pendiente',
    automation_type TEXT NOT NULL DEFAULT 'selenium',
    priority INTEGER DEFAULT 5,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    config TEXT,
    result TEXT,
    error_details TEXT,
    current_step TEXT,
    progress_percentage INTEGER DEFAULT 0,
    scheduled_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    estimated_completion TEXT,
    session_id TEXT NOT NULL,
    company_id TEXT NOT NULL DEFAULT 'default',
    selenium_session_id TEXT,
    captcha_attempts INTEGER DEFAULT 0,
    ocr_confidence DOUBLE PRECISION,
    created_at TEXT NOT NULL DEFAULT (TIMESTAMP('now')),
    updated_at TEXT NOT NULL DEFAULT (TIMESTAMP('now')), checkpoint_data TEXT, recovery_metadata TEXT, automation_health TEXT, performance_metrics TEXT, recovery_actions TEXT,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Table: automation_logs (0 rows)
CREATE TABLE automation_logs (
    id SERIAL PRIMARY KEY ,
    job_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'info',
    category TEXT,
    message TEXT NOT NULL,
    url TEXT,
    element_selector TEXT,
    screenshot_id INTEGER,
    execution_time_ms INTEGER,
    data TEXT,
    user_agent TEXT,
    ip_address TEXT,
    timestamp TEXT NOT NULL DEFAULT (TIMESTAMP('now')),
    company_id TEXT NOT NULL DEFAULT 'default',
    FOREIGN KEY (job_id) REFERENCES automation_jobs(id)
);

-- Table: automation_screenshots (0 rows)
CREATE TABLE automation_screenshots (
    id SERIAL PRIMARY KEY ,
    job_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    screenshot_type TEXT NOT NULL DEFAULT 'step',
    file_path TEXT NOT NULL,
    file_size INTEGER,
    url TEXT,
    window_title TEXT,
    viewport_size TEXT,
    page_load_time_ms INTEGER,
    has_captcha INTEGER DEFAULT 0,
    captcha_type TEXT,
    detected_elements TEXT,
    ocr_text TEXT,
    manual_annotations TEXT,
    is_sensitive INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (TIMESTAMP('now')),
    company_id TEXT NOT NULL DEFAULT 'default',
    FOREIGN KEY (job_id) REFERENCES automation_jobs(id)
);

-- Table: automation_sessions (0 rows)
CREATE TABLE automation_sessions (
    id SERIAL PRIMARY KEY ,
    session_id TEXT UNIQUE NOT NULL,
    tenant_id INTEGER NOT NULL,
    state_data TEXT, -- JSON as TEXT
    checkpoint_data TEXT, -- ✅ CAMPO FALTANTE CRÍTICO (JSON as TEXT)
    recovery_metadata TEXT, -- ✅ CAMPO FALTANTE CRÍTICO (JSON as TEXT)
    session_status TEXT DEFAULT 'active',
    compression_type TEXT DEFAULT 'gzip',
    integrity_validation TEXT, -- JSON as TEXT
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Table: bank_match_links (0 rows)
CREATE TABLE bank_match_links (
    id SERIAL PRIMARY KEY ,
    bank_movement_id INTEGER NOT NULL REFERENCES bank_movements(id) ON DELETE CASCADE,
    expense_id INTEGER REFERENCES expense_records(id),
    cfdi_uuid TEXT REFERENCES expense_invoices(uuid),
    monto_asignado DOUBLE PRECISION NOT NULL,
    score DOUBLE PRECISION,
    source TEXT,
    explanation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    tenant_id INTEGER,
    UNIQUE (bank_movement_id, expense_id, cfdi_uuid)
);

-- Table: bank_movements (0 rows)
CREATE TABLE bank_movements (
    id SERIAL PRIMARY KEY ,
    amount DOUBLE PRECISION NOT NULL,
    description TEXT,
    DATE TIMESTAMP,
    account TEXT,
    tenant_id INTEGER,
    matched_expense_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, movement_kind TEXT DEFAULT 'Gasto', decision TEXT, bank_metadata TEXT, confidence DOUBLE PRECISION DEFAULT 0.0, movement_id TEXT, transaction_type TEXT, reference TEXT, balance_after DOUBLE PRECISION, raw_data TEXT, processing_status TEXT DEFAULT 'pending', matched_at TIMESTAMP, matched_by INTEGER, auto_matched BOOLEAN DEFAULT FALSE, reconciliation_notes TEXT, bank_account_id TEXT, category TEXT, context_used TEXT, ai_model TEXT, context_confidence DOUBLE PRECISION, context_version TEXT, matching_confidence DOUBLE PRECISION,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (matched_expense_id) REFERENCES expense_records(id)
);

-- Table: banking_institutions (30 rows)
CREATE TABLE banking_institutions (
    id SERIAL PRIMARY KEY ,
    name TEXT NOT NULL UNIQUE,
    short_name TEXT,
    type TEXT NOT NULL DEFAULT 'bank',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER DEFAULT 100,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (type IN ('bank', 'credit_union', 'fintech', 'other'))
);

-- Table: category_learning_metrics (0 rows)
CREATE TABLE category_learning_metrics (
    id SERIAL PRIMARY KEY ,
    tenant_id INTEGER NOT NULL,
    user_id INTEGER DEFAULT NULL,
    category_name TEXT NOT NULL,
    total_predictions INTEGER DEFAULT 0,
    correct_predictions INTEGER DEFAULT 0,
    accuracy_rate DOUBLE PRECISION DEFAULT 0.0,
    avg_confidence DOUBLE PRECISION DEFAULT 0.0,
    most_common_keywords TEXT, -- JSON array
    most_common_merchants TEXT, -- JSON array
    typical_amount_range TEXT, -- e.g., "100-500"
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Table: category_prediction_config (1 rows)
CREATE TABLE category_prediction_config (
    id SERIAL PRIMARY KEY ,
    tenant_id INTEGER NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    auto_apply_high_confidence BOOLEAN DEFAULT TRUE, -- Auto-aplicar si confianza > threshold
    high_confidence_threshold DOUBLE PRECISION DEFAULT 0.85,
    medium_confidence_threshold DOUBLE PRECISION DEFAULT 0.65,
    use_llm BOOLEAN DEFAULT TRUE,
    llm_model TEXT DEFAULT 'gpt-3.5-turbo',
    use_user_history BOOLEAN DEFAULT TRUE,
    history_weight DOUBLE PRECISION DEFAULT 0.3, -- Peso del historial en la predicción
    categories_config TEXT, -- JSON config for categories
    features_weights TEXT, -- JSON weights for different features
    fallback_category TEXT DEFAULT 'oficina',
    require_manual_review BOOLEAN DEFAULT FALSE, -- Require manual review for low confidence
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Table: category_prediction_history (40 rows)
CREATE TABLE category_prediction_history (
    id SERIAL PRIMARY KEY ,
    expense_id INTEGER NOT NULL,
    predicted_category TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    reasoning TEXT,
    alternatives TEXT, -- JSON array of alternatives
    prediction_method TEXT DEFAULT 'hybrid', -- llm, rules, hybrid
    ml_model_version TEXT DEFAULT '1.0',
    user_feedback TEXT DEFAULT NULL, -- accepted, corrected, rejected
    corrected_category TEXT DEFAULT NULL,
    feedback_date TIMESTAMP DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tenant_id INTEGER NOT NULL,
    FOREIGN KEY (expense_id) REFERENCES expense_records(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Table: cfdi_payments (0 rows)
CREATE TABLE cfdi_payments (
    id SERIAL PRIMARY KEY ,
    uuid_pago TEXT NOT NULL UNIQUE,
    fecha_pago TIMESTAMP NOT NULL,
    moneda TEXT DEFAULT 'MXN',
    tipo_cambio DOUBLE PRECISION DEFAULT 1.0,
    tenant_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: classification_trace (33 rows)
CREATE TABLE classification_trace (id SERIAL PRIMARY KEY , expense_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, sat_account_code TEXT, family_code TEXT, confidence_sat DOUBLE PRECISION, confidence_family DOUBLE PRECISION, explanation_short TEXT, explanation_detail TEXT, tokens TEXT, model_version TEXT, embedding_version TEXT, raw_payload TEXT, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);

-- Table: companies (2 rows)
CREATE TABLE companies (
    id SERIAL PRIMARY KEY ,
    tenant_id INTEGER NOT NULL,
    company_name TEXT NOT NULL,
    legal_name TEXT,
    short_name TEXT,
    email TEXT,
    is_active BOOLEAN DEFAULT 1,
    config TEXT,
    giro TEXT,
    modelo_negocio TEXT,
    clientes_clave TEXT,
    proveedores_clave TEXT,
    canales_venta TEXT,
    frecuencia_operacion TEXT,
    descripcion_negocio TEXT,
    context_last_updated TIMESTAMP,
    context_profile TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Table: custom_categories (8 rows)
CREATE TABLE custom_categories (
    id SERIAL PRIMARY KEY ,
    tenant_id INTEGER NOT NULL,
    category_name TEXT NOT NULL,
    category_description TEXT,
    parent_category TEXT DEFAULT NULL, -- Para jerarquías de categorías
    color_hex TEXT DEFAULT '#6B7280', -- Color para UI
    icon_name TEXT DEFAULT 'folder', -- Icono para UI
    keywords TEXT, -- JSON array of detection keywords
    merchant_patterns TEXT, -- JSON array of merchant patterns
    amount_ranges TEXT, -- JSON array of typical amount ranges
    tax_deductible BOOLEAN DEFAULT TRUE,
    requires_receipt BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- Table: duplicate_detection_config (1 rows)
CREATE TABLE duplicate_detection_config (
    id SERIAL PRIMARY KEY ,
    tenant_id INTEGER NOT NULL,
    similarity_threshold_high DOUBLE PRECISION DEFAULT 0.85,
    similarity_threshold_medium DOUBLE PRECISION DEFAULT 0.70,
    similarity_threshold_low DOUBLE PRECISION DEFAULT 0.55,
    time_window_days INTEGER DEFAULT 30,
    auto_block_high_risk BOOLEAN DEFAULT TRUE,
    auto_review_medium_risk BOOLEAN DEFAULT TRUE,
    enabled_methods TEXT DEFAULT 'hybrid', -- comma separated: ml,heuristic,hybrid
    weights_description DOUBLE PRECISION DEFAULT 0.4,
    weights_amount DOUBLE PRECISION DEFAULT 0.3,
    weights_provider DOUBLE PRECISION DEFAULT 0.2,
    weights_date DOUBLE PRECISION DEFAULT 0.1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Table: duplicate_detections (0 rows)
CREATE TABLE duplicate_detections (
    id SERIAL PRIMARY KEY ,
    expense_id INTEGER NOT NULL,
    potential_duplicate_id INTEGER NOT NULL,
    similarity_score DOUBLE PRECISION NOT NULL,
    risk_level TEXT NOT NULL,
    confidence_level TEXT NOT NULL,
    match_reasons TEXT, -- JSON array of reasons
    detection_method TEXT DEFAULT 'hybrid',
    ml_features_json TEXT, -- JSON ML features
    status TEXT DEFAULT 'pending', -- pending, confirmed, rejected
    reviewed_by INTEGER DEFAULT NULL,
    reviewed_at TIMESTAMP DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tenant_id INTEGER NOT NULL,
    FOREIGN KEY (expense_id) REFERENCES expense_records(id),
    FOREIGN KEY (potential_duplicate_id) REFERENCES expense_records(id),
    FOREIGN KEY (reviewed_by) REFERENCES users(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Table: error_logs (7 rows)
CREATE TABLE error_logs (
                    id SERIAL PRIMARY KEY ,
                    error_id TEXT UNIQUE NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    user_id INTEGER,
                    tenant_id INTEGER,
                    endpoint TEXT,
                    method TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    stack_trace TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP,
                    resolution_notes TEXT
                );

-- Table: expense_attachments (0 rows)
CREATE TABLE expense_attachments (
    id SERIAL PRIMARY KEY ,
    expense_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT,
    file_size INTEGER,
    mime_type TEXT,
    attachment_type TEXT DEFAULT 'receipt',
    uploaded_by INTEGER,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (expense_id) REFERENCES expense_records(id) ON DELETE CASCADE,
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
);

-- Table: expense_invoices (0 rows)
CREATE TABLE expense_invoices (
    id SERIAL PRIMARY KEY ,
    expense_id INTEGER,
    filename TEXT,
    file_path TEXT,
    content_type TEXT,
    parsed_data TEXT,
    tenant_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, subtotal DOUBLE PRECISION, iva_amount DOUBLE PRECISION, discount DOUBLE PRECISION DEFAULT 0.0, retention DOUBLE PRECISION DEFAULT 0.0, xml_content TEXT, validation_status TEXT DEFAULT 'pending', processing_metadata TEXT, template_match DOUBLE PRECISION, validation_rules TEXT, detected_format TEXT, parser_used TEXT, ocr_confidence DOUBLE PRECISION, processing_metrics TEXT, quality_score DOUBLE PRECISION, processor_used TEXT, extraction_confidence DOUBLE PRECISION,
    FOREIGN KEY (expense_id) REFERENCES expense_records(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Table: expense_ml_features (0 rows)
CREATE TABLE expense_ml_features (
    id SERIAL PRIMARY KEY ,
    expense_id INTEGER NOT NULL,
    feature_vector TEXT NOT NULL, -- JSON vector of ML features
    embedding_vector TEXT DEFAULT NULL, -- JSON OpenAI embeddings
    extraction_method TEXT DEFAULT 'rule_based',
    feature_quality_score DOUBLE PRECISION DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tenant_id INTEGER NOT NULL,
    FOREIGN KEY (expense_id) REFERENCES expense_records(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Table: expense_records (14 rows)
CREATE TABLE expense_records (
    id SERIAL PRIMARY KEY ,
    amount DOUBLE PRECISION NOT NULL,
    currency TEXT DEFAULT 'MXN',
    description TEXT,
    category TEXT,
    merchant_name TEXT,
    merchant_category TEXT,
    DATE TIMESTAMP,
    user_id INTEGER,
    tenant_id INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Fiscal pipeline v1
    tax_source TEXT,
    explanation_short TEXT,
    explanation_detail TEXT,
    catalog_version TEXT DEFAULT 'v1',
    classification_source TEXT, descripcion_normalizada TEXT, descripcion_normalizada_fuente TEXT, categoria_normalizada TEXT, categoria_slug TEXT, categoria_confianza DOUBLE PRECISION, categoria_fuente TEXT, sat_account_code TEXT, sat_product_service_code TEXT, deducible BOOLEAN, requiere_factura BOOLEAN, centro_costo TEXT, proyecto TEXT, metodo_pago TEXT, moneda TEXT, rfc_proveedor TEXT, cfdi_uuid TEXT, invoice_status TEXT, bank_status TEXT, approval_status TEXT, approved_by INTEGER, approved_at TIMESTAMP, updated_at TIMESTAMP, updated_by INTEGER, metadata TEXT, similarity_score DOUBLE PRECISION DEFAULT NULL, risk_level TEXT DEFAULT NULL, is_duplicate BOOLEAN DEFAULT FALSE, duplicate_of INTEGER DEFAULT NULL, duplicate_confidence DOUBLE PRECISION DEFAULT NULL, ml_features_json TEXT DEFAULT NULL, categoria_sugerida TEXT DEFAULT NULL, confianza DOUBLE PRECISION DEFAULT NULL, razonamiento TEXT DEFAULT NULL, category_alternatives TEXT DEFAULT NULL, prediction_method TEXT DEFAULT NULL, ml_model_version TEXT DEFAULT NULL, predicted_at TIMESTAMP DEFAULT NULL, category_confirmed BOOLEAN DEFAULT FALSE, category_corrected_by INTEGER DEFAULT NULL, tags TEXT, audit_trail TEXT, user_context TEXT, enhanced_data TEXT, completion_status TEXT DEFAULT 'draft', validation_errors TEXT, field_completeness DOUBLE PRECISION DEFAULT 0.0, tipo_cambio DOUBLE PRECISION DEFAULT 1.0, deducible_status TEXT DEFAULT 'pendiente', deducible_percent DOUBLE PRECISION DEFAULT 100.0, iva_acreditable BOOLEAN DEFAULT 1, periodo TEXT, reconciliation_type TEXT DEFAULT 'simple', split_group_id TEXT, amount_reconciled DOUBLE PRECISION DEFAULT 0, amount_pending DOUBLE PRECISION, is_employee_advance BOOLEAN DEFAULT FALSE, advance_id INTEGER, reimbursement_status TEXT DEFAULT 'not_required', subtotal DOUBLE PRECISION, iva_16 DOUBLE PRECISION DEFAULT 0, iva_8 DOUBLE PRECISION DEFAULT 0, iva_0 DOUBLE PRECISION DEFAULT 0, ieps DOUBLE PRECISION DEFAULT 0, isr_retenido DOUBLE PRECISION DEFAULT 0, iva_retenido DOUBLE PRECISION DEFAULT 0, otros_impuestos DOUBLE PRECISION DEFAULT 0, impuestos_incluidos TEXT, cfdi_status TEXT DEFAULT 'no_disponible', cfdi_pdf_url TEXT, cfdi_xml_url TEXT, cfdi_fecha_timbrado TEXT, cfdi_folio_fiscal TEXT, ticket_image_url TEXT, ticket_folio TEXT, registro_via TEXT, payment_account_id INTEGER, paid_by TEXT DEFAULT 'company_account', will_have_cfdi BOOLEAN DEFAULT 1, company_id TEXT, ticket_id INTEGER, processing_stage TEXT DEFAULT 'converted', classification_stage TEXT DEFAULT 'catalog_context', estado_iva TEXT DEFAULT 'pendiente', validation_status TEXT DEFAULT 'pending', workflow_status TEXT, estado_factura TEXT, estado_factura_original TEXT, estado_conciliacion TEXT, estado_conciliacion_original TEXT, factura_generada BOOLEAN DEFAULT 0, needs_reclassification INTEGER DEFAULT 0, descripcion TEXT, proveedor_nombre TEXT, categoria TEXT, monto_total DOUBLE PRECISION, escalated_to_invoicing BOOLEAN DEFAULT 0, escalated_ticket_id INTEGER, escalation_reason TEXT, escalated_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Table: expense_tag_relations (0 rows)
CREATE TABLE expense_tag_relations (
    expense_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (expense_id, tag_id),
    FOREIGN KEY (expense_id) REFERENCES expense_records(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES expense_tags(id) ON DELETE CASCADE
);

-- Table: expense_tags (8 rows)
CREATE TABLE expense_tags (
    id SERIAL PRIMARY KEY ,
    name TEXT UNIQUE NOT NULL,
    color TEXT DEFAULT '#3498db',
    description TEXT,
    tenant_id INTEGER NOT NULL,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- Table: gpt_usage_events (0 rows)
CREATE TABLE gpt_usage_events (
    id SERIAL PRIMARY KEY ,
    timestamp TEXT NOT NULL,
    field_name TEXT NOT NULL,
    reason TEXT NOT NULL,
    tokens_estimated INTEGER NOT NULL,
    cost_estimated_usd DOUBLE PRECISION NOT NULL,
    confidence_before DOUBLE PRECISION NOT NULL,
    confidence_after DOUBLE PRECISION NOT NULL,
    success INTEGER NOT NULL,
    merchant_type TEXT,
    ticket_id TEXT,
    error_message TEXT,
    tenant_id INTEGER,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Table: ia_metrics_history (2 rows)
CREATE TABLE ia_metrics_history (
                id SERIAL PRIMARY KEY ,
                captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_expenses INTEGER,
                ia_expenses INTEGER,
                catalog_expenses INTEGER,
                provider_rules INTEGER,
                manual_feedback INTEGER,
                traces INTEGER,
                high_confidence_ratio DOUBLE PRECISION
            );

-- Table: invoicing_jobs (0 rows)
CREATE TABLE invoicing_jobs (
    id SERIAL PRIMARY KEY ,
    ticket_id INTEGER NOT NULL,
    merchant_id INTEGER,
    estado TEXT DEFAULT 'pendiente',
    resultado TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    scheduled_at TIMESTAMP,
    completed_at TIMESTAMP,
    company_id TEXT DEFAULT 'default',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);

-- Table: merchants (0 rows)
CREATE TABLE merchants (
    id SERIAL PRIMARY KEY ,
    nombre TEXT NOT NULL,
    metodo_facturacion TEXT NOT NULL,
    metadata TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: model_config_history (27 rows)
CREATE TABLE model_config_history (
                id SERIAL PRIMARY KEY ,
                model_version TEXT,
                prompt_version TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

-- Table: onboarding_steps (6 rows)
CREATE TABLE onboarding_steps (
    id SERIAL PRIMARY KEY ,
    step_number INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    description TEXT,
    required BOOLEAN DEFAULT TRUE,
    active BOOLEAN DEFAULT TRUE,
    tenant_id INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Table: payment_applications (0 rows)
CREATE TABLE payment_applications (
    id SERIAL PRIMARY KEY ,
    uuid_pago TEXT NOT NULL REFERENCES cfdi_payments(uuid_pago) ON DELETE CASCADE,
    cfdi_uuid TEXT NOT NULL REFERENCES expense_invoices(uuid),
    no_parcialidad INTEGER NOT NULL,
    monto_pagado DOUBLE PRECISION NOT NULL,
    saldo_insoluto DOUBLE PRECISION NOT NULL,
    moneda TEXT DEFAULT 'MXN',
    tipo_cambio DOUBLE PRECISION DEFAULT 1.0,
    fecha_pago TIMESTAMP NOT NULL,
    tenant_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (uuid_pago, cfdi_uuid, no_parcialidad)
);

-- Table: provider_rules (0 rows)
CREATE TABLE provider_rules (
                        id SERIAL PRIMARY KEY ,
                        tenant_id INTEGER REFERENCES tenants(id),
                        provider_name_normalized TEXT,
                        category_slug TEXT,
                        sat_account_code TEXT,
                        sat_product_service_code TEXT,
                        default_iva_rate DOUBLE PRECISION DEFAULT 0,
                        iva_tipo TEXT DEFAULT 'tasa_0',
                        confidence DOUBLE PRECISION DEFAULT 0.9,
                        last_confirmed_by INTEGER,
                        last_confirmed_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

-- Table: refresh_tokens (20 rows)
CREATE TABLE refresh_tokens (
    id SERIAL PRIMARY KEY ,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tenant_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Table: sat_account_catalog (1077 rows)
CREATE TABLE sat_account_catalog (
    id SERIAL PRIMARY KEY ,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    parent_code TEXT,
    type TEXT DEFAULT 'agrupador',
    is_active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (TIMESTAMP('now'))
);

-- Table: sat_product_service_catalog (12 rows)
CREATE TABLE sat_product_service_catalog (
    id SERIAL PRIMARY KEY ,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    unit_key TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (TIMESTAMP('now'))
);

-- Table: schema_migrations (4 rows)
CREATE TABLE schema_migrations (id SERIAL PRIMARY KEY , version TEXT UNIQUE, description TEXT, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);

-- Table: schema_versions (4 rows)
CREATE TABLE schema_versions (
    id SERIAL PRIMARY KEY ,
    version TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Table: system_health (0 rows)
CREATE TABLE system_health (
    id SERIAL PRIMARY KEY ,
    component_name TEXT NOT NULL,
    health_status TEXT NOT NULL,
    automation_health TEXT, -- JSON as TEXT
    performance_metrics TEXT, -- JSON as TEXT
    error_count INTEGER DEFAULT 0,
    last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT -- JSON as TEXT
);

-- Table: tenant_policies (1 rows)
CREATE TABLE tenant_policies (
                tenant_id SERIAL PRIMARY KEY,
                family_preferences TEXT,
                overrides TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

-- Table: tenants (2 rows)
CREATE TABLE tenants (
    id SERIAL PRIMARY KEY ,
    name TEXT NOT NULL,
    api_key TEXT,
    config TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
, domain TEXT);

-- Table: tickets (0 rows)
CREATE TABLE tickets (
    id SERIAL PRIMARY KEY ,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'open',
    priority TEXT DEFAULT 'medium',
    assignee TEXT,
    tenant_id INTEGER,
    user_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, raw_data TEXT, tipo TEXT DEFAULT 'texto', estado TEXT DEFAULT 'pendiente', whatsapp_message_id TEXT, company_id TEXT DEFAULT 'default', original_image TEXT, merchant_id INTEGER, merchant_name TEXT, category TEXT, confidence DOUBLE PRECISION, invoice_data TEXT, llm_analysis TEXT, extracted_text TEXT, expense_id INTEGER, is_mirror_ticket BOOLEAN DEFAULT 0,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Table: user_category_preferences (0 rows)
CREATE TABLE user_category_preferences (
    id SERIAL PRIMARY KEY ,
    user_id INTEGER NOT NULL,
    category_name TEXT NOT NULL,
    frequency INTEGER DEFAULT 1, -- Cuántas veces ha usado esta categoría
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    preference_score DOUBLE PRECISION DEFAULT 1.0, -- Score de preferencia (0.0 - 1.0)
    keywords TEXT, -- JSON array of keywords that trigger this category
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tenant_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Table: user_demo_config (0 rows)
CREATE TABLE user_demo_config (
    id SERIAL PRIMARY KEY ,
    user_id INTEGER NOT NULL,
    demo_type TEXT NOT NULL, -- 'expense_data', 'bank_data', 'invoice_data'
    config_data TEXT, -- JSON con preferencias específicas
    generated_records INTEGER DEFAULT 0,
    last_generated TIMESTAMP,
    tenant_id INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Table: user_onboarding_progress (0 rows)
CREATE TABLE user_onboarding_progress (
    id SERIAL PRIMARY KEY ,
    user_id INTEGER NOT NULL,
    step_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending', -- 'pending', 'in_progress', 'completed', 'skipped'
    completed_at TIMESTAMP,
    metadata TEXT, -- JSON con datos específicos del paso
    tenant_id INTEGER DEFAULT 1,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (step_id) REFERENCES onboarding_steps(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),

    UNIQUE(user_id, step_id)
);

-- Table: user_payment_accounts (5 rows)
CREATE TABLE user_payment_accounts (
    id SERIAL PRIMARY KEY ,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL,
    subtipo TEXT,
    moneda TEXT NOT NULL DEFAULT 'MXN',
    saldo_inicial DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    saldo_actual DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    limite_credito DOUBLE PRECISION,
    fecha_corte INTEGER,
    fecha_pago INTEGER,
    credito_disponible DOUBLE PRECISION,
    propietario_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    proveedor_terminal TEXT,
    banco_nombre TEXT,
    numero_tarjeta TEXT,
    numero_cuenta_enmascarado TEXT,
    numero_identificacion TEXT,
    numero_cuenta TEXT,
    clabe TEXT,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_default BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (propietario_id) REFERENCES users(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Table: user_preferences (0 rows)
CREATE TABLE user_preferences (
    id SERIAL PRIMARY KEY ,
    user_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    preferences TEXT, -- JSON as TEXT
    onboarding_step TEXT DEFAULT 'start',
    demo_preferences TEXT, -- JSON as TEXT
    completion_rules TEXT, -- JSON as TEXT
    field_priorities TEXT, -- JSON as TEXT
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Table: users (2 rows)
CREATE TABLE users (
    id SERIAL PRIMARY KEY ,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    tenant_id INTEGER DEFAULT 1,
    role TEXT DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Campos de autenticación (de fix_auth_schema.sql)
    password_hash TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMP,

    -- Campos de onboarding (FALTANTE en auditoria)
    identifier TEXT, -- email o phone
    full_name TEXT,
    company_name TEXT,
    onboarding_step INTEGER DEFAULT 0, -- ⚠️ FALTABA EN BD
    demo_preferences TEXT, -- JSON - ❌ FALTABA EN API
    onboarding_completed BOOLEAN DEFAULT FALSE,
    onboarding_completed_at TIMESTAMP,

    -- Metadata adicional
    phone TEXT,
    registration_method TEXT DEFAULT 'email', -- 'email', 'whatsapp'
    verification_token TEXT,
    email_verified BOOLEAN DEFAULT FALSE,
    phone_verified BOOLEAN DEFAULT FALSE, username TEXT, employee_id INTEGER, department TEXT, created_by INTEGER, is_email_verified BOOLEAN DEFAULT FALSE, failed_login_attempts INTEGER DEFAULT 0, locked_until TIMESTAMP, company_id INTEGER, metadata TEXT,

    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Table: workers (0 rows)
CREATE TABLE workers (
    id SERIAL PRIMARY KEY ,
    task_id TEXT UNIQUE NOT NULL,
    tenant_id INTEGER NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    progress DOUBLE PRECISION DEFAULT 0.0, -- ✅ CAMPO FALTANTE CRÍTICO
    worker_metadata TEXT, -- ✅ CAMPO FALTANTE CRÍTICO (JSON as TEXT)
    retry_policy TEXT, -- ✅ CAMPO FALTANTE CRÍTICO (JSON as TEXT)
    retry_count INTEGER DEFAULT 0,
    result_data TEXT, -- JSON as TEXT
    performance_tracking TEXT, -- JSON as TEXT
    task_scheduling TEXT, -- JSON as TEXT
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);


-- ============================================
-- INDEXES
-- ============================================

-- Index: idx_ai_context_memory_company_version
CREATE INDEX idx_ai_context_memory_company_version
    ON ai_context_memory(company_id, context_version);

-- Index: idx_ai_context_memory_created_by
CREATE INDEX idx_ai_context_memory_created_by
    ON ai_context_memory(created_by);

-- Index: idx_ai_correction_company
CREATE INDEX idx_ai_correction_company
            ON ai_correction_memory(company_id, created_at DESC)
            ;

-- Index: idx_attachments_expense
CREATE INDEX idx_attachments_expense ON expense_attachments(expense_id);

-- Index: idx_attachments_type
CREATE INDEX idx_attachments_type ON expense_attachments(attachment_type);

-- Index: idx_attachments_uploaded
CREATE INDEX idx_attachments_uploaded ON expense_attachments(uploaded_at DESC);

-- Index: idx_audit_trail_entidad
CREATE INDEX idx_audit_trail_entidad
    ON audit_trail(entidad);

-- Index: idx_audit_trail_usuario
CREATE INDEX idx_audit_trail_usuario
    ON audit_trail(usuario_id);

-- Index: idx_automation_jobs_company
CREATE INDEX idx_automation_jobs_company ON automation_jobs(company_id);

-- Index: idx_automation_jobs_created
CREATE INDEX idx_automation_jobs_created ON automation_jobs(created_at);

-- Index: idx_automation_jobs_estado
CREATE INDEX idx_automation_jobs_estado ON automation_jobs(estado);

-- Index: idx_automation_jobs_session
CREATE INDEX idx_automation_jobs_session ON automation_jobs(session_id);

-- Index: idx_automation_logs_category
CREATE INDEX idx_automation_logs_category ON automation_logs(category);

-- Index: idx_automation_logs_job
CREATE INDEX idx_automation_logs_job ON automation_logs(job_id);

-- Index: idx_automation_logs_level
CREATE INDEX idx_automation_logs_level ON automation_logs(level);

-- Index: idx_automation_screenshots_job
CREATE INDEX idx_automation_screenshots_job ON automation_screenshots(job_id);

-- Index: idx_automation_screenshots_type
CREATE INDEX idx_automation_screenshots_type ON automation_screenshots(screenshot_type);

-- Index: idx_automation_sessions_status
CREATE INDEX idx_automation_sessions_status ON automation_sessions(session_status);

-- Index: idx_automation_sessions_tenant
CREATE INDEX idx_automation_sessions_tenant ON automation_sessions(tenant_id);

-- Index: idx_bank_match_links_cfdi
CREATE INDEX idx_bank_match_links_cfdi ON bank_match_links(cfdi_uuid);

-- Index: idx_bank_match_links_movement
CREATE INDEX idx_bank_match_links_movement ON bank_match_links(bank_movement_id);

-- Index: idx_bank_movements_confidence
CREATE INDEX idx_bank_movements_confidence ON bank_movements(matching_confidence);

-- Index: idx_bank_movements_decision
CREATE INDEX idx_bank_movements_decision ON bank_movements(decision);

-- Index: idx_bank_movements_fecha_monto
CREATE INDEX idx_bank_movements_fecha_monto ON bank_movements(date, amount);

-- Index: idx_bank_movements_reconciliation
CREATE INDEX idx_bank_movements_reconciliation ON bank_movements (tenant_id, date, amount);

-- Index: idx_bank_movements_tenant
CREATE INDEX idx_bank_movements_tenant ON bank_movements(tenant_id);

-- Index: idx_banking_institutions_active_sort
CREATE INDEX idx_banking_institutions_active_sort
ON banking_institutions(active, sort_order);

-- Index: idx_banking_institutions_name
CREATE INDEX idx_banking_institutions_name
ON banking_institutions(name) WHERE active = TRUE;

-- Index: idx_banking_institutions_type
CREATE INDEX idx_banking_institutions_type
ON banking_institutions(type);

-- Index: idx_category_config_tenant
CREATE INDEX idx_category_config_tenant ON category_prediction_config(tenant_id);

-- Index: idx_category_prediction_category
CREATE INDEX idx_category_prediction_category ON category_prediction_history(predicted_category);

-- Index: idx_category_prediction_confidence
CREATE INDEX idx_category_prediction_confidence ON category_prediction_history(confidence DESC);

-- Index: idx_category_prediction_expense
CREATE INDEX idx_category_prediction_expense ON category_prediction_history(expense_id);

-- Index: idx_category_prediction_feedback
CREATE INDEX idx_category_prediction_feedback ON category_prediction_history(user_feedback);

-- Index: idx_category_prediction_method
CREATE INDEX idx_category_prediction_method ON category_prediction_history(prediction_method);

-- Index: idx_category_prediction_tenant
CREATE INDEX idx_category_prediction_tenant ON category_prediction_history(tenant_id);

-- Index: idx_classification_trace_expense
CREATE INDEX idx_classification_trace_expense ON classification_trace (expense_id, tenant_id, created_at DESC);

-- Index: idx_companies_tenant
CREATE INDEX idx_companies_tenant ON companies(tenant_id);

-- Index: idx_custom_categories_active
CREATE INDEX idx_custom_categories_active ON custom_categories(is_active);

-- Index: idx_custom_categories_name
CREATE INDEX idx_custom_categories_name ON custom_categories(category_name);

-- Index: idx_custom_categories_sort
CREATE INDEX idx_custom_categories_sort ON custom_categories(sort_order);

-- Index: idx_custom_categories_tenant
CREATE INDEX idx_custom_categories_tenant ON custom_categories(tenant_id);

-- Index: idx_duplicate_config_tenant
CREATE INDEX idx_duplicate_config_tenant ON duplicate_detection_config(tenant_id);

-- Index: idx_duplicate_detections_expense
CREATE INDEX idx_duplicate_detections_expense ON duplicate_detections(expense_id);

-- Index: idx_duplicate_detections_potential
CREATE INDEX idx_duplicate_detections_potential ON duplicate_detections(potential_duplicate_id);

-- Index: idx_duplicate_detections_risk
CREATE INDEX idx_duplicate_detections_risk ON duplicate_detections(risk_level);

-- Index: idx_duplicate_detections_score
CREATE INDEX idx_duplicate_detections_score ON duplicate_detections(similarity_score DESC);

-- Index: idx_duplicate_detections_status
CREATE INDEX idx_duplicate_detections_status ON duplicate_detections(status);

-- Index: idx_duplicate_detections_tenant
CREATE INDEX idx_duplicate_detections_tenant ON duplicate_detections(tenant_id);

-- Index: idx_expense_approval
CREATE INDEX idx_expense_approval ON expense_records(approval_status);

-- Index: idx_expense_bank_status
CREATE INDEX idx_expense_bank_status ON expense_records(bank_status);

-- Index: idx_expense_categoria_sugerida
CREATE INDEX idx_expense_categoria_sugerida ON expense_records(categoria_sugerida);

-- Index: idx_expense_category_confirmed
CREATE INDEX idx_expense_category_confirmed ON expense_records(category_confirmed);

-- Index: idx_expense_category_corrected_by
CREATE INDEX idx_expense_category_corrected_by ON expense_records(category_corrected_by);

-- Index: idx_expense_centro_costo
CREATE INDEX idx_expense_centro_costo ON expense_records(centro_costo);

-- Index: idx_expense_cfdi
CREATE INDEX idx_expense_cfdi ON expense_records(cfdi_uuid);

-- Index: idx_expense_confianza
CREATE INDEX idx_expense_confianza ON expense_records(confianza DESC);

-- Index: idx_expense_deducible
CREATE INDEX idx_expense_deducible ON expense_records(deducible);

-- Index: idx_expense_duplicate_of
CREATE INDEX idx_expense_duplicate_of ON expense_records(duplicate_of);

-- Index: idx_expense_duplicate_ref
CREATE INDEX idx_expense_duplicate_ref ON expense_records(duplicate_of);

-- Index: idx_expense_escalated
CREATE INDEX idx_expense_escalated ON expense_records(escalated_to_invoicing, will_have_cfdi);

-- Index: idx_expense_escalated_ticket
CREATE INDEX idx_expense_escalated_ticket ON expense_records(escalated_ticket_id);

-- Index: idx_expense_invoice_status
CREATE INDEX idx_expense_invoice_status ON expense_records(invoice_status);

-- Index: idx_expense_invoice_uuid
CREATE UNIQUE INDEX idx_expense_invoice_uuid ON expense_records(cfdi_uuid) WHERE cfdi_uuid IS NOT NULL;

-- Index: idx_expense_invoices_detected_format
CREATE INDEX idx_expense_invoices_detected_format ON expense_invoices(detected_format);

-- Index: idx_expense_invoices_expense_id
CREATE INDEX idx_expense_invoices_expense_id ON expense_invoices (expense_id);

-- Index: idx_expense_invoices_quality_score
CREATE INDEX idx_expense_invoices_quality_score ON expense_invoices(quality_score);

-- Index: idx_expense_invoices_template_match
CREATE INDEX idx_expense_invoices_template_match ON expense_invoices(template_match);

-- Index: idx_expense_invoices_validation_status
CREATE INDEX idx_expense_invoices_validation_status ON expense_invoices(validation_status);

-- Index: idx_expense_is_duplicate
CREATE INDEX idx_expense_is_duplicate ON expense_records(is_duplicate);

-- Index: idx_expense_metodo_pago
CREATE INDEX idx_expense_metodo_pago ON expense_records(metodo_pago);

-- Index: idx_expense_moneda
CREATE INDEX idx_expense_moneda ON expense_records(moneda);

-- Index: idx_expense_predicted_at
CREATE INDEX idx_expense_predicted_at ON expense_records(predicted_at DESC);

-- Index: idx_expense_prediction_method
CREATE INDEX idx_expense_prediction_method ON expense_records(prediction_method);

-- Index: idx_expense_proyecto
CREATE INDEX idx_expense_proyecto ON expense_records(proyecto);

-- Index: idx_expense_records_centro_costo
CREATE INDEX idx_expense_records_centro_costo ON expense_records(centro_costo);

-- Index: idx_expense_records_completion
CREATE INDEX idx_expense_records_completion ON expense_records(completion_status);

-- Index: idx_expense_records_compound
CREATE INDEX idx_expense_records_compound ON expense_records (tenant_id, status, date);

-- Index: idx_expense_records_date
CREATE INDEX idx_expense_records_date ON expense_records(date);

-- Index: idx_expense_records_date_range
CREATE INDEX idx_expense_records_date_range ON expense_records (date, tenant_id);

-- Index: idx_expense_records_deducible
CREATE INDEX idx_expense_records_deducible ON expense_records(deducible);

-- Index: idx_expense_records_provider
CREATE INDEX idx_expense_records_provider ON expense_records (rfc_proveedor, merchant_name);

-- Index: idx_expense_records_proyecto
CREATE INDEX idx_expense_records_proyecto ON expense_records(proyecto);

-- Index: idx_expense_records_tenant
CREATE INDEX idx_expense_records_tenant ON expense_records(tenant_id);

-- Index: idx_expense_records_user
CREATE INDEX idx_expense_records_user ON expense_records(user_id);

-- Index: idx_expense_risk_level
CREATE INDEX idx_expense_risk_level ON expense_records(risk_level);

-- Index: idx_expense_similarity_score
CREATE INDEX idx_expense_similarity_score ON expense_records(similarity_score DESC);

-- Index: idx_expense_tags_name
CREATE INDEX idx_expense_tags_name ON expense_tags(name);

-- Index: idx_expense_tags_tenant
CREATE INDEX idx_expense_tags_tenant ON expense_tags(tenant_id);

-- Index: idx_expense_updated
CREATE INDEX idx_expense_updated ON expense_records(updated_at DESC);

-- Index: idx_expense_workflow_status
CREATE INDEX idx_expense_workflow_status ON expense_records(workflow_status);

-- Index: idx_gpt_usage_tenant
CREATE INDEX idx_gpt_usage_tenant ON gpt_usage_events(tenant_id);

-- Index: idx_invoicing_jobs_company
CREATE INDEX idx_invoicing_jobs_company ON invoicing_jobs(company_id);

-- Index: idx_invoicing_jobs_estado
CREATE INDEX idx_invoicing_jobs_estado ON invoicing_jobs(estado);

-- Index: idx_invoicing_jobs_ticket
CREATE INDEX idx_invoicing_jobs_ticket ON invoicing_jobs(ticket_id);

-- Index: idx_learning_metrics_category
CREATE INDEX idx_learning_metrics_category ON category_learning_metrics(category_name);

-- Index: idx_learning_metrics_tenant
CREATE INDEX idx_learning_metrics_tenant ON category_learning_metrics(tenant_id);

-- Index: idx_learning_metrics_user
CREATE INDEX idx_learning_metrics_user ON category_learning_metrics(user_id);

-- Index: idx_merchants_active
CREATE INDEX idx_merchants_active ON merchants(is_active);

-- Index: idx_merchants_nombre
CREATE INDEX idx_merchants_nombre ON merchants(nombre);

-- Index: idx_ml_features_expense
CREATE INDEX idx_ml_features_expense ON expense_ml_features(expense_id);

-- Index: idx_ml_features_tenant
CREATE INDEX idx_ml_features_tenant ON expense_ml_features(tenant_id);

-- Index: idx_onboarding_steps_active
CREATE INDEX idx_onboarding_steps_active ON onboarding_steps(active);

-- Index: idx_onboarding_steps_number
CREATE INDEX idx_onboarding_steps_number ON onboarding_steps(step_number);

-- Index: idx_onboarding_steps_tenant
CREATE INDEX idx_onboarding_steps_tenant ON onboarding_steps(tenant_id);

-- Index: idx_payment_applications_cfdi
CREATE INDEX idx_payment_applications_cfdi ON payment_applications(cfdi_uuid);

-- Index: idx_provider_rules_lookup
CREATE INDEX idx_provider_rules_lookup
                        ON provider_rules(tenant_id, provider_name_normalized)
                    ;

-- Index: idx_refresh_tokens_expires
CREATE INDEX idx_refresh_tokens_expires ON refresh_tokens(expires_at);

-- Index: idx_refresh_tokens_hash
CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens(token_hash);

-- Index: idx_refresh_tokens_user
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id);

-- Index: idx_sat_account_catalog_code
CREATE INDEX idx_sat_account_catalog_code
    ON sat_account_catalog(code);

-- Index: idx_sat_product_service_catalog_code
CREATE INDEX idx_sat_product_service_catalog_code
    ON sat_product_service_catalog(code);

-- Index: idx_system_health_component
CREATE INDEX idx_system_health_component ON system_health(component_name);

-- Index: idx_system_health_status
CREATE INDEX idx_system_health_status ON system_health(health_status);

-- Index: idx_tag_relations_expense
CREATE INDEX idx_tag_relations_expense ON expense_tag_relations(expense_id);

-- Index: idx_tag_relations_tag
CREATE INDEX idx_tag_relations_tag ON expense_tag_relations(tag_id);

-- Index: idx_tickets_company_id
CREATE INDEX idx_tickets_company_id ON tickets(company_id);

-- Index: idx_tickets_estado
CREATE INDEX idx_tickets_estado ON tickets(estado);

-- Index: idx_tickets_expense_id
CREATE INDEX idx_tickets_expense_id ON tickets(expense_id);

-- Index: idx_tickets_mirror
CREATE INDEX idx_tickets_mirror ON tickets(is_mirror_ticket, expense_id);

-- Index: idx_tickets_processing
CREATE INDEX idx_tickets_processing ON tickets (status, tenant_id, created_at);

-- Index: idx_tickets_tenant
CREATE INDEX idx_tickets_tenant ON tickets(tenant_id);

-- Index: idx_user_demo_config_tenant
CREATE INDEX idx_user_demo_config_tenant ON user_demo_config(tenant_id);

-- Index: idx_user_demo_config_type
CREATE INDEX idx_user_demo_config_type ON user_demo_config(demo_type);

-- Index: idx_user_demo_config_user
CREATE INDEX idx_user_demo_config_user ON user_demo_config(user_id);

-- Index: idx_user_payment_accounts_propietario_activo
CREATE INDEX idx_user_payment_accounts_propietario_activo
    ON user_payment_accounts(propietario_id, activo);

-- Index: idx_user_payment_accounts_tenant
CREATE INDEX idx_user_payment_accounts_tenant
    ON user_payment_accounts(tenant_id);

-- Index: idx_user_payment_accounts_tipo
CREATE INDEX idx_user_payment_accounts_tipo
    ON user_payment_accounts(tipo);

-- Index: idx_user_preferences_active
CREATE INDEX idx_user_preferences_active ON user_category_preferences(active);

-- Index: idx_user_preferences_category
CREATE INDEX idx_user_preferences_category ON user_category_preferences(category_name);

-- Index: idx_user_preferences_frequency
CREATE INDEX idx_user_preferences_frequency ON user_category_preferences(frequency DESC);

-- Index: idx_user_preferences_tenant
CREATE INDEX idx_user_preferences_tenant ON user_category_preferences(tenant_id);

-- Index: idx_user_preferences_user
CREATE INDEX idx_user_preferences_user ON user_category_preferences(user_id);

-- Index: idx_user_progress_status
CREATE INDEX idx_user_progress_status ON user_onboarding_progress(status);

-- Index: idx_user_progress_tenant
CREATE INDEX idx_user_progress_tenant ON user_onboarding_progress(tenant_id);

-- Index: idx_user_progress_user
CREATE INDEX idx_user_progress_user ON user_onboarding_progress(user_id);

-- Index: idx_users_email
CREATE INDEX idx_users_email ON users(email);

-- Index: idx_users_identifier
CREATE INDEX idx_users_identifier ON users(identifier);

-- Index: idx_users_onboarding_step
CREATE INDEX idx_users_onboarding_step ON users(onboarding_step);

-- Index: idx_users_registration_method
CREATE INDEX idx_users_registration_method ON users(registration_method);

-- Index: idx_users_tenant
CREATE INDEX idx_users_tenant ON users(tenant_id);

-- Index: idx_users_verification
CREATE INDEX idx_users_verification ON users(verification_token);

-- Index: idx_workers_status
CREATE INDEX idx_workers_status ON workers(status);

-- Index: idx_workers_task_type
CREATE INDEX idx_workers_task_type ON workers(task_type);

-- Index: idx_workers_tenant
CREATE INDEX idx_workers_tenant ON workers(tenant_id);


-- ============================================
-- VIEWS
-- ============================================

-- View: onboarding_status_view
CREATE VIEW onboarding_status_view AS
SELECT
    u.id as user_id,
    u.name,
    u.email,
    u.identifier,
    u.full_name,
    u.company_name,
    u.onboarding_step,
    u.onboarding_completed,
    u.registration_method,
    u.email_verified,
    u.phone_verified,
    u.demo_preferences,
    COUNT(uop.id) as completed_steps,
    MAX(os.step_number) as total_steps,
    CASE
        WHEN u.onboarding_completed = TRUE THEN 'completed'
        WHEN COUNT(uop.id) = 0 THEN 'not_started'
        WHEN COUNT(uop.id) < MAX(os.step_number) THEN 'in_progress'
        ELSE 'ready_to_complete'
    END as overall_status
FROM users u
CROSS JOIN (SELECT MAX(step_number) as step_number FROM onboarding_steps WHERE active = TRUE AND tenant_id = 1) os
LEFT JOIN user_onboarding_progress uop ON u.id = uop.user_id AND uop.status = 'completed'
WHERE u.tenant_id = 1
GROUP BY u.id;

-- View: user_payment_accounts_view
CREATE VIEW user_payment_accounts_view AS
SELECT
    upa.id,
    upa.nombre,
    upa.tipo,
    upa.subtipo,
    upa.moneda,
    upa.saldo_inicial,
    upa.saldo_actual,
    upa.limite_credito,
    upa.credito_disponible,
    upa.fecha_corte,
    upa.fecha_pago,
    upa.propietario_id,
    u.email AS propietario_email,
    u.full_name AS propietario_nombre,
    upa.tenant_id,
    t.name AS tenant_nombre,
    upa.proveedor_terminal,
    upa.banco_nombre,
    upa.numero_tarjeta,
    upa.numero_cuenta,
    upa.numero_cuenta_enmascarado,
    upa.clabe,
    upa.activo,
    upa.created_at,
    upa.updated_at
FROM user_payment_accounts upa
LEFT JOIN users u ON upa.propietario_id = u.id
LEFT JOIN tenants t ON upa.tenant_id = t.id;


-- ============================================
-- TRIGGERS
-- ============================================
-- Note: Triggers require manual conversion
-- Found 10 triggers to convert manually

-- TODO: Convert trigger: category_config_updated_at
-- TODO: Convert trigger: custom_categories_updated_at
-- TODO: Convert trigger: duplicate_config_updated_at
-- TODO: Convert trigger: expense_records_updated_at
-- TODO: Convert trigger: ml_features_updated_at
-- TODO: Convert trigger: trg_upa_credito_disponible
-- TODO: Convert trigger: trg_upa_credito_disponible_update
-- TODO: Convert trigger: trg_upa_init_saldo
-- TODO: Convert trigger: trg_upa_updated_at
-- TODO: Convert trigger: user_preferences_updated_at
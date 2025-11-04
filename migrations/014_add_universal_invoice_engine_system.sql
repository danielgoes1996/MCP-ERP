-- Migration 014: Universal Invoice Engine System
-- Implementa engine universal para procesamiento de facturas multi-formato
-- Resuelve gaps: template_match, validation_rules

BEGIN;

-- Tabla principal para sesiones de procesamiento universal de facturas
CREATE TABLE IF NOT EXISTS universal_invoice_sessions (
    id TEXT PRIMARY KEY DEFAULT ('uis_' || lower(hex(randomblob(16)))),
    company_id TEXT NOT NULL,
    user_id TEXT,

    -- Información de la factura
    invoice_file_path TEXT NOT NULL,
    original_filename TEXT,
    file_size_bytes INTEGER,
    file_hash TEXT,

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    template_match JSONB DEFAULT '{}',      -- ✅ CAMPO FALTANTE: Template matching results
    validation_rules JSONB DEFAULT '{}',   -- ✅ CAMPO FALTANTE: Validation rules applied

    -- Detección de formato
    detected_format TEXT,
    format_confidence DECIMAL(5,2) DEFAULT 0.00,
    parser_used TEXT,
    backup_parsers JSONB DEFAULT '[]',

    -- Processing results
    extraction_status TEXT DEFAULT 'pending' CHECK (extraction_status IN ('pending', 'processing', 'completed', 'failed', 'partial')),
    extracted_data JSONB DEFAULT '{}',
    validation_status TEXT DEFAULT 'pending' CHECK (validation_status IN ('pending', 'validating', 'valid', 'invalid', 'warning')),
    validation_errors JSONB DEFAULT '[]',

    -- Quality metrics
    extraction_confidence DECIMAL(5,2) DEFAULT 0.00,
    validation_score DECIMAL(5,2) DEFAULT 0.00,
    overall_quality_score DECIMAL(5,2) DEFAULT 0.00,

    -- Performance tracking
    processing_time_ms INTEGER,
    parser_selection_time_ms INTEGER,
    validation_time_ms INTEGER,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Tabla para formatos de facturas soportados
CREATE TABLE IF NOT EXISTS universal_invoice_formats (
    id TEXT PRIMARY KEY DEFAULT ('uif_' || lower(hex(randomblob(16)))),
    company_id TEXT NOT NULL,

    -- Format information
    format_name TEXT NOT NULL,
    format_type TEXT NOT NULL CHECK (format_type IN ('pdf', 'xml', 'json', 'csv', 'image', 'txt')),
    format_version TEXT,
    issuer_name TEXT,

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    template_match JSONB DEFAULT '{}',      -- ✅ CAMPO FALTANTE: Template matching rules
    validation_rules JSONB DEFAULT '{}',   -- ✅ CAMPO FALTANTE: Validation rules for format

    -- Parser configuration
    parser_class TEXT NOT NULL,
    parser_config JSONB DEFAULT '{}',
    extraction_rules JSONB DEFAULT '{}',

    -- Template matching
    template_patterns JSONB DEFAULT '[]',
    key_indicators JSONB DEFAULT '[]',
    confidence_thresholds JSONB DEFAULT '{}',

    -- Validation configuration
    required_fields JSONB DEFAULT '[]',
    field_formats JSONB DEFAULT '{}',
    business_rules JSONB DEFAULT '[]',

    -- Usage statistics
    usage_count INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 100.00,
    avg_confidence DECIMAL(5,2) DEFAULT 0.00,
    last_used TIMESTAMP,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    priority INTEGER DEFAULT 50,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    UNIQUE(company_id, format_name, format_version)
);

-- Tabla para template matching results
CREATE TABLE IF NOT EXISTS universal_invoice_templates (
    id TEXT PRIMARY KEY DEFAULT ('uit_' || lower(hex(randomblob(16)))),
    session_id TEXT NOT NULL,
    format_id TEXT NOT NULL,

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    template_match JSONB DEFAULT '{}',      -- ✅ CAMPO FALTANTE: Matching results

    -- Template matching details
    template_name TEXT NOT NULL,
    match_score DECIMAL(5,2) DEFAULT 0.00,
    matched_patterns JSONB DEFAULT '[]',
    confidence_factors JSONB DEFAULT '{}',

    -- Matching process
    matching_method TEXT CHECK (matching_method IN ('pattern_based', 'ml_based', 'hybrid', 'manual')),
    matching_time_ms INTEGER,
    fallback_used BOOLEAN DEFAULT FALSE,

    -- Template data
    template_structure JSONB DEFAULT '{}',
    field_mappings JSONB DEFAULT '{}',
    extraction_hints JSONB DEFAULT '{}',

    -- Results
    is_selected BOOLEAN DEFAULT FALSE,
    selection_reason TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (session_id) REFERENCES universal_invoice_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (format_id) REFERENCES universal_invoice_formats(id) ON DELETE CASCADE
);

-- Tabla para validation rules y results
CREATE TABLE IF NOT EXISTS universal_invoice_validations (
    id TEXT PRIMARY KEY DEFAULT ('uiv_' || lower(hex(randomblob(16)))),
    session_id TEXT NOT NULL,

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    validation_rules JSONB DEFAULT '{}',    -- ✅ CAMPO FALTANTE: Applied validation rules

    -- Validation configuration
    rule_set_name TEXT NOT NULL,
    rule_category TEXT CHECK (rule_category IN ('format', 'business', 'compliance', 'custom')),
    rule_priority INTEGER DEFAULT 50,

    -- Rule definition
    rule_definition JSONB NOT NULL,
    rule_parameters JSONB DEFAULT '{}',
    error_messages JSONB DEFAULT '{}',

    -- Validation execution
    validation_status TEXT DEFAULT 'pending' CHECK (validation_status IN ('pending', 'running', 'passed', 'failed', 'skipped')),
    validation_result JSONB DEFAULT '{}',
    error_details TEXT,

    -- Performance
    execution_time_ms INTEGER,
    memory_usage_mb DECIMAL(8,2),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP,

    FOREIGN KEY (session_id) REFERENCES universal_invoice_sessions(id) ON DELETE CASCADE
);

-- Tabla para parsers disponibles
CREATE TABLE IF NOT EXISTS universal_invoice_parsers (
    id TEXT PRIMARY KEY DEFAULT ('uip_' || lower(hex(randomblob(16)))),
    company_id TEXT NOT NULL,

    -- Parser information
    parser_name TEXT NOT NULL,
    parser_type TEXT NOT NULL CHECK (parser_type IN ('pdf', 'xml', 'image', 'hybrid', 'custom')),
    parser_version TEXT,

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    validation_rules JSONB DEFAULT '{}',    -- ✅ CAMPO FALTANTE: Parser-specific validation

    -- Parser capabilities
    supported_formats JSONB DEFAULT '[]',
    extraction_capabilities JSONB DEFAULT '[]',
    quality_indicators JSONB DEFAULT '{}',

    -- Configuration
    parser_config JSONB DEFAULT '{}',
    default_settings JSONB DEFAULT '{}',
    optimization_settings JSONB DEFAULT '{}',

    -- Performance metrics
    avg_processing_time_ms INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 100.00,
    accuracy_score DECIMAL(5,2) DEFAULT 0.00,
    usage_count INTEGER DEFAULT 0,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    requires_training BOOLEAN DEFAULT FALSE,
    last_training_date TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    UNIQUE(company_id, parser_name, parser_version)
);

-- Tabla para analytics y métricas
CREATE TABLE IF NOT EXISTS universal_invoice_analytics (
    id TEXT PRIMARY KEY DEFAULT ('uia_' || lower(hex(randomblob(16)))),
    company_id TEXT NOT NULL,

    -- Analytics period
    analysis_date DATE NOT NULL,
    analysis_hour INTEGER CHECK (analysis_hour >= 0 AND analysis_hour <= 23),

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    template_match JSONB DEFAULT '{}',      -- ✅ CAMPO FALTANTE: Template matching analytics
    validation_rules JSONB DEFAULT '{}',   -- ✅ CAMPO FALTANTE: Validation analytics

    -- Volume metrics
    total_invoices INTEGER DEFAULT 0,
    successful_extractions INTEGER DEFAULT 0,
    failed_extractions INTEGER DEFAULT 0,
    partial_extractions INTEGER DEFAULT 0,

    -- Quality metrics
    avg_extraction_confidence DECIMAL(5,2) DEFAULT 0.00,
    avg_validation_score DECIMAL(5,2) DEFAULT 0.00,
    avg_overall_quality DECIMAL(5,2) DEFAULT 0.00,

    -- Performance metrics
    avg_processing_time_ms INTEGER DEFAULT 0,
    avg_parser_selection_time_ms INTEGER DEFAULT 0,
    avg_validation_time_ms INTEGER DEFAULT 0,

    -- Format distribution
    format_distribution JSONB DEFAULT '{}',
    parser_usage_distribution JSONB DEFAULT '{}',

    -- Error analysis
    common_errors JSONB DEFAULT '[]',
    error_rate DECIMAL(5,2) DEFAULT 0.00,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    UNIQUE(company_id, analysis_date, analysis_hour)
);

-- Tabla para extraction results
CREATE TABLE IF NOT EXISTS universal_invoice_extractions (
    id TEXT PRIMARY KEY DEFAULT ('uie_' || lower(hex(randomblob(16)))),
    session_id TEXT NOT NULL,

    -- Extraction metadata
    extraction_method TEXT NOT NULL,
    parser_used TEXT NOT NULL,
    template_used TEXT,

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    template_match JSONB DEFAULT '{}',      -- ✅ CAMPO FALTANTE: Template match info
    validation_rules JSONB DEFAULT '{}',   -- ✅ CAMPO FALTANTE: Applied validation rules

    -- Extracted data
    raw_extracted_data JSONB NOT NULL,
    normalized_data JSONB DEFAULT '{}',
    confidence_scores JSONB DEFAULT '{}',

    -- Quality assessment
    extraction_confidence DECIMAL(5,2) DEFAULT 0.00,
    data_completeness DECIMAL(5,2) DEFAULT 0.00,
    structure_compliance DECIMAL(5,2) DEFAULT 0.00,

    -- Field-level extraction
    extracted_fields JSONB DEFAULT '{}',
    missing_fields JSONB DEFAULT '[]',
    uncertain_fields JSONB DEFAULT '[]',

    -- Performance
    extraction_time_ms INTEGER,
    memory_usage_mb DECIMAL(8,2),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (session_id) REFERENCES universal_invoice_sessions(id) ON DELETE CASCADE
);

-- Índices optimizados para performance
CREATE INDEX IF NOT EXISTS idx_universal_invoice_sessions_company ON universal_invoice_sessions(company_id);
CREATE INDEX IF NOT EXISTS idx_universal_invoice_sessions_status ON universal_invoice_sessions(extraction_status);
CREATE INDEX IF NOT EXISTS idx_universal_invoice_sessions_format ON universal_invoice_sessions(detected_format);
CREATE INDEX IF NOT EXISTS idx_universal_invoice_sessions_created ON universal_invoice_sessions(created_at);

CREATE INDEX IF NOT EXISTS idx_universal_invoice_formats_company ON universal_invoice_formats(company_id);
CREATE INDEX IF NOT EXISTS idx_universal_invoice_formats_type ON universal_invoice_formats(format_type);
CREATE INDEX IF NOT EXISTS idx_universal_invoice_formats_active ON universal_invoice_formats(is_active);
CREATE INDEX IF NOT EXISTS idx_universal_invoice_formats_priority ON universal_invoice_formats(priority);

CREATE INDEX IF NOT EXISTS idx_universal_invoice_templates_session ON universal_invoice_templates(session_id);
CREATE INDEX IF NOT EXISTS idx_universal_invoice_templates_format ON universal_invoice_templates(format_id);
CREATE INDEX IF NOT EXISTS idx_universal_invoice_templates_score ON universal_invoice_templates(match_score);
CREATE INDEX IF NOT EXISTS idx_universal_invoice_templates_selected ON universal_invoice_templates(is_selected);

CREATE INDEX IF NOT EXISTS idx_universal_invoice_validations_session ON universal_invoice_validations(session_id);
CREATE INDEX IF NOT EXISTS idx_universal_invoice_validations_status ON universal_invoice_validations(validation_status);
CREATE INDEX IF NOT EXISTS idx_universal_invoice_validations_category ON universal_invoice_validations(rule_category);

CREATE INDEX IF NOT EXISTS idx_universal_invoice_parsers_company ON universal_invoice_parsers(company_id);
CREATE INDEX IF NOT EXISTS idx_universal_invoice_parsers_type ON universal_invoice_parsers(parser_type);
CREATE INDEX IF NOT EXISTS idx_universal_invoice_parsers_active ON universal_invoice_parsers(is_active);

CREATE INDEX IF NOT EXISTS idx_universal_invoice_analytics_company ON universal_invoice_analytics(company_id);
CREATE INDEX IF NOT EXISTS idx_universal_invoice_analytics_date ON universal_invoice_analytics(analysis_date);

CREATE INDEX IF NOT EXISTS idx_universal_invoice_extractions_session ON universal_invoice_extractions(session_id);
CREATE INDEX IF NOT EXISTS idx_universal_invoice_extractions_parser ON universal_invoice_extractions(parser_used);

-- Triggers para mantener updated_at actualizado
CREATE TRIGGER IF NOT EXISTS update_universal_invoice_sessions_updated_at
    AFTER UPDATE ON universal_invoice_sessions
    FOR EACH ROW
    BEGIN
        UPDATE universal_invoice_sessions
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_universal_invoice_formats_updated_at
    AFTER UPDATE ON universal_invoice_formats
    FOR EACH ROW
    BEGIN
        UPDATE universal_invoice_formats
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_universal_invoice_parsers_updated_at
    AFTER UPDATE ON universal_invoice_parsers
    FOR EACH ROW
    BEGIN
        UPDATE universal_invoice_parsers
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END;

-- Trigger para actualizar statistics cuando se completa una sesión
CREATE TRIGGER IF NOT EXISTS update_universal_invoice_analytics_on_completion
    AFTER UPDATE OF extraction_status ON universal_invoice_sessions
    FOR EACH ROW
    WHEN NEW.extraction_status = 'completed' AND OLD.extraction_status != 'completed'
    BEGIN
        INSERT OR REPLACE INTO universal_invoice_analytics (
            company_id,
            analysis_date,
            analysis_hour,
            template_match,
            validation_rules,
            total_invoices,
            successful_extractions,
            avg_extraction_confidence,
            avg_validation_score,
            avg_processing_time_ms,
            format_distribution
        )
        SELECT
            NEW.company_id,
            DATE(NEW.completed_at),
            CAST(strftime('%H', NEW.completed_at) AS INTEGER),
            json_object(
                'total_matches', 1,
                'template_used', COALESCE(
                    (SELECT template_name FROM universal_invoice_templates
                     WHERE session_id = NEW.id AND is_selected = 1 LIMIT 1),
                    'no_template'
                ),
                'match_score', COALESCE(NEW.extraction_confidence, 0.0),
                'last_updated', CURRENT_TIMESTAMP
            ),
            json_object(
                'total_validations', (
                    SELECT COUNT(*) FROM universal_invoice_validations
                    WHERE session_id = NEW.id
                ),
                'passed_validations', (
                    SELECT COUNT(*) FROM universal_invoice_validations
                    WHERE session_id = NEW.id AND validation_status = 'passed'
                ),
                'validation_categories', (
                    SELECT json_group_array(DISTINCT rule_category)
                    FROM universal_invoice_validations
                    WHERE session_id = NEW.id
                ),
                'last_updated', CURRENT_TIMESTAMP
            ),
            COALESCE(uia.total_invoices, 0) + 1,
            COALESCE(uia.successful_extractions, 0) + 1,
            CASE
                WHEN COALESCE(uia.total_invoices, 0) = 0 THEN NEW.extraction_confidence
                ELSE (COALESCE(uia.avg_extraction_confidence, 0) * COALESCE(uia.total_invoices, 0) + NEW.extraction_confidence) / (COALESCE(uia.total_invoices, 0) + 1)
            END,
            CASE
                WHEN COALESCE(uia.total_invoices, 0) = 0 THEN NEW.validation_score
                ELSE (COALESCE(uia.avg_validation_score, 0) * COALESCE(uia.total_invoices, 0) + NEW.validation_score) / (COALESCE(uia.total_invoices, 0) + 1)
            END,
            CASE
                WHEN COALESCE(uia.total_invoices, 0) = 0 THEN NEW.processing_time_ms
                ELSE (COALESCE(uia.avg_processing_time_ms, 0) * COALESCE(uia.total_invoices, 0) + NEW.processing_time_ms) / (COALESCE(uia.total_invoices, 0) + 1)
            END,
            json_object(
                NEW.detected_format,
                COALESCE(json_extract(uia.format_distribution, '$.' || NEW.detected_format), 0) + 1
            )
        FROM (
            SELECT * FROM universal_invoice_analytics
            WHERE company_id = NEW.company_id
              AND analysis_date = DATE(NEW.completed_at)
              AND analysis_hour = CAST(strftime('%H', NEW.completed_at) AS INTEGER)
        ) uia;
    END;

-- Trigger para actualizar parser statistics
CREATE TRIGGER IF NOT EXISTS update_parser_statistics_on_use
    AFTER INSERT ON universal_invoice_extractions
    FOR EACH ROW
    BEGIN
        UPDATE universal_invoice_parsers
        SET usage_count = usage_count + 1,
            last_used = CURRENT_TIMESTAMP
        WHERE parser_name = NEW.parser_used
          AND company_id = (
              SELECT company_id FROM universal_invoice_sessions
              WHERE id = NEW.session_id
          );
    END;

COMMIT;

-- Verificación de la migración
SELECT 'Migration 014: Universal Invoice Engine System completed successfully' as status;
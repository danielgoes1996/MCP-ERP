-- Migration 007: Bulk Invoice Processing System
-- Implementing Point 14 improvements for bulk invoice matching with enhanced tracking

-- =========================================================
-- 1. BULK INVOICE PROCESSING BATCHES TABLE
-- =========================================================

CREATE TABLE bulk_invoice_batches (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(50) UNIQUE NOT NULL,
    company_id VARCHAR(50) NOT NULL,

    -- Request parameters
    total_invoices INTEGER NOT NULL DEFAULT 0,
    auto_link_threshold DECIMAL(3,2) NOT NULL DEFAULT 0.80,
    auto_mark_invoiced BOOLEAN NOT NULL DEFAULT false,

    -- Processing status
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    processing_time_ms INTEGER, -- ✅ MISSING FIELD IMPLEMENTED

    -- Results summary
    processed_count INTEGER DEFAULT 0,
    linked_count INTEGER DEFAULT 0,
    no_matches_count INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    success_rate DECIMAL(5,4), -- 0.0 to 1.0

    -- Performance metrics
    avg_processing_time_per_invoice INTEGER, -- milliseconds
    throughput_invoices_per_second DECIMAL(8,4),
    peak_memory_usage_mb INTEGER,
    cpu_usage_percent DECIMAL(5,2),

    -- Batch metadata ✅ MISSING FIELD IMPLEMENTED
    batch_metadata JSONB DEFAULT '{}',
    request_metadata JSONB DEFAULT '{}',
    system_metrics JSONB DEFAULT '{}',

    -- Error handling
    error_summary TEXT,
    failed_invoices INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Audit fields
    created_by INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT valid_status CHECK (status IN (
        'pending', 'processing', 'completed', 'failed',
        'partially_failed', 'cancelled', 'retrying'
    )),
    CONSTRAINT valid_success_rate CHECK (success_rate IS NULL OR (success_rate >= 0.0 AND success_rate <= 1.0)),
    CONSTRAINT valid_threshold CHECK (auto_link_threshold >= 0.0 AND auto_link_threshold <= 1.0),
    CONSTRAINT processing_times_consistent CHECK (
        (started_at IS NULL AND completed_at IS NULL) OR
        (started_at IS NOT NULL AND completed_at IS NULL) OR
        (started_at IS NOT NULL AND completed_at IS NOT NULL AND completed_at >= started_at)
    )
);

-- =========================================================
-- 2. BULK INVOICE BATCH ITEMS TABLE
-- =========================================================

CREATE TABLE bulk_invoice_batch_items (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(50) NOT NULL REFERENCES bulk_invoice_batches(batch_id) ON DELETE CASCADE,

    -- Invoice identification
    filename VARCHAR(500) NOT NULL,
    uuid VARCHAR(100),
    file_size INTEGER,
    file_hash VARCHAR(64), -- SHA-256 for deduplication

    -- Invoice data
    total_amount DECIMAL(12,2),
    subtotal_amount DECIMAL(12,2),
    iva_amount DECIMAL(12,2),
    currency VARCHAR(3) DEFAULT 'MXN',
    issued_date DATE,
    provider_name VARCHAR(500),
    provider_rfc VARCHAR(20),

    -- Processing results
    item_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    processing_started_at TIMESTAMP WITH TIME ZONE,
    processing_completed_at TIMESTAMP WITH TIME ZONE,
    processing_time_ms INTEGER,

    -- Matching results
    matched_expense_id INTEGER,
    match_confidence DECIMAL(4,3), -- 0.000 to 1.000
    match_method VARCHAR(50), -- 'auto', 'manual', 'rule_based'
    match_reasons TEXT[], -- Array of matching reasons

    -- Candidates found
    candidates_found INTEGER DEFAULT 0,
    candidates_data JSONB DEFAULT '[]',

    -- Error handling
    error_message TEXT,
    error_code VARCHAR(50),
    error_details JSONB,

    -- Processing metrics
    ocr_confidence DECIMAL(4,3),
    extraction_quality DECIMAL(4,3),
    validation_score DECIMAL(4,3),

    -- Audit trail
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT valid_item_status CHECK (item_status IN (
        'pending', 'processing', 'matched', 'no_match',
        'error', 'skipped', 'manual_review_required'
    )),
    CONSTRAINT valid_confidence CHECK (match_confidence IS NULL OR (match_confidence >= 0.0 AND match_confidence <= 1.0)),
    CONSTRAINT valid_currency CHECK (currency IN ('MXN', 'USD', 'EUR')),
    CONSTRAINT processing_times_valid CHECK (
        (processing_started_at IS NULL AND processing_completed_at IS NULL) OR
        (processing_started_at IS NOT NULL AND processing_completed_at IS NULL) OR
        (processing_started_at IS NOT NULL AND processing_completed_at IS NOT NULL AND processing_completed_at >= processing_started_at)
    )
);

-- =========================================================
-- 3. BULK PROCESSING RULES TABLE
-- =========================================================

CREATE TABLE bulk_processing_rules (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50) NOT NULL,

    -- Rule identification
    rule_name VARCHAR(200) NOT NULL,
    rule_code VARCHAR(50) NOT NULL,
    rule_type VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,

    -- Rule conditions
    conditions JSONB NOT NULL DEFAULT '{}',
    priority INTEGER NOT NULL DEFAULT 100, -- Lower = higher priority

    -- Actions to take
    actions JSONB NOT NULL DEFAULT '{}',

    -- Performance settings
    max_batch_size INTEGER DEFAULT 100,
    parallel_processing BOOLEAN DEFAULT true,
    timeout_seconds INTEGER DEFAULT 300,

    -- Rule metadata
    description TEXT,
    created_by INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER DEFAULT 0,

    -- Constraints
    UNIQUE(company_id, rule_code),
    CONSTRAINT valid_rule_type CHECK (rule_type IN (
        'pre_processing', 'matching', 'post_processing',
        'error_handling', 'performance_optimization'
    )),
    CONSTRAINT valid_priority CHECK (priority >= 1 AND priority <= 1000)
);

-- =========================================================
-- 4. BULK PROCESSING PERFORMANCE LOG
-- =========================================================

CREATE TABLE bulk_processing_performance (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(50) NOT NULL REFERENCES bulk_invoice_batches(batch_id) ON DELETE CASCADE,

    -- Timing metrics
    measurement_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    phase VARCHAR(50) NOT NULL, -- 'initialization', 'processing', 'finalization'

    -- Resource usage
    cpu_usage_percent DECIMAL(5,2),
    memory_usage_mb INTEGER,
    disk_io_read_mb DECIMAL(10,2),
    disk_io_write_mb DECIMAL(10,2),
    network_io_kb DECIMAL(10,2),

    -- Processing metrics
    items_processed INTEGER DEFAULT 0,
    items_per_second DECIMAL(8,2),
    current_queue_size INTEGER,
    active_workers INTEGER,

    -- Database metrics
    db_connections_active INTEGER,
    db_query_time_avg_ms DECIMAL(8,2),
    db_queries_per_second DECIMAL(8,2),

    -- Custom metrics
    custom_metrics JSONB DEFAULT '{}',

    CONSTRAINT valid_phase CHECK (phase IN (
        'initialization', 'preprocessing', 'processing',
        'postprocessing', 'finalization', 'error_handling'
    ))
);

-- =========================================================
-- 5. BULK PROCESSING ANALYTICS CACHE
-- =========================================================

CREATE TABLE bulk_processing_analytics (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50) NOT NULL,

    -- Time dimension
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    period_type VARCHAR(20) NOT NULL, -- 'hourly', 'daily', 'weekly', 'monthly'

    -- Volume metrics
    total_batches INTEGER DEFAULT 0,
    total_invoices_processed INTEGER DEFAULT 0,
    successful_batches INTEGER DEFAULT 0,
    failed_batches INTEGER DEFAULT 0,

    -- Performance metrics
    avg_processing_time_ms DECIMAL(10,2),
    median_processing_time_ms DECIMAL(10,2),
    p95_processing_time_ms DECIMAL(10,2),
    throughput_invoices_per_hour DECIMAL(10,2),

    -- Quality metrics
    avg_success_rate DECIMAL(5,4),
    avg_match_confidence DECIMAL(4,3),
    auto_match_rate DECIMAL(5,4),
    manual_review_rate DECIMAL(5,4),

    -- Resource utilization
    avg_cpu_usage DECIMAL(5,2),
    peak_memory_usage_mb INTEGER,
    avg_memory_usage_mb INTEGER,

    -- Error analysis
    error_rate DECIMAL(5,4),
    most_common_errors JSONB DEFAULT '{}',
    retry_success_rate DECIMAL(5,4),

    -- Business impact
    total_amount_processed DECIMAL(15,2),
    avg_invoice_amount DECIMAL(10,2),
    processing_cost_estimate DECIMAL(10,4), -- Cost per invoice

    -- Comparative metrics
    vs_previous_period JSONB DEFAULT '{}',
    trends JSONB DEFAULT '{}',

    -- System metadata
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    calculation_time_ms INTEGER,
    data_quality_score DECIMAL(4,3),

    -- Constraints
    UNIQUE(company_id, period_start, period_end, period_type),
    CONSTRAINT valid_period_type CHECK (period_type IN ('hourly', 'daily', 'weekly', 'monthly')),
    CONSTRAINT valid_period CHECK (period_start < period_end),
    CONSTRAINT valid_rates CHECK (
        (avg_success_rate IS NULL OR (avg_success_rate >= 0.0 AND avg_success_rate <= 1.0)) AND
        (auto_match_rate IS NULL OR (auto_match_rate >= 0.0 AND auto_match_rate <= 1.0)) AND
        (error_rate IS NULL OR (error_rate >= 0.0 AND error_rate <= 1.0))
    )
);

-- =========================================================
-- INDEXES FOR PERFORMANCE
-- =========================================================

-- Primary lookup indexes
CREATE INDEX CONCURRENTLY idx_bulk_invoice_batches_company_status
ON bulk_invoice_batches(company_id, status, created_at DESC);

CREATE INDEX CONCURRENTLY idx_bulk_invoice_batches_processing_time
ON bulk_invoice_batches(started_at, completed_at)
WHERE status IN ('processing', 'completed');

-- Batch items indexes
CREATE INDEX CONCURRENTLY idx_bulk_invoice_batch_items_batch
ON bulk_invoice_batch_items(batch_id, item_status);

CREATE INDEX CONCURRENTLY idx_bulk_invoice_batch_items_uuid
ON bulk_invoice_batch_items(uuid)
WHERE uuid IS NOT NULL;

CREATE INDEX CONCURRENTLY idx_bulk_invoice_batch_items_file_hash
ON bulk_invoice_batch_items(file_hash)
WHERE file_hash IS NOT NULL;

CREATE INDEX CONCURRENTLY idx_bulk_invoice_batch_items_expense
ON bulk_invoice_batch_items(matched_expense_id)
WHERE matched_expense_id IS NOT NULL;

-- Performance monitoring indexes
CREATE INDEX CONCURRENTLY idx_bulk_processing_performance_batch_phase
ON bulk_processing_performance(batch_id, phase, measurement_timestamp DESC);

-- Analytics indexes
CREATE INDEX CONCURRENTLY idx_bulk_processing_analytics_company_period
ON bulk_processing_analytics(company_id, period_start DESC, period_type);

-- Rules indexes
CREATE INDEX CONCURRENTLY idx_bulk_processing_rules_company_active
ON bulk_processing_rules(company_id, is_active, priority);

-- =========================================================
-- FUNCTIONS AND TRIGGERS
-- =========================================================

-- Function to update processing metrics
CREATE OR REPLACE FUNCTION update_batch_processing_metrics()
RETURNS TRIGGER AS $$
DECLARE
    batch_record RECORD;
    items_summary RECORD;
BEGIN
    -- Get current batch status
    SELECT * INTO batch_record FROM bulk_invoice_batches WHERE batch_id = NEW.batch_id;

    -- Calculate summary metrics from items
    SELECT
        COUNT(*) as total_items,
        COUNT(CASE WHEN item_status = 'matched' THEN 1 END) as linked_items,
        COUNT(CASE WHEN item_status = 'no_match' THEN 1 END) as no_match_items,
        COUNT(CASE WHEN item_status = 'error' THEN 1 END) as error_items,
        AVG(processing_time_ms) as avg_processing_time,
        AVG(match_confidence) as avg_confidence
    INTO items_summary
    FROM bulk_invoice_batch_items
    WHERE batch_id = NEW.batch_id;

    -- Update batch summary
    UPDATE bulk_invoice_batches SET
        processed_count = COALESCE(items_summary.total_items, 0),
        linked_count = COALESCE(items_summary.linked_items, 0),
        no_matches_count = COALESCE(items_summary.no_match_items, 0),
        errors_count = COALESCE(items_summary.error_items, 0),
        success_rate = CASE
            WHEN items_summary.total_items > 0 THEN
                CAST(items_summary.linked_items AS DECIMAL) / items_summary.total_items
            ELSE NULL
        END,
        avg_processing_time_per_invoice = COALESCE(items_summary.avg_processing_time, 0),
        updated_at = CURRENT_TIMESTAMP
    WHERE batch_id = NEW.batch_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update batch metrics when items change
CREATE TRIGGER trigger_update_batch_metrics
    AFTER INSERT OR UPDATE ON bulk_invoice_batch_items
    FOR EACH ROW EXECUTE FUNCTION update_batch_processing_metrics();

-- Function to calculate batch completion
CREATE OR REPLACE FUNCTION check_batch_completion()
RETURNS TRIGGER AS $$
DECLARE
    pending_items INTEGER;
    processing_items INTEGER;
BEGIN
    -- Count pending and processing items
    SELECT
        COUNT(CASE WHEN item_status IN ('pending', 'processing') THEN 1 END),
        COUNT(CASE WHEN item_status = 'processing' THEN 1 END)
    INTO pending_items, processing_items
    FROM bulk_invoice_batch_items
    WHERE batch_id = NEW.batch_id;

    -- If no pending items and batch is still processing, mark as completed
    IF pending_items = 0 AND processing_items = 0 THEN
        UPDATE bulk_invoice_batches SET
            status = 'completed',
            completed_at = CURRENT_TIMESTAMP,
            processing_time_ms = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at)) * 1000,
            updated_at = CURRENT_TIMESTAMP
        WHERE batch_id = NEW.batch_id AND status = 'processing';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to check batch completion
CREATE TRIGGER trigger_check_batch_completion
    AFTER UPDATE ON bulk_invoice_batch_items
    FOR EACH ROW EXECUTE FUNCTION check_batch_completion();

-- Function for automatic performance recording
CREATE OR REPLACE FUNCTION record_batch_performance(
    p_batch_id VARCHAR(50),
    p_phase VARCHAR(50),
    p_metrics JSONB DEFAULT '{}'
) RETURNS VOID AS $$
BEGIN
    INSERT INTO bulk_processing_performance (
        batch_id,
        phase,
        cpu_usage_percent,
        memory_usage_mb,
        items_processed,
        custom_metrics
    ) VALUES (
        p_batch_id,
        p_phase,
        (p_metrics->>'cpu_usage_percent')::DECIMAL,
        (p_metrics->>'memory_usage_mb')::INTEGER,
        (p_metrics->>'items_processed')::INTEGER,
        p_metrics
    );
END;
$$ LANGUAGE plpgsql;

-- =========================================================
-- VIEWS FOR COMMON QUERIES
-- =========================================================

-- Active batch processing view
CREATE VIEW v_active_batch_processing AS
SELECT
    b.batch_id,
    b.company_id,
    b.status,
    b.total_invoices,
    b.processed_count,
    b.linked_count,
    b.errors_count,
    b.success_rate,
    b.started_at,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - b.started_at)) / 60 as minutes_running,
    CASE
        WHEN b.processed_count > 0 AND b.total_invoices > 0 THEN
            CAST(b.processed_count AS DECIMAL) / b.total_invoices * 100
        ELSE 0
    END as progress_percent,
    CASE
        WHEN b.avg_processing_time_per_invoice > 0 AND b.processed_count < b.total_invoices THEN
            (b.total_invoices - b.processed_count) * b.avg_processing_time_per_invoice / 1000 / 60
        ELSE NULL
    END as estimated_minutes_remaining
FROM bulk_invoice_batches b
WHERE b.status IN ('processing', 'pending');

-- Batch performance summary view
CREATE VIEW v_batch_performance_summary AS
SELECT
    b.company_id,
    DATE(b.created_at) as processing_date,
    COUNT(*) as total_batches,
    COUNT(CASE WHEN b.status = 'completed' THEN 1 END) as completed_batches,
    COUNT(CASE WHEN b.status = 'failed' THEN 1 END) as failed_batches,
    SUM(b.total_invoices) as total_invoices_processed,
    SUM(b.linked_count) as total_invoices_linked,
    AVG(b.success_rate) as avg_success_rate,
    AVG(b.processing_time_ms) / 1000 as avg_processing_time_seconds,
    AVG(b.throughput_invoices_per_second) as avg_throughput
FROM bulk_invoice_batches b
WHERE b.created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY b.company_id, DATE(b.created_at)
ORDER BY processing_date DESC;

-- Processing errors analysis view
CREATE VIEW v_processing_errors_analysis AS
SELECT
    i.batch_id,
    i.error_code,
    COUNT(*) as error_count,
    ARRAY_AGG(DISTINCT i.error_message) as error_messages,
    AVG(i.total_amount) as avg_failed_invoice_amount,
    MIN(i.created_at) as first_occurrence,
    MAX(i.created_at) as last_occurrence
FROM bulk_invoice_batch_items i
WHERE i.item_status = 'error' AND i.error_code IS NOT NULL
GROUP BY i.batch_id, i.error_code
ORDER BY error_count DESC;

-- Comment: Migration 007 complete - comprehensive bulk invoice processing system
-- This migration addresses Point 14 gaps and provides enterprise-grade
-- bulk invoice matching with performance monitoring, error tracking, and analytics
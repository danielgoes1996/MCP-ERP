-- Migration 006: Non-Reconciliation System Tables
-- Implementing Point 13 improvements for expense non-reconciliation workflow

-- =========================================================
-- 1. EXPENSE NON-RECONCILIATION RECORDS TABLE
-- =========================================================

CREATE TABLE expense_non_reconciliation (
    id SERIAL PRIMARY KEY,
    expense_id INTEGER NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    company_id VARCHAR(50) NOT NULL,

    -- Core non-reconciliation data
    reason_code VARCHAR(50) NOT NULL,
    reason_description TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',

    -- Resolution tracking
    estimated_resolution_date TIMESTAMP WITH TIME ZONE,
    actual_resolution_date TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,

    -- Escalation management
    escalation_level INTEGER NOT NULL DEFAULT 1,
    escalation_rules JSONB DEFAULT '{}',
    next_escalation_date TIMESTAMP WITH TIME ZONE,
    escalated_to_user_id INTEGER,

    -- Context and metadata
    context_data JSONB DEFAULT '{}',
    supporting_documents TEXT[],
    tags VARCHAR(50)[],

    -- Workflow tracking
    workflow_state VARCHAR(30) NOT NULL DEFAULT 'initial',
    workflow_data JSONB DEFAULT '{}',

    -- Audit fields
    created_by INTEGER NOT NULL,
    updated_by INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Performance fields
    resolution_priority INTEGER DEFAULT 3, -- 1=high, 2=medium, 3=low, 4=minimal
    business_impact VARCHAR(20) DEFAULT 'low', -- low, medium, high, critical

    -- Constraints
    CONSTRAINT valid_status CHECK (status IN (
        'pending', 'in_progress', 'escalated', 'resolved',
        'dismissed', 'on_hold', 'requires_approval'
    )),
    CONSTRAINT valid_escalation_level CHECK (escalation_level BETWEEN 1 AND 5),
    CONSTRAINT valid_priority CHECK (resolution_priority BETWEEN 1 AND 4),
    CONSTRAINT valid_business_impact CHECK (business_impact IN ('low', 'medium', 'high', 'critical')),

    -- Unique constraint to prevent duplicates
    UNIQUE(expense_id, reason_code)
);

-- =========================================================
-- 2. NON-RECONCILIATION REASON CODES CATALOG
-- =========================================================

CREATE TABLE non_reconciliation_reason_codes (
    code VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,
    default_escalation_rules JSONB DEFAULT '{}',
    auto_resolution_possible BOOLEAN DEFAULT false,
    typical_resolution_days INTEGER DEFAULT 30,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Categorization
    CONSTRAINT valid_category CHECK (category IN (
        'missing_data', 'format_mismatch', 'amount_discrepancy',
        'date_inconsistency', 'vendor_mismatch', 'duplicate_suspected',
        'system_error', 'manual_review_required', 'external_dependency'
    ))
);

-- =========================================================
-- 3. NON-RECONCILIATION HISTORY AND ACTIONS
-- =========================================================

CREATE TABLE non_reconciliation_history (
    id SERIAL PRIMARY KEY,
    non_reconciliation_id INTEGER NOT NULL REFERENCES expense_non_reconciliation(id) ON DELETE CASCADE,

    -- Action details
    action_type VARCHAR(50) NOT NULL,
    action_description TEXT,
    previous_status VARCHAR(30),
    new_status VARCHAR(30),

    -- User and context
    performed_by INTEGER NOT NULL,
    performed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT,

    -- Data changes
    field_changes JSONB DEFAULT '{}',
    notes TEXT,

    -- System metadata
    system_generated BOOLEAN DEFAULT false,
    correlation_id VARCHAR(50),

    CONSTRAINT valid_action_type CHECK (action_type IN (
        'created', 'updated', 'escalated', 'resolved', 'dismissed',
        'assigned', 'commented', 'document_added', 'status_changed',
        'priority_changed', 'deadline_extended', 'workflow_advanced'
    ))
);

-- =========================================================
-- 4. ESCALATION RULES AND CONFIGURATION
-- =========================================================

CREATE TABLE non_reconciliation_escalation_rules (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50) NOT NULL,

    -- Rule identification
    rule_name VARCHAR(200) NOT NULL,
    rule_code VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT true,

    -- Trigger conditions
    applies_to_reason_codes VARCHAR(50)[], -- NULL means all codes
    applies_to_categories VARCHAR(50)[], -- NULL means all categories
    minimum_amount DECIMAL(10,2),
    maximum_amount DECIMAL(10,2),

    -- Escalation configuration
    escalation_after_days INTEGER NOT NULL DEFAULT 7,
    escalation_levels JSONB NOT NULL DEFAULT '[]',

    -- Notification settings
    notification_settings JSONB DEFAULT '{}',

    -- Rule metadata
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    UNIQUE(company_id, rule_code)
);

-- =========================================================
-- 5. NON-RECONCILIATION NOTIFICATIONS
-- =========================================================

CREATE TABLE non_reconciliation_notifications (
    id SERIAL PRIMARY KEY,
    non_reconciliation_id INTEGER NOT NULL REFERENCES expense_non_reconciliation(id) ON DELETE CASCADE,

    -- Notification details
    notification_type VARCHAR(50) NOT NULL,
    recipient_type VARCHAR(30) NOT NULL, -- user, role, email, webhook
    recipient_identifier VARCHAR(255) NOT NULL,

    -- Message content
    subject VARCHAR(500),
    message_template VARCHAR(100),
    message_data JSONB DEFAULT '{}',

    -- Delivery tracking
    status VARCHAR(20) DEFAULT 'pending',
    scheduled_for TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,

    -- Error handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- System tracking
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_notification_type CHECK (notification_type IN (
        'escalation_warning', 'escalation_occurred', 'resolution_reminder',
        'deadline_approaching', 'status_change', 'assignment_notification',
        'resolution_completed', 'manual_review_required'
    )),
    CONSTRAINT valid_recipient_type CHECK (recipient_type IN ('user', 'role', 'email', 'webhook')),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'sent', 'delivered', 'failed', 'cancelled'))
);

-- =========================================================
-- 6. NON-RECONCILIATION ANALYTICS CACHE
-- =========================================================

CREATE TABLE non_reconciliation_analytics (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50) NOT NULL,

    -- Time dimension
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    period_type VARCHAR(20) NOT NULL, -- daily, weekly, monthly, quarterly

    -- Core metrics
    total_non_reconciled INTEGER DEFAULT 0,
    resolved_count INTEGER DEFAULT 0,
    pending_count INTEGER DEFAULT 0,
    escalated_count INTEGER DEFAULT 0,
    dismissed_count INTEGER DEFAULT 0,

    -- Performance metrics
    avg_resolution_days DECIMAL(5,2),
    median_resolution_days DECIMAL(5,2),
    sla_compliance_rate DECIMAL(5,4), -- 0.0 to 1.0

    -- Category breakdown
    by_reason_code JSONB DEFAULT '{}',
    by_category JSONB DEFAULT '{}',
    by_escalation_level JSONB DEFAULT '{}',
    by_business_impact JSONB DEFAULT '{}',

    -- Financial impact
    total_amount_non_reconciled DECIMAL(12,2),
    avg_amount_per_case DECIMAL(10,2),

    -- System performance
    auto_resolution_rate DECIMAL(5,4),
    manual_intervention_rate DECIMAL(5,4),

    -- Timestamps
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    UNIQUE(company_id, period_start, period_end, period_type),
    CONSTRAINT valid_period_type CHECK (period_type IN ('daily', 'weekly', 'monthly', 'quarterly')),
    CONSTRAINT valid_period CHECK (period_start < period_end)
);

-- =========================================================
-- INDEXES FOR PERFORMANCE
-- =========================================================

-- Primary lookup indexes
CREATE INDEX CONCURRENTLY idx_expense_non_reconciliation_expense
ON expense_non_reconciliation(expense_id);

CREATE INDEX CONCURRENTLY idx_expense_non_reconciliation_company_status
ON expense_non_reconciliation(company_id, status);

CREATE INDEX CONCURRENTLY idx_expense_non_reconciliation_escalation_date
ON expense_non_reconciliation(next_escalation_date)
WHERE next_escalation_date IS NOT NULL AND status IN ('pending', 'in_progress');

CREATE INDEX CONCURRENTLY idx_expense_non_reconciliation_resolution_date
ON expense_non_reconciliation(estimated_resolution_date)
WHERE status IN ('pending', 'in_progress', 'escalated');

-- History and audit indexes
CREATE INDEX CONCURRENTLY idx_non_reconciliation_history_record
ON non_reconciliation_history(non_reconciliation_id, performed_at DESC);

CREATE INDEX CONCURRENTLY idx_non_reconciliation_history_user
ON non_reconciliation_history(performed_by, performed_at DESC);

-- Notification indexes
CREATE INDEX CONCURRENTLY idx_non_reconciliation_notifications_status
ON non_reconciliation_notifications(status, scheduled_for)
WHERE status IN ('pending', 'failed');

-- Analytics indexes
CREATE INDEX CONCURRENTLY idx_non_reconciliation_analytics_company_period
ON non_reconciliation_analytics(company_id, period_start DESC, period_type);

-- Reason codes indexes
CREATE INDEX CONCURRENTLY idx_reason_codes_category_active
ON non_reconciliation_reason_codes(category, is_active);

-- Escalation rules indexes
CREATE INDEX CONCURRENTLY idx_escalation_rules_company_active
ON non_reconciliation_escalation_rules(company_id, is_active);

-- =========================================================
-- INITIAL DATA - STANDARD REASON CODES
-- =========================================================

INSERT INTO non_reconciliation_reason_codes (code, name, description, category, typical_resolution_days, auto_resolution_possible) VALUES
-- Missing data reasons
('MISSING_VENDOR', 'Missing Vendor Information', 'Expense lacks vendor/supplier identification', 'missing_data', 14, false),
('MISSING_RECEIPT', 'Missing Receipt/Invoice', 'Supporting documentation not provided', 'missing_data', 21, false),
('MISSING_CATEGORY', 'Missing Category Assignment', 'Expense category not specified or invalid', 'missing_data', 7, true),
('MISSING_PROJECT', 'Missing Project Code', 'Project or cost center not assigned', 'missing_data', 10, false),

-- Format and data quality
('INVALID_FORMAT', 'Invalid Data Format', 'Data format does not meet system requirements', 'format_mismatch', 5, true),
('ENCODING_ERROR', 'Character Encoding Issues', 'Text encoding problems in expense data', 'format_mismatch', 3, true),
('CURRENCY_MISMATCH', 'Currency Format Mismatch', 'Currency information inconsistent or invalid', 'format_mismatch', 7, false),

-- Amount discrepancies
('AMOUNT_ZERO', 'Zero or Negative Amount', 'Expense amount is zero or negative', 'amount_discrepancy', 5, true),
('AMOUNT_EXCESSIVE', 'Amount Exceeds Limits', 'Expense amount exceeds defined thresholds', 'amount_discrepancy', 14, false),
('AMOUNT_PRECISION', 'Decimal Precision Issues', 'Amount has incorrect decimal precision', 'amount_discrepancy', 3, true),

-- Date inconsistencies
('DATE_FUTURE', 'Future Date Detected', 'Expense date is in the future', 'date_inconsistency', 7, true),
('DATE_TOO_OLD', 'Date Too Far in Past', 'Expense date exceeds retention policy', 'date_inconsistency', 14, false),
('DATE_FORMAT', 'Invalid Date Format', 'Date format not recognized by system', 'date_inconsistency', 3, true),

-- Vendor and external issues
('VENDOR_NOT_FOUND', 'Vendor Not in System', 'Vendor not found in approved vendor list', 'vendor_mismatch', 21, false),
('VENDOR_INACTIVE', 'Inactive Vendor Account', 'Vendor account is deactivated', 'vendor_mismatch', 14, false),

-- Duplicates and conflicts
('DUPLICATE_SUSPECTED', 'Potential Duplicate Entry', 'Expense appears to be duplicate of existing entry', 'duplicate_suspected', 10, false),
('CONFLICT_DETECTED', 'Data Conflict Detected', 'Conflicting information found in related records', 'duplicate_suspected', 14, false),

-- System and technical issues
('SYSTEM_ERROR', 'System Processing Error', 'Technical error occurred during processing', 'system_error', 7, true),
('API_TIMEOUT', 'External API Timeout', 'Timeout occurred while validating with external system', 'system_error', 5, true),
('DATABASE_CONSTRAINT', 'Database Constraint Violation', 'Data violates database integrity constraints', 'system_error', 3, true),

-- Manual review required
('POLICY_VIOLATION', 'Policy Compliance Issue', 'Expense may violate company policies', 'manual_review_required', 21, false),
('HIGH_RISK_VENDOR', 'High Risk Vendor Flag', 'Vendor flagged for additional review', 'manual_review_required', 30, false),
('UNUSUAL_PATTERN', 'Unusual Spending Pattern', 'Expense shows unusual characteristics', 'manual_review_required', 14, false),

-- External dependencies
('BANK_RECONCILIATION', 'Bank Reconciliation Pending', 'Waiting for bank statement reconciliation', 'external_dependency', 30, false),
('APPROVAL_PENDING', 'Approval Workflow Pending', 'Waiting for management approval', 'external_dependency', 21, false),
('DOCUMENT_VERIFICATION', 'Document Verification Pending', 'External document verification in progress', 'external_dependency', 14, false);

-- =========================================================
-- FUNCTIONS AND TRIGGERS
-- =========================================================

-- Function to update timestamps
CREATE OR REPLACE FUNCTION update_non_reconciliation_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for automatic timestamp updates
CREATE TRIGGER trigger_update_expense_non_reconciliation_timestamp
    BEFORE UPDATE ON expense_non_reconciliation
    FOR EACH ROW EXECUTE FUNCTION update_non_reconciliation_timestamp();

CREATE TRIGGER trigger_update_reason_codes_timestamp
    BEFORE UPDATE ON non_reconciliation_reason_codes
    FOR EACH ROW EXECUTE FUNCTION update_non_reconciliation_timestamp();

-- Function to automatically create history entries
CREATE OR REPLACE FUNCTION create_non_reconciliation_history()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO non_reconciliation_history (
            non_reconciliation_id, action_type, action_description,
            new_status, performed_by, system_generated
        ) VALUES (
            NEW.id, 'created', 'Non-reconciliation record created',
            NEW.status, NEW.created_by, true
        );
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.status != NEW.status THEN
            INSERT INTO non_reconciliation_history (
                non_reconciliation_id, action_type, action_description,
                previous_status, new_status, performed_by, system_generated
            ) VALUES (
                NEW.id, 'status_changed', 'Status changed from ' || OLD.status || ' to ' || NEW.status,
                OLD.status, NEW.status, NEW.updated_by, true
            );
        END IF;
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger for automatic history creation
CREATE TRIGGER trigger_create_non_reconciliation_history
    AFTER INSERT OR UPDATE ON expense_non_reconciliation
    FOR EACH ROW EXECUTE FUNCTION create_non_reconciliation_history();

-- Function for escalation date calculation
CREATE OR REPLACE FUNCTION calculate_next_escalation_date(
    p_non_reconciliation_id INTEGER
) RETURNS TIMESTAMP WITH TIME ZONE AS $$
DECLARE
    v_escalation_rules JSONB;
    v_current_level INTEGER;
    v_days_to_add INTEGER := 7;
    v_result TIMESTAMP WITH TIME ZONE;
BEGIN
    SELECT escalation_rules, escalation_level
    INTO v_escalation_rules, v_current_level
    FROM expense_non_reconciliation
    WHERE id = p_non_reconciliation_id;

    -- Extract days from escalation rules if available
    IF v_escalation_rules ? 'escalation_days' THEN
        v_days_to_add := (v_escalation_rules->>'escalation_days')::INTEGER;
    END IF;

    -- Calculate next escalation date
    v_result := CURRENT_TIMESTAMP + (v_days_to_add || ' days')::INTERVAL;

    RETURN v_result;
END;
$$ LANGUAGE plpgsql;

-- =========================================================
-- VIEWS FOR COMMON QUERIES
-- =========================================================

-- Active non-reconciliation cases view
CREATE VIEW v_active_non_reconciliation AS
SELECT
    nr.*,
    e.amount,
    e.description as expense_description,
    e.expense_date,
    rc.name as reason_name,
    rc.category as reason_category,
    EXTRACT(DAYS FROM (CURRENT_TIMESTAMP - nr.created_at)) as days_open,
    CASE
        WHEN nr.estimated_resolution_date < CURRENT_TIMESTAMP THEN true
        ELSE false
    END as is_overdue
FROM expense_non_reconciliation nr
JOIN expenses e ON nr.expense_id = e.id
LEFT JOIN non_reconciliation_reason_codes rc ON nr.reason_code = rc.code
WHERE nr.status IN ('pending', 'in_progress', 'escalated');

-- Non-reconciliation summary by company view
CREATE VIEW v_non_reconciliation_summary AS
SELECT
    company_id,
    COUNT(*) as total_cases,
    COUNT(CASE WHEN status IN ('pending', 'in_progress', 'escalated') THEN 1 END) as active_cases,
    COUNT(CASE WHEN status = 'resolved' THEN 1 END) as resolved_cases,
    COUNT(CASE WHEN estimated_resolution_date < CURRENT_TIMESTAMP AND status IN ('pending', 'in_progress') THEN 1 END) as overdue_cases,
    AVG(EXTRACT(DAYS FROM (COALESCE(actual_resolution_date, CURRENT_TIMESTAMP) - created_at))) as avg_resolution_days,
    MIN(created_at) as first_case_date,
    MAX(created_at) as latest_case_date
FROM expense_non_reconciliation
GROUP BY company_id;

-- Comment: Migration 006 complete - comprehensive non-reconciliation system
-- This migration addresses Point 13 gaps and provides enterprise-grade
-- non-reconciliation workflow with escalation, analytics, and automation capabilities.
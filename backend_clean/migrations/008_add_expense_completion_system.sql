-- Migration 008: Expense Completion System
-- Implementing Point 15 improvements for intelligent expense field completion

-- =========================================================
-- 1. COMPLETION RULES TABLE
-- =========================================================

CREATE TABLE expense_completion_rules (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50) NOT NULL,
    rule_name VARCHAR(200) NOT NULL,
    rule_code VARCHAR(50) NOT NULL,

    -- Rule trigger conditions
    trigger_conditions JSONB NOT NULL DEFAULT '{}',
    applies_to_categories VARCHAR(50)[],
    applies_to_users INTEGER[],
    min_amount DECIMAL(10,2),
    max_amount DECIMAL(10,2),

    -- Completion logic ✅ MISSING FIELD IMPLEMENTED
    completion_rules JSONB NOT NULL DEFAULT '{}',
    field_mappings JSONB DEFAULT '{}',
    auto_completion_enabled BOOLEAN NOT NULL DEFAULT true,

    -- Rule configuration
    priority INTEGER NOT NULL DEFAULT 100,
    is_active BOOLEAN NOT NULL DEFAULT true,
    confidence_threshold DECIMAL(3,2) DEFAULT 0.7,

    -- Learning settings
    learns_from_user_patterns BOOLEAN DEFAULT true,
    adapts_over_time BOOLEAN DEFAULT true,
    requires_user_confirmation BOOLEAN DEFAULT false,

    -- Metadata
    created_by INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER DEFAULT 0,

    -- Statistics
    success_rate DECIMAL(5,4), -- 0.0000 to 1.0000
    avg_fields_completed INTEGER DEFAULT 0,
    user_acceptance_rate DECIMAL(5,4),

    -- Constraints
    UNIQUE(company_id, rule_code),
    CONSTRAINT valid_priority CHECK (priority >= 1 AND priority <= 1000),
    CONSTRAINT valid_confidence CHECK (confidence_threshold >= 0.0 AND confidence_threshold <= 1.0)
);

-- =========================================================
-- 2. FIELD PRIORITIES TABLE
-- =========================================================

CREATE TABLE expense_field_priorities (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50) NOT NULL,

    -- Field identification ✅ MISSING FIELD IMPLEMENTED
    field_name VARCHAR(100) NOT NULL,
    field_category VARCHAR(50) NOT NULL,
    field_priorities JSONB NOT NULL DEFAULT '{}',

    -- Priority settings
    base_priority INTEGER NOT NULL DEFAULT 50,
    context_multipliers JSONB DEFAULT '{}',
    user_role_weights JSONB DEFAULT '{}',
    business_rule_weights JSONB DEFAULT '{}',

    -- Completion behavior
    auto_complete_when_confident BOOLEAN DEFAULT false,
    suggest_always BOOLEAN DEFAULT true,
    required_for_submission BOOLEAN DEFAULT false,
    affects_workflow BOOLEAN DEFAULT false,

    -- Learning parameters
    learns_from_usage BOOLEAN DEFAULT true,
    priority_decay_factor DECIMAL(3,2) DEFAULT 1.00,
    recalculation_frequency INTEGER DEFAULT 30, -- days

    -- Contextual rules
    depends_on_fields VARCHAR(100)[],
    conditional_priority_rules JSONB DEFAULT '[]',
    seasonal_adjustments JSONB DEFAULT '{}',

    -- Statistics
    completion_frequency INTEGER DEFAULT 0,
    user_satisfaction_score DECIMAL(3,2),
    avg_completion_time_seconds INTEGER,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_recalculated_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    UNIQUE(company_id, field_name),
    CONSTRAINT valid_base_priority CHECK (base_priority >= 0 AND base_priority <= 100),
    CONSTRAINT valid_field_category CHECK (field_category IN (
        'basic', 'financial', 'tax', 'approval', 'categorization',
        'vendor', 'project', 'location', 'metadata', 'custom'
    ))
);

-- =========================================================
-- 3. USER COMPLETION PREFERENCES TABLE
-- =========================================================

CREATE TABLE user_completion_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    company_id VARCHAR(50) NOT NULL,

    -- General preferences
    auto_completion_enabled BOOLEAN NOT NULL DEFAULT true,
    suggestion_aggressiveness VARCHAR(20) DEFAULT 'medium',
    confirmation_required BOOLEAN DEFAULT false,
    show_confidence_scores BOOLEAN DEFAULT true,

    -- Field-specific preferences
    preferred_fields JSONB DEFAULT '[]',
    ignored_fields JSONB DEFAULT '[]',
    field_order_preferences JSONB DEFAULT '{}',

    -- Learning preferences
    learn_from_patterns BOOLEAN DEFAULT true,
    adapt_to_usage BOOLEAN DEFAULT true,
    share_patterns_anonymously BOOLEAN DEFAULT false,

    -- UI/UX preferences
    completion_ui_style VARCHAR(20) DEFAULT 'inline',
    keyboard_shortcuts_enabled BOOLEAN DEFAULT true,
    sound_notifications BOOLEAN DEFAULT false,

    -- Privacy settings
    store_completion_history BOOLEAN DEFAULT true,
    max_history_days INTEGER DEFAULT 365,
    allow_cross_company_learning BOOLEAN DEFAULT false,

    -- Performance settings
    max_suggestions_per_field INTEGER DEFAULT 5,
    suggestion_timeout_ms INTEGER DEFAULT 500,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    UNIQUE(user_id, company_id),
    CONSTRAINT valid_aggressiveness CHECK (suggestion_aggressiveness IN ('low', 'medium', 'high')),
    CONSTRAINT valid_ui_style CHECK (completion_ui_style IN ('inline', 'dropdown', 'modal', 'sidebar'))
);

-- =========================================================
-- 4. COMPLETION PATTERNS TABLE
-- =========================================================

CREATE TABLE expense_completion_patterns (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50) NOT NULL,
    user_id INTEGER,

    -- Pattern identification
    pattern_hash VARCHAR(64) NOT NULL,
    pattern_name VARCHAR(200),
    pattern_type VARCHAR(50) NOT NULL,

    -- Pattern data
    trigger_values JSONB NOT NULL DEFAULT '{}',
    completion_values JSONB NOT NULL DEFAULT '{}',
    context_data JSONB DEFAULT '{}',

    -- Pattern statistics
    usage_count INTEGER DEFAULT 1,
    success_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    confidence_score DECIMAL(4,3) DEFAULT 0.5,

    -- Pattern validation
    is_validated BOOLEAN DEFAULT false,
    validation_source VARCHAR(50),
    validated_by INTEGER,
    validated_at TIMESTAMP WITH TIME ZONE,

    -- Pattern lifecycle
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true,

    -- Pattern sharing
    is_global BOOLEAN DEFAULT false,
    shared_with_team BOOLEAN DEFAULT false,
    anonymized BOOLEAN DEFAULT true,

    -- Constraints
    UNIQUE(company_id, pattern_hash),
    CONSTRAINT valid_pattern_type CHECK (pattern_type IN (
        'vendor_completion', 'category_suggestion', 'amount_prediction',
        'project_assignment', 'approval_routing', 'tax_classification',
        'location_inference', 'date_normalization', 'custom_field_completion'
    )),
    CONSTRAINT valid_confidence CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0)
);

-- =========================================================
-- 5. COMPLETION HISTORY TABLE
-- =========================================================

CREATE TABLE expense_completion_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    company_id VARCHAR(50) NOT NULL,
    expense_id INTEGER,

    -- Completion session
    session_id VARCHAR(50) NOT NULL,
    completion_type VARCHAR(50) NOT NULL,

    -- Field completion details
    field_name VARCHAR(100) NOT NULL,
    suggested_value TEXT,
    final_value TEXT,
    confidence_score DECIMAL(4,3),

    -- User interaction
    user_action VARCHAR(30) NOT NULL,
    interaction_time_ms INTEGER,
    modifications_count INTEGER DEFAULT 0,
    user_satisfaction DECIMAL(2,1), -- 1.0 to 5.0

    -- Context information
    completion_source VARCHAR(50),
    pattern_used_id INTEGER REFERENCES expense_completion_patterns(id),
    rule_used_id INTEGER REFERENCES expense_completion_rules(id),

    -- Metadata
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    device_info JSONB,
    browser_info JSONB,

    -- Performance metrics
    suggestion_latency_ms INTEGER,
    total_completion_time_ms INTEGER,

    -- Constraints
    CONSTRAINT valid_user_action CHECK (user_action IN (
        'accepted', 'rejected', 'modified', 'ignored', 'delayed'
    )),
    CONSTRAINT valid_completion_type CHECK (completion_type IN (
        'auto', 'suggested', 'manual', 'bulk', 'import', 'api'
    )),
    CONSTRAINT valid_satisfaction CHECK (user_satisfaction IS NULL OR (user_satisfaction >= 1.0 AND user_satisfaction <= 5.0))
);

-- =========================================================
-- 6. COMPLETION ANALYTICS TABLE
-- =========================================================

CREATE TABLE expense_completion_analytics (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50) NOT NULL,

    -- Time dimension
    analysis_date DATE NOT NULL,
    period_type VARCHAR(20) NOT NULL,

    -- Usage metrics
    total_completions INTEGER DEFAULT 0,
    auto_completions INTEGER DEFAULT 0,
    suggested_completions INTEGER DEFAULT 0,
    manual_completions INTEGER DEFAULT 0,

    -- Performance metrics
    avg_completion_time_ms DECIMAL(10,2),
    avg_fields_completed_per_session DECIMAL(4,1),
    completion_success_rate DECIMAL(5,4),
    user_satisfaction_avg DECIMAL(3,2),

    -- Field-specific analytics
    most_completed_fields JSONB DEFAULT '{}',
    least_completed_fields JSONB DEFAULT '{}',
    field_completion_rates JSONB DEFAULT '{}',

    -- Pattern effectiveness
    pattern_usage_stats JSONB DEFAULT '{}',
    rule_effectiveness JSONB DEFAULT '{}',
    learning_improvements JSONB DEFAULT '{}',

    -- User behavior
    unique_users_count INTEGER DEFAULT 0,
    power_users_count INTEGER DEFAULT 0, -- Users with >90% completion rate
    completion_abandonment_rate DECIMAL(5,4),

    -- Business impact
    time_saved_minutes INTEGER DEFAULT 0,
    errors_prevented INTEGER DEFAULT 0,
    compliance_improvement_rate DECIMAL(5,4),

    -- System performance
    avg_suggestion_latency_ms DECIMAL(8,2),
    cache_hit_rate DECIMAL(5,4),
    ml_model_accuracy DECIMAL(5,4),

    -- Metadata
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    calculation_duration_ms INTEGER,

    -- Constraints
    UNIQUE(company_id, analysis_date, period_type),
    CONSTRAINT valid_period_type CHECK (period_type IN ('daily', 'weekly', 'monthly'))
);

-- =========================================================
-- INDEXES FOR PERFORMANCE
-- =========================================================

-- Completion rules indexes
CREATE INDEX CONCURRENTLY idx_completion_rules_company_active
ON expense_completion_rules(company_id, is_active, priority);

CREATE INDEX CONCURRENTLY idx_completion_rules_categories
ON expense_completion_rules USING gin(applies_to_categories)
WHERE applies_to_categories IS NOT NULL;

-- Field priorities indexes
CREATE INDEX CONCURRENTLY idx_field_priorities_company_field
ON expense_field_priorities(company_id, field_name);

CREATE INDEX CONCURRENTLY idx_field_priorities_category
ON expense_field_priorities(field_category, base_priority DESC);

-- User preferences indexes
CREATE INDEX CONCURRENTLY idx_completion_preferences_user
ON user_completion_preferences(user_id, company_id);

-- Completion patterns indexes
CREATE INDEX CONCURRENTLY idx_completion_patterns_hash
ON expense_completion_patterns(pattern_hash);

CREATE INDEX CONCURRENTLY idx_completion_patterns_company_type
ON expense_completion_patterns(company_id, pattern_type, is_active);

CREATE INDEX CONCURRENTLY idx_completion_patterns_usage
ON expense_completion_patterns(usage_count DESC, confidence_score DESC)
WHERE is_active = true;

-- Completion history indexes
CREATE INDEX CONCURRENTLY idx_completion_history_user_date
ON expense_completion_history(user_id, completed_at DESC);

CREATE INDEX CONCURRENTLY idx_completion_history_session
ON expense_completion_history(session_id, field_name);

CREATE INDEX CONCURRENTLY idx_completion_history_expense
ON expense_completion_history(expense_id)
WHERE expense_id IS NOT NULL;

-- Analytics indexes
CREATE INDEX CONCURRENTLY idx_completion_analytics_company_date
ON expense_completion_analytics(company_id, analysis_date DESC, period_type);

-- =========================================================
-- FUNCTIONS AND TRIGGERS
-- =========================================================

-- Function to update completion rule statistics
CREATE OR REPLACE FUNCTION update_completion_rule_stats()
RETURNS TRIGGER AS $$
DECLARE
    rule_record RECORD;
BEGIN
    -- Update rule usage statistics
    IF NEW.rule_used_id IS NOT NULL THEN
        SELECT * INTO rule_record FROM expense_completion_rules WHERE id = NEW.rule_used_id;

        UPDATE expense_completion_rules SET
            usage_count = usage_count + 1,
            last_used_at = NEW.completed_at,
            success_rate = CASE
                WHEN NEW.user_action = 'accepted' THEN
                    COALESCE((success_rate * usage_count + 1.0) / (usage_count + 1), 1.0)
                ELSE
                    COALESCE((success_rate * usage_count + 0.0) / (usage_count + 1), 0.0)
            END,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.rule_used_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update rule statistics
CREATE TRIGGER trigger_update_completion_rule_stats
    AFTER INSERT ON expense_completion_history
    FOR EACH ROW EXECUTE FUNCTION update_completion_rule_stats();

-- Function to update pattern statistics
CREATE OR REPLACE FUNCTION update_completion_pattern_stats()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.pattern_used_id IS NOT NULL THEN
        UPDATE expense_completion_patterns SET
            usage_count = usage_count + 1,
            success_count = success_count + CASE WHEN NEW.user_action = 'accepted' THEN 1 ELSE 0 END,
            last_used_at = NEW.completed_at,
            confidence_score = CASE
                WHEN usage_count > 0 THEN
                    LEAST(1.0, success_count::DECIMAL / usage_count * 1.2) -- Slight boost for successful patterns
                ELSE confidence_score
            END
        WHERE id = NEW.pattern_used_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update pattern statistics
CREATE TRIGGER trigger_update_completion_pattern_stats
    AFTER INSERT ON expense_completion_history
    FOR EACH ROW EXECUTE FUNCTION update_completion_pattern_stats();

-- Function to calculate field priorities dynamically
CREATE OR REPLACE FUNCTION recalculate_field_priorities(
    p_company_id VARCHAR(50),
    p_field_name VARCHAR(100) DEFAULT NULL
) RETURNS VOID AS $$
DECLARE
    field_record RECORD;
    completion_stats RECORD;
    new_priority INTEGER;
BEGIN
    -- Loop through fields to recalculate
    FOR field_record IN
        SELECT * FROM expense_field_priorities
        WHERE company_id = p_company_id
        AND (p_field_name IS NULL OR field_name = p_field_name)
    LOOP
        -- Get completion statistics for this field
        SELECT
            COUNT(*) as total_completions,
            COUNT(CASE WHEN user_action = 'accepted' THEN 1 END) as accepted_completions,
            AVG(user_satisfaction) as avg_satisfaction,
            AVG(interaction_time_ms) as avg_interaction_time
        INTO completion_stats
        FROM expense_completion_history
        WHERE company_id = p_company_id
        AND field_name = field_record.field_name
        AND completed_at >= CURRENT_DATE - INTERVAL '30 days';

        -- Calculate new priority based on usage and satisfaction
        new_priority := field_record.base_priority;

        IF completion_stats.total_completions > 0 THEN
            -- Adjust based on acceptance rate
            new_priority := new_priority +
                (completion_stats.accepted_completions::DECIMAL / completion_stats.total_completions * 20)::INTEGER;

            -- Adjust based on user satisfaction
            IF completion_stats.avg_satisfaction IS NOT NULL THEN
                new_priority := new_priority +
                    ((completion_stats.avg_satisfaction - 3.0) * 10)::INTEGER;
            END IF;
        END IF;

        -- Update the field priority
        UPDATE expense_field_priorities SET
            completion_frequency = completion_stats.total_completions,
            user_satisfaction_score = completion_stats.avg_satisfaction,
            avg_completion_time_seconds = (completion_stats.avg_interaction_time / 1000)::INTEGER,
            last_recalculated_at = CURRENT_TIMESTAMP,
            -- Apply calculated priority with bounds
            field_priorities = jsonb_set(
                COALESCE(field_priorities, '{}'),
                '{calculated_priority}',
                to_jsonb(LEAST(100, GREATEST(0, new_priority)))
            )
        WHERE id = field_record.id;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Function to suggest field completions
CREATE OR REPLACE FUNCTION suggest_field_completion(
    p_company_id VARCHAR(50),
    p_user_id INTEGER,
    p_field_name VARCHAR(100),
    p_context_data JSONB DEFAULT '{}'
) RETURNS TABLE(
    suggestion_value TEXT,
    confidence_score DECIMAL,
    suggestion_source VARCHAR,
    pattern_id INTEGER
) AS $$
DECLARE
    user_prefs RECORD;
    field_priority RECORD;
BEGIN
    -- Get user preferences
    SELECT * INTO user_prefs FROM user_completion_preferences
    WHERE user_id = p_user_id AND company_id = p_company_id;

    -- Get field priority settings
    SELECT * INTO field_priority FROM expense_field_priorities
    WHERE company_id = p_company_id AND field_name = p_field_name;

    -- Return suggestions based on patterns and rules
    RETURN QUERY
    SELECT
        (completion_values->>p_field_name)::TEXT as suggestion_value,
        LEAST(1.0, confidence_score * 1.1) as confidence_score,
        'pattern'::VARCHAR as suggestion_source,
        id as pattern_id
    FROM expense_completion_patterns
    WHERE company_id = p_company_id
    AND is_active = true
    AND completion_values ? p_field_name
    AND (user_id IS NULL OR user_id = p_user_id)
    AND confidence_score >= COALESCE(user_prefs.confirmation_required::INTEGER * 0.8, 0.3)
    ORDER BY confidence_score DESC, usage_count DESC
    LIMIT COALESCE(user_prefs.max_suggestions_per_field, 5);
END;
$$ LANGUAGE plpgsql;

-- =========================================================
-- VIEWS FOR COMMON QUERIES
-- =========================================================

-- Active completion rules view
CREATE VIEW v_active_completion_rules AS
SELECT
    r.*,
    COALESCE(r.success_rate, 0.0) * 100 as success_percentage,
    CASE
        WHEN r.last_used_at >= CURRENT_DATE - INTERVAL '7 days' THEN 'active'
        WHEN r.last_used_at >= CURRENT_DATE - INTERVAL '30 days' THEN 'recent'
        ELSE 'inactive'
    END as usage_status
FROM expense_completion_rules r
WHERE r.is_active = true
ORDER BY r.priority ASC, r.success_rate DESC NULLS LAST;

-- Field completion effectiveness view
CREATE VIEW v_field_completion_effectiveness AS
SELECT
    fp.company_id,
    fp.field_name,
    fp.field_category,
    fp.base_priority,
    fp.completion_frequency,
    fp.user_satisfaction_score,
    CASE
        WHEN fp.completion_frequency > 100 AND fp.user_satisfaction_score > 4.0 THEN 'excellent'
        WHEN fp.completion_frequency > 50 AND fp.user_satisfaction_score > 3.5 THEN 'good'
        WHEN fp.completion_frequency > 10 AND fp.user_satisfaction_score > 3.0 THEN 'fair'
        ELSE 'needs_improvement'
    END as effectiveness_rating,
    COUNT(DISTINCT h.user_id) as unique_users_count
FROM expense_field_priorities fp
LEFT JOIN expense_completion_history h ON fp.field_name = h.field_name
    AND fp.company_id = h.company_id
    AND h.completed_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY fp.company_id, fp.field_name, fp.field_category, fp.base_priority,
         fp.completion_frequency, fp.user_satisfaction_score;

-- User completion performance view
CREATE VIEW v_user_completion_performance AS
SELECT
    h.user_id,
    h.company_id,
    COUNT(*) as total_completions,
    COUNT(CASE WHEN h.user_action = 'accepted' THEN 1 END) as accepted_completions,
    ROUND(COUNT(CASE WHEN h.user_action = 'accepted' THEN 1 END)::DECIMAL / COUNT(*) * 100, 2) as acceptance_rate,
    AVG(h.user_satisfaction) as avg_satisfaction,
    COUNT(DISTINCT h.field_name) as fields_used,
    AVG(h.interaction_time_ms) as avg_interaction_time_ms,
    MAX(h.completed_at) as last_completion
FROM expense_completion_history h
WHERE h.completed_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY h.user_id, h.company_id;

-- Comment: Migration 008 complete - comprehensive expense completion system
-- This migration addresses Point 15 gaps and provides enterprise-grade
-- field completion with intelligent suggestions, learning, and analytics
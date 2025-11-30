-- Migration: Create fixed_assets and asset_depreciation_history tables
-- Author: System
-- Date: 2025-11-28
-- Description: Tables for fixed assets registry, depreciation tracking, and lifecycle management

-- ============================================================================
-- MAIN TABLE: fixed_assets
-- ============================================================================

CREATE TABLE IF NOT EXISTS fixed_assets (
    -- Primary key
    id SERIAL PRIMARY KEY,

    -- Multi-tenancy
    company_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,

    -- Asset identification
    asset_code VARCHAR(50) UNIQUE NOT NULL,     -- Internal code: "AF-2025-001"
    description TEXT NOT NULL,                  -- "Laptop Dell Precision 5570"
    asset_class VARCHAR(50) NOT NULL,           -- "equipo_computo", "vehiculos", "mobiliario"
    asset_category VARCHAR(20) NOT NULL,        -- SAT family: "156", "154", "155"

    -- Purchase information (link to invoice)
    purchase_expense_id INTEGER REFERENCES manual_expenses(id),
    invoice_uuid VARCHAR(255),
    purchase_date DATE NOT NULL,
    supplier_name VARCHAR(255),
    supplier_rfc VARCHAR(20),

    -- Financial values
    purchase_value DECIMAL(15,2) NOT NULL,      -- Original purchase price (subtotal, no IVA)
    additional_costs JSONB DEFAULT '[]',        -- [{"concept": "flete", "amount": 500, "expense_id": 123}]
    total_cost DECIMAL(15,2) NOT NULL,          -- purchase_value + sum(additional_costs)
    residual_value DECIMAL(15,2) DEFAULT 0,     -- Salvage value at end of useful life

    -- Depreciation ACCOUNTING (NIF - for financial statements)
    depreciation_method_accounting VARCHAR(30) DEFAULT 'straight_line',  -- "straight_line", "declining_balance"
    depreciation_rate_accounting DECIMAL(5,2) NOT NULL,     -- Annual % (e.g., 20.00)
    depreciation_years_accounting DECIMAL(5,2) NOT NULL,    -- Useful life (e.g., 5.00)
    depreciation_months_accounting INTEGER NOT NULL,        -- Total months (e.g., 60)
    accumulated_depreciation_accounting DECIMAL(15,2) DEFAULT 0,
    months_depreciated_accounting INTEGER DEFAULT 0,        -- Track progress

    -- Depreciation FISCAL (LISR - for tax returns)
    depreciation_rate_fiscal DECIMAL(5,2) NOT NULL,         -- Annual % (e.g., 30.00)
    depreciation_years_fiscal DECIMAL(5,2) NOT NULL,        -- Useful life (e.g., 3.33)
    depreciation_months_fiscal INTEGER NOT NULL,            -- Total months (e.g., 40)
    accumulated_depreciation_fiscal DECIMAL(15,2) DEFAULT 0,
    months_depreciated_fiscal INTEGER DEFAULT 0,

    -- Legal basis (from RAG service)
    legal_basis JSONB,                          -- {"law": "LISR", "article": "34", "section": "Fracción V", ...}

    -- Operational tracking
    department VARCHAR(100),                    -- "IT", "Administración", "Ventas"
    location VARCHAR(255),                      -- "Oficina CDMX - Piso 3", "Almacén Monterrey"
    responsible_user_id INTEGER,               -- User who has custody
    physical_tag VARCHAR(50),                   -- Physical label: "TAG-12345"

    -- Asset status
    status VARCHAR(20) DEFAULT 'active',        -- "active", "disposed", "lost", "in_repair", "retired"
    disposal_date DATE,
    disposal_value DECIMAL(15,2),               -- Sale price if disposed
    disposal_method VARCHAR(50),                -- "sale", "donation", "scrap", "loss"
    disposal_reason TEXT,

    -- Metadata
    notes TEXT,
    attachments JSONB DEFAULT '[]',             -- [{"type": "photo", "url": "...", "name": "..."}]

    -- Audit
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Foreign keys
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (purchase_expense_id) REFERENCES manual_expenses(id) ON DELETE SET NULL,
    FOREIGN KEY (responsible_user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

-- Indices for performance
CREATE INDEX idx_fixed_assets_company ON fixed_assets(company_id);
CREATE INDEX idx_fixed_assets_tenant ON fixed_assets(tenant_id);
CREATE INDEX idx_fixed_assets_class ON fixed_assets(asset_class);
CREATE INDEX idx_fixed_assets_category ON fixed_assets(asset_category);
CREATE INDEX idx_fixed_assets_status ON fixed_assets(status);
CREATE INDEX idx_fixed_assets_department ON fixed_assets(department);
CREATE INDEX idx_fixed_assets_purchase_date ON fixed_assets(purchase_date DESC);
CREATE INDEX idx_fixed_assets_invoice_uuid ON fixed_assets(invoice_uuid);

-- Full-text search on description
CREATE INDEX idx_fixed_assets_description_search ON fixed_assets USING GIN(to_tsvector('spanish', description));

-- Comments
COMMENT ON TABLE fixed_assets IS 'Registry of fixed assets with depreciation tracking and lifecycle management';
COMMENT ON COLUMN fixed_assets.asset_code IS 'Unique internal code like AF-2025-001 (auto-generated)';
COMMENT ON COLUMN fixed_assets.asset_class IS 'Internal classification: equipo_computo, vehiculos, mobiliario, maquinaria, etc.';
COMMENT ON COLUMN fixed_assets.asset_category IS 'SAT account family: 156, 154, 155, 153, etc.';
COMMENT ON COLUMN fixed_assets.additional_costs IS 'JSONB array of related costs like freight, installation, setup';
COMMENT ON COLUMN fixed_assets.accumulated_depreciation_accounting IS 'Total depreciation for accounting (NIF) - updates monthly';
COMMENT ON COLUMN fixed_assets.accumulated_depreciation_fiscal IS 'Total depreciation for tax (LISR) - updates monthly';
COMMENT ON COLUMN fixed_assets.legal_basis IS 'JSONB with LISR article reference from depreciation_rate_service';

-- ============================================================================
-- HISTORY TABLE: asset_depreciation_history
-- ============================================================================

CREATE TABLE IF NOT EXISTS asset_depreciation_history (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES fixed_assets(id) ON DELETE CASCADE,

    -- Period
    period_year INTEGER NOT NULL,
    period_month INTEGER NOT NULL,              -- 1-12

    -- Depreciation amounts for this month
    depreciation_amount_accounting DECIMAL(15,2) NOT NULL,
    depreciation_amount_fiscal DECIMAL(15,2) NOT NULL,

    -- Accumulated totals at end of month
    accumulated_accounting DECIMAL(15,2) NOT NULL,
    accumulated_fiscal DECIMAL(15,2) NOT NULL,

    -- Book values at end of month
    book_value_accounting DECIMAL(15,2) NOT NULL,    -- total_cost - accumulated_accounting
    book_value_fiscal DECIMAL(15,2) NOT NULL,        -- total_cost - accumulated_fiscal

    -- Accounting entry reference
    poliza_id VARCHAR(100),                     -- Reference to generated poliza
    poliza_data JSONB,                          -- Full poliza details

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),

    -- Ensure one record per asset per month
    UNIQUE(asset_id, period_year, period_month)
);

-- Indices
CREATE INDEX idx_asset_depreciation_asset ON asset_depreciation_history(asset_id);
CREATE INDEX idx_asset_depreciation_period ON asset_depreciation_history(period_year, period_month);

-- Comments
COMMENT ON TABLE asset_depreciation_history IS 'Monthly depreciation history for each asset (both accounting and fiscal)';
COMMENT ON COLUMN asset_depreciation_history.depreciation_amount_accounting IS 'Depreciation expense for this month (accounting/NIF)';
COMMENT ON COLUMN asset_depreciation_history.depreciation_amount_fiscal IS 'Depreciation expense for this month (fiscal/LISR)';
COMMENT ON COLUMN asset_depreciation_history.book_value_accounting IS 'Remaining value for financial statements';
COMMENT ON COLUMN asset_depreciation_history.book_value_fiscal IS 'Remaining value for tax purposes';

-- ============================================================================
-- TRIGGER: Auto-update updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_fixed_assets_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER fixed_assets_updated_at
    BEFORE UPDATE ON fixed_assets
    FOR EACH ROW
    EXECUTE FUNCTION update_fixed_assets_updated_at();

-- ============================================================================
-- FUNCTION: Generate next asset code
-- ============================================================================

CREATE OR REPLACE FUNCTION generate_next_asset_code(
    p_company_id INTEGER,
    p_year INTEGER DEFAULT EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER
)
RETURNS VARCHAR(50) AS $$
DECLARE
    v_next_number INTEGER;
    v_code VARCHAR(50);
BEGIN
    -- Get next sequential number for this company and year
    SELECT COALESCE(MAX(
        CAST(
            SUBSTRING(asset_code FROM 'AF-\d{4}-(\d+)')
            AS INTEGER
        )
    ), 0) + 1
    INTO v_next_number
    FROM fixed_assets
    WHERE company_id = p_company_id
      AND asset_code LIKE 'AF-' || p_year || '-%';

    -- Format as AF-YYYY-NNN
    v_code := 'AF-' || p_year || '-' || LPAD(v_next_number::TEXT, 3, '0');

    RETURN v_code;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION generate_next_asset_code IS 'Generates next asset code like AF-2025-001, AF-2025-002, etc.';

-- ============================================================================
-- VIEW: Assets with current book values
-- ============================================================================

CREATE OR REPLACE VIEW fixed_assets_current_values AS
SELECT
    fa.id,
    fa.company_id,
    fa.tenant_id,
    fa.asset_code,
    fa.description,
    fa.asset_class,
    fa.asset_category,
    fa.purchase_date,
    fa.status,
    fa.department,
    fa.location,

    -- Financial
    fa.total_cost,
    fa.accumulated_depreciation_accounting,
    fa.accumulated_depreciation_fiscal,

    -- Current book values
    (fa.total_cost - fa.accumulated_depreciation_accounting) AS book_value_accounting,
    (fa.total_cost - fa.accumulated_depreciation_fiscal) AS book_value_fiscal,

    -- Progress
    fa.months_depreciated_accounting,
    fa.depreciation_months_accounting,
    ROUND(
        (fa.months_depreciated_accounting::DECIMAL / NULLIF(fa.depreciation_months_accounting, 0)) * 100,
        2
    ) AS depreciation_progress_accounting_pct,

    fa.months_depreciated_fiscal,
    fa.depreciation_months_fiscal,
    ROUND(
        (fa.months_depreciated_fiscal::DECIMAL / NULLIF(fa.depreciation_months_fiscal, 0)) * 100,
        2
    ) AS depreciation_progress_fiscal_pct,

    -- Flags
    (fa.months_depreciated_accounting >= fa.depreciation_months_accounting) AS fully_depreciated_accounting,
    (fa.months_depreciated_fiscal >= fa.depreciation_months_fiscal) AS fully_depreciated_fiscal,

    -- Dates
    fa.created_at,
    fa.updated_at

FROM fixed_assets fa;

COMMENT ON VIEW fixed_assets_current_values IS 'Assets with calculated current book values and depreciation progress';

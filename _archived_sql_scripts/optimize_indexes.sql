-- OPTIMIZACIÓN DE ÍNDICES - DB UNIFICADA
-- Mejora la performance de queries frecuentes

-- Índices para expense_records (tabla más usada)
CREATE INDEX IF NOT EXISTS idx_expense_tenant_status ON expense_records(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_expense_user_date ON expense_records(user_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_expense_category ON expense_records(category);
CREATE INDEX IF NOT EXISTS idx_expense_amount ON expense_records(amount DESC);
CREATE INDEX IF NOT EXISTS idx_expense_created ON expense_records(created_at DESC);

-- Índices para bank_movements
CREATE INDEX IF NOT EXISTS idx_bank_tenant_date ON bank_movements(tenant_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_bank_matched ON bank_movements(matched_expense_id);
CREATE INDEX IF NOT EXISTS idx_bank_amount ON bank_movements(amount);

-- Índices para automation_jobs (segunda tabla más usada)
CREATE INDEX IF NOT EXISTS idx_automation_tenant_status ON automation_jobs(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_automation_type ON automation_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_automation_created ON automation_jobs(created_at DESC);

-- Índices para automation_logs
CREATE INDEX IF NOT EXISTS idx_logs_job_timestamp ON automation_logs(job_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_logs_level ON automation_logs(level);

-- Índices para tickets
CREATE INDEX IF NOT EXISTS idx_tickets_tenant_status ON tickets(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);
CREATE INDEX IF NOT EXISTS idx_tickets_created ON tickets(created_at DESC);

-- Índices para expense_invoices
CREATE INDEX IF NOT EXISTS idx_invoices_expense ON expense_invoices(expense_id);
CREATE INDEX IF NOT EXISTS idx_invoices_tenant ON expense_invoices(tenant_id);

-- Índices para users
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);

-- Índices para gpt_usage_events
CREATE INDEX IF NOT EXISTS idx_gpt_tenant_timestamp ON gpt_usage_events(tenant_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_gpt_field_name ON gpt_usage_events(field_name);
CREATE INDEX IF NOT EXISTS idx_gpt_success ON gpt_usage_events(success);

-- Índices compuestos para queries complejas
CREATE INDEX IF NOT EXISTS idx_expense_tenant_user_date ON expense_records(tenant_id, user_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_bank_tenant_amount_date ON bank_movements(tenant_id, amount DESC, date DESC);

-- Actualizar estadísticas para el optimizador
ANALYZE;
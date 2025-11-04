#!/usr/bin/env python3
"""
Apply migration 009 - Simple SQL execution
"""

import sqlite3
from pathlib import Path
from datetime import datetime

def main():
    db_path = "data/mcp_internal.db"

    print("🚀 Applying Migration 009 - Simple Mode")
    print("=" * 45)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")  # Disable FK checks during migration

    try:
        # Check if already applied
        existing = conn.execute("""
            SELECT name FROM schema_versions
            WHERE name = '009_automation_engine'
        """).fetchone()

        if existing:
            print("⚠️ Migration already applied")
            return 0

        # Create tables one by one
        print("📋 Creating automation_jobs table...")
        conn.execute("""
            CREATE TABLE automation_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                ocr_confidence REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK (priority BETWEEN 1 AND 10),
                CHECK (retry_count >= 0),
                CHECK (max_retries >= 0),
                CHECK (progress_percentage BETWEEN 0 AND 100),
                CHECK (estado IN ('pendiente', 'en_progreso', 'completado', 'fallido', 'cancelado', 'pausado')),
                CHECK (automation_type IN ('selenium', 'api', 'manual', 'hybrid'))
            )
        """)

        print("📋 Creating automation_logs table...")
        conn.execute("""
            CREATE TABLE automation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                level TEXT NOT NULL,
                category TEXT NOT NULL,
                message TEXT NOT NULL,
                url TEXT,
                element_selector TEXT,
                screenshot_id INTEGER,
                execution_time_ms INTEGER,
                data TEXT,
                user_agent TEXT,
                ip_address TEXT,
                timestamp TEXT NOT NULL,
                company_id TEXT NOT NULL DEFAULT 'default',
                CHECK (level IN ('debug', 'info', 'warning', 'error', 'critical')),
                CHECK (category IN ('navigation', 'ocr', 'captcha', 'form_fill', 'download', 'validation')),
                CHECK (execution_time_ms >= 0),
                FOREIGN KEY (job_id) REFERENCES automation_jobs(id) ON DELETE CASCADE
            )
        """)

        print("📋 Creating automation_screenshots table...")
        conn.execute("""
            CREATE TABLE automation_screenshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                step_name TEXT NOT NULL,
                screenshot_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                url TEXT,
                window_title TEXT,
                viewport_size TEXT,
                page_load_time_ms INTEGER,
                has_captcha BOOLEAN DEFAULT FALSE,
                captcha_type TEXT,
                detected_elements TEXT,
                ocr_text TEXT,
                manual_annotations TEXT,
                is_sensitive BOOLEAN DEFAULT FALSE,
                created_at TEXT NOT NULL,
                company_id TEXT NOT NULL DEFAULT 'default',
                CHECK (screenshot_type IN ('step', 'error', 'success', 'captcha', 'manual')),
                CHECK (file_size >= 0),
                CHECK (page_load_time_ms >= 0),
                FOREIGN KEY (job_id) REFERENCES automation_jobs(id) ON DELETE CASCADE
            )
        """)

        print("📋 Creating automation_config table...")
        conn.execute("""
            CREATE TABLE automation_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                value_type TEXT NOT NULL DEFAULT 'string',
                scope TEXT NOT NULL DEFAULT 'global',
                scope_id TEXT,
                description TEXT,
                category TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                is_readonly BOOLEAN DEFAULT FALSE,
                previous_value TEXT,
                updated_at TEXT NOT NULL,
                updated_by TEXT,
                change_reason TEXT,
                CHECK (value_type IN ('string', 'boolean', 'integer', 'json')),
                CHECK (scope IN ('global', 'company', 'merchant', 'user')),
                UNIQUE(key, scope, scope_id)
            )
        """)

        print("📋 Creating indexes...")
        indexes = [
            "CREATE INDEX idx_automation_jobs_estado ON automation_jobs(estado)",
            "CREATE INDEX idx_automation_jobs_company ON automation_jobs(company_id)",
            "CREATE INDEX idx_automation_jobs_session ON automation_jobs(session_id)",
            "CREATE INDEX idx_automation_jobs_ticket ON automation_jobs(ticket_id)",
            "CREATE INDEX idx_automation_logs_job ON automation_logs(job_id)",
            "CREATE INDEX idx_automation_logs_session ON automation_logs(session_id)",
            "CREATE INDEX idx_automation_screenshots_job ON automation_screenshots(job_id)",
            "CREATE INDEX idx_automation_config_key ON automation_config(key)"
        ]

        for index_sql in indexes:
            conn.execute(index_sql)

        print("📋 Inserting seed configuration...")
        configs = [
            ('automation_engine_enabled', 'false', 'boolean', 'global', 'Master switch for automation engine v2', 'automation'),
            ('selenium_grid_url', 'http://localhost:4444/wd/hub', 'string', 'global', 'Selenium Grid hub URL', 'selenium'),
            ('max_concurrent_jobs', '5', 'integer', 'global', 'Maximum concurrent automation jobs', 'automation'),
            ('screenshot_retention_days', '30', 'integer', 'global', 'Days to retain screenshots', 'storage'),
            ('captcha_service_enabled', 'true', 'boolean', 'global', 'Enable 2Captcha integration', 'captcha')
        ]

        now = datetime.now().isoformat()
        for key, value, value_type, scope, description, category in configs:
            conn.execute("""
                INSERT INTO automation_config (
                    key, value, value_type, scope, description, category,
                    is_active, is_readonly, updated_at, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?, 'migration_009')
            """, (key, value, value_type, scope, description, category, now))

        print("📋 Recording migration...")
        conn.execute("""
            INSERT INTO schema_versions (name, applied_at)
            VALUES ('009_automation_engine', ?)
        """, (now,))

        conn.commit()

        print("✅ Migration 009 applied successfully!")

        # Validation
        tables = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name LIKE 'automation_%'
        """).fetchall()

        print(f"📊 Created {len(tables)} automation tables")
        for table in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
            print(f"   • {table[0]}: {count} records")

        conn.close()
        return 0

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        conn.close()
        return 1

if __name__ == "__main__":
    exit(main())
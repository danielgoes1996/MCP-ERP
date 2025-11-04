#!/usr/bin/env python3
"""
Database Migration Script - MCP System
Migra datos de múltiples DBs SQLite fragmentadas a una DB unificada
"""

import sqlite3
import os
from pathlib import Path
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseMigrator:
    def __init__(self, base_path="/Users/danielgoes96/Desktop/mcp-server"):
        self.base_path = Path(base_path)
        self.unified_db = self.base_path / "unified_mcp_system.db"

        # Mapeo de bases de datos origen
        self.source_dbs = {
            'main': self.base_path / "data" / "mcp_internal.db",
            'tenants': self.base_path / "multi_tenant_platform.db",
            'automation': self.base_path / "expenses.db",
            'analytics': self.base_path / "gpt_usage_analytics.db"
        }

    def verify_source_dbs(self):
        """Verifica que todas las DBs origen existan"""
        logger.info("🔍 Verificando bases de datos origen...")
        for name, path in self.source_dbs.items():
            if path.exists():
                logger.info(f"✅ {name}: {path} (encontrada)")
            else:
                logger.warning(f"⚠️  {name}: {path} (NO encontrada)")

        if not self.unified_db.exists():
            logger.error(f"❌ DB destino no existe: {self.unified_db}")
            return False

        logger.info(f"✅ DB destino: {self.unified_db}")
        return True

    def migrate_tenants_and_users(self):
        """Migra tenants y usuarios desde multi_tenant_platform.db"""
        logger.info("📋 Migrando tenants y usuarios...")

        source_path = self.source_dbs['tenants']
        if not source_path.exists():
            logger.warning("⚠️ multi_tenant_platform.db no encontrada")
            return

        with sqlite3.connect(source_path) as source, sqlite3.connect(self.unified_db) as target:
            # Migrar tenants (adaptando campos)
            tenants = source.execute("SELECT id, name, company_name FROM tenants").fetchall()
            for tenant in tenants:
                target.execute("""
                    INSERT INTO tenants (name, api_key, config)
                    VALUES (?, ?, ?)
                """, (tenant[1], None, f'{{"company_name": "{tenant[2]}"}}'))
                logger.info(f"✅ Tenant migrado: {tenant[1]}")

            # Migrar users desde multi_tenant
            try:
                users = source.execute("SELECT * FROM users").fetchall()
                for user in users:
                    target.execute("""
                        INSERT INTO users (name, email, tenant_id)
                        VALUES (?, ?, 1)
                    """, (user[1], user[2]))
                    logger.info(f"✅ Usuario migrado: {user[2]}")
            except Exception as e:
                logger.warning(f"⚠️ Error migrando usuarios: {e}")

            target.commit()

    def migrate_main_data(self):
        """Migra datos principales desde mcp_internal.db"""
        logger.info("📊 Migrando datos principales...")

        source_path = self.source_dbs['main']
        if not source_path.exists():
            logger.warning("⚠️ mcp_internal.db no encontrada")
            return

        with sqlite3.connect(source_path) as source, sqlite3.connect(self.unified_db) as target:
            # Migrar usuarios adicionales
            try:
                users = source.execute("SELECT * FROM users").fetchall()
                for user in users:
                    target.execute("""
                        INSERT OR IGNORE INTO users (name, email, tenant_id)
                        VALUES (?, ?, 1)
                    """, (user[1] if len(user) > 1 else 'Unknown',
                          user[2] if len(user) > 2 else f'user{user[0]}@mcp.local', 1))
                logger.info(f"✅ {len(users)} usuarios adicionales migrados")
            except Exception as e:
                logger.warning(f"⚠️ Error migrando usuarios adicionales: {e}")

            # Migrar expense_records
            try:
                expenses = source.execute("SELECT * FROM expense_records").fetchall()
                for expense in expenses:
                    target.execute("""
                        INSERT INTO expense_records
                        (amount, description, category, date, user_id, tenant_id, status)
                        VALUES (?, ?, ?, ?, ?, 1, 'migrated')
                    """, (expense[1], expense[2] if len(expense) > 2 else 'Migrated expense',
                          expense[3] if len(expense) > 3 else 'General',
                          expense[4] if len(expense) > 4 else datetime.now().isoformat(),
                          1))
                logger.info(f"✅ {len(expenses)} gastos migrados")
            except Exception as e:
                logger.warning(f"⚠️ Error migrando gastos: {e}")

            # Migrar bank_movements
            try:
                movements = source.execute("SELECT * FROM bank_movements").fetchall()
                for movement in movements:
                    target.execute("""
                        INSERT INTO bank_movements
                        (amount, description, date, account, tenant_id)
                        VALUES (?, ?, ?, ?, 1)
                    """, (movement[1], movement[2] if len(movement) > 2 else 'Bank movement',
                          movement[3] if len(movement) > 3 else datetime.now().isoformat(),
                          movement[4] if len(movement) > 4 else 'Unknown'))
                logger.info(f"✅ {len(movements)} movimientos bancarios migrados")
            except Exception as e:
                logger.warning(f"⚠️ Error migrando movimientos bancarios: {e}")

            # Migrar tickets
            try:
                tickets = source.execute("SELECT * FROM tickets").fetchall()
                for ticket in tickets:
                    target.execute("""
                        INSERT INTO tickets
                        (title, description, status, tenant_id, user_id)
                        VALUES (?, ?, ?, 1, 1)
                    """, (ticket[1] if len(ticket) > 1 else f'Ticket #{ticket[0]}',
                          ticket[2] if len(ticket) > 2 else 'Migrated ticket',
                          ticket[3] if len(ticket) > 3 else 'open'))
                logger.info(f"✅ {len(tickets)} tickets migrados")
            except Exception as e:
                logger.warning(f"⚠️ Error migrando tickets: {e}")

            target.commit()

    def migrate_automation_data(self):
        """Migra datos de automatización desde expenses.db"""
        logger.info("🤖 Migrando datos de automatización...")

        source_path = self.source_dbs['automation']
        if not source_path.exists():
            logger.warning("⚠️ expenses.db no encontrada")
            return

        with sqlite3.connect(source_path) as source, sqlite3.connect(self.unified_db) as target:
            # Migrar automation_jobs
            try:
                jobs = source.execute("SELECT * FROM automation_jobs").fetchall()
                for job in jobs:
                    target.execute("""
                        INSERT INTO automation_jobs
                        (job_type, status, config, tenant_id)
                        VALUES (?, ?, ?, 1)
                    """, (job[1] if len(job) > 1 else 'unknown',
                          job[2] if len(job) > 2 else 'completed',
                          job[3] if len(job) > 3 else '{}'))
                logger.info(f"✅ {len(jobs)} jobs de automatización migrados")
            except Exception as e:
                logger.warning(f"⚠️ Error migrando jobs: {e}")

            # Migrar automation_logs
            try:
                logs = source.execute("SELECT * FROM automation_logs").fetchall()
                for log in logs:
                    target.execute("""
                        INSERT INTO automation_logs
                        (job_id, level, message)
                        VALUES (?, ?, ?)
                    """, (log[1] if len(log) > 1 else 1,
                          log[2] if len(log) > 2 else 'info',
                          log[3] if len(log) > 3 else 'Migrated log'))
                logger.info(f"✅ {len(logs)} logs de automatización migrados")
            except Exception as e:
                logger.warning(f"⚠️ Error migrando logs: {e}")

            target.commit()

    def migrate_analytics_data(self):
        """Migra datos de analytics desde gpt_usage_analytics.db"""
        logger.info("📈 Migrando datos de analytics...")

        source_path = self.source_dbs['analytics']
        if not source_path.exists():
            logger.warning("⚠️ gpt_usage_analytics.db no encontrada")
            return

        with sqlite3.connect(source_path) as source, sqlite3.connect(self.unified_db) as target:
            try:
                events = source.execute("SELECT * FROM gpt_usage_events").fetchall()
                for event in events:
                    target.execute("""
                        INSERT INTO gpt_usage_events
                        (timestamp, field_name, reason, tokens_estimated, cost_estimated_usd,
                         confidence_before, confidence_after, success, merchant_type,
                         ticket_id, error_message, tenant_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """, event[1:] + (1,))  # Agregar tenant_id = 1
                logger.info(f"✅ {len(events)} eventos de analytics migrados")
            except Exception as e:
                logger.warning(f"⚠️ Error migrando analytics: {e}")

            target.commit()

    def generate_migration_report(self):
        """Genera reporte de migración"""
        logger.info("📊 Generando reporte de migración...")

        with sqlite3.connect(self.unified_db) as db:
            report = []

            tables = [
                ('tenants', 'Tenants'),
                ('users', 'Usuarios'),
                ('expense_records', 'Gastos'),
                ('bank_movements', 'Movimientos Bancarios'),
                ('tickets', 'Tickets'),
                ('automation_jobs', 'Jobs de Automatización'),
                ('automation_logs', 'Logs de Automatización'),
                ('gpt_usage_events', 'Eventos de Analytics')
            ]

            for table, name in tables:
                try:
                    count = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    report.append(f"✅ {name}: {count} registros")
                except Exception as e:
                    report.append(f"❌ {name}: Error - {e}")

            return "\n".join(report)

    def run_full_migration(self):
        """Ejecuta migración completa"""
        logger.info("🚀 INICIANDO MIGRACIÓN COMPLETA")

        if not self.verify_source_dbs():
            logger.error("❌ Verificación de DBs falló")
            return False

        try:
            self.migrate_tenants_and_users()
            self.migrate_main_data()
            self.migrate_automation_data()
            self.migrate_analytics_data()

            report = self.generate_migration_report()
            logger.info("📊 REPORTE FINAL:")
            logger.info("\n" + report)

            logger.info("🎉 MIGRACIÓN COMPLETADA EXITOSAMENTE")
            return True

        except Exception as e:
            logger.error(f"❌ Error en migración: {e}")
            return False

if __name__ == "__main__":
    migrator = DatabaseMigrator()
    success = migrator.run_full_migration()

    if success:
        print("🎉 Migración completada. Revisa unified_mcp_system.db")
    else:
        print("❌ Migración falló. Revisa los logs.")
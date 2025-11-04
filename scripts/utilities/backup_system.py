#!/usr/bin/env python3
"""
Sistema de Backup Automático para DB Unificada
Protege la base de datos con backups programados y rotación automática
"""

import sqlite3
import shutil
import os
from datetime import datetime, timedelta
from pathlib import Path
import logging
import schedule
import time

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backup_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DatabaseBackupSystem:
    """Sistema de backup automático con rotación"""

    def __init__(self, db_path="/Users/danielgoes96/Desktop/mcp-server/unified_mcp_system.db"):
        self.db_path = Path(db_path)
        self.backup_dir = self.db_path.parent / "backups"
        self.backup_dir.mkdir(exist_ok=True)

        # Configuración
        self.max_daily_backups = 7    # 7 días de backups diarios
        self.max_hourly_backups = 24  # 24 horas de backups por hora
        self.max_weekly_backups = 4   # 4 semanas de backups semanales

        logger.info(f"🔧 Backup system inicializado")
        logger.info(f"📁 DB: {self.db_path}")
        logger.info(f"📁 Backup dir: {self.backup_dir}")

    def create_backup(self, backup_type="manual"):
        """Crea un backup de la base de datos"""
        try:
            if not self.db_path.exists():
                logger.error(f"❌ DB no encontrada: {self.db_path}")
                return False

            # Generar nombre de backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"unified_mcp_backup_{backup_type}_{timestamp}.db"
            backup_path = self.backup_dir / backup_name

            # Verificar integridad antes del backup
            if not self.verify_db_integrity():
                logger.error("❌ DB corrupta, no se puede hacer backup")
                return False

            # Crear backup usando SQLite's backup API (más seguro que copy)
            with sqlite3.connect(self.db_path) as source:
                with sqlite3.connect(backup_path) as backup_db:
                    source.backup(backup_db)

            # Verificar que el backup se creó correctamente
            backup_size = backup_path.stat().st_size
            original_size = self.db_path.stat().st_size

            if backup_size == 0:
                logger.error("❌ Backup creado pero está vacío")
                backup_path.unlink()
                return False

            logger.info(f"✅ Backup creado: {backup_name}")
            logger.info(f"📊 Tamaño: {backup_size:,} bytes (original: {original_size:,})")

            return True

        except Exception as e:
            logger.error(f"❌ Error creando backup: {e}")
            return False

    def verify_db_integrity(self):
        """Verifica la integridad de la base de datos"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()

                if result and result[0] == "ok":
                    return True
                else:
                    logger.error(f"❌ DB integrity check failed: {result}")
                    return False

        except Exception as e:
            logger.error(f"❌ Error verificando integridad: {e}")
            return False

    def cleanup_old_backups(self):
        """Elimina backups antiguos según política de retención"""
        try:
            now = datetime.now()
            backups_removed = 0

            for backup_file in self.backup_dir.glob("unified_mcp_backup_*.db"):
                # Extraer timestamp del nombre del archivo
                try:
                    parts = backup_file.stem.split('_')
                    if len(parts) >= 5:
                        date_str = parts[3]
                        time_str = parts[4]
                        backup_datetime = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")

                        # Política de retención
                        age = now - backup_datetime
                        backup_type = parts[2]  # manual, hourly, daily, weekly

                        should_delete = False

                        if backup_type == "hourly" and age > timedelta(hours=self.max_hourly_backups):
                            should_delete = True
                        elif backup_type == "daily" and age > timedelta(days=self.max_daily_backups):
                            should_delete = True
                        elif backup_type == "weekly" and age > timedelta(weeks=self.max_weekly_backups):
                            should_delete = True
                        elif backup_type == "manual" and age > timedelta(days=30):  # Manuales 30 días
                            should_delete = True

                        if should_delete:
                            backup_file.unlink()
                            backups_removed += 1
                            logger.info(f"🗑️ Backup eliminado (edad: {age.days}d): {backup_file.name}")

                except ValueError:
                    logger.warning(f"⚠️ Nombre de backup inválido: {backup_file.name}")
                    continue

            if backups_removed > 0:
                logger.info(f"🧹 Limpieza completada: {backups_removed} backups eliminados")

        except Exception as e:
            logger.error(f"❌ Error limpiando backups: {e}")

    def get_backup_stats(self):
        """Obtiene estadísticas de backups"""
        try:
            backups = list(self.backup_dir.glob("unified_mcp_backup_*.db"))

            stats = {
                'total_backups': len(backups),
                'total_size': sum(b.stat().st_size for b in backups),
                'by_type': {},
                'latest_backup': None,
                'oldest_backup': None
            }

            if backups:
                # Ordenar por fecha de modificación
                backups_sorted = sorted(backups, key=lambda x: x.stat().st_mtime)
                stats['latest_backup'] = backups_sorted[-1].name
                stats['oldest_backup'] = backups_sorted[0].name

                # Contar por tipo
                for backup in backups:
                    parts = backup.stem.split('_')
                    backup_type = parts[2] if len(parts) >= 3 else 'unknown'
                    stats['by_type'][backup_type] = stats['by_type'].get(backup_type, 0) + 1

            return stats

        except Exception as e:
            logger.error(f"❌ Error obteniendo stats: {e}")
            return {}

    def restore_from_backup(self, backup_name):
        """Restaura la DB desde un backup específico"""
        try:
            backup_path = self.backup_dir / backup_name

            if not backup_path.exists():
                logger.error(f"❌ Backup no encontrado: {backup_name}")
                return False

            # Crear backup de la DB actual antes de restaurar
            current_backup = f"pre_restore_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2(self.db_path, self.backup_dir / current_backup)
            logger.info(f"💾 DB actual respaldada como: {current_backup}")

            # Restaurar
            shutil.copy2(backup_path, self.db_path)

            # Verificar integridad de la restauración
            if self.verify_db_integrity():
                logger.info(f"✅ DB restaurada exitosamente desde: {backup_name}")
                return True
            else:
                logger.error("❌ DB restaurada pero falló verificación de integridad")
                return False

        except Exception as e:
            logger.error(f"❌ Error restaurando desde backup: {e}")
            return False

    def run_scheduled_backups(self):
        """Ejecuta el sistema de backups programados"""
        logger.info("🚀 Sistema de backups programados iniciado")

        # Programar backups
        schedule.every().hour.do(lambda: self.create_backup("hourly"))
        schedule.every().day.at("02:00").do(lambda: self.create_backup("daily"))
        schedule.every().sunday.at("03:00").do(lambda: self.create_backup("weekly"))
        schedule.every().day.at("04:00").do(self.cleanup_old_backups)

        # Crear backup inicial
        self.create_backup("initial")

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Revisar cada minuto
        except KeyboardInterrupt:
            logger.info("🛑 Sistema de backups detenido")

def create_cron_job():
    """Crea un cron job para backups automáticos"""
    cron_command = f"""
# MCP Server Database Backup System
0 */1 * * * cd {Path(__file__).parent} && python3 backup_system.py hourly
0 2 * * * cd {Path(__file__).parent} && python3 backup_system.py daily
0 3 * * 0 cd {Path(__file__).parent} && python3 backup_system.py weekly
0 4 * * * cd {Path(__file__).parent} && python3 backup_system.py cleanup
"""

    cron_file = Path(__file__).parent / "mcp_backup_cron.txt"
    with open(cron_file, 'w') as f:
        f.write(cron_command.strip())

    logger.info(f"📅 Cron job creado en: {cron_file}")
    logger.info("Para activar ejecuta: crontab mcp_backup_cron.txt")

    return cron_file

if __name__ == "__main__":
    import sys

    backup_system = DatabaseBackupSystem()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "backup":
            backup_type = sys.argv[2] if len(sys.argv) > 2 else "manual"
            success = backup_system.create_backup(backup_type)
            sys.exit(0 if success else 1)

        elif command == "cleanup":
            backup_system.cleanup_old_backups()

        elif command == "stats":
            stats = backup_system.get_backup_stats()
            print("📊 ESTADÍSTICAS DE BACKUPS:")
            print(f"Total backups: {stats.get('total_backups', 0)}")
            print(f"Tamaño total: {stats.get('total_size', 0):,} bytes")
            print(f"Por tipo: {stats.get('by_type', {})}")
            print(f"Más reciente: {stats.get('latest_backup', 'N/A')}")

        elif command in ["hourly", "daily", "weekly"]:
            backup_system.create_backup(command)
            backup_system.cleanup_old_backups()

        elif command == "restore":
            if len(sys.argv) > 2:
                backup_name = sys.argv[2]
                backup_system.restore_from_backup(backup_name)
            else:
                print("❌ Especifica el nombre del backup para restaurar")

        elif command == "cron":
            create_cron_job()

        elif command == "daemon":
            backup_system.run_scheduled_backups()

        else:
            print("❌ Comando no reconocido")

    else:
        # Crear backup manual por defecto
        print("🔧 Creando backup manual...")
        success = backup_system.create_backup("manual")

        # Mostrar stats
        stats = backup_system.get_backup_stats()
        print("\n📊 ESTADÍSTICAS:")
        print(f"✅ Total backups: {stats.get('total_backups', 0)}")
        print(f"📁 Tamaño total: {stats.get('total_size', 0):,} bytes")

        if success:
            print("🎉 Sistema de backup listo!")
            print("\nComandos disponibles:")
            print("  python3 backup_system.py backup manual")
            print("  python3 backup_system.py stats")
            print("  python3 backup_system.py cleanup")
            print("  python3 backup_system.py cron")
        else:
            sys.exit(1)
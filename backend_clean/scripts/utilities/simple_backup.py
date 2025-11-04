#!/usr/bin/env python3
"""
Sistema de Backup Simple sin dependencias externas
Protege la base de datos unificada con backups básicos
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import logging

# Configurar logging básico
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleBackupSystem:
    """Sistema de backup simple y efectivo"""

    def __init__(self, db_path="/Users/danielgoes96/Desktop/mcp-server/unified_mcp_system.db"):
        self.db_path = Path(db_path)
        self.backup_dir = self.db_path.parent / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        logger.info(f"🔧 Sistema de backup inicializado: {self.backup_dir}")

    def create_backup(self, backup_type="manual"):
        """Crea un backup de la base de datos"""
        try:
            if not self.db_path.exists():
                logger.error(f"❌ DB no encontrada: {self.db_path}")
                return False

            # Verificar integridad
            if not self.verify_db_integrity():
                logger.error("❌ DB corrupta, abortando backup")
                return False

            # Generar nombre de backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"unified_mcp_{backup_type}_{timestamp}.db"
            backup_path = self.backup_dir / backup_name

            # Crear backup usando SQLite backup API
            with sqlite3.connect(self.db_path) as source:
                with sqlite3.connect(backup_path) as backup_db:
                    source.backup(backup_db)

            # Verificar backup
            if backup_path.exists() and backup_path.stat().st_size > 0:
                logger.info(f"✅ Backup creado: {backup_name}")
                logger.info(f"📊 Tamaño: {backup_path.stat().st_size:,} bytes")
                return True
            else:
                logger.error("❌ Backup falló - archivo vacío o no creado")
                return False

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
                return result and result[0] == "ok"
        except Exception as e:
            logger.error(f"❌ Error verificando integridad: {e}")
            return False

    def cleanup_old_backups(self, keep_days=7):
        """Elimina backups más antiguos que keep_days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            removed = 0

            for backup_file in self.backup_dir.glob("unified_mcp_*.db"):
                file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                if file_time < cutoff_date:
                    backup_file.unlink()
                    removed += 1
                    logger.info(f"🗑️ Eliminado backup antiguo: {backup_file.name}")

            logger.info(f"🧹 Limpieza completada: {removed} backups eliminados")

        except Exception as e:
            logger.error(f"❌ Error limpiando backups: {e}")

    def list_backups(self):
        """Lista todos los backups disponibles"""
        backups = []
        for backup_file in sorted(self.backup_dir.glob("unified_mcp_*.db")):
            stat = backup_file.stat()
            backups.append({
                'name': backup_file.name,
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
            })
        return backups

    def get_stats(self):
        """Obtiene estadísticas básicas"""
        backups = self.list_backups()
        total_size = sum(b['size'] for b in backups)

        return {
            'total_backups': len(backups),
            'total_size_mb': round(total_size / (1024*1024), 2),
            'latest': backups[-1]['name'] if backups else None,
            'db_size_mb': round(self.db_path.stat().st_size / (1024*1024), 2) if self.db_path.exists() else 0
        }

def create_cron_script():
    """Crea script para cron job"""
    script_path = Path(__file__).parent / "backup_cron.sh"

    script_content = f"""#!/bin/bash
# MCP Database Backup Script
cd {Path(__file__).parent}

# Backup diario a las 2 AM
python3 simple_backup.py daily

# Limpieza semanal los domingos a las 3 AM
if [ "$(date +%u)" = "7" ]; then
    python3 simple_backup.py cleanup
fi
"""

    with open(script_path, 'w') as f:
        f.write(script_content)

    # Hacer ejecutable
    script_path.chmod(0o755)

    logger.info(f"📅 Script de cron creado: {script_path}")
    logger.info("Para activar: crontab -e y agregar:")
    logger.info(f"0 2 * * * {script_path}")

    return script_path

if __name__ == "__main__":
    import sys

    backup_system = SimpleBackupSystem()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command in ["manual", "daily", "weekly", "backup"]:
            backup_type = command if command != "backup" else "manual"
            success = backup_system.create_backup(backup_type)
            sys.exit(0 if success else 1)

        elif command == "cleanup":
            keep_days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            backup_system.cleanup_old_backups(keep_days)

        elif command == "list":
            backups = backup_system.list_backups()
            print("📋 BACKUPS DISPONIBLES:")
            for backup in backups:
                print(f"  {backup['name']} - {backup['size']:,} bytes - {backup['created']}")

        elif command == "stats":
            stats = backup_system.get_stats()
            print("📊 ESTADÍSTICAS DE BACKUP:")
            print(f"  Total backups: {stats['total_backups']}")
            print(f"  Tamaño total: {stats['total_size_mb']} MB")
            print(f"  DB actual: {stats['db_size_mb']} MB")
            print(f"  Último backup: {stats['latest'] or 'N/A'}")

        elif command == "cron":
            create_cron_script()

        else:
            print("❌ Comando no válido. Usa: backup, cleanup, list, stats, cron")

    else:
        # Crear backup por defecto
        print("🔧 Creando backup manual...")
        success = backup_system.create_backup("manual")

        if success:
            stats = backup_system.get_stats()
            print(f"✅ Backup completado!")
            print(f"📊 Total backups: {stats['total_backups']}")
            print(f"💾 Tamaño total: {stats['total_size_mb']} MB")
            print("\n🛠️ Comandos disponibles:")
            print("  python3 simple_backup.py backup")
            print("  python3 simple_backup.py list")
            print("  python3 simple_backup.py stats")
            print("  python3 simple_backup.py cleanup")
            print("  python3 simple_backup.py cron")
        else:
            print("❌ Error creando backup")
            sys.exit(1)
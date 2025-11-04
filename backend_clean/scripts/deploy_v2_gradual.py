#!/usr/bin/env python3
"""
Script de Deployment Gradual v2

Implementa rollout progresivo con feature flags y rollback automático.
"""

import os
import time
import sqlite3
import requests
import logging
import subprocess
from datetime import datetime
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GradualDeployment:
    """Gestor de deployment gradual con validaciones."""

    def __init__(self, base_url: str = "http://localhost:8000", db_path: str = "expenses.db"):
        self.base_url = base_url
        self.db_path = db_path
        self.deployment_log = []

    def run_deployment(self):
        """Ejecutar deployment completo con validaciones."""
        try:
            logger.info("🚀 Iniciando deployment gradual v2")

            # Fase 1: Validaciones pre-deployment
            self._validate_pre_deployment()

            # Fase 2: Backup y preparación
            self._create_backups()

            # Fase 3: Aplicar migraciones
            self._apply_migrations()

            # Fase 4: Deploy código
            self._deploy_code()

            # Fase 5: Validar endpoints básicos
            self._validate_basic_functionality()

            # Fase 6: Habilitar features gradualmente
            self._gradual_feature_rollout()

            # Fase 7: Monitoreo post-deployment
            self._post_deployment_monitoring()

            logger.info("✅ Deployment completado exitosamente")

        except Exception as e:
            logger.error(f"❌ Deployment falló: {e}")
            self._emergency_rollback()
            raise

    def _validate_pre_deployment(self):
        """Validaciones antes del deployment."""
        logger.info("🔍 Validando pre-requisitos...")

        # 1. Verificar servidor actual funciona
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            if response.status_code != 200:
                raise Exception(f"Servidor actual no responde: {response.status_code}")
        except requests.RequestException as e:
            raise Exception(f"No se puede conectar al servidor: {e}")

        # 2. Verificar base de datos accesible
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM tickets")
                count = cursor.fetchone()[0]
                logger.info(f"Base de datos accesible: {count} tickets")
        except Exception as e:
            raise Exception(f"Error accediendo base de datos: {e}")

        # 3. Verificar archivos de código existen
        required_files = [
            "main_enhanced.py",
            "core/unified_automation_engine.py",
            "modules/invoicing_agent/integration_layer.py",
            "migrations/010_enhance_automation_20240922.sql"
        ]

        for file in required_files:
            if not os.path.exists(file):
                raise Exception(f"Archivo requerido no encontrado: {file}")

        logger.info("✅ Pre-validaciones completadas")

    def _create_backups(self):
        """Crear backups de seguridad."""
        logger.info("💾 Creando backups...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Backup database
        backup_db = f"backup_expenses_{timestamp}.db"
        subprocess.run(f"cp {self.db_path} {backup_db}", shell=True, check=True)
        logger.info(f"Database backup: {backup_db}")

        # Backup código actual
        if os.path.exists("main.py"):
            subprocess.run(f"cp main.py main_backup_{timestamp}.py", shell=True, check=True)
            logger.info(f"Code backup: main_backup_{timestamp}.py")

        # Tag git
        try:
            subprocess.run(f"git tag deployment_backup_{timestamp}", shell=True, check=True)
            logger.info(f"Git tag created: deployment_backup_{timestamp}")
        except:
            logger.warning("No se pudo crear git tag (no es crítico)")

        self.deployment_log.append(f"Backups created at {timestamp}")

    def _apply_migrations(self):
        """Aplicar migraciones de base de datos."""
        logger.info("🗄️ Aplicando migraciones...")

        migration_file = "migrations/010_enhance_automation_20240922.sql"

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Verificar si ya está aplicada
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='feature_flags'"
                )
                if cursor.fetchone():
                    logger.info("Migración ya aplicada anteriormente")
                    return

                # Aplicar migración
                with open(migration_file, 'r') as f:
                    migration_sql = f.read()

                conn.executescript(migration_sql)
                logger.info("✅ Migración aplicada exitosamente")

                # Verificar tablas creadas
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'automation_%' OR name IN ('feature_flags', 'tenant_config')"
                )
                tables = [row[0] for row in cursor.fetchall()]
                logger.info(f"Tablas creadas: {tables}")

        except Exception as e:
            raise Exception(f"Error aplicando migración: {e}")

    def _deploy_code(self):
        """Deploy del código nuevo."""
        logger.info("🚀 Deploying código v2...")

        try:
            # Mover main.py actual a backup
            if os.path.exists("main.py"):
                os.rename("main.py", "main_v1_backup.py")

            # Activar versión enhanced
            os.rename("main_enhanced.py", "main.py")

            logger.info("✅ Código v2 activado")

            # Reiniciar servidor (esto depende de tu setup)
            # En producción usarías tu sistema de deployment
            self._restart_server()

        except Exception as e:
            # Rollback automático
            if os.path.exists("main_v1_backup.py"):
                os.rename("main_v1_backup.py", "main.py")
            raise Exception(f"Error deploying código: {e}")

    def _restart_server(self):
        """Reiniciar servidor (adaptar según tu setup)."""
        logger.info("🔄 Reiniciando servidor...")

        # Método 1: Si usas systemd
        try:
            subprocess.run("sudo systemctl restart mcp-server", shell=True, check=True)
            time.sleep(5)  # Esperar a que arranque
            return
        except:
            pass

        # Método 2: Si usas docker
        try:
            subprocess.run("docker-compose restart", shell=True, check=True)
            time.sleep(10)
            return
        except:
            pass

        # Método 3: Desarrollo local
        logger.warning("⚠️ Reinicio manual requerido - mata el proceso y ejecuta: python main.py")

    def _validate_basic_functionality(self):
        """Validar que funcionalidad básica funciona."""
        logger.info("🧪 Validando funcionalidad básica...")

        # Esperar a que el servidor arranque
        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                response = requests.get(f"{self.base_url}/health", timeout=5)
                if response.status_code == 200:
                    break
                time.sleep(2)
            except:
                time.sleep(2)
        else:
            raise Exception("Servidor no arrancó después del deployment")

        # Test endpoints críticos
        critical_tests = [
            ("/health", "Health check"),
            ("/invoicing/tickets", "Tickets endpoint"),
            ("/invoicing/merchants", "Merchants endpoint"),
            ("/static/automation-viewer.html", "Automation viewer")
        ]

        for endpoint, description in critical_tests:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                if response.status_code not in [200, 404]:  # 404 OK for empty lists
                    raise Exception(f"{description} failed: {response.status_code}")
                logger.info(f"✅ {description} OK")
            except Exception as e:
                raise Exception(f"Critical test failed - {description}: {e}")

        # Test v2 endpoints existen
        v2_tests = [
            ("/invoicing/v2/health", "v2 health"),
            ("/invoicing/system/status", "Enhanced status")
        ]

        for endpoint, description in v2_tests:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                logger.info(f"✅ {description}: {response.status_code}")
            except Exception as e:
                logger.warning(f"⚠️ {description} no disponible: {e}")

    def _gradual_feature_rollout(self):
        """Habilitar features gradualmente."""
        logger.info("🎛️ Rollout gradual de features...")

        # Configurar feature flags conservadores
        feature_rollout = [
            ("enhanced_automation", "default", True),  # Base functionality
            ("screenshot_evidence", "default", True),   # Low risk
            ("claude_analysis", "default", False),      # Start disabled
            ("google_vision_ocr", "default", False),    # Start disabled
            ("captcha_solving", "default", False),      # Start disabled
            ("bulk_operations", "default", False),      # Start disabled
        ]

        try:
            with sqlite3.connect(self.db_path) as conn:
                for feature, company, enabled in feature_rollout:
                    conn.execute("""
                        INSERT OR REPLACE INTO feature_flags
                        (company_id, feature_name, enabled, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (company, feature, enabled, datetime.now().isoformat(), datetime.now().isoformat()))

                conn.commit()
                logger.info("✅ Feature flags configurados conservadoramente")

        except Exception as e:
            logger.error(f"Error configurando feature flags: {e}")

        # Test con cliente de prueba
        self._enable_for_test_client()

    def _enable_for_test_client(self):
        """Habilitar todas las features para cliente de prueba."""
        logger.info("🧪 Habilitando features para cliente test...")

        test_features = [
            "claude_analysis",
            "google_vision_ocr",
            "captcha_solving",
            "bulk_operations"
        ]

        try:
            with sqlite3.connect(self.db_path) as conn:
                for feature in test_features:
                    conn.execute("""
                        INSERT OR REPLACE INTO feature_flags
                        (company_id, feature_name, enabled, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, ("test_client", feature, True, datetime.now().isoformat(), datetime.now().isoformat()))

                conn.commit()
                logger.info("✅ Features habilitadas para test_client")

        except Exception as e:
            logger.warning(f"Error configurando test client: {e}")

    def _post_deployment_monitoring(self):
        """Monitoreo post-deployment."""
        logger.info("📊 Iniciando monitoreo post-deployment...")

        # Monitorear por 5 minutos
        monitor_duration = 300  # 5 minutos
        check_interval = 30     # Cada 30 segundos

        start_time = time.time()
        error_count = 0
        max_errors = 3

        while time.time() - start_time < monitor_duration:
            try:
                # Health check
                response = requests.get(f"{self.base_url}/health", timeout=5)
                if response.status_code != 200:
                    error_count += 1
                    logger.warning(f"Health check failed: {response.status_code}")

                    if error_count >= max_errors:
                        raise Exception("Demasiados errores consecutivos")

                else:
                    error_count = 0  # Reset on success
                    health_data = response.json()
                    logger.info(f"✅ Health OK - Enhanced: {health_data.get('features', {}).get('enhanced_automation', False)}")

                time.sleep(check_interval)

            except Exception as e:
                error_count += 1
                logger.error(f"Monitor error: {e}")

                if error_count >= max_errors:
                    raise Exception("Sistema inestable - iniciando rollback")

        logger.info("✅ Monitoreo completado - sistema estable")

    def _emergency_rollback(self):
        """Rollback de emergencia."""
        logger.error("🚨 INICIANDO ROLLBACK DE EMERGENCIA")

        try:
            # 1. Restaurar código
            if os.path.exists("main_v1_backup.py"):
                if os.path.exists("main.py"):
                    os.rename("main.py", "main_v2_failed.py")
                os.rename("main_v1_backup.py", "main.py")
                logger.info("✅ Código restaurado")

            # 2. Reiniciar servidor
            self._restart_server()

            # 3. Verificar funcionalidad básica
            time.sleep(10)
            response = requests.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                logger.info("✅ Rollback exitoso - sistema funcionando")
            else:
                logger.error("❌ Rollback falló - intervención manual requerida")

        except Exception as e:
            logger.error(f"❌ Error en rollback: {e}")
            logger.error("🚨 INTERVENCIÓN MANUAL REQUERIDA")

    def enable_feature_for_company(self, company_id: str, feature_name: str):
        """Habilitar feature específica para company."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO feature_flags
                    (company_id, feature_name, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (company_id, feature_name, True, datetime.now().isoformat(), datetime.now().isoformat()))

                conn.commit()
                logger.info(f"✅ Feature {feature_name} habilitada para {company_id}")

        except Exception as e:
            logger.error(f"Error habilitando feature: {e}")

    def get_deployment_status(self) -> Dict[str, Any]:
        """Obtener estado del deployment."""
        try:
            # Check server
            response = requests.get(f"{self.base_url}/health", timeout=5)
            server_ok = response.status_code == 200

            # Check v2 endpoints
            v2_response = requests.get(f"{self.base_url}/invoicing/v2/health", timeout=5)
            v2_ok = v2_response.status_code == 200

            # Check database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM feature_flags")
                feature_flags_count = cursor.fetchone()[0]

            return {
                "server_status": "OK" if server_ok else "ERROR",
                "v2_endpoints": "OK" if v2_ok else "ERROR",
                "feature_flags_count": feature_flags_count,
                "deployment_log": self.deployment_log,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

def main():
    """Función principal."""
    import argparse

    parser = argparse.ArgumentParser(description="Deployment gradual v2")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL del servidor")
    parser.add_argument("--db", default="expenses.db", help="Path a la base de datos")
    parser.add_argument("--dry-run", action="store_true", help="Solo validar, no aplicar cambios")
    parser.add_argument("--enable-feature", nargs=2, metavar=("COMPANY", "FEATURE"), help="Habilitar feature para company")

    args = parser.parse_args()

    deployment = GradualDeployment(args.url, args.db)

    if args.enable_feature:
        company, feature = args.enable_feature
        deployment.enable_feature_for_company(company, feature)
    elif args.dry_run:
        deployment._validate_pre_deployment()
        logger.info("✅ Dry run completado - sistema listo para deployment")
    else:
        deployment.run_deployment()

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
🚀 EJECUTOR MAESTRO DE TESTS - SISTEMA MCP
Ejecuta toda la suite de testing UI ↔ API ↔ BD de forma automatizada
"""

import sys
import subprocess
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict

# Add root to path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

class TestOrchestrator:
    """Orquestador de todos los tests del sistema"""

    def __init__(self):
        self.base_path = ROOT
        self.test_results = {}
        self.total_start_time = time.time()

    def run_test_file(self, test_file: str, description: str) -> Dict:
        """Ejecutar un archivo de test específico"""
        print(f"\n🧪 EJECUTANDO: {description}")
        print("=" * 50)

        start_time = time.time()
        test_path = self.base_path / "tests" / test_file

        if not test_path.exists():
            return {
                "status": "SKIPPED",
                "reason": f"Archivo {test_file} no encontrado",
                "duration": 0,
                "output": ""
            }

        try:
            # Ejecutar el test
            result = subprocess.run(
                [sys.executable, str(test_path)],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutos timeout
                cwd=str(self.base_path)
            )

            duration = time.time() - start_time

            if result.returncode == 0:
                print(f"✅ ÉXITO: {description} ({duration:.2f}s)")
                status = "PASSED"
            else:
                print(f"❌ FALLO: {description} ({duration:.2f}s)")
                print(f"Error: {result.stderr}")
                status = "FAILED"

            return {
                "status": status,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }

        except subprocess.TimeoutExpired:
            return {
                "status": "TIMEOUT",
                "duration": time.time() - start_time,
                "stdout": "",
                "stderr": "Test timeout after 5 minutes",
                "returncode": -1
            }

        except Exception as e:
            return {
                "status": "ERROR",
                "duration": time.time() - start_time,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1
            }

    def check_prerequisites(self) -> bool:
        """Verificar prerequisitos del sistema"""
        print("🔍 VERIFICANDO PREREQUISITOS")
        print("=" * 50)

        checks = {
            "Python 3.7+": sys.version_info >= (3, 7),
            "Database exists": (self.base_path / "unified_mcp_system.db").exists(),
            "Tests directory": (self.base_path / "tests").exists(),
        }

        # Verificar dependencias Python
        required_packages = [
            "requests", "selenium", "pytest", "sqlite3"
        ]

        for package in required_packages:
            try:
                __import__(package)
                checks[f"Package {package}"] = True
            except ImportError:
                checks[f"Package {package}"] = False

        all_good = True
        for check, status in checks.items():
            if status:
                print(f"✅ {check}")
            else:
                print(f"❌ {check}")
                all_good = False

        if not all_good:
            print("\n⚠️ PREREQUISITOS NO CUMPLIDOS")
            print("Instalar dependencias: pip install requests selenium pytest")
            if not (self.base_path / "unified_mcp_system.db").exists():
                print("Base de datos no encontrada. Ejecutar servidor primero.")

        return all_good

    def run_server_health_check(self) -> bool:
        """Verificar que el servidor esté corriendo"""
        print("\n🏥 VERIFICANDO SALUD DEL SERVIDOR")
        print("=" * 50)

        try:
            import requests
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                print("✅ Servidor respondiendo en puerto 8000")
                return True
            else:
                print(f"⚠️ Servidor responde con status {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Servidor no responde: {e}")
            print("💡 CONSEJO: Ejecutar 'python main.py' en otra terminal")
            return False

    def run_all_tests(self) -> Dict:
        """Ejecutar toda la suite de tests"""
        print("🚀 INICIANDO SUITE COMPLETA DE TESTS")
        print("🎯 Sistema MCP - Validación UI ↔ API ↔ BD")
        print("=" * 60)

        # Verificar prerequisitos
        if not self.check_prerequisites():
            return {"status": "PREREQUISITES_FAILED", "results": {}}

        # Verificar servidor
        server_ok = self.run_server_health_check()

        # Tests a ejecutar (en orden de importancia)
        test_suite = [
            {
                "file": "test_field_mapping_validation.py",
                "description": "Validación de Mapeo de Campos BD",
                "critical": True
            },
            {
                "file": "test_ui_api_bd_coherence.py",
                "description": "Tests de Coherencia UI ↔ API ↔ BD",
                "critical": True,
                "requires_server": True
            },
            {
                "file": "test_regression_suite.py",
                "description": "Suite de Regresión Automática",
                "critical": True,
                "requires_server": True
            },
            {
                "file": "test_e2e_user_flows.py",
                "description": "Tests End-to-End de Flujos Completos",
                "critical": False,
                "requires_server": True
            }
        ]

        results = {}
        critical_failures = 0
        total_tests = len(test_suite)

        for i, test in enumerate(test_suite, 1):
            print(f"\n📋 TEST {i}/{total_tests}: {test['description']}")

            # Skip tests que requieren servidor si no está disponible
            if test.get("requires_server", False) and not server_ok:
                print(f"⏭️ SKIPPED: Requiere servidor activo")
                results[test["file"]] = {
                    "status": "SKIPPED",
                    "reason": "Servidor no disponible",
                    "duration": 0
                }
                continue

            # Ejecutar test
            result = self.run_test_file(test["file"], test["description"])
            results[test["file"]] = result

            # Contar fallos críticos
            if test.get("critical", False) and result["status"] != "PASSED":
                critical_failures += 1

        # Calcular estadísticas finales
        total_duration = time.time() - self.total_start_time
        passed = sum(1 for r in results.values() if r["status"] == "PASSED")
        failed = sum(1 for r in results.values() if r["status"] == "FAILED")
        skipped = sum(1 for r in results.values() if r["status"] == "SKIPPED")

        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_duration": round(total_duration, 2),
            "total_tests": total_tests,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "critical_failures": critical_failures,
            "results": results
        }

        self.print_final_report(summary)
        self.save_test_report(summary)

        return summary

    def print_final_report(self, summary: Dict):
        """Imprimir reporte final"""
        print("\n" + "=" * 60)
        print("📊 REPORTE FINAL DE TESTING")
        print("=" * 60)

        print(f"⏱️  Duración total: {summary['total_duration']:.2f} segundos")
        print(f"🧪 Tests ejecutados: {summary['total_tests']}")
        print(f"✅ Exitosos: {summary['passed']}")
        print(f"❌ Fallidos: {summary['failed']}")
        print(f"⏭️ Omitidos: {summary['skipped']}")
        print(f"🔴 Fallos críticos: {summary['critical_failures']}")

        # Estado del sistema
        if summary['critical_failures'] == 0:
            print("\n🎯 ESTADO: ✅ SISTEMA ESTABLE")
            print("   Todas las funcionalidades críticas funcionan correctamente")
        elif summary['critical_failures'] <= 2:
            print("\n🎯 ESTADO: 🟡 SISTEMA FUNCIONAL CON ADVERTENCIAS")
            print("   Algunas funcionalidades requieren atención")
        else:
            print("\n🎯 ESTADO: 🔴 SISTEMA REQUIERE ATENCIÓN CRÍTICA")
            print("   Múltiples funcionalidades críticas fallando")

        # Detalles por test
        print("\n📋 DETALLE POR TEST:")
        for test_file, result in summary['results'].items():
            status_icon = {
                "PASSED": "✅",
                "FAILED": "❌",
                "SKIPPED": "⏭️",
                "TIMEOUT": "⏰",
                "ERROR": "💥"
            }.get(result['status'], "❓")

            print(f"   {status_icon} {test_file}: {result['status']} ({result['duration']:.2f}s)")

    def save_test_report(self, summary: Dict):
        """Guardar reporte en archivo JSON"""
        report_file = self.base_path / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(report_file, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"\n📄 Reporte guardado en: {report_file}")

    def run_specific_test(self, test_name: str):
        """Ejecutar un test específico"""
        test_mapping = {
            "mapping": "test_field_mapping_validation.py",
            "coherence": "test_ui_api_bd_coherence.py",
            "regression": "test_regression_suite.py",
            "e2e": "test_e2e_user_flows.py"
        }

        if test_name in test_mapping:
            file_name = test_mapping[test_name]
            result = self.run_test_file(file_name, f"Test específico: {test_name}")
            print(f"\n📊 Resultado: {result['status']} ({result['duration']:.2f}s)")
        else:
            print(f"❌ Test '{test_name}' no encontrado")
            print(f"Tests disponibles: {list(test_mapping.keys())}")

def main():
    """Función principal"""
    if len(sys.argv) > 1:
        # Ejecutar test específico
        test_name = sys.argv[1]
        orchestrator = TestOrchestrator()
        orchestrator.run_specific_test(test_name)
    else:
        # Ejecutar todos los tests
        orchestrator = TestOrchestrator()
        summary = orchestrator.run_all_tests()

        # Exit code basado en resultados
        if summary.get("critical_failures", 0) == 0:
            sys.exit(0)  # Éxito
        else:
            sys.exit(1)  # Fallo

if __name__ == "__main__":
    main()
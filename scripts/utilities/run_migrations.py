#!/usr/bin/env python3
"""
Script para aplicar migraciones de base de datos
"""

import os
import sys

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.internal_db import initialize_internal_database

def run_migrations():
    """Ejecutar todas las migraciones pendientes"""

    print("🔧 APLICANDO MIGRACIONES DE BASE DE DATOS")
    print("=" * 50)

    try:
        initialize_internal_database()
        print("✅ Migraciones aplicadas exitosamente")
        return True

    except Exception as e:
        print(f"❌ Error aplicando migraciones: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_migrations()

    if not success:
        sys.exit(1)
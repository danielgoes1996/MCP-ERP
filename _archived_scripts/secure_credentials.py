#!/usr/bin/env python3
"""
Script para limpiar credenciales hardcodeadas del proyecto.
Ejecutar después de rotar las API keys expuestas.
"""

import os
import re
import glob
from pathlib import Path

# API Keys expuestas que deben ser reemplazadas
EXPOSED_KEYS = {
    "REPLACE_WITH_NEW_GOOGLE_API_KEY": "REPLACE_WITH_NEW_GOOGLE_API_KEY",
    "REPLACE_WITH_NEW_OPENAI_API_KEY": "REPLACE_WITH_NEW_OPENAI_API_KEY"
}

def clean_file(file_path):
    """Limpiar un archivo de credenciales hardcodeadas."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Reemplazar cada key expuesta
        for exposed_key, replacement in EXPOSED_KEYS.items():
            if exposed_key in content:
                print(f"🔧 Limpiando {file_path}: {exposed_key[:20]}...")
                content = content.replace(exposed_key, replacement)

        # Solo escribir si hubo cambios
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True

        return False

    except Exception as e:
        print(f"❌ Error procesando {file_path}: {e}")
        return False

def main():
    """Ejecutar limpieza de credenciales."""
    print("🧹 INICIANDO LIMPIEZA DE CREDENCIALES HARDCODEADAS")
    print("="*60)

    # Buscar archivos Python
    python_files = list(Path('.').glob('**/*.py'))
    cleaned_files = 0

    for file_path in python_files:
        if clean_file(file_path):
            cleaned_files += 1

    print(f"\n✅ LIMPIEZA COMPLETADA")
    print(f"📁 Archivos procesados: {len(python_files)}")
    print(f"🔧 Archivos limpiados: {cleaned_files}")

    if cleaned_files > 0:
        print(f"\n⚠️  IMPORTANTE:")
        print(f"1. Las API keys expuestas han sido reemplazadas con placeholders")
        print(f"2. DEBES rotar las keys reales en OpenAI y Google Cloud Console")
        print(f"3. Configura las nuevas keys en .env con las variables de reemplazo")
        print(f"4. NO commitees las nuevas keys al repositorio")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Script para actualizar todas las referencias de código después del renombrado de tablas.

Cambios:
- sat_invoices → sat_invoices
- expenses → manual_expenses

Autor: Claude Code
Fecha: 2025-11-15
"""

import os
import re
from pathlib import Path
from typing import List, Tuple, Dict

# Mapeo de reemplazos
REPLACEMENTS = {
    # Tabla sat_invoices → sat_invoices
    r'\buniversal_invoice_sessions\b': 'sat_invoices',
    r'\bUNIVERSAL_INVOICE_SESSIONS\b': 'SAT_INVOICES',
    r'\bUniversalInvoiceSessions\b': 'SatInvoices',

    # Tabla expenses → manual_expenses (solo cuando es tabla, no clase/variable)
    # Cuidado: no cambiar "manual_expenses" en contextos como "total_expenses" o "get_expenses()"
    r'\bFROM expenses\b': 'FROM manual_expenses',
    r'\bJOIN expenses\b': 'JOIN manual_expenses',
    r'\bINTO expenses\b': 'INTO manual_expenses',
    r'\bUPDATE expenses\b': 'UPDATE manual_expenses',
    r'\bDELETE FROM manual_expenses\b': 'DELETE FROM manual_expenses',
    r'\bTABLE expenses\b': 'TABLE manual_expenses',
    r'\"expenses\"': '"manual_expenses"',
    r"'manual_expenses'": "'manual_expenses'",
}

# Archivos a excluir (no modificar)
EXCLUDE_PATTERNS = [
    '*.pyc',
    '__pycache__',
    '.git',
    'node_modules',
    '.next',
    'venv',
    'env',
    '.venv',
    '*.egg-info',
    'build',
    'dist',
    '.pytest_cache',
    '.mypy_cache',
    '.tox',
    '*.log',
    '.DS_Store',
]

# Extensiones de archivo a procesar
EXTENSIONS = [
    '.py',
    '.sql',
    '.ts',
    '.tsx',
    '.js',
    '.jsx',
    '.md',
    '.txt',
    '.sh',
]


def should_process_file(file_path: Path) -> bool:
    """Determinar si un archivo debe ser procesado."""
    # Excluir patrones
    for pattern in EXCLUDE_PATTERNS:
        if pattern in str(file_path):
            return False

    # Solo procesar extensiones permitidas
    return file_path.suffix in EXTENSIONS


def process_file(file_path: Path, dry_run: bool = True) -> Tuple[bool, int]:
    """
    Procesar un archivo y aplicar reemplazos.

    Returns:
        (changed, num_replacements)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Archivo binario, skip
        return False, 0
    except Exception as e:
        print(f"⚠️  Error leyendo {file_path}: {e}")
        return False, 0

    original_content = content
    total_replacements = 0

    # Aplicar todos los reemplazos
    for pattern, replacement in REPLACEMENTS.items():
        matches = len(re.findall(pattern, content))
        if matches > 0:
            content = re.sub(pattern, replacement, content)
            total_replacements += matches

    changed = content != original_content

    if changed and not dry_run:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            print(f"❌ Error escribiendo {file_path}: {e}")
            return False, 0

    return changed, total_replacements


def scan_and_update(
    root_dir: Path,
    dry_run: bool = True,
    verbose: bool = False
) -> Dict[str, List[Path]]:
    """
    Escanear directorio y actualizar archivos.

    Returns:
        Dict con resultados por categoría
    """
    results = {
        'changed': [],
        'unchanged': [],
        'errors': []
    }

    total_files = 0
    total_replacements = 0

    for file_path in root_dir.rglob('*'):
        if not file_path.is_file():
            continue

        if not should_process_file(file_path):
            continue

        total_files += 1

        changed, num_replacements = process_file(file_path, dry_run=dry_run)

        if changed:
            results['changed'].append(file_path)
            total_replacements += num_replacements

            if verbose or not dry_run:
                rel_path = file_path.relative_to(root_dir)
                print(f"{'[DRY RUN] ' if dry_run else ''}✏️  {rel_path}: {num_replacements} reemplazos")
        else:
            results['unchanged'].append(file_path)

    # Resumen
    print("\n" + "="*80)
    print("RESUMEN DE CAMBIOS" + (" [DRY RUN]" if dry_run else ""))
    print("="*80)
    print(f"Archivos procesados: {total_files}")
    print(f"Archivos modificados: {len(results['changed'])}")
    print(f"Archivos sin cambios: {len(results['unchanged'])}")
    print(f"Total de reemplazos: {total_replacements}")
    print("="*80)

    if dry_run and results['changed']:
        print("\n📋 ARCHIVOS QUE SERÁN MODIFICADOS:")
        for file_path in sorted(results['changed']):
            rel_path = file_path.relative_to(root_dir)
            print(f"  - {rel_path}")

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Actualizar referencias de código después del renombrado de tablas"
    )
    parser.add_argument(
        '--root-dir',
        type=Path,
        default=Path('/Users/danielgoes96/Desktop/mcp-server'),
        help='Directorio raíz del proyecto'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Modo dry-run (no modificar archivos)'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Aplicar cambios reales (desactiva dry-run)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Mostrar todos los archivos procesados'
    )

    args = parser.parse_args()

    # Si --apply está activado, dry_run = False
    dry_run = not args.apply

    print("🔄 Actualizando referencias de código...")
    print(f"📂 Directorio: {args.root_dir}")
    print(f"🔍 Modo: {'DRY RUN (preview)' if dry_run else 'APLICANDO CAMBIOS'}")
    print()

    if not dry_run:
        confirm = input("⚠️  ¿Estás seguro de aplicar cambios? (escribe 'yes' para confirmar): ")
        if confirm.lower() != 'yes':
            print("❌ Operación cancelada")
            return

    results = scan_and_update(
        root_dir=args.root_dir,
        dry_run=dry_run,
        verbose=args.verbose
    )

    if dry_run:
        print("\n💡 Para aplicar los cambios, ejecuta:")
        print(f"   python3 {__file__} --apply")
    else:
        print("\n✅ Cambios aplicados exitosamente")
        print("\n📝 Próximos pasos:")
        print("   1. Revisar los cambios con: git diff")
        print("   2. Ejecutar tests: pytest")
        print("   3. Aplicar migración SQL:")
        print("      psql -f migrations/2025_11_15_rename_tables_sat_invoices_manual_expenses.sql")


if __name__ == '__main__':
    main()

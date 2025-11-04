#!/usr/bin/env python3
"""
Script para identificar y limpiar código muerto en el módulo de tickets.
"""

import os
import ast
import glob
from pathlib import Path
from typing import Set, Dict, List

def extract_function_definitions(file_path: str) -> Set[str]:
    """Extraer nombres de funciones definidas en un archivo."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)
        functions = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.add(node.name)
            elif isinstance(node, ast.AsyncFunctionDef):
                functions.add(node.name)

        return functions
    except:
        return set()

def extract_function_calls(file_path: str) -> Set[str]:
    """Extraer nombres de funciones llamadas en un archivo."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)
        calls = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)

        return calls
    except:
        return set()

def find_dead_functions():
    """Encontrar funciones que se definen pero nunca se llaman."""
    print("🔍 ANALIZANDO CÓDIGO MUERTO EN MÓDULO DE TICKETS")
    print("="*60)

    # Buscar archivos Python en módulos relevantes
    search_patterns = [
        "modules/invoicing_agent/**/*.py",
        "core/**/*.py",
        "*.py"
    ]

    all_files = []
    for pattern in search_patterns:
        all_files.extend(glob.glob(pattern, recursive=True))

    # Filtrar archivos válidos
    python_files = [f for f in all_files if f.endswith('.py') and os.path.isfile(f)]

    # Extraer todas las definiciones y llamadas
    all_definitions = {}
    all_calls = set()

    for file_path in python_files:
        definitions = extract_function_definitions(file_path)
        calls = extract_function_calls(file_path)

        if definitions:
            all_definitions[file_path] = definitions

        all_calls.update(calls)

    # Encontrar funciones no llamadas
    dead_functions = {}
    for file_path, definitions in all_definitions.items():
        dead = definitions - all_calls
        if dead:
            dead_functions[file_path] = dead

    # Reportar resultados
    print(f"📁 Archivos analizados: {len(python_files)}")
    print(f"🔍 Funciones definidas: {sum(len(defs) for defs in all_definitions.values())}")
    print(f"📞 Funciones llamadas: {len(all_calls)}")

    if dead_functions:
        print(f"\n💀 FUNCIONES POTENCIALMENTE MUERTAS:")
        print("-" * 50)
        total_dead = 0
        for file_path, dead_funcs in dead_functions.items():
            print(f"\n📄 {file_path}:")
            for func in sorted(dead_funcs):
                # Filtrar funciones privadas y especiales
                if not func.startswith('_') and func not in ['main', 'setup_logging', 'test_']:
                    print(f"   💀 {func}()")
                    total_dead += 1

        print(f"\n📊 RESUMEN:")
        print(f"   Funciones muertas encontradas: {total_dead}")

        if total_dead > 0:
            print(f"\n⚠️  RECOMENDACIONES:")
            print(f"   1. Revisar manualmente cada función antes de eliminar")
            print(f"   2. Algunas pueden ser APIs públicas o puntos de entrada")
            print(f"   3. Considerar mover a directorio 'unused' en lugar de eliminar")
    else:
        print(f"\n✅ No se encontraron funciones claramente muertas")

    # Buscar archivos sin referencias
    print(f"\n🔍 BUSCANDO MÓDULOS SIN REFERENCIAS...")

    module_files = [f for f in python_files if 'modules/' in f or 'core/' in f]
    imported_modules = set()

    # Buscar imports en todos los archivos
    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_modules.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imported_modules.add(node.module)
        except:
            continue

    unused_modules = []
    for module_file in module_files:
        module_name = module_file.replace('/', '.').replace('.py', '')
        if module_name not in imported_modules:
            # Verificar variantes del nombre
            variants = [
                module_name,
                module_name.replace('modules.', ''),
                module_name.replace('core.', ''),
                module_name.split('.')[-1]  # Solo el nombre final
            ]

            if not any(variant in imported_modules for variant in variants):
                unused_modules.append(module_file)

    if unused_modules:
        print(f"\n📦 MÓDULOS POTENCIALMENTE NO IMPORTADOS:")
        print("-" * 50)
        for module in unused_modules:
            print(f"   📦 {module}")

        print(f"\n📊 Total módulos sin referencias: {len(unused_modules)}")
    else:
        print(f"✅ Todos los módulos parecen estar referenciados")

if __name__ == "__main__":
    find_dead_functions()
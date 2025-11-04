#!/usr/bin/env python3
"""
Auditoría completa de tablas - Uso en código + Datos reales
"""
import sqlite3
import subprocess
import json
from pathlib import Path

DB_PATH = "unified_mcp_system.db"
SEARCH_PATHS = ["core/", "api/", "modules/", "services/"]

def get_all_tables():
    """Get all table names from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables

def search_table_usage(table_name):
    """Search for table usage in code"""
    results = {
        'mentions': 0,
        'files': [],
        'sql_queries': 0,
        'insert_queries': 0,
        'select_queries': 0,
        'update_queries': 0
    }

    for path in SEARCH_PATHS:
        try:
            # Count total mentions
            cmd = f"grep -ri '{table_name}' {path} --include='*.py' 2>/dev/null | wc -l"
            mentions = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            count = int(mentions.stdout.strip() or 0)
            results['mentions'] += count

            # Get file list
            cmd = f"grep -ril '{table_name}' {path} --include='*.py' 2>/dev/null"
            files = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if files.stdout.strip():
                results['files'].extend([f.strip() for f in files.stdout.strip().split('\n')])

            # Count SQL operations
            cmd = f"grep -ri 'FROM {table_name}\\|JOIN {table_name}' {path} --include='*.py' 2>/dev/null | wc -l"
            selects = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            results['select_queries'] += int(selects.stdout.strip() or 0)

            cmd = f"grep -ri 'INSERT INTO {table_name}' {path} --include='*.py' 2>/dev/null | wc -l"
            inserts = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            results['insert_queries'] += int(inserts.stdout.strip() or 0)

            cmd = f"grep -ri 'UPDATE {table_name}' {path} --include='*.py' 2>/dev/null | wc -l"
            updates = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            results['update_queries'] += int(updates.stdout.strip() or 0)

        except Exception as e:
            print(f"Error searching {path}: {e}")

    results['sql_queries'] = results['select_queries'] + results['insert_queries'] + results['update_queries']
    results['files'] = list(set(results['files']))[:10]  # Unique, limit to 10

    return results

def get_table_data(table_name):
    """Get real data from table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    data = {
        'total_rows': 0,
        'has_tenant_id': False,
        'tenant_distribution': {},
        'date_range': {},
        'schema': []
    }

    try:
        # Count rows
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        data['total_rows'] = cursor.fetchone()[0]

        # Check schema
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        data['schema'] = [{'name': col[1], 'type': col[2], 'notnull': col[3]} for col in columns]

        # Check if has tenant_id
        column_names = [col[1] for col in columns]
        data['has_tenant_id'] = 'tenant_id' in column_names

        # If has tenant_id, get distribution
        if data['has_tenant_id'] and data['total_rows'] > 0:
            cursor.execute(f"SELECT tenant_id, COUNT(*) FROM {table_name} GROUP BY tenant_id")
            data['tenant_distribution'] = {str(row[0]): row[1] for row in cursor.fetchall()}

        # Get date range if has created_at
        if 'created_at' in column_names and data['total_rows'] > 0:
            cursor.execute(f"SELECT MIN(created_at), MAX(created_at) FROM {table_name}")
            min_date, max_date = cursor.fetchone()
            data['date_range'] = {'min': min_date, 'max': max_date}

    except Exception as e:
        data['error'] = str(e)

    conn.close()
    return data

def classify_table(table_name, usage, data):
    """Classify table based on usage and data"""
    if data['total_rows'] == 0 and usage['mentions'] == 0:
        return 'UNUSED'
    elif data['total_rows'] == 0 and usage['mentions'] > 0:
        return 'DEFINED_NO_DATA'
    elif usage['mentions'] == 0 and data['total_rows'] > 0:
        return 'LEGACY_DATA'
    elif data['has_tenant_id']:
        return 'ACTIVE_MULTI_TENANT'
    else:
        return 'ACTIVE_NO_TENANT'

def main():
    print("🔍 AUDITORÍA DE TABLAS - INICIANDO...\n")

    tables = get_all_tables()
    print(f"Total tablas encontradas: {len(tables)}\n")

    results = {}

    for i, table in enumerate(tables, 1):
        print(f"[{i}/{len(tables)}] Analizando: {table}...", end='')

        usage = search_table_usage(table)
        data = get_table_data(table)
        classification = classify_table(table, usage, data)

        results[table] = {
            'usage': usage,
            'data': data,
            'classification': classification
        }

        print(f" ✓ ({classification})")

    # Save results
    with open('table_audit_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print("\n✅ Auditoría completa. Resultados guardados en: table_audit_results.json")

    # Generate summary
    print("\n" + "="*80)
    print("📊 RESUMEN POR CLASIFICACIÓN")
    print("="*80)

    classifications = {}
    for table, info in results.items():
        cls = info['classification']
        if cls not in classifications:
            classifications[cls] = []
        classifications[cls].append(table)

    for cls, tables in sorted(classifications.items()):
        print(f"\n{cls}: {len(tables)} tablas")
        for table in sorted(tables)[:5]:
            print(f"  - {table} ({results[table]['data']['total_rows']} rows, {results[table]['usage']['mentions']} mentions)")
        if len(tables) > 5:
            print(f"  ... y {len(tables) - 5} más")

if __name__ == '__main__':
    main()

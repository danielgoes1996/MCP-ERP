#!/usr/bin/env python3
"""
Análisis profundo de tablas DEFINED_NO_DATA
Determina si mantener, evaluar, o eliminar cada tabla
"""
import sqlite3
import subprocess
import json

DB_PATH = "unified_mcp_system.db"
SEARCH_PATHS = ["core/", "api/", "modules/", "static/"]

# Lista de 18 tablas DEFINED_NO_DATA
TABLES = [
    "tickets",
    "workers",
    "automation_screenshots",
    "automation_sessions",
    "expense_invoices",
    "system_health",
    "bank_reconciliation_feedback",
    "duplicate_detection",
    "duplicate_detections",
    "category_learning",
    "category_learning_metrics",
    "category_prediction_history",
    "expense_attachments",
    "expense_ml_features",
    "expense_tag_relations",
    "gpt_usage_events",
    "user_preferences",
    "user_sessions"
]

def analyze_table_deeply(table_name):
    """Análisis profundo de uso de tabla"""

    result = {
        'table': table_name,
        'mentions_total': 0,
        'mentions_by_type': {
            'create_table': 0,
            'insert': 0,
            'select': 0,
            'update': 0,
            'delete': 0,
            'reference': 0
        },
        'files': {
            'python': [],
            'sql': [],
            'html': []
        },
        'endpoints': [],
        'models': [],
        'services': [],
        'schema_info': {},
        'recommendation': ''
    }

    # 1. Buscar en archivos Python
    for path in SEARCH_PATHS:
        try:
            # Buscar menciones totales
            cmd = f"grep -ri '{table_name}' {path} --include='*.py' 2>/dev/null | wc -l"
            mentions = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            count = int(mentions.stdout.strip() or 0)
            result['mentions_total'] += count

            # Buscar archivos específicos
            cmd = f"grep -ril '{table_name}' {path} --include='*.py' 2>/dev/null"
            files = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if files.stdout.strip():
                result['files']['python'].extend([f.strip() for f in files.stdout.strip().split('\n')])

            # Buscar INSERTs
            cmd = f"grep -ri 'INSERT INTO {table_name}' {path} --include='*.py' 2>/dev/null | wc -l"
            inserts = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            result['mentions_by_type']['insert'] += int(inserts.stdout.strip() or 0)

            # Buscar SELECTs
            cmd = f"grep -ri 'FROM {table_name}\\|JOIN {table_name}' {path} --include='*.py' 2>/dev/null | wc -l"
            selects = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            result['mentions_by_type']['select'] += int(selects.stdout.strip() or 0)

        except Exception as e:
            print(f"Error en {path}: {e}")

    # 2. Buscar en migrations
    try:
        cmd = f"grep -ri 'CREATE TABLE.*{table_name}' migrations/ --include='*.sql' 2>/dev/null"
        creates = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if creates.stdout.strip():
            result['mentions_by_type']['create_table'] = 1
            result['files']['sql'].append('migrations/')
    except:
        pass

    # 3. Buscar en HTML/JS
    try:
        cmd = f"grep -ri '{table_name}' static/ --include='*.html' --include='*.js' 2>/dev/null | wc -l"
        html_mentions = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        html_count = int(html_mentions.stdout.strip() or 0)
        if html_count > 0:
            result['mentions_total'] += html_count
            result['files']['html'] = ['static/']
    except:
        pass

    # 4. Obtener schema
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        result['schema_info'] = {
            'columns': len(columns),
            'has_tenant_id': any(col[1] == 'tenant_id' for col in columns),
            'column_names': [col[1] for col in columns]
        }
        conn.close()
    except Exception as e:
        result['schema_info'] = {'error': str(e)}

    # 5. Clasificar archivos por tipo
    for py_file in result['files']['python']:
        if '/api/' in py_file:
            result['endpoints'].append(py_file)
        elif '/models/' in py_file or 'models.py' in py_file:
            result['models'].append(py_file)
        elif '/services/' in py_file or '/core/' in py_file:
            result['services'].append(py_file)

    # 6. Generar recomendación
    result['recommendation'] = classify_recommendation(result)

    return result

def classify_recommendation(data):
    """Clasifica tabla en: KEEP, EVALUATE, DELETE"""

    mentions = data['mentions_total']
    inserts = data['mentions_by_type']['insert']
    selects = data['mentions_by_type']['select']
    has_schema = data['mentions_by_type']['create_table'] > 0

    # Reglas de decisión
    if mentions >= 50:
        return "KEEP - Alto uso en código (50+ menciones)"

    elif mentions >= 20 and (inserts > 0 or selects > 0):
        return "KEEP - Uso moderado con queries activas"

    elif mentions >= 15 and len(data['endpoints']) > 0:
        return "KEEP - Usado en endpoints de API"

    elif inserts > 0 or selects > 0:
        return "EVALUATE - Tiene queries pero poco uso general"

    elif mentions >= 10 and has_schema:
        return "EVALUATE - Definido pero sin queries (roadmap futuro?)"

    elif mentions >= 5:
        return "EVALUATE - Poco uso, revisar si necesario"

    elif mentions <= 1 and not has_schema:
        return "DELETE - Sin schema y sin uso"

    else:
        return "DELETE - Menciones mínimas, probablemente obsoleto"

def main():
    print("🔍 ANÁLISIS PROFUNDO DE TABLAS DEFINED_NO_DATA")
    print("=" * 80)
    print(f"Analizando {len(TABLES)} tablas...\n")

    results = {}

    for i, table in enumerate(TABLES, 1):
        print(f"[{i}/{len(TABLES)}] Analizando: {table}...", end=' ')
        analysis = analyze_table_deeply(table)
        results[table] = analysis

        # Emoji según recomendación
        emoji = "✅" if "KEEP" in analysis['recommendation'] else "⚠️" if "EVALUATE" in analysis['recommendation'] else "🗑️"
        print(f"{emoji} {analysis['recommendation']}")

    # Guardar resultados
    with open('defined_no_data_analysis.json', 'w') as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 80)
    print("📊 RESUMEN POR RECOMENDACIÓN")
    print("=" * 80)

    keep = [t for t, r in results.items() if "KEEP" in r['recommendation']]
    evaluate = [t for t, r in results.items() if "EVALUATE" in r['recommendation']]
    delete = [t for t, r in results.items() if "DELETE" in r['recommendation']]

    print(f"\n✅ KEEP ({len(keep)} tablas):")
    for table in keep:
        print(f"  - {table}: {results[table]['mentions_total']} menciones, "
              f"{results[table]['mentions_by_type']['insert']} INSERTs, "
              f"{results[table]['mentions_by_type']['select']} SELECTs")

    print(f"\n⚠️ EVALUATE ({len(evaluate)} tablas):")
    for table in evaluate:
        print(f"  - {table}: {results[table]['mentions_total']} menciones, "
              f"{results[table]['mentions_by_type']['insert']} INSERTs, "
              f"{results[table]['mentions_by_type']['select']} SELECTs")

    print(f"\n🗑️ DELETE ({len(delete)} tablas):")
    for table in delete:
        print(f"  - {table}: {results[table]['mentions_total']} menciones")

    print("\n✅ Resultados guardados en: defined_no_data_analysis.json")
    print("\nPróximo paso: Revisar archivo JSON para detalles completos")

if __name__ == '__main__':
    main()

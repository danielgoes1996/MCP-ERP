#!/usr/bin/env python3
"""
Auditoría urgente: ¿Qué funciona AHORA para la demo?
"""
import os
import sys

print("="*80)
print("🔍 AUDITORÍA URGENTE - DEMO VC MAÑANA")
print("="*80)
print()

# 1. Verificar tablas PostgreSQL
print("1. TABLAS POSTGRESQL:")
os.system("""
PGPASSWORD=changeme psql -h 127.0.0.1 -p 5433 -U mcp_user -d mcp_system -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY tablename
" 2>&1 | grep -v "Password\|Contraseña"
""")

print()
print("2. ESTADO CONCILIACIÓN ENERO:")
os.system("""
PGPASSWORD=changeme psql -h 127.0.0.1 -p 5433 -U mcp_user -d mcp_system -c "
SELECT 
    COUNT(*) FILTER (WHERE linked_expense_id IS NOT NULL) as conciliados,
    COUNT(*) as total,
    ROUND(COUNT(*) FILTER (WHERE linked_expense_id IS NOT NULL)::numeric / COUNT(*)::numeric * 100, 1) as porcentaje
FROM expense_invoices
WHERE EXTRACT(YEAR FROM fecha_emision) = 2025
AND EXTRACT(MONTH FROM fecha_emision) = 1
AND tipo_comprobante = 'I'
" 2>&1 | grep -v "Password\|Contraseña"
""")

print()
print("3. MÓDULOS CLAVE:")

# Verificar archivos clave
modulos = {
    "✅ Extracción Gemini": "extraer_msi_gemini.py",
    "✅ Config Centralizada": "core/shared/db_config.py",
    "✅ Matching Embeddings": "core/reconciliation/embedding_matcher.py",
    "⚠️  API Main": "main.py",
    "⚠️  Frontend": "frontend/src",
}

for nombre, ruta in modulos.items():
    existe = "✅" if os.path.exists(ruta) else "❌"
    print(f"{existe} {nombre}: {ruta}")

print()
print("4. SCRIPTS CRÍTICOS PARA DEMO:")
scripts_demo = [
    "extraer_msi_gemini.py",
    "aplicar_conciliacion_amex.py", 
    "sincronizar_conciliaciones.py",
    "validar_antes_de_procesar.py",
]

for script in scripts_demo:
    existe = "✅" if os.path.exists(script) else "❌"
    print(f"{existe} {script}")

print()
print("5. DATOS DE PRUEBA:")
os.system("""
PGPASSWORD=changeme psql -h 127.0.0.1 -p 5433 -U mcp_user -d mcp_system -c "
SELECT 
    'CFDIs Enero' as item,
    COUNT(*) as cantidad,
    SUM(total) as monto_total
FROM expense_invoices
WHERE EXTRACT(YEAR FROM fecha_emision) = 2025
AND EXTRACT(MONTH FROM fecha_emision) = 1

UNION ALL

SELECT 
    'Transacciones Banco Enero',
    COUNT(*),
    SUM(ABS(amount))
FROM bank_transactions
WHERE EXTRACT(YEAR FROM transaction_date) = 2025
AND EXTRACT(MONTH FROM transaction_date) = 1
" 2>&1 | grep -v "Password\|Contraseña"
""")

print()
print("="*80)
print("FIN AUDITORÍA")
print("="*80)

#!/usr/bin/env python3
"""
Compare references found in PDF vs database to find missing transactions
"""
import sys
sys.path.append('.')
import sqlite3
import re
from core.robust_pdf_parser import RobustPDFParser

def compare_references():
    # Get references from PDF
    pdf_path = "./uploads/statements/9_20250928_211924_Periodo_DIC 2024 (1).pdf"
    parser = RobustPDFParser()
    text = parser.extract_text(pdf_path)
    lines = text.split('\n')

    pdf_references = set()
    for line in lines:
        line_clean = line.strip()
        match = re.search(r'DIC\.\s+\d{1,2}\s+(\d{8,12})\s+', line_clean)
        if match:
            reference = match.group(1)
            pdf_references.add(reference)

    print(f"📄 Referencias en PDF: {len(pdf_references)}")

    # Get references from database
    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT reference
        FROM bank_movements
        WHERE user_id = 9 AND tenant_id = 3 AND account_id = 7
        AND date LIKE '2024-12%'
        AND reference IS NOT NULL AND reference != ''
    """)

    db_references = set(row[0] for row in cursor.fetchall())
    conn.close()

    print(f"💾 Referencias en BD: {len(db_references)}")

    # Find missing references
    missing_refs = pdf_references - db_references
    extra_refs = db_references - pdf_references

    print(f"\n❌ Referencias faltantes en BD: {len(missing_refs)}")
    if missing_refs:
        for ref in sorted(missing_refs):
            print(f"  - {ref}")

    print(f"\n➕ Referencias extra en BD: {len(extra_refs)}")
    if extra_refs:
        for ref in sorted(extra_refs):
            print(f"  - {ref}")

    print(f"\n📊 RESUMEN:")
    print(f"  - PDF: {len(pdf_references)} referencias únicas")
    print(f"  - BD: {len(db_references)} referencias únicas")
    print(f"  - Faltantes: {len(missing_refs)}")
    print(f"  - BD total transacciones: 69")
    print(f"  - Coincidencia: {len(pdf_references & db_references)}")

if __name__ == "__main__":
    compare_references()
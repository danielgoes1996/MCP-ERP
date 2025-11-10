#!/usr/bin/env python3
"""
Analyze why specific references are not being extracted
"""
import sys
sys.path.append('.')
import re
from core.ai_pipeline.parsers.robust_pdf_parser import RobustPDFParser

def analyze_missing_references():
    pdf_path = "./uploads/statements/9_20250928_211924_Periodo_DIC 2024 (1).pdf"

    # Missing references from comparison
    missing_refs = [
        '3218488397', '3221086629', '3221933442', '3223875681', '3224740709',
        '3234448830', '3234764406', '3236182874', '3238665332', '3242294952',
        '3243233071', '3244031794', '3251302789', '3252078952', '3253416801',
        '3256078102'
    ]

    parser = RobustPDFParser()
    text = parser.extract_text(pdf_path)
    lines = text.split('\n')

    print(f"🔍 Analizando {len(missing_refs)} referencias faltantes...\n")

    for ref in missing_refs:
        print(f"📍 Referencia: {ref}")
        found_lines = []

        for i, line in enumerate(lines):
            if ref in line:
                found_lines.append((i+1, line.strip()))

        if found_lines:
            print(f"  ✅ Encontrada en {len(found_lines)} línea(s):")
            for line_num, line_content in found_lines:
                print(f"    Línea {line_num}: {line_content}")

                # Test against Pattern 1 (with reference)
                pattern1 = r'((?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.\s+\d{1,2})\s+(\d{8,12})\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)'
                match1 = re.search(pattern1, line_content)
                if match1:
                    print(f"      ✅ Coincide con Patrón 1: {match1.groups()}")
                else:
                    print(f"      ❌ NO coincide con Patrón 1")

                    # Test line structure
                    parts = line_content.split()
                    print(f"      📝 Partes de la línea ({len(parts)}): {parts[:8]}...")
        else:
            print(f"  ❌ NO encontrada en el PDF")

        print()

if __name__ == "__main__":
    analyze_missing_references()
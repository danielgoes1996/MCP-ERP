#!/usr/bin/env python3
"""
Guardar chunks que recibe el LLM en archivos para revisión
"""

import os
from core.ai_pipeline.parsers.robust_pdf_parser import RobustPDFParser
from core.llm_pdf_parser import LLMPDFParser

def guardar_chunks_para_revision():
    """Guarda los chunks en archivos separados"""

    print("💾 GUARDANDO CHUNKS PARA REVISIÓN...")

    pdf_path = "/Users/danielgoes96/Desktop/mcp-server/uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf"

    # Extraer texto
    robust_parser = RobustPDFParser()
    texto_completo = robust_parser.extract_text(pdf_path)

    # Dividir en chunks
    llm_parser = LLMPDFParser()
    chunks = llm_parser._split_text_for_llm(texto_completo)

    print(f"📊 Total chunks encontrados: {len(chunks)}")

    for i, chunk in enumerate(chunks):
        filename = f"chunk_{i+1}_llm_input.txt"

        newlines = chunk.count('\n')
        jul_count = chunk.upper().count('JUL.')

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"CHUNK {i+1} - TEXTO ENVIADO AL LLM\n")
            f.write("=" * 80 + "\n")
            f.write(f"Tamaño: {len(chunk):,} caracteres\n")
            f.write(f"Líneas: {newlines:,}\n")
            f.write(f"Fechas JUL.: {jul_count}\n")
            f.write("=" * 80 + "\n\n")
            f.write(chunk)

        print(f"✅ Guardado: {filename} ({len(chunk):,} chars, {jul_count} fechas JUL.)")

    # También guardar el texto completo original
    with open("texto_completo_original.txt", 'w', encoding='utf-8') as f:
        f.write("TEXTO COMPLETO EXTRAÍDO DEL PDF\n")
        f.write("=" * 80 + "\n")
        f.write(f"Tamaño total: {len(texto_completo):,} caracteres\n")
        f.write(f"Total fechas JUL.: {texto_completo.upper().count('JUL.')}\n")
        f.write("=" * 80 + "\n\n")
        f.write(texto_completo)

    print(f"✅ Guardado: texto_completo_original.txt")

    print(f"\n📁 Archivos creados:")
    print(f"   • chunk_1_llm_input.txt")
    print(f"   • chunk_2_llm_input.txt")
    print(f"   • texto_completo_original.txt")

    print(f"\n🔍 ANÁLISIS RÁPIDO:")
    total_jul_chunks = sum(chunk.upper().count('JUL.') for chunk in chunks)
    total_jul_original = texto_completo.upper().count('JUL.')

    print(f"   Fechas JUL. en original: {total_jul_original}")
    print(f"   Fechas JUL. suma chunks: {total_jul_chunks}")
    print(f"   Diferencia: {total_jul_original - total_jul_chunks}")

    if total_jul_original == total_jul_chunks:
        print("   ✅ Sin pérdida de fechas en chunks")
    else:
        print("   ⚠️ Se perdieron fechas al dividir")

if __name__ == "__main__":
    guardar_chunks_para_revision()
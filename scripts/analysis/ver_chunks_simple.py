#!/usr/bin/env python3
"""
Ver chunks de texto extraído de forma simple
"""

import os
from core.ai_pipeline.parsers.robust_pdf_parser import RobustPDFParser
from core.llm_pdf_parser import LLMPDFParser

def mostrar_chunks():
    """Muestra los chunks extraídos"""

    print("🔍 CHUNKS DE TEXTO EXTRAÍDO")
    print("=" * 60)

    pdf_path = "/Users/danielgoes96/Desktop/mcp-server/uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf"

    if not os.path.exists(pdf_path):
        print(f"❌ PDF no encontrado")
        return

    # Extraer texto
    robust_parser = RobustPDFParser()
    texto_completo = robust_parser.extract_text(pdf_path)

    newlines = texto_completo.count('\n')
    print(f"✅ Texto extraído: {len(texto_completo):,} caracteres")
    print(f"📏 Líneas totales: {newlines:,}")

    # Dividir en chunks
    llm_parser = LLMPDFParser()
    chunks = llm_parser._split_text_for_llm(texto_completo)

    print(f"✅ Total chunks: {len(chunks)}")

    # Mostrar cada chunk
    for i, chunk in enumerate(chunks):
        print(f"\n{'='*80}")
        print(f"📦 CHUNK {i+1} de {len(chunks)}")
        print(f"{'='*80}")

        chunk_newlines = chunk.count('\n')
        print(f"📏 Tamaño: {len(chunk):,} caracteres")
        print(f"📄 Líneas: {chunk_newlines:,}")

        # Contar indicadores
        jul_count = chunk.upper().count('JUL.')
        deposito_count = chunk.upper().count('DEPOSITO')
        spei_count = chunk.upper().count('SPEI')

        print(f"📊 Indicadores:")
        print(f"   • JUL.: {jul_count}")
        print(f"   • DEPOSITO: {deposito_count}")
        print(f"   • SPEI: {spei_count}")

        # Mostrar primeras líneas
        lineas = chunk.split('\n')
        print(f"\n📋 PRIMERAS 20 LÍNEAS:")
        print("-" * 60)

        for j, linea in enumerate(lineas[:20]):
            if linea.strip():
                print(f"{j+1:3d}: {linea.strip()}")

        # Buscar líneas con fechas
        lineas_fecha = []
        for linea in lineas:
            linea_clean = linea.strip()
            if linea_clean.startswith('JUL.'):
                lineas_fecha.append(linea_clean)

        if lineas_fecha:
            print(f"\n📅 LÍNEAS CON FECHAS JUL. ({len(lineas_fecha)}):")
            print("-" * 40)
            for k, linea_fecha in enumerate(lineas_fecha[:5]):
                print(f"{k+1:2d}: {linea_fecha}")
            if len(lineas_fecha) > 5:
                print(f"     ... y {len(lineas_fecha) - 5} más")

        print(f"\n📋 ÚLTIMAS 5 LÍNEAS:")
        print("-" * 30)
        for j, linea in enumerate(lineas[-5:]):
            if linea.strip():
                line_num = len(lineas) - 5 + j + 1
                print(f"{line_num:3d}: {linea.strip()}")

        # Pausa entre chunks
        if i < len(chunks) - 1:
            print(f"\n⏸️  Presiona ENTER para continuar...")
            input()

if __name__ == "__main__":
    mostrar_chunks()
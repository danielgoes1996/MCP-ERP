#!/usr/bin/env python3
"""
Mostrar los chunks de texto extraído tal como se envían a OpenAI
"""

import os
from core.ai_pipeline.parsers.robust_pdf_parser import RobustPDFParser
from core.llm_pdf_parser import LLMPDFParser

def mostrar_chunks_completos():
    """Muestra todos los chunks extraídos del PDF"""

    print("🔍 CHUNKS DE TEXTO EXTRAÍDO")
    print("=" * 60)

    pdf_path = "/Users/danielgoes96/Desktop/mcp-server/uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf"

    if not os.path.exists(pdf_path):
        print(f"❌ PDF no encontrado: {pdf_path}")
        return

    # 1. Extraer texto completo
    print("📄 PASO 1: Extrayendo texto completo del PDF...")
    robust_parser = RobustPDFParser()
    texto_completo = robust_parser.extract_text(pdf_path)

    print(f"✅ Texto extraído: {len(texto_completo):,} caracteres")
    print(f"📏 Líneas totales: {texto_completo.count('\\n'):,}")

    # 2. Dividir en chunks
    print("\\n📦 PASO 2: Dividiendo en chunks...")
    llm_parser = LLMPDFParser()
    chunks = llm_parser._split_text_for_llm(texto_completo)

    print(f"✅ Total chunks creados: {len(chunks)}")

    # 3. Mostrar cada chunk
    for i, chunk in enumerate(chunks):
        print(f"\\n{'='*80}")
        print(f"📦 CHUNK {i+1} de {len(chunks)}")
        print(f"{'='*80}")
        print(f"📏 Tamaño: {len(chunk):,} caracteres")
        print(f"📄 Líneas: {chunk.count('\\n'):,}")

        # Contar indicadores de transacciones
        jul_count = chunk.upper().count('JUL.')
        deposito_count = chunk.upper().count('DEPOSITO')
        spei_count = chunk.upper().count('SPEI')
        cargo_count = chunk.upper().count('CARGO')
        abono_count = chunk.upper().count('ABONO')

        print(f"📊 Indicadores encontrados:")
        print(f"   • JUL.: {jul_count}")
        print(f"   • DEPOSITO: {deposito_count}")
        print(f"   • SPEI: {spei_count}")
        print(f"   • CARGO: {cargo_count}")
        print(f"   • ABONO: {abono_count}")

        # Mostrar las primeras 30 líneas del chunk
        lineas = chunk.split('\\n')
        print(f"\\n📋 PRIMERAS 30 LÍNEAS DEL CHUNK:")
        print("-" * 60)
        for j, linea in enumerate(lineas[:30]):
            if linea.strip():
                print(f"{j+1:3d}: {linea.strip()}")

        if len(lineas) > 30:
            print(f"     ... y {len(lineas) - 30} líneas más")

        # Buscar líneas que empiecen con fechas
        lineas_fecha = []
        for linea in lineas:
            linea_clean = linea.strip()
            if linea_clean.startswith('JUL.') or 'JUL' in linea_clean[:10]:
                lineas_fecha.append(linea_clean)

        if lineas_fecha:
            print(f"\\n📅 LÍNEAS CON FECHAS DETECTADAS ({len(lineas_fecha)}):")
            print("-" * 40)
            for k, linea_fecha in enumerate(lineas_fecha[:10]):  # Solo primeras 10
                print(f"{k+1:2d}: {linea_fecha}")
            if len(lineas_fecha) > 10:
                print(f"     ... y {len(lineas_fecha) - 10} líneas más con fechas")

        # Mostrar las últimas 10 líneas del chunk
        print(f"\\n📋 ÚLTIMAS 10 LÍNEAS DEL CHUNK:")
        print("-" * 40)
        for j, linea in enumerate(lineas[-10:], len(lineas)-9):
            if linea.strip():
                print(f"{j:3d}: {linea.strip()}")

        # Pausa para revisión
        if i < len(chunks) - 1:
            print(f"\\n⏸️  Presiona ENTER para ver el siguiente chunk...")
            input()

def analizar_distribucion_transacciones():
    """Analiza cómo se distribuyen las transacciones entre chunks"""

    print(f"\\n🔍 ANÁLISIS DE DISTRIBUCIÓN")
    print("=" * 50)

    pdf_path = "/Users/danielgoes96/Desktop/mcp-server/uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf"

    robust_parser = RobustPDFParser()
    texto_completo = robust_parser.extract_text(pdf_path)

    llm_parser = LLMPDFParser()
    chunks = llm_parser._split_text_for_llm(texto_completo)

    total_jul = 0
    for i, chunk in enumerate(chunks):
        jul_count = chunk.upper().count('JUL.')
        total_jul += jul_count
        print(f"Chunk {i+1}: {jul_count:2d} fechas JUL.")

    # Contar total en texto completo
    total_jul_completo = texto_completo.upper().count('JUL.')

    print(f"\\n📊 RESUMEN:")
    print(f"   Fechas JUL. en texto completo: {total_jul_completo}")
    print(f"   Fechas JUL. suma de chunks: {total_jul}")
    print(f"   Diferencia: {total_jul_completo - total_jul}")

    if total_jul_completo == total_jul:
        print("   ✅ Todas las fechas están en los chunks")
    else:
        print("   ⚠️ Algunas fechas se perdieron al dividir en chunks")

if __name__ == "__main__":
    mostrar_chunks_completos()
    analizar_distribucion_transacciones()
#!/usr/bin/env python3
"""
Ver chunks completos sin pausas
"""

from core.robust_pdf_parser import RobustPDFParser
from core.llm_pdf_parser import LLMPDFParser

def mostrar_todos_chunks():
    """Muestra todos los chunks sin pausas"""

    print("🔍 ANÁLISIS COMPLETO DE CHUNKS")
    print("=" * 60)

    pdf_path = "/Users/danielgoes96/Desktop/mcp-server/uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf"

    # Extraer texto
    robust_parser = RobustPDFParser()
    texto_completo = robust_parser.extract_text(pdf_path)

    # Dividir en chunks
    llm_parser = LLMPDFParser()
    chunks = llm_parser._split_text_for_llm(texto_completo)

    print(f"📄 Texto total: {len(texto_completo):,} caracteres")
    print(f"📦 Total chunks: {len(chunks)}")

    total_jul_chunks = 0

    # Mostrar cada chunk
    for i, chunk in enumerate(chunks):
        print(f"\n{'='*80}")
        print(f"📦 CHUNK {i+1} de {len(chunks)}")
        print(f"{'='*80}")

        jul_count = chunk.upper().count('JUL.')
        total_jul_chunks += jul_count

        print(f"📏 Tamaño: {len(chunk):,} caracteres")
        print(f"📊 Fechas JUL.: {jul_count}")

        # Buscar líneas con fechas
        lineas = chunk.split('\n')
        lineas_fecha = []
        for linea in lineas:
            linea_clean = linea.strip()
            if linea_clean.startswith('JUL.'):
                lineas_fecha.append(linea_clean)

        if lineas_fecha:
            print(f"\n📅 PRIMERAS 10 LÍNEAS CON FECHAS:")
            for k, linea_fecha in enumerate(lineas_fecha[:10]):
                print(f"  {k+1:2d}: {linea_fecha}")
            if len(lineas_fecha) > 10:
                print(f"      ... y {len(lineas_fecha) - 10} más")

            print(f"\n📅 ÚLTIMAS 5 LÍNEAS CON FECHAS:")
            for k, linea_fecha in enumerate(lineas_fecha[-5:]):
                print(f"  {k+1:2d}: {linea_fecha}")

    # Comparar con total en texto
    total_jul_texto = texto_completo.upper().count('JUL.')

    print(f"\n🔍 RESUMEN FINAL:")
    print(f"   Fechas JUL. en texto completo: {total_jul_texto}")
    print(f"   Fechas JUL. suma de chunks: {total_jul_chunks}")
    print(f"   Diferencia: {total_jul_texto - total_jul_chunks}")

    if total_jul_texto == total_jul_chunks:
        print("   ✅ Todas las fechas están preservadas en chunks")
    else:
        print("   ⚠️ Se perdieron fechas al dividir en chunks")

    # Conteo esperado vs encontrado
    print(f"\n🎯 COMPARACIÓN CON OBJETIVO:")
    print(f"   Fechas encontradas: {total_jul_chunks}")
    print(f"   Objetivo (86 total): 86")
    print(f"   Balance inicial: 1 (no cuenta como JUL.)")
    print(f"   Transacciones esperadas: 85")

    if total_jul_chunks >= 85:
        print("   ✅ Suficientes fechas encontradas")
    else:
        print(f"   ❌ Faltan {85 - total_jul_chunks} fechas")

if __name__ == "__main__":
    mostrar_todos_chunks()
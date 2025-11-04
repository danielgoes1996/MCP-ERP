#!/usr/bin/env python3
"""
Resumen simple del parsing actual
"""

import os
import sqlite3

def mostrar_resumen_parsing():
    """Muestra un resumen del proceso de parsing actual"""

    print("🔍 RESUMEN DEL PARSING ACTUAL")
    print("=" * 50)

    # 1. INPUT: PDF
    pdf_path = "./uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf"
    print("📄 INPUT:")
    print(f"   PDF: {os.path.basename(pdf_path)}")
    if os.path.exists(pdf_path):
        print(f"   Tamaño: {os.path.getsize(pdf_path):,} bytes")
        print("   ✅ Archivo existe")
    else:
        print("   ❌ Archivo no encontrado")

    # 2. PROCESO
    print("\n🔄 PROCESO:")
    print("   1. Extracción texto RAW del PDF (RobustPDFParser)")
    print("   2. División del texto en chunks (~20,000 chars)")
    print("   3. Envío de cada chunk a OpenAI (Claude API)")
    print("   4. Conversión JSON response → BankTransaction objects")
    print("   5. Eliminación de duplicados")
    print("   6. Validación de completitud")
    print("   7. Guardado en base de datos")

    # 3. CONFIGURACIÓN ACTUAL
    print("\n⚙️ CONFIGURACIÓN:")
    print("   🤖 Modelo: claude-3-haiku-20240307")
    print("   🎯 Max tokens: 6,000")
    print("   🌡️ Temperature: 0 (determinista)")
    print("   📊 Chunk size: ~20,000 caracteres")

    # 4. PROMPT USADO
    print("\n📝 PROMPT USADO (resumen):")
    print("   • Analizar estado de cuenta bancario")
    print("   • Extraer transacciones con descripción mejorada")
    print("   • Reglas anti-duplicados (SPEI, mismo monto +/-)")
    print("   • Categorizar automáticamente")
    print("   • Formato fechas: JUL. 14 → 2024-07-14")
    print("   • Montos: CARGOS = negativo, ABONOS = positivo")
    print("   • Respuesta: JSON con array de transactions")

    # 5. OUTPUT ESPERADO
    print("\n📤 OUTPUT ESPERADO:")
    print("   JSON con structure:")
    print("   {")
    print("     \"transactions\": [")
    print("       {")
    print("         \"date\": \"2025-07-01\",")
    print("         \"description\": \"Descripción completa\",")
    print("         \"category\": \"Categoría\",")
    print("         \"amount\": -378.85")
    print("       }")
    print("     ]")
    print("   }")

    # 6. ESTADO ACTUAL BD
    print("\n📊 ESTADO ACTUAL BD:")
    try:
        conn = sqlite3.connect('unified_mcp_system.db')
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM bank_movements
            WHERE account_id = 5 AND user_id = 9
        """)
        total = cursor.fetchone()[0]

        cursor.execute("""
            SELECT
                CASE
                    WHEN amount > 0 THEN 'ABONOS'
                    WHEN amount < 0 THEN 'CARGOS'
                    ELSE 'BALANCE'
                END as tipo,
                COUNT(*) as cantidad
            FROM bank_movements
            WHERE account_id = 5 AND user_id = 9
            GROUP BY tipo
        """)

        tipos = cursor.fetchall()
        conn.close()

        print(f"   Total transacciones: {total}")
        for tipo, cantidad in tipos:
            print(f"   {tipo}: {cantidad}")

        print(f"\n🎯 OBJETIVO:")
        print(f"   Total: 86 transacciones")
        print(f"   ABONOS: 40")
        print(f"   CARGOS: 45")
        print(f"   BALANCE: 1")
        print(f"   Faltan: {86 - total}")

    except Exception as e:
        print(f"   ❌ Error consultando BD: {e}")

def mostrar_chunks_detectados():
    """Muestra cuántos chunks se detectarían con el texto actual"""

    print("\n🔍 ANÁLISIS DE CHUNKS")
    print("=" * 30)

    try:
        from core.robust_pdf_parser import RobustPDFParser
        from core.llm_pdf_parser import LLMPDFParser

        pdf_path = "./uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf"

        if not os.path.exists(pdf_path):
            print("❌ PDF no encontrado")
            return

        # Extraer texto
        parser = RobustPDFParser()
        texto = parser.extract_text(pdf_path)

        # Dividir en chunks
        llm_parser = LLMPDFParser()
        chunks = llm_parser._split_text_for_llm(texto)

        print(f"📊 Texto total: {len(texto):,} caracteres")
        print(f"📦 Total chunks: {len(chunks)}")

        for i, chunk in enumerate(chunks):
            # Contar transacciones potenciales
            jul_count = chunk.upper().count('JUL.')
            print(f"   Chunk {i+1}: {len(chunk):,} chars, ~{jul_count} transacciones JUL")

        # Indicadores de transacciones
        indicadores = ['JUL.', 'DEPOSITO', 'SPEI', 'CARGO', 'ABONO']
        for indicador in indicadores:
            count = texto.upper().count(indicador)
            print(f"📍 Indicador '{indicador}': {count} ocurrencias")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    mostrar_resumen_parsing()
    mostrar_chunks_detectados()
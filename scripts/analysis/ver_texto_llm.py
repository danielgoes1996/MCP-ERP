#!/usr/bin/env python3
"""
Mostrar el texto exacto que recibe el LLM en cada chunk
"""

import os
from core.robust_pdf_parser import RobustPDFParser
from core.llm_pdf_parser import LLMPDFParser

def mostrar_texto_llm_chunks():
    """Muestra el texto exacto que se envía al LLM"""

    print("📄 TEXTO EXACTO ENVIADO AL LLM")
    print("=" * 60)

    pdf_path = "/Users/danielgoes96/Desktop/mcp-server/uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf"

    # Extraer texto
    robust_parser = RobustPDFParser()
    texto_completo = robust_parser.extract_text(pdf_path)

    # Dividir en chunks
    llm_parser = LLMPDFParser()
    chunks = llm_parser._split_text_for_llm(texto_completo)

    print(f"📊 Total chunks: {len(chunks)}")

    for i, chunk in enumerate(chunks):
        print(f"\n{'='*100}")
        print(f"📦 CHUNK {i+1} - TEXTO COMPLETO QUE RECIBE EL LLM")
        print(f"{'='*100}")
        print(f"📏 Tamaño: {len(chunk):,} caracteres")
        print(f"📄 Líneas: {chunk.count('\\n'):,}")

        jul_count = chunk.upper().count('JUL.')
        print(f"🔍 Fechas JUL.: {jul_count}")

        print(f"\n{'📄 INICIO DEL CHUNK':-^80}")

        # Mostrar las primeras 100 líneas del chunk
        lineas = chunk.split('\\n')
        print(f"\\n[PRIMERAS 100 LÍNEAS DEL CHUNK {i+1}]")
        print("-" * 80)

        for j, linea in enumerate(lineas[:100]):
            print(f"{j+1:4d}: {linea}")

        if len(lineas) > 100:
            print(f"\\n... [OMITIDAS {len(lineas) - 200} LÍNEAS INTERMEDIAS] ...")

            # Mostrar las últimas 100 líneas
            print(f"\\n[ÚLTIMAS 100 LÍNEAS DEL CHUNK {i+1}]")
            print("-" * 80)

            for j, linea in enumerate(lineas[-100:], len(lineas) - 99):
                print(f"{j:4d}: {linea}")

        print(f"\\n{'📄 FIN DEL CHUNK':-^80}")

        # Mostrar solo las líneas que contienen fechas JUL.
        print(f"\\n🔍 LÍNEAS CON FECHAS JUL. EN ESTE CHUNK:")
        print("-" * 60)

        jul_lineas = []
        for j, linea in enumerate(lineas):
            if 'JUL.' in linea.upper():
                jul_lineas.append((j+1, linea.strip()))

        for line_num, linea in jul_lineas:
            print(f"{line_num:4d}: {linea}")

        print(f"\\n📊 RESUMEN CHUNK {i+1}:")
        print(f"   Total líneas: {len(lineas)}")
        print(f"   Líneas con JUL.: {len(jul_lineas)}")
        print(f"   Caracteres: {len(chunk):,}")

        # Pausa entre chunks si hay más de uno
        if i < len(chunks) - 1:
            print(f"\\n{'⏸️ PRESIONA ENTER PARA VER EL SIGUIENTE CHUNK':-^80}")
            input()

def guardar_chunks_archivo():
    """Guarda los chunks en archivos separados para revisión"""

    print("\\n💾 GUARDANDO CHUNKS EN ARCHIVOS...")

    pdf_path = "/Users/danielgoes96/Desktop/mcp-server/uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf"

    # Extraer texto
    robust_parser = RobustPDFParser()
    texto_completo = robust_parser.extract_text(pdf_path)

    # Dividir en chunks
    llm_parser = LLMPDFParser()
    chunks = llm_parser._split_text_for_llm(texto_completo)

    for i, chunk in enumerate(chunks):
        filename = f"chunk_{i+1}_llm_input.txt"

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"CHUNK {i+1} - TEXTO ENVIADO AL LLM\\n")
            f.write("=" * 80 + "\\n")
            f.write(f"Tamaño: {len(chunk):,} caracteres\\n")
            f.write(f"Líneas: {chunk.count('\\n'):,}\\n")
            f.write(f"Fechas JUL.: {chunk.upper().count('JUL.')}\\n")
            f.write("=" * 80 + "\\n\\n")
            f.write(chunk)

        print(f"✅ Guardado: {filename}")

    print(f"\\n📁 Se guardaron {len(chunks)} archivos de chunks")

if __name__ == "__main__":
    print("1. Mostrar chunks en terminal")
    print("2. Guardar chunks en archivos")
    print("3. Ambos")

    try:
        opcion = input("\\nElige opción (1/2/3): ").strip()
    except EOFError:
        opcion = "3"  # Default para scripts automáticos

    if opcion in ["1", "3"]:
        mostrar_texto_llm_chunks()

    if opcion in ["2", "3"]:
        guardar_chunks_archivo()
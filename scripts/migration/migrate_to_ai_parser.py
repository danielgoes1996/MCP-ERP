"""
Script de migración a AI-driven parser

Este script te ayuda a:
1. Verificar configuración de Gemini
2. Probar AI parser con archivos existentes
3. Comparar resultados AI vs tradicional
4. Migrar gradualmente
"""

import os
import sys
from pathlib import Path
import time
import argparse
from typing import List, Dict, Any

# Agregar path del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def check_configuration():
    """Verifica configuración necesaria"""

    print("🔍 Verificando configuración...\n")

    # Verificar GEMINI_API_KEY
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY no configurada")
        print("\nPara configurarla:")
        print("1. Ve a https://ai.google.dev/")
        print("2. Obtén tu API key gratuita")
        print("3. Agrégala a .env:")
        print("   echo 'GEMINI_API_KEY=tu-api-key-aqui' >> .env\n")
        return False
    else:
        print(f"✅ GEMINI_API_KEY configurada ({api_key[:10]}...)")

    # Verificar google-generativeai
    try:
        import google.generativeai as genai
        print("✅ google-generativeai instalado")
    except ImportError:
        print("❌ google-generativeai no instalado")
        print("\nPara instalarlo:")
        print("   pip install google-generativeai\n")
        return False

    # Verificar PostgreSQL
    postgres_host = os.getenv("POSTGRES_HOST", "127.0.0.1")
    postgres_port = os.getenv("POSTGRES_PORT", "5433")
    print(f"✅ PostgreSQL configurado ({postgres_host}:{postgres_port})")

    # Verificar flags
    ai_enabled = os.getenv("AI_PARSER_ENABLED", "true").lower() == "true"
    fallback_enabled = os.getenv("AI_FALLBACK_ENABLED", "true").lower() == "true"

    print(f"{'✅' if ai_enabled else '⚠️ '} AI_PARSER_ENABLED={ai_enabled}")
    print(f"{'✅' if fallback_enabled else '⚠️ '} AI_FALLBACK_ENABLED={fallback_enabled}")

    print("\n✅ Configuración completa\n")
    return True


def test_gemini_connection():
    """Prueba conexión con Gemini"""

    print("🔌 Probando conexión con Gemini...\n")

    try:
        import google.generativeai as genai

        api_key = os.getenv("GEMINI_API_KEY")
        genai.configure(api_key=api_key)

        # Crear modelo
        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        # Test simple
        response = model.generate_content("Di 'Hola' en JSON: {\"message\": \"...\"}")

        print(f"✅ Conexión exitosa")
        print(f"   Respuesta: {response.text[:100]}\n")

        return True

    except Exception as e:
        print(f"❌ Error conectando con Gemini: {e}\n")
        return False


def compare_parsers(pdf_path: str):
    """Compara resultados AI vs tradicional"""

    print(f"⚖️  Comparando parsers: {pdf_path}\n")

    # Parser AI
    print("🤖 Probando AI Parser...")
    ai_start = time.time()

    try:
        from core.ai_pipeline.ai_bank_orchestrator import get_ai_orchestrator

        orchestrator = get_ai_orchestrator()
        ai_result = orchestrator.process_bank_statement(
            pdf_path=pdf_path,
            account_id=1,
            company_id=1,
            user_id=1,
            tenant_id="test"
        )

        ai_time = time.time() - ai_start

        if ai_result.success:
            print(f"   ✅ Éxito en {ai_time:.2f}s")
            print(f"   Transacciones: {ai_result.transactions_created}")
            print(f"   MSI: {len(ai_result.msi_matches)}")
            if ai_result.statement_data:
                print(f"   Banco: {ai_result.statement_data.bank_name}")
                print(f"   Tipo: {ai_result.statement_data.account_type}")
                print(f"   Confianza: {ai_result.statement_data.confidence:.2%}")
        else:
            print(f"   ❌ Error: {ai_result.error}")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        ai_result = None
        ai_time = 0

    print()

    # Parser tradicional
    print("📋 Probando Parser Tradicional...")
    trad_start = time.time()

    try:
        from core.reconciliation.bank.bank_file_parser import bank_file_parser

        transactions, summary = bank_file_parser.parse(pdf_path, account_id=1)

        trad_time = time.time() - trad_start

        print(f"   ✅ Éxito en {trad_time:.2f}s")
        print(f"   Transacciones: {len(transactions)}")
        print(f"   Banco: {summary.get('bank', 'Unknown')}")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        transactions = []
        trad_time = 0

    print()

    # Comparación
    print("📊 COMPARACIÓN:")
    print("-" * 60)

    if ai_result and ai_result.success and transactions:
        print(f"{'Métrica':<25} {'AI':<15} {'Tradicional':<15} {'Diferencia'}")
        print("-" * 60)

        ai_txs = ai_result.transactions_created
        trad_txs = len(transactions)
        diff_txs = ai_txs - trad_txs

        print(f"{'Transacciones':<25} {ai_txs:<15} {trad_txs:<15} {diff_txs:+d}")
        print(f"{'Tiempo (s)':<25} {ai_time:<15.2f} {trad_time:<15.2f} {ai_time - trad_time:+.2f}")

        if ai_result.statement_data:
            print(f"{'Confianza AI':<25} {ai_result.statement_data.confidence:.2%}")

    print()


def batch_test(directory: str):
    """Prueba AI parser con múltiples archivos"""

    print(f"📁 Prueba batch en: {directory}\n")

    pdf_files = list(Path(directory).glob("*.pdf"))

    if not pdf_files:
        print(f"⚠️  No se encontraron archivos PDF en {directory}")
        return

    print(f"Encontrados {len(pdf_files)} archivos PDF\n")

    results = []

    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"[{i}/{len(pdf_files)}] Procesando: {pdf_path.name}")

        try:
            from core.ai_pipeline.ai_bank_orchestrator import get_ai_orchestrator

            orchestrator = get_ai_orchestrator()
            result = orchestrator.process_bank_statement(
                pdf_path=str(pdf_path),
                account_id=i,
                company_id=1,
                user_id=1,
                tenant_id="test"
            )

            if result.success:
                results.append({
                    "file": pdf_path.name,
                    "success": True,
                    "transactions": result.transactions_created,
                    "msi": len(result.msi_matches),
                    "time": result.processing_time_seconds,
                    "confidence": result.statement_data.confidence if result.statement_data else 0
                })
                print(f"   ✅ {result.transactions_created} txs, {len(result.msi_matches)} MSI, {result.processing_time_seconds:.2f}s")
            else:
                results.append({
                    "file": pdf_path.name,
                    "success": False,
                    "error": result.error
                })
                print(f"   ❌ {result.error}")

        except Exception as e:
            results.append({
                "file": pdf_path.name,
                "success": False,
                "error": str(e)
            })
            print(f"   ❌ {e}")

        print()

    # Resumen
    print("="*60)
    print("📊 RESUMEN BATCH")
    print("="*60)

    success_count = sum(1 for r in results if r.get("success"))
    total_txs = sum(r.get("transactions", 0) for r in results if r.get("success"))
    avg_time = sum(r.get("time", 0) for r in results if r.get("success")) / max(success_count, 1)
    avg_confidence = sum(r.get("confidence", 0) for r in results if r.get("success")) / max(success_count, 1)

    print(f"Total archivos: {len(results)}")
    print(f"Exitosos: {success_count} ({success_count/len(results)*100:.1f}%)")
    print(f"Fallidos: {len(results) - success_count}")
    print(f"Total transacciones: {total_txs}")
    print(f"Tiempo promedio: {avg_time:.2f}s")
    print(f"Confianza promedio: {avg_confidence:.2%}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Migración a AI-driven parser"
    )

    parser.add_argument(
        '--check',
        action='store_true',
        help="Verificar configuración"
    )

    parser.add_argument(
        '--test-connection',
        action='store_true',
        help="Probar conexión con Gemini"
    )

    parser.add_argument(
        '--compare',
        type=str,
        metavar='PDF',
        help="Comparar AI vs tradicional con un archivo"
    )

    parser.add_argument(
        '--batch',
        type=str,
        metavar='DIR',
        help="Prueba batch en directorio"
    )

    args = parser.parse_args()

    print("\n" + "="*60)
    print("🤖 MIGRACIÓN A AI-DRIVEN PARSER")
    print("="*60 + "\n")

    # Si no hay args, mostrar ayuda
    if not any(vars(args).values()):
        parser.print_help()
        return

    # Verificar configuración
    if args.check or args.test_connection or args.compare or args.batch:
        if not check_configuration():
            print("❌ Configuración incompleta. Abortando.\n")
            return

    # Test de conexión
    if args.test_connection:
        if not test_gemini_connection():
            print("❌ No se pudo conectar con Gemini. Verifica tu API key.\n")
            return

    # Comparar parsers
    if args.compare:
        if not Path(args.compare).exists():
            print(f"❌ Archivo no encontrado: {args.compare}\n")
            return

        compare_parsers(args.compare)

    # Batch test
    if args.batch:
        if not Path(args.batch).exists():
            print(f"❌ Directorio no encontrado: {args.batch}\n")
            return

        batch_test(args.batch)

    print("✅ Completado\n")


if __name__ == "__main__":
    main()

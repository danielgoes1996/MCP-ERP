#!/usr/bin/env python3
"""
Extraer saldo inicial y final del PDF del estado de cuenta
Esto permitirá calcular los saldos corrientes de manera más precisa
"""
from pypdf import PdfReader
import re
import requests
import json
from datetime import datetime

def extract_balances_from_pdf(pdf_path):
    """Extraer saldo inicial y final del PDF"""

    balances = {
        'saldo_inicial': None,
        'saldo_final': None,
        'fecha_inicial': None,
        'fecha_final': None
    }

    try:
        with open(pdf_path, 'rb') as file:
        pdf_reader = PdfReader(file)
            full_text = ""

            print(f"📄 PDF tiene {len(pdf_reader.pages)} páginas")

            # Extraer texto de todas las páginas con manejo de errores
            for i, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + "\n"
                        print(f"   Página {i+1}: {len(page_text)} caracteres")
                except Exception as e:
                    print(f"   ⚠️ Error página {i+1}: {e}")

            print(f"📄 PDF extraído, {len(full_text)} caracteres totales")

            if len(full_text) < 100:
                print("⚠️ Poco texto extraído, intentando método alternativo...")
                # Si no se puede extraer texto, usar el parser existente
                from core.llm_pdf_parser import LLMPDFParser
                parser = LLMPDFParser()
                full_text = parser.extract_text_from_pdf(pdf_path)
                print(f"📄 Texto alternativo: {len(full_text)} caracteres")

            # Buscar saldos con LLM para mayor precisión
            return extract_balances_with_llm(full_text)

    except Exception as e:
        print(f"❌ Error extrayendo PDF: {e}")
        import traceback
        traceback.print_exc()
        return balances

def extract_balances_with_llm(pdf_text):
    """Usar LLM para extraer saldos inicial y final del texto del PDF"""

    api_key = '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'

    # Tomar solo las primeras y últimas líneas para encontrar saldos
    lines = pdf_text.split('\n')
    context_text = '\n'.join(lines[:50] + ['...'] + lines[-50:])

    prompt = f"""Analiza este estado de cuenta bancario y extrae los saldos inicial y final.

IMPORTANTE: Buscar específicamente:
1. SALDO INICIAL/ANTERIOR - El saldo al inicio del período
2. SALDO FINAL/NUEVO - El saldo al final del período
3. FECHAS - Período del estado de cuenta

TEXTO DEL ESTADO DE CUENTA:
{context_text}

Responde SOLO con JSON válido:
{{
  "saldo_inicial": 12345.67,
  "saldo_final": 23456.78,
  "fecha_inicial": "2024-07-01",
  "fecha_final": "2024-07-31",
  "moneda": "MXN",
  "detalles": "Información adicional encontrada"
}}

Si no encuentras algún valor, usa null."""

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    payload = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 1000,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        print("🤖 Analizando saldos con LLM...")
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            content = data.get("content", [])
            if content:
                response_text = content[0].get("text", "")
                print(f"📄 Respuesta LLM: {response_text}")

                try:
                    start_idx = response_text.find('{')
                    end_idx = response_text.rfind('}')
                    json_text = response_text[start_idx:end_idx + 1]
                    result = json.loads(json_text)

                    return result

                except json.JSONDecodeError as e:
                    print(f"❌ Error JSON: {e}")
                    return None
        else:
            print(f"❌ Error API: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def update_running_balances_with_pdf_data(account_id, user_id, saldo_inicial):
    """Recalcular saldos corrientes usando el saldo inicial del PDF"""

    import sqlite3

    print(f"🔄 Recalculando saldos con saldo inicial: ${saldo_inicial:,.2f}")

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Obtener todas las transacciones ordenadas por fecha
    cursor.execute("""
        SELECT id, date, description, amount
        FROM bank_movements
        WHERE account_id = ? AND user_id = ?
        ORDER BY date ASC, id ASC
    """, (account_id, user_id))

    transactions = cursor.fetchall()

    if not transactions:
        print("❌ No se encontraron transacciones")
        conn.close()
        return

    print(f"📋 Encontradas {len(transactions)} transacciones")

    # Calcular saldos corrientes con el saldo inicial correcto
    current_balance = saldo_inicial
    updates = []

    print(f"💰 Saldo inicial: ${current_balance:,.2f}")
    print("\n📈 Calculando saldos:")

    for i, (txn_id, date, description, amount) in enumerate(transactions):
        # Calcular nuevo saldo
        current_balance += amount

        # Preparar actualización
        updates.append((current_balance, txn_id))

        # Mostrar progreso
        if i < 5 or i >= len(transactions) - 5:
            print(f"  {date} | {description[:40]:40} | ${amount:8.2f} | Saldo: ${current_balance:10.2f}")
        elif i == 5:
            print("  ...")

    # Ejecutar actualizaciones
    print(f"\n💾 Actualizando {len(updates)} registros...")

    cursor.executemany("""
        UPDATE bank_movements
        SET balance_after = ?
        WHERE id = ?
    """, updates)

    conn.commit()

    # Verificar resultados
    cursor.execute("""
        SELECT COUNT(*) as total,
               MIN(balance_after) as min_balance,
               MAX(balance_after) as max_balance
        FROM bank_movements
        WHERE account_id = ? AND user_id = ? AND balance_after IS NOT NULL
    """, (account_id, user_id))

    total, min_balance, max_balance = cursor.fetchone()

    print(f"✅ Actualizados {total} registros")
    print(f"📊 Saldo mínimo: ${min_balance:,.2f}")
    print(f"📊 Saldo máximo: ${max_balance:,.2f}")
    print(f"💰 Saldo final calculado: ${current_balance:,.2f}")

    conn.close()

    return current_balance

def main():
    print("🏦 EXTRACTOR DE SALDOS INICIAL Y FINAL DEL PDF")
    print("=" * 50)

    # PDF más reciente de AMEX Gold
    pdf_path = "./uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf"

    if not os.path.exists(pdf_path):
        print(f"❌ PDF no encontrado: {pdf_path}")
        return

    # Extraer saldos del PDF
    balances = extract_balances_from_pdf(pdf_path)

    if balances and balances.get('saldo_inicial') is not None:
        print(f"\n✅ Saldos extraídos del PDF:")
        print(f"💰 Saldo inicial: ${balances['saldo_inicial']:,.2f}")
        if balances.get('saldo_final'):
            print(f"💰 Saldo final: ${balances['saldo_final']:,.2f}")
        if balances.get('fecha_inicial'):
            print(f"📅 Fecha inicial: {balances['fecha_inicial']}")
        if balances.get('fecha_final'):
            print(f"📅 Fecha final: {balances['fecha_final']}")

        # Preguntar si recalcular
        print(f"\n🔄 ¿Recalcular saldos corrientes con saldo inicial ${balances['saldo_inicial']:,.2f}?")

        # Recalcular automáticamente
        account_id = 5  # AMEX Gold
        user_id = 9

        saldo_final_calculado = update_running_balances_with_pdf_data(
            account_id, user_id, balances['saldo_inicial']
        )

        if balances.get('saldo_final'):
            diferencia = abs(saldo_final_calculado - balances['saldo_final'])
            print(f"\n📊 VALIDACIÓN:")
            print(f"   Saldo final PDF: ${balances['saldo_final']:,.2f}")
            print(f"   Saldo final calculado: ${saldo_final_calculado:,.2f}")
            print(f"   Diferencia: ${diferencia:,.2f}")

            if diferencia < 1.0:
                print("✅ ¡Saldos coinciden! Cálculo correcto.")
            else:
                print("⚠️ Hay diferencia en los saldos. Revisar transacciones.")

    else:
        print("❌ No se pudieron extraer los saldos del PDF")

if __name__ == "__main__":
    import os
    main()

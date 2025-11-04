#!/usr/bin/env python3
"""
Extraer saldo inicial y final del PDF usando múltiples métodos
"""
import os
import fitz  # PyMuPDF
import pdfplumber
import requests
import json
import sqlite3

def extract_text_with_pymupdf(pdf_path):
    """Extraer texto usando PyMuPDF"""
    try:
        doc = fitz.open(pdf_path)
        full_text = ""

        print(f"📄 PyMuPDF: PDF tiene {len(doc)} páginas")

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()
            full_text += text + "\n"
            print(f"   Página {page_num+1}: {len(text)} caracteres")

        doc.close()
        print(f"✅ PyMuPDF extrajo {len(full_text)} caracteres")
        return full_text

    except Exception as e:
        print(f"❌ Error PyMuPDF: {e}")
        return None

def extract_text_with_pdfplumber(pdf_path):
    """Extraer texto usando pdfplumber"""
    try:
        full_text = ""

        with pdfplumber.open(pdf_path) as pdf:
            print(f"📄 pdfplumber: PDF tiene {len(pdf.pages)} páginas")

            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
                    print(f"   Página {i+1}: {len(text)} caracteres")

        print(f"✅ pdfplumber extrajo {len(full_text)} caracteres")
        return full_text

    except Exception as e:
        print(f"❌ Error pdfplumber: {e}")
        return None

def extract_balances_with_llm(pdf_text):
    """Usar LLM para extraer saldos del PDF"""

    if not pdf_text or len(pdf_text) < 100:
        print("❌ No hay suficiente texto para analizar")
        return None

    api_key = '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'

    # Tomar texto relevante del inicio y final
    lines = pdf_text.split('\n')
    context_text = '\n'.join(lines[:100] + ['...'] + lines[-100:])

    prompt = f"""Analiza este estado de cuenta bancario de AMEX y extrae los saldos inicial y final.

BUSCAR ESPECÍFICAMENTE:
1. SALDO INICIAL/ANTERIOR al inicio del período
2. SALDO FINAL/NUEVO al final del período
3. FECHAS del período del estado de cuenta
4. Para AMEX puede aparecer como "Balance anterior", "Nuevo balance", etc.

ESTADO DE CUENTA:
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

                # Mostrar solo las primeras líneas de la respuesta
                print(f"📄 Respuesta LLM: {response_text[:200]}...")

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
            print(f"❌ Error API: {response.status_code}")
            return None

    except Exception as e:
        print(f"❌ Error LLM: {e}")
        return None

def update_balances_with_pdf_data(account_id, user_id, saldo_inicial):
    """Recalcular saldos usando el saldo inicial del PDF"""

    print(f"🔄 Recalculando saldos con saldo inicial del PDF: ${saldo_inicial:,.2f}")

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Obtener transacciones ordenadas
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
        return None

    print(f"📋 Procesando {len(transactions)} transacciones")

    # Calcular saldos corrientes
    current_balance = saldo_inicial
    updates = []

    for i, (txn_id, date, description, amount) in enumerate(transactions):
        current_balance += amount
        updates.append((current_balance, txn_id))

        # Mostrar progreso
        if i < 3 or i >= len(transactions) - 3:
            print(f"  {date} | {description[:30]:30} | ${amount:8.2f} | Saldo: ${current_balance:10.2f}")
        elif i == 3:
            print("  ...")

    # Actualizar base de datos
    cursor.executemany("""
        UPDATE bank_movements
        SET balance_after = ?
        WHERE id = ?
    """, updates)

    conn.commit()
    conn.close()

    print(f"✅ Actualizados {len(updates)} registros")
    print(f"💰 Saldo final calculado: ${current_balance:,.2f}")

    return current_balance

def main():
    print("🏦 EXTRACTOR DE SALDOS DEL PDF - VERSIÓN MEJORADA")
    print("=" * 55)

    pdf_path = "./uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf"

    if not os.path.exists(pdf_path):
        print(f"❌ PDF no encontrado: {pdf_path}")
        return

    # Intentar múltiples métodos de extracción
    pdf_text = None

    print("🔄 Intentando PyMuPDF...")
    pdf_text = extract_text_with_pymupdf(pdf_path)

    if not pdf_text or len(pdf_text) < 100:
        print("🔄 Intentando pdfplumber...")
        pdf_text = extract_text_with_pdfplumber(pdf_path)

    if not pdf_text or len(pdf_text) < 100:
        print("❌ No se pudo extraer texto del PDF")
        return

    # Extraer saldos con LLM
    balances = extract_balances_with_llm(pdf_text)

    if balances and balances.get('saldo_inicial') is not None:
        print(f"\n✅ SALDOS EXTRAÍDOS DEL PDF:")
        print(f"💰 Saldo inicial: ${balances['saldo_inicial']:,.2f}")
        if balances.get('saldo_final'):
            print(f"💰 Saldo final: ${balances['saldo_final']:,.2f}")
        if balances.get('fecha_inicial'):
            print(f"📅 Período: {balances['fecha_inicial']} al {balances.get('fecha_final', 'N/A')}")

        # Recalcular saldos
        account_id = 5  # AMEX Gold
        user_id = 9

        saldo_final_calculado = update_balances_with_pdf_data(
            account_id, user_id, balances['saldo_inicial']
        )

        # Validar resultados
        if balances.get('saldo_final') and saldo_final_calculado:
            diferencia = abs(saldo_final_calculado - balances['saldo_final'])
            print(f"\n📊 VALIDACIÓN DE SALDOS:")
            print(f"   📄 Saldo final del PDF: ${balances['saldo_final']:,.2f}")
            print(f"   🧮 Saldo final calculado: ${saldo_final_calculado:,.2f}")
            print(f"   📐 Diferencia: ${diferencia:,.2f}")

            if diferencia < 1.0:
                print("✅ ¡PERFECTO! Los saldos coinciden.")
            elif diferencia < 10.0:
                print("⚠️ Pequeña diferencia, posibles comisiones o ajustes.")
            else:
                print("❌ Diferencia significativa, revisar transacciones.")

        print(f"\n🎉 ¡Saldos corrientes actualizados con datos del PDF!")

    else:
        print("❌ No se pudieron extraer los saldos del PDF")

if __name__ == "__main__":
    main()
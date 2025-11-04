#!/usr/bin/env python3
"""
Arreglar específicamente la descripción de TELMEX usando la información completa del PDF
"""
import sqlite3
import os
import requests
import json

def test_telmex_with_full_context():
    """Probar procesamiento de TELMEX con contexto completo"""

    # Información completa como está en el PDF
    telmex_context = """
    JUL. 15 3506659075 DOMICILIACION 389.00 19,891.85
    TME840315KT6 TELEFONOS DE MEXICO S.A.B DE
    C.V.
    """

    api_key = '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'

    prompt = f"""Analiza esta transacción bancaria y crea una descripción completa usando TODA la información disponible.

La información está separada en líneas, pero pertenece a la MISMA transacción:

REGLAS ESPECÍFICAS:
- USAR toda la información: RFC, razón social completa
- La línea "TME840315KT6 TELEFONOS DE MEXICO S.A.B DE C.V." es información adicional de la misma transacción
- Crear descripción completa: "Domiciliación TELMEX (TME840315KT6) - Teléfonos de México S.A.B. de C.V."

TEXTO A ANALIZAR:
{telmex_context}

Responde SOLO con JSON:
{{
  "description": "Descripción completa con RFC y razón social",
  "category": "Categoría apropiada"
}}"""

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
        print("🤖 Procesando TELMEX con contexto completo...")
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

                # Parsear JSON
                try:
                    start_idx = response_text.find('{')
                    end_idx = response_text.rfind('}')
                    json_text = response_text[start_idx:end_idx + 1]
                    result = json.loads(json_text)

                    new_description = result.get("description", "")
                    new_category = result.get("category", "")

                    print(f"✅ Descripción mejorada: {new_description}")
                    print(f"🏷️ Categoría: {new_category}")

                    return new_description, new_category

                except json.JSONDecodeError as e:
                    print(f"❌ Error JSON: {e}")
                    return None, None
        else:
            print(f"❌ Error API: {response.status_code} - {response.text}")
            return None, None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None

def update_telmex_in_database(new_description, new_category):
    """Actualizar la descripción de TELMEX en la base de datos"""

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Buscar transacciones de domiciliación de servicios que probablemente sean TELMEX
    cursor.execute("""
        SELECT id, description, amount, transaction_date
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        AND (description LIKE '%Domiciliación de Servicios%'
             OR description LIKE '%DOMICILIACION%')
        AND ABS(amount + 389.00) < 0.01  -- Monto específico de TELMEX
        ORDER BY id DESC
        LIMIT 5
    """)

    candidates = cursor.fetchall()

    if candidates:
        print(f"🔍 Encontradas {len(candidates)} transacciones candidatas:")
        for txn_id, desc, amount, date in candidates:
            print(f"  ID {txn_id}: {desc} | ${amount} | {date}")

        # Actualizar la primera candidata (más probable)
        txn_id = candidates[0][0]

        cursor.execute("""
            UPDATE bank_movements
            SET description = ?, category = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_description, new_category, txn_id))

        conn.commit()
        print(f"✅ Actualizada transacción ID {txn_id}")
        print(f"📝 Nueva descripción: {new_description}")
        print(f"🏷️ Nueva categoría: {new_category}")

    else:
        print("❌ No se encontraron transacciones candidatas para TELMEX")

    conn.close()

def main():
    print("🔧 Arreglando descripción de TELMEX con información completa...")

    # Procesar con LLM
    new_description, new_category = test_telmex_with_full_context()

    if new_description and new_category:
        # Actualizar en base de datos
        update_telmex_in_database(new_description, new_category)
        print("🎉 ¡TELMEX actualizado con información completa!")
    else:
        print("❌ No se pudo procesar la información de TELMEX")

if __name__ == "__main__":
    main()
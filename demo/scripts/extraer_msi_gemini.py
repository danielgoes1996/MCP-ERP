#!/usr/bin/env python3
"""
Extracción AI-Driven de Meses Sin Intereses (MSI) usando Gemini Vision
Analiza el PDF completo y extrae la tabla de pagos diferidos automáticamente
"""

import os
import sys
import json
import base64
import google.generativeai as genai
from pathlib import Path

# Configurar Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ Error: GEMINI_API_KEY no configurada")
    print("   export GEMINI_API_KEY='tu-key'")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)


def extraer_msi_con_gemini(pdf_path: str) -> dict:
    """
    Extraer información de MSI usando Gemini Vision (AI-Driven)

    Args:
        pdf_path: Ruta al PDF del estado de cuenta AMEX

    Returns:
        dict con pagos diferidos extraídos
    """

    # Leer PDF como bytes
    with open(pdf_path, 'rb') as f:
        pdf_data = f.read()

    # Codificar en base64 para enviar a Gemini
    pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')

    # Prompt para Gemini
    prompt = """
Analiza este estado de cuenta de tarjeta de crédito American Express.

OBJETIVO: Extraer información sobre Meses Sin Intereses (MSI) y Pagos Diferidos.

BUSCA LA SECCIÓN: "Resumen de Planes de Pagos Diferidos con Intereses y Meses sin Intereses"

EXTRAE:
1. Cada compra que tiene un plan de pagos diferidos
2. Para cada compra extrae:
   - Descripción/comercio
   - Fecha original
   - Monto original
   - Tasa de interés anual (%)
   - Saldo pendiente
   - Número de mensualidades (total)
   - Mensualidad actual (cuál de cuántas, ej: "1 de 12")
   - Monto de la mensualidad
   - Monto total a pagar

FORMATO DE SALIDA (JSON):
{
  "tiene_pagos_diferidos": true/false,
  "saldo_total_pendiente": float,
  "pagos_diferidos": [
    {
      "comercio": "MERCADO LIBRE MEXICO",
      "fecha_original": "2025-01-23",
      "monto_original": 59900.00,
      "tasa_interes_anual": 0.00,
      "saldo_pendiente": 54908.33,
      "mensualidad_actual": 1,
      "total_mensualidades": 12,
      "monto_mensualidad": 4991.67,
      "monto_total_a_pagar": 59900.00,
      "desglose_mensualidad": {
        "pago_capital": 4991.67,
        "interes": 0.00,
        "iva": 0.00
      }
    }
  ]
}

IMPORTANTE:
- Si NO hay sección de pagos diferidos, retorna {"tiene_pagos_diferidos": false, "pagos_diferidos": []}
- Todos los montos en formato numérico (float)
- Fechas en formato YYYY-MM-DD
- Si la tasa es "0.00%" significa Meses Sin Intereses (MSI)
- Extrae TODA la información visible en la tabla

Retorna SOLO el JSON, sin explicaciones adicionales.
"""

    print("🤖 Enviando PDF a Gemini Vision para análisis AI-Driven...")
    print(f"   Archivo: {pdf_path}")
    print(f"   Tamaño: {len(pdf_data) / 1024:.1f} KB")
    print()

    # Crear modelo Gemini con visión
    model = genai.GenerativeModel('gemini-2.5-pro')

    # Enviar PDF y prompt
    response = model.generate_content([
        prompt,
        {
            'mime_type': 'application/pdf',
            'data': pdf_base64
        }
    ])

    # Extraer JSON de la respuesta
    respuesta_texto = response.text.strip()

    # Limpiar markdown si existe
    if respuesta_texto.startswith('```json'):
        respuesta_texto = respuesta_texto.replace('```json', '').replace('```', '').strip()

    try:
        resultado = json.loads(respuesta_texto)
        print("✅ Gemini extrajo la información correctamente")
        return resultado
    except json.JSONDecodeError as e:
        print(f"❌ Error parseando JSON de Gemini: {e}")
        print(f"Respuesta raw:\n{respuesta_texto}")
        return None


def mostrar_resultados(resultado: dict):
    """Mostrar resultados de forma legible"""

    if not resultado:
        print("❌ No se pudo extraer información")
        return

    print()
    print("=" * 80)
    print("RESULTADO DE EXTRACCIÓN AI-DRIVEN (GEMINI VISION)")
    print("=" * 80)
    print()

    if not resultado.get('tiene_pagos_diferidos'):
        print("ℹ️  No se encontraron pagos diferidos en este estado de cuenta")
        return

    print(f"💰 Saldo Total Pendiente: ${resultado.get('saldo_total_pendiente', 0):,.2f}")
    print(f"📊 Número de Pagos Diferidos: {len(resultado.get('pagos_diferidos', []))}")
    print()

    for i, pago in enumerate(resultado.get('pagos_diferidos', []), 1):
        print(f"{i}. {pago['comercio']}")
        print(f"   Fecha Original: {pago['fecha_original']}")
        print(f"   Monto Original: ${pago['monto_original']:,.2f}")

        tasa = pago['tasa_interes_anual']
        if tasa == 0.0:
            print(f"   ✨ MESES SIN INTERESES (0%)")
        else:
            print(f"   Tasa Interés: {tasa}% anual")

        print(f"   Saldo Pendiente: ${pago['saldo_pendiente']:,.2f}")
        print(f"   Mensualidad: {pago['mensualidad_actual']} de {pago['total_mensualidades']}")
        print(f"   Pago Mensual: ${pago['monto_mensualidad']:,.2f}")

        if 'desglose_mensualidad' in pago:
            d = pago['desglose_mensualidad']
            print(f"      - Capital: ${d['pago_capital']:,.2f}")
            print(f"      - Interés: ${d['interes']:,.2f}")
            print(f"      - IVA: ${d['iva']:,.2f}")

        print()

    print("=" * 80)


def guardar_resultado(resultado: dict, output_path: str):
    """Guardar resultado en JSON"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)
    print(f"💾 Resultado guardado en: {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Extraer MSI de estado de cuenta AMEX con Gemini Vision (AI-Driven)'
    )
    parser.add_argument('--archivo', required=True, help='Ruta al PDF AMEX')
    parser.add_argument('--output', help='Archivo JSON de salida (opcional)')

    args = parser.parse_args()

    if not os.path.exists(args.archivo):
        print(f"❌ Error: Archivo no encontrado: {args.archivo}")
        sys.exit(1)

    # Extraer con Gemini AI
    resultado = extraer_msi_con_gemini(args.archivo)

    # Mostrar resultados
    mostrar_resultados(resultado)

    # Guardar si se especificó output
    if args.output and resultado:
        guardar_resultado(resultado, args.output)
    elif resultado:
        # Guardar automáticamente con nombre basado en el PDF
        pdf_name = Path(args.archivo).stem
        output_path = f"msi_{pdf_name}.json"
        guardar_resultado(resultado, output_path)

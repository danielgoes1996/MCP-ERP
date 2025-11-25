#!/usr/bin/env python3
"""
Script para estimar tokens consumidos en nuestras pruebas de hoy
"""
def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Cuenta tokens usando aproximación de 4 caracteres = 1 token"""
    return len(text) // 4

# Ejemplo de prompt que usamos
ejemplo_html = """
<html><body><nav><a href="/facturacion" class="nav-item">FACTURACIÓN</a></nav></body></html>
""" * 100  # Simular HTML largo

ejemplo_prompt = f"""
🤖 AGENTE DE AUTOMATIZACIÓN WEB PARA FACTURACIÓN ELECTRÓNICA

🎯 OBJETIVO FINAL: Descargar factura PDF completando formulario con datos fiscales del cliente

DATOS DEL TICKET OCR (Google Vision):
- Folio/Número: 16
- Total: $1133.57
- Fecha: 16/09/2025, 20:42
- RFC Cliente: XAXX010101000
- Email Cliente: test@example.com
- Texto OCR completo: E11167 LINERIA LITEO LEERAIN ENTO SUR POTENTE NO...

🌐 HTML DE LA PÁGINA ACTUAL:
{ejemplo_html}

📋 FLUJO COMPLETO DE FACTURACIÓN:
[... resto del prompt ...]
"""

# Calcular tokens
tokens_prompt = count_tokens(ejemplo_prompt)
tokens_respuesta = count_tokens('{"action": "click", "selector": "#facturar", "value": "", "reason": "Botón de facturación detectado", "confidence": 0.95}')

print(f"📊 ESTIMACIÓN DE TOKENS POR LLAMADA:")
print(f"🔹 Prompt: ~{tokens_prompt:,} tokens")
print(f"🔹 Respuesta: ~{tokens_respuesta:,} tokens")
print(f"🔹 Total por llamada: ~{tokens_prompt + tokens_respuesta:,} tokens")

print(f"\n📈 ESTIMACIONES PARA PRUEBAS DE HOY:")
print(f"🔹 1 llamada simple: ~{tokens_prompt + tokens_respuesta:,} tokens")
print(f"🔹 4 llamadas (loop): ~{(tokens_prompt + tokens_respuesta) * 4:,} tokens")
print(f"🔹 10 llamadas (sesión larga): ~{(tokens_prompt + tokens_respuesta) * 10:,} tokens")

# Costo aproximado (GPT-4 pricing: $30/1M input tokens, $60/1M output tokens)
input_cost_per_1k = 0.03
output_cost_per_1k = 0.06

costo_por_llamada = (tokens_prompt * input_cost_per_1k / 1000) + (tokens_respuesta * output_cost_per_1k / 1000)
print(f"\n💰 COSTO ESTIMADO:")
print(f"🔹 Por llamada: ~${costo_por_llamada:.4f}")
print(f"🔹 Por loop de 4: ~${costo_por_llamada * 4:.4f}")
print(f"🔹 Por sesión de 10: ~${costo_por_llamada * 10:.4f}")
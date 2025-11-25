"""
Integración de Claude (Anthropic) como LLM principal del sistema de facturación.
Ahora Claude es el LLM principal con OpenAI como fallback.
"""

import anthropic
import json
import os
import logging

async def call_claude_for_state(prompt):
    """Llamar a Claude para decisión de estado"""
    try:
        client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")  # Necesitarás esta variable
        )

        message = client.messages.create(
            model="claude-3-haiku-20240307",  # Modelo más barato y estable
            max_tokens=300,
            temperature=0.1,
            system="Eres un agente de automatización web. Responde SOLO con JSON válido siguiendo el formato especificado.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        text = message.content[0].text.strip()

        # Limpiar JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        return json.loads(text)

    except Exception as e:
        logging.error(f"Error llamando a Claude: {e}")
        return {
            "action": "error",
            "selector": "",
            "reason": f"Error Claude: {e}",
            "confidence": 0.0
        }


# Función principal: Claude primero, OpenAI como fallback
async def call_llm_hybrid(prompt, prefer_claude=True):
    """
    Llamar a Claude como LLM principal, OpenAI como fallback.

    Args:
        prompt: Prompt para el LLM
        prefer_claude: Siempre True ahora (Claude es principal)

    Returns:
        Respuesta JSON del LLM
    """

    # Intentar Claude primero (LLM principal)
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            logging.info("🤖 Usando Claude como LLM principal")
            return await call_claude_for_state(prompt)
        except Exception as e:
            logging.warning(f"❌ Claude falló, usando OpenAI como fallback: {e}")

    # Fallback a OpenAI
    if os.getenv("OPENAI_API_KEY"):
        try:
            logging.info("🔄 Usando OpenAI como fallback")
            return await call_openai_fallback(prompt)
        except Exception as e:
            logging.error(f"❌ OpenAI también falló: {e}")

    # Si ambos fallan
    logging.error("❌ No hay LLM disponible")
    return {
        "action": "error",
        "selector": "",
        "reason": "No hay LLM disponible",
        "confidence": 0.0
    }


async def call_openai_fallback(prompt):
    """Función separada para llamadas de fallback a OpenAI"""
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Responde SOLO con JSON válido."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        temperature=0.1
    )

    text = response.choices[0].message.content.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()

    return json.loads(text)


def get_claude_pricing_info():
    """Información de precios de Claude vs OpenAI"""
    return {
        "claude_3_haiku": {
            "input": "$0.25/1M tokens",  # 12x más barato que GPT-4
            "output": "$1.25/1M tokens",
            "speed": "Muy rápido",
            "uso_recomendado": "Automatización web simple"
        },
        "claude_3_sonnet": {
            "input": "$3/1M tokens",  # Igual que GPT-3.5-turbo
            "output": "$15/1M tokens",
            "speed": "Rápido",
            "uso_recomendado": "Automatización web compleja"
        },
        "gpt_35_turbo": {
            "input": "$3/1M tokens",
            "output": "$6/1M tokens",
            "speed": "Rápido",
            "uso_recomendado": "Baseline"
        },
        "gpt_4": {
            "input": "$30/1M tokens",  # 10x más caro
            "output": "$60/1M tokens",
            "speed": "Lento",
            "uso_recomendado": "Solo tareas muy complejas"
        }
    }
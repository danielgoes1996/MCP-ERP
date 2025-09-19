#!/usr/bin/env python3
"""
Prueba simple para verificar que OpenAI funciona
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def test_openai_connection():
    """Probar conexión con OpenAI"""
    api_key = os.getenv('OPENAI_API_KEY')

    if not api_key:
        print("❌ OPENAI_API_KEY no encontrada en .env")
        return False

    if not api_key.startswith('sk-'):
        print("❌ OPENAI_API_KEY no tiene formato válido")
        return False

    print("✅ OPENAI_API_KEY configurada correctamente")
    print(f"   Clave: {api_key[:10]}...{api_key[-10:]}")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        # Prueba simple de TTS
        print("🔊 Probando Text-to-Speech...")
        response = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input="Hola, esta es una prueba del sistema de voz"
        )

        # Guardar archivo de prueba
        with open("/tmp/test_voice.mp3", "wb") as f:
            f.write(response.content)

        print("✅ TTS funcionando - archivo guardado en /tmp/test_voice.mp3")
        return True

    except Exception as e:
        print(f"❌ Error con OpenAI: {e}")
        return False

if __name__ == "__main__":
    test_openai_connection()
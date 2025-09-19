#!/usr/bin/env python3
"""
Prueba rápida sin dotenv
"""

import os

# Configurar directamente la API key (solo para pruebas locales)
os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', 'sk-your-openai-api-key-here')

def create_test_audio():
    """Crear archivo de audio de prueba"""
    try:
        from openai import OpenAI

        client = OpenAI()

        print("🔊 Creando audio de prueba...")

        # Crear audio
        response = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input="Registrar gasto de gasolina de quinientos pesos"
        )

        # Crear directorio examples si no existe
        os.makedirs("examples", exist_ok=True)

        # Guardar archivo
        with open("examples/test_audio.mp3", "wb") as f:
            f.write(response.content)

        print("✅ Audio creado: examples/test_audio.mp3")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    create_test_audio()

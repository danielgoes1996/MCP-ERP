#!/usr/bin/env python3
"""
Script para crear un archivo de audio de prueba usando OpenAI TTS
"""

import os
import sys
from pathlib import Path

# Agregar el directorio actual al path para importar los módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def create_test_audio():
    """Crear archivo de audio de prueba"""
    try:
        # Intentar importar el voice handler
        from core.voice_handler import text_to_speech

        # Texto de prueba en español
        test_text = "Registrar gasto de gasolina de quinientos pesos"

        print(f"Creando audio de prueba con el texto: '{test_text}'")

        # Generar audio
        result = text_to_speech(test_text, voice="nova")  # Nova tiene mejor pronunciación en español

        if result["success"]:
            # Mover el archivo a la carpeta examples
            examples_dir = Path(__file__).parent / "examples"
            examples_dir.mkdir(exist_ok=True)

            test_audio_path = examples_dir / "test_audio.mp3"

            # Copiar el archivo temporal al destino final
            import shutil
            shutil.copy2(result["audio_file"], test_audio_path)

            # Limpiar archivo temporal
            os.unlink(result["audio_file"])

            print(f"✅ Archivo de audio creado: {test_audio_path}")
            print(f"   Duración: ~3 segundos")
            print(f"   Contenido: '{test_text}'")

            return str(test_audio_path)

        else:
            print(f"❌ Error creando audio: {result.get('error')}")
            return None

    except ImportError as e:
        print(f"❌ Error importando voice_handler: {e}")
        print("   Asegúrate de que OPENAI_API_KEY esté configurado en .env")
        return None
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return None

if __name__ == "__main__":
    create_test_audio()
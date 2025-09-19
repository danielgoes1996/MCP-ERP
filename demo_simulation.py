#!/usr/bin/env python3
"""
Simulación del flujo de voz para demostrar el funcionamiento
"""

import json
import time

def simulate_voice_to_json_conversion():
    """
    Simula el proceso completo de conversión de voz a JSON
    """
    print("🎤 DEMO: Sistema de Reconocimiento de Voz MCP")
    print("=" * 50)

    # Paso 1: Recepción del audio
    print("\n1. 📱 RECIBIENDO ARCHIVO DE AUDIO")
    print("   Usuario envía: test_audio.mp3")
    print("   Contenido del audio: 'Registrar gasto de gasolina de 500 pesos'")
    time.sleep(1)

    # Paso 2: Transcripción
    print("\n2. 🗣️  TRANSCRIPCIÓN (OpenAI Whisper)")
    print("   Procesando audio...")
    time.sleep(1)
    transcript = "Registrar gasto de gasolina de 500 pesos"
    print(f"   ✅ Texto transcrito: '{transcript}'")

    # Paso 3: Procesamiento NLP
    print("\n3. 🧠 PROCESAMIENTO DE LENGUAJE NATURAL")
    print("   Analizando palabras clave...")
    print("   - Detectado: 'gasto' → Acción: crear_expense")
    print("   - Detectado: '500' → Cantidad: 500.0")
    print("   - Detectado: 'gasolina' → Descripción: incluida")

    # Paso 4: Conversión a MCP Request
    mcp_request = {
        "method": "create_expense",
        "params": {
            "description": transcript,
            "amount": 500.0,
            "employee": "Usuario Voz"
        }
    }

    print("\n4. 🔄 CONVERSIÓN A FORMATO MCP")
    print("   Generando request MCP:")
    print(f"   {json.dumps(mcp_request, indent=4, ensure_ascii=False)}")

    # Paso 5: Procesamiento MCP
    print("\n5. ⚙️  PROCESAMIENTO MCP")
    time.sleep(1)

    # Simular respuesta del sistema
    mcp_response = {
        "success": True,
        "data": {
            "expense_id": "EXP-2024-001",
            "amount": 500.0,
            "description": "Registrar gasto de gasolina de 500 pesos",
            "employee": "Usuario Voz",
            "status": "pending",
            "created_at": "2024-09-17T06:54:00Z",
            "category": "transport"
        }
    }

    print("   ✅ Gasto creado en el sistema")
    print(f"   ID generado: {mcp_response['data']['expense_id']}")

    # Paso 6: Respuesta TTS
    print("\n6. 🔊 GENERANDO RESPUESTA DE VOZ")
    response_text = f"Gasto creado exitosamente por {mcp_response['data']['amount']} pesos con ID {mcp_response['data']['expense_id']}. Estado: pendiente de aprobación."
    print(f"   Texto a voz: '{response_text}'")
    print("   Generando audio de respuesta...")
    time.sleep(1)
    print("   ✅ Audio de respuesta creado: response_audio.mp3")

    # Paso 7: Respuesta JSON final
    final_response = {
        "success": True,
        "transcript": transcript,
        "mcp_response": mcp_response,
        "response_text": response_text,
        "audio_file_url": "/audio/response_20240917_065400.mp3",
        "tts_success": True
    }

    print("\n7. 📤 RESPUESTA JSON FINAL")
    print("   El sistema retorna:")
    print(json.dumps(final_response, indent=2, ensure_ascii=False))

    print("\n" + "=" * 50)
    print("🎉 PROCESO COMPLETADO EXITOSAMENTE")
    print("\n📋 RESUMEN:")
    print("   • Audio recibido y transcrito ✅")
    print("   • Gasto registrado en el sistema ✅")
    print("   • Respuesta generada en audio ✅")
    print("   • JSON completo retornado ✅")

    return final_response

def show_curl_example():
    """Muestra el comando curl que el usuario usaría"""
    print("\n" + "=" * 50)
    print("🔧 COMANDO PARA PROBAR EN REAL:")
    print("\n1. Crear archivo de audio con tu voz:")
    print("   - Graba: 'Registrar gasto de gasolina de 500 pesos'")
    print("   - Guarda como: test_audio.mp3")

    print("\n2. Iniciar servidor:")
    print("   python3 main.py")

    print("\n3. Enviar audio:")
    print('   curl -X POST "http://localhost:8000/voice_mcp" \\')
    print('        -F "file=@test_audio.mp3"')

    print("\n4. Resultado esperado:")
    print("   JSON igual al mostrado arriba + archivo de audio")

if __name__ == "__main__":
    result = simulate_voice_to_json_conversion()
    show_curl_example()
#!/usr/bin/env python3
"""
Example script to test voice functionality with MCP Server
Demonstrates how to use the voice endpoints
"""

import requests
import json
import os
from pathlib import Path

# Server configuration
SERVER_URL = "http://localhost:8000"
VOICE_ENDPOINT = f"{SERVER_URL}/voice_mcp"
METHODS_ENDPOINT = f"{SERVER_URL}/methods"

def test_voice_capability():
    """
    Test if voice processing is enabled on the server
    """
    try:
        response = requests.get(METHODS_ENDPOINT)
        if response.status_code == 200:
            data = response.json()
            voice_enabled = data.get("voice_enabled", False)
            print(f"🎤 Voice processing enabled: {voice_enabled}")
            
            if voice_enabled:
                print("✅ Voice endpoints available:")
                methods = data.get("supported_methods", {})
                for method_name, details in methods.items():
                    if "voice" in method_name.lower() or "audio" in method_name.lower():
                        print(f"  - {method_name}: {details.get('description', '')}")
            else:
                print("❌ Voice processing not enabled. Check OPENAI_API_KEY configuration.")
            
            return voice_enabled
        else:
            print(f"❌ Failed to connect to server: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing voice capability: {e}")
        return False

def create_test_audio_file():
    """
    Create a simple test audio file using text-to-speech if available.
    For testing purposes, you should provide your own audio file.
    """
    print("📝 To test voice functionality, you need an audio file.")
    print("   You can:")
    print("   1. Record yourself saying: 'Registrar gasto de gasolina de 500 pesos'")
    print("   2. Use any audio file (MP3, WAV, etc.)")
    print("   3. Save it as 'test_audio.mp3' in the examples folder")
    
    # Check if test file exists
    test_file = Path(__file__).parent / "test_audio.mp3"
    if test_file.exists():
        print(f"✅ Found test audio file: {test_file}")
        return str(test_file)
    else:
        print(f"❌ Test audio file not found: {test_file}")
        print("   Create an audio file to test voice functionality.")
        return None

def test_voice_mcp(audio_file_path):
    """
    Test the voice MCP endpoint with an audio file
    """
    if not audio_file_path or not os.path.exists(audio_file_path):
        print("❌ Audio file not found")
        return False
    
    try:
        print(f"🎤 Testing voice MCP with: {audio_file_path}")
        
        # Prepare file for upload
        with open(audio_file_path, 'rb') as audio_file:
            files = {'file': (os.path.basename(audio_file_path), audio_file, 'audio/mpeg')}
            
            # Send request
            response = requests.post(VOICE_ENDPOINT, files=files, timeout=60)
            
        if response.status_code == 200:
            data = response.json()
            print("✅ Voice processing successful!")
            print(f"📝 Transcript: {data.get('transcript', '')}")
            print(f"🤖 MCP Response: {json.dumps(data.get('mcp_response', {}), indent=2)}")
            print(f"🔊 Response Text: {data.get('response_text', '')}")
            print(f"🎵 Audio File URL: {data.get('audio_file_url', '')}")
            
            # Try to download the response audio
            audio_url = data.get('audio_file_url', '')
            if audio_url:
                download_response_audio(f"{SERVER_URL}{audio_url}")
            
            return True
            
        elif response.status_code == 503:
            print("❌ Voice processing disabled on server")
            print("   Check server configuration and OPENAI_API_KEY")
            return False
            
        else:
            print(f"❌ Voice processing failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing voice MCP: {e}")
        return False

def download_response_audio(audio_url):
    """
    Download the generated response audio file
    """
    try:
        print(f"⬇️ Downloading response audio: {audio_url}")
        
        response = requests.get(audio_url)
        if response.status_code == 200:
            # Save to examples folder
            output_file = Path(__file__).parent / "response_audio.mp3"
            with open(output_file, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ Response audio saved: {output_file}")
            print("   You can play this file to hear the MCP response")
            
        else:
            print(f"❌ Failed to download audio: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error downloading response audio: {e}")

def main():
    """
    Main test function
    """
    print("🎤 MCP Server Voice Processing Test")
    print("=" * 40)
    
    # Test 1: Check voice capability
    print("\n1. Testing voice capability...")
    if not test_voice_capability():
        print("❌ Voice processing not available. Exiting.")
        return
    
    # Test 2: Check for test audio file
    print("\n2. Checking for test audio file...")
    audio_file = create_test_audio_file()
    if not audio_file:
        print("❌ No test audio file available. Please create one to test.")
        return
    
    # Test 3: Test voice MCP endpoint
    print("\n3. Testing voice MCP endpoint...")
    success = test_voice_mcp(audio_file)
    
    if success:
        print("\n🎉 Voice processing test completed successfully!")
        print("\n📋 Usage examples:")
        print(f"   curl -X POST \"{VOICE_ENDPOINT}\" -F \"file=@your_audio.mp3\"")
    else:
        print("\n❌ Voice processing test failed.")
        print("\n🔧 Troubleshooting:")
        print("   1. Make sure OPENAI_API_KEY is set in .env")
        print("   2. Install dependencies: pip install openai pydub")
        print("   3. Restart the MCP server")
        print("   4. Check server logs for errors")

if __name__ == "__main__":
    main()
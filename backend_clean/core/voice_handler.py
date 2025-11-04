"""
Voice processing handler for MCP Server
Handles audio transcription (speech-to-text) and text-to-speech conversion
using OpenAI Whisper and TTS APIs
"""

import os
import tempfile
import logging
from typing import BinaryIO, Union
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from pydub import AudioSegment
except ImportError:
    AudioSegment = None

from config.config import config

logger = logging.getLogger(__name__)


class VoiceHandler:
    """
    Handles voice processing operations including speech-to-text and text-to-speech
    """

    def __init__(self):
        """Initialize the VoiceHandler with OpenAI client"""
        if not OpenAI:
            raise ImportError("OpenAI library not installed. Run: pip install openai")
        
        if not config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured in environment variables")
        
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        logger.info("VoiceHandler initialized successfully")

    def transcribe_audio(self, audio_file: Union[BinaryIO, str, Path]) -> dict:
        """
        Transcribe audio file to text using OpenAI Whisper.
        
        Args:
            audio_file: Audio file path, file object, or binary data
            
        Returns:
            dict: {
                "success": bool,
                "transcript": str,
                "language": str,
                "duration": float,
                "error": str (if failed)
            }
        """
        try:
            logger.info("Starting audio transcription")
            
            # Handle different input types
            if isinstance(audio_file, (str, Path)):
                with open(audio_file, "rb") as f:
                    response = self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        response_format="verbose_json"
                    )
            else:
                # Assume it's a file-like object
                response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json"
                )
            
            logger.info(f"Transcription successful: {response.text[:100]}...")
            
            return {
                "success": True,
                "transcript": response.text,
                "language": getattr(response, 'language', 'unknown'),
                "duration": getattr(response, 'duration', 0.0)
            }
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            return {
                "success": False,
                "transcript": "",
                "error": str(e)
            }

    def text_to_speech(self, text: str, voice: str = "alloy", model: str = "tts-1") -> dict:
        """
        Convert text to speech using OpenAI TTS.
        
        Args:
            text: Text to convert to speech
            voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
            model: TTS model to use (tts-1 or tts-1-hd)
            
        Returns:
            dict: {
                "success": bool,
                "audio_file": str (path to generated audio),
                "audio_data": bytes,
                "error": str (if failed)
            }
        """
        try:
            logger.info(f"Starting text-to-speech conversion for: {text[:50]}...")
            
            # Validate inputs
            if not text.strip():
                raise ValueError("Text cannot be empty")
            
            valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
            if voice not in valid_voices:
                voice = "alloy"
                logger.warning(f"Invalid voice, using default: {voice}")
            
            # Generate speech
            response = self.client.audio.speech.create(
                model=model,
                voice=voice,
                input=text
            )
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
                tmp_file.write(response.content)
                audio_file_path = tmp_file.name
            
            logger.info(f"TTS successful, saved to: {audio_file_path}")
            
            return {
                "success": True,
                "audio_file": audio_file_path,
                "audio_data": response.content
            }
            
        except Exception as e:
            logger.error(f"Error converting text to speech: {str(e)}")
            return {
                "success": False,
                "audio_file": "",
                "error": str(e)
            }

    def process_voice_request(self, audio_file: Union[BinaryIO, str], mcp_handler_func) -> dict:
        """
        Complete voice processing pipeline:
        1. Transcribe audio to text
        2. Process text through MCP handler
        3. Convert MCP response to speech
        
        Args:
            audio_file: Input audio file
            mcp_handler_func: Function to process MCP requests
            
        Returns:
            dict: Complete voice processing result
        """
        try:
            logger.info("Starting complete voice processing pipeline")
            
            # Step 1: Transcribe audio
            transcription_result = self.transcribe_audio(audio_file)
            if not transcription_result["success"]:
                return {
                    "success": False,
                    "error": f"Transcription failed: {transcription_result.get('error', 'Unknown error')}",
                    "transcript": "",
                    "mcp_response": {},
                    "audio_file": ""
                }
            
            transcript = transcription_result["transcript"]
            logger.info(f"Transcribed text: {transcript}")
            
            # Step 2: Process through MCP handler
            # Try to parse as JSON first, fallback to simple text
            try:
                # Attempt to extract method and params from natural language
                mcp_request = self._parse_natural_language_to_mcp(transcript)
                mcp_response = mcp_handler_func(mcp_request)
            except Exception as e:
                logger.warning(f"Failed to parse as MCP request: {e}")
                # Fallback: treat as simple text
                mcp_response = {
                    "success": True,
                    "message": f"Received voice message: {transcript}",
                    "data": {"transcript": transcript}
                }
            
            # Step 3: Generate response text
            if mcp_response.get("success"):
                response_text = self._format_mcp_response_for_speech(mcp_response)
            else:
                response_text = f"Error processing request: {mcp_response.get('error', 'Unknown error')}"
            
            # Step 4: Convert response to speech
            tts_result = self.text_to_speech(response_text)
            
            return {
                "success": True,
                "transcript": transcript,
                "mcp_response": mcp_response,
                "response_text": response_text,
                "audio_file": tts_result.get("audio_file", ""),
                "tts_success": tts_result["success"],
                "tts_error": tts_result.get("error")
            }
            
        except Exception as e:
            logger.error(f"Error in voice processing pipeline: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "transcript": "",
                "mcp_response": {},
                "audio_file": ""
            }

    def _parse_natural_language_to_mcp(self, text: str) -> dict:
        """
        Parse natural language text into MCP request format.
        This is a basic implementation - can be enhanced with NLP.
        
        Args:
            text: Natural language text
            
        Returns:
            dict: MCP request format
        """
        text_lower = text.lower()
        
        # Basic keyword matching for expense creation
        if any(word in text_lower for word in ["gasto", "expense", "registrar", "crear"]):
            # Extract amount if possible
            import re
            amount_match = re.search(r'(\d+(?:\.\d+)?)', text)
            amount = float(amount_match.group(1)) if amount_match else 100.0
            
            return {
                "method": "create_expense",
                "params": {
                    "description": text,
                    "amount": amount,
                    "employee": "Usuario Voz"
                }
            }
        
        # Default: return as informational request
        return {
            "method": "process_text",
            "params": {
                "text": text
            }
        }

    def _format_mcp_response_for_speech(self, mcp_response: dict) -> str:
        """
        Format MCP response into speech-friendly text.
        
        Args:
            mcp_response: MCP response dictionary
            
        Returns:
            str: Speech-friendly response text
        """
        try:
            if not mcp_response.get("success"):
                return f"Error: {mcp_response.get('error', 'Unknown error')}"
            
            data = mcp_response.get("data", {})
            
            # Handle expense creation responses
            if "expense_id" in data:
                amount = data.get("amount", "unknown")
                expense_id = data.get("expense_id", "unknown")
                return f"Gasto creado exitosamente por {amount} pesos con ID {expense_id}. Estado: pendiente de aprobación."
            
            # Handle expense list responses
            if "expenses" in data:
                count = len(data["expenses"])
                return f"Se encontraron {count} gastos en el sistema."
            
            # Generic success response
            return "Solicitud procesada exitosamente."
            
        except Exception as e:
            logger.error(f"Error formatting response for speech: {e}")
            return "Respuesta procesada."

    def cleanup_temp_files(self, file_path: str):
        """
        Clean up temporary audio files.
        
        Args:
            file_path: Path to temporary file to delete
        """
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.info(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")


# Global voice handler instance
voice_handler = None

def get_voice_handler() -> VoiceHandler:
    """
    Get or create global voice handler instance.
    
    Returns:
        VoiceHandler: Global voice handler instance
    """
    global voice_handler
    if voice_handler is None:
        voice_handler = VoiceHandler()
    return voice_handler


# Convenience functions
def transcribe_audio(audio_file: Union[BinaryIO, str]) -> dict:
    """Convenience function for audio transcription"""
    return get_voice_handler().transcribe_audio(audio_file)


def text_to_speech(text: str, voice: str = "alloy") -> dict:
    """Convenience function for text-to-speech"""
    return get_voice_handler().text_to_speech(text, voice)


def process_voice_request(audio_file: Union[BinaryIO, str], mcp_handler_func) -> dict:
    """Convenience function for complete voice processing"""
    return get_voice_handler().process_voice_request(audio_file, mcp_handler_func)
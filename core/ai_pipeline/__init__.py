"""
AI Pipeline Module

Pipeline de procesamiento con IA/ML incluyendo:
- Parsers: Extracción de texto y datos de documentos
- OCR: Servicios de visión por computadora
- Classification: Categorización automática
- Automation: RPA y automatización inteligente
"""

# Exponemos los módulos principales para facilitar imports
from . import parsers
from . import ocr
from . import classification
from . import automation

__all__ = ['parsers', 'ocr', 'classification', 'automation']

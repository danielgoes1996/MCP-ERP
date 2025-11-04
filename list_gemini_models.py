#!/usr/bin/env python3
"""Lista los modelos disponibles en Gemini API"""
import os
os.environ['GOOGLE_AI_API_KEY'] = '***REMOVED_GEMINI_API_KEY***'

import google.generativeai as genai

genai.configure(api_key=os.environ['GOOGLE_AI_API_KEY'])

print("Modelos disponibles en Gemini API:")
print("="*50)

for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"✅ {model.name}")
        print(f"   Display name: {model.display_name}")
        print(f"   Métodos soportados: {', '.join(model.supported_generation_methods)}")
        print()
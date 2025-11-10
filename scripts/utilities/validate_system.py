#!/usr/bin/env python3
"""
Script de validación rápida del sistema de tickets después de las mejoras.
Testea que los servicios críticos funcionen correctamente.
"""

import asyncio
import os
import sys
from pathlib import Path

async def test_ocr_service():
    """Test del servicio OCR avanzado."""
    print("🔍 Testing OCR Service...")
    try:
        from core.ai_pipeline.ocr.advanced_ocr_service import AdvancedOCRService

        service = AdvancedOCRService()

        # Test de backends disponibles
        health = await service.get_backend_health()

        available_backends = [backend.value for backend, is_healthy in health.items() if is_healthy]
        print(f"   ✅ OCR backends available: {', '.join(available_backends)}")

        # Test básico con imagen dummy
        dummy_base64 = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k="

        result = await service.extract_text_intelligent(dummy_base64, context_hint="ticket")

        if result.backend:
            print(f"   ✅ OCR working with {result.backend.value} backend")
            return True
        else:
            print(f"   ❌ OCR failed")
            return False

    except Exception as e:
        print(f"   ❌ OCR Service error: {e}")
        return False

async def test_ticket_analyzer():
    """Test del analizador de tickets."""
    print("🧠 Testing Ticket Analyzer...")
    try:
        from core.ticket_analyzer import analyze_ticket_content

        test_ticket = """
        OXXO TIENDA #1234
        COCA COLA 600ML $18.50
        TOTAL: $18.50
        RFC: ABC123456789
        """

        analysis = await analyze_ticket_content(test_ticket)

        if analysis and analysis.merchant_name:
            print(f"   ✅ Ticket analysis working: {analysis.merchant_name} - {analysis.category}")
            return True
        else:
            print(f"   ❌ Ticket analysis failed")
            return False

    except Exception as e:
        print(f"   ❌ Ticket Analyzer error: {e}")
        return False

def test_url_extractor():
    """Test del extractor de URLs."""
    print("🔗 Testing URL Extractor...")
    try:
        from modules.invoicing_agent.services.url_extractor import URLExtractor

        extractor = URLExtractor()

        test_text = """
        GASOLINERA PEMEX
        Total: $500.00
        Para tu factura visita: factura.pemex.com
        """

        urls = extractor.extract_urls(test_text)

        if urls:
            print(f"   ✅ URL extraction working: found {len(urls)} URLs")
            for url in urls[:2]:  # Show first 2
                print(f"      → {url.url} (confidence: {url.confidence:.2f})")
            return True
        else:
            print(f"   ❌ URL extraction failed")
            return False

    except Exception as e:
        print(f"   ❌ URL Extractor error: {e}")
        return False

def test_database():
    """Test de la base de datos."""
    print("💾 Testing Database...")
    try:
        from modules.invoicing_agent.models import create_ticket, get_ticket

        # Crear ticket de prueba
        ticket_id = create_ticket(
            raw_data="Test ticket",
            tipo="texto",
            company_id="test"
        )

        # Recuperar ticket
        ticket = get_ticket(ticket_id)

        if ticket and ticket["id"] == ticket_id:
            print(f"   ✅ Database working: created and retrieved ticket #{ticket_id}")
            return True
        else:
            print(f"   ❌ Database failed")
            return False

    except Exception as e:
        print(f"   ❌ Database error: {e}")
        return False

def test_web_automation():
    """Test de automatización web (básico)."""
    print("🌐 Testing Web Automation...")
    try:
        from modules.invoicing_agent.web_automation import WebAutomationWorker

        worker = WebAutomationWorker()

        # Test de configuración del driver (sin inicializar)
        options = worker.setup_driver.__code__.co_varnames

        if 'headless' in options:
            print(f"   ✅ Web automation configured")
            return True
        else:
            print(f"   ❌ Web automation not configured")
            return False

    except Exception as e:
        print(f"   ❌ Web automation error: {e}")
        return False

async def test_api_endpoints():
    """Test de que los endpoints principales se pueden importar."""
    print("🚀 Testing API Endpoints...")
    try:
        from modules.invoicing_agent.api import router

        # Contar rutas definidas
        routes = len(router.routes)

        if routes > 0:
            print(f"   ✅ API endpoints configured: {routes} routes")
            return True
        else:
            print(f"   ❌ No API routes found")
            return False

    except Exception as e:
        print(f"   ❌ API endpoints error: {e}")
        return False

async def main():
    """Ejecutar todos los tests."""
    print("🧪 SISTEMA DE TICKETS - VALIDACIÓN POST-AUDITORÍA")
    print("=" * 55)

    tests = [
        ("OCR Service", test_ocr_service()),
        ("Ticket Analyzer", test_ticket_analyzer()),
        ("URL Extractor", test_url_extractor()),
        ("Database", test_database()),
        ("Web Automation", test_web_automation()),
        ("API Endpoints", test_api_endpoints()),
    ]

    results = []

    for test_name, test_coro in tests:
        if asyncio.iscoroutine(test_coro):
            result = await test_coro
        else:
            result = test_coro
        results.append((test_name, result))

    print(f"\n📊 RESULTS SUMMARY")
    print("-" * 25)

    passed = 0
    failed = 0

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {test_name}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\n🎯 FINAL SCORE: {passed}/{len(results)} tests passed")

    if failed == 0:
        print("🎉 ALL SYSTEMS OPERATIONAL!")
        print("💡 El módulo de tickets está listo para usar")
        print("⚠️  Recuerda configurar las API keys en .env")
    elif failed <= 2:
        print("⚠️  Minor issues detected")
        print("💡 El sistema funcionará pero con limitaciones")
    else:
        print("🚨 Major issues detected")
        print("💡 Revisar configuración antes de usar")

    return failed == 0

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
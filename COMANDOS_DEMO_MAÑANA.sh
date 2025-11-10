#!/bin/bash
#
# 🎯 COMANDOS PARA DEMO VC - MAÑANA
# Copiar y pegar estos comandos exactamente como están
#

echo "=========================================="
echo "🚀 PREPARACIÓN DEMO VC"
echo "=========================================="
echo ""

# Directorio base
cd /Users/danielgoes96/Desktop/mcp-server

echo "1️⃣  Verificando sistema..."
python3 demo/verificacion_final.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Sistema verificado correctamente"
    echo ""
else
    echo ""
    echo "❌ ERROR: Sistema no pasó verificación"
    echo "Por favor revisa los errores arriba"
    exit 1
fi

echo "=========================================="
echo "📋 OPCIONES DE DEMO"
echo "=========================================="
echo ""
echo "Elige una opción:"
echo ""
echo "  A) Demo Script Interactivo (Recomendado)"
echo "     python3 demo/DEMO_COMPLETA.py"
echo ""
echo "  B) Frontend Live"
echo "     1. docker-compose up -d postgres"
echo "     2. uvicorn main:app --reload --port 8001 &"
echo "     3. cd frontend && npm run dev &"
echo "     4. open http://localhost:3000/reconciliation"
echo ""
echo "  C) API REST (Swagger)"
echo "     1. uvicorn main:app --reload --port 8001 &"
echo "     2. open http://localhost:8001/docs"
echo ""
echo "=========================================="
echo ""

read -p "¿Quieres ejecutar la DEMO SCRIPT ahora? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🎬 Ejecutando demo script..."
    echo ""
    python3 demo/DEMO_COMPLETA.py
else
    echo ""
    echo "📖 Consulta GUIA_RAPIDA_VC.md para instrucciones completas"
    echo ""
fi

echo ""
echo "=========================================="
echo "✅ LISTO PARA PRESENTACIÓN"
echo "=========================================="
echo ""
echo "URLs importantes:"
echo "  - Backend API: http://localhost:8001"
echo "  - Swagger Docs: http://localhost:8001/docs"
echo "  - Frontend: http://localhost:3000"
echo "  - Conciliación: http://localhost:3000/reconciliation"
echo ""
echo "Documentación:"
echo "  - GUIA_RAPIDA_VC.md"
echo "  - SISTEMA_LISTO_VC.md"
echo "  - README.md"
echo ""
echo "¡Éxito en la presentación! 🚀"
echo ""

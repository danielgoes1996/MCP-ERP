#!/bin/bash
cd "$(dirname "$0")"
echo "================================================================================"
echo "✅ VERIFICACIÓN MENSUAL DE FACTURAS"
echo "================================================================================"
python3 scripts/utilities/verificar_todas_companias.py --verify-sat --notify --yes

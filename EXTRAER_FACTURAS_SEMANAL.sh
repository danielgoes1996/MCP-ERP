#!/bin/bash
cd "$(dirname "$0")"
echo "================================================================================"
echo "📥 EXTRACCIÓN SEMANAL DE FACTURAS"
echo "================================================================================"
python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --yes

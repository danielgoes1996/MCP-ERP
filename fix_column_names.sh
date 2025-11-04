#!/bin/bash

# Fix all column name references in the API file
cd /Users/danielgoes96/Desktop/mcp-server

# Create backup
cp api/expense_placeholder_completion_api.py api/expense_placeholder_completion_api.py.backup

# Replace column names in SQL queries
sed -i.tmp '
s/monto_total/amount/g
s/fecha_gasto/expense_date/g
s/descripcion/description/g
s/categoria/category/g
s/proveedor_nombre/provider_name/g
s/proveedor_rfc/provider_rfc/g
s/rfc_proveedor/provider_rfc/g
' api/expense_placeholder_completion_api.py

rm api/expense_placeholder_completion_api.py.tmp

echo "✅ Column names fixed"
echo "Backup saved as: api/expense_placeholder_completion_api.py.backup"

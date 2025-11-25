#!/bin/bash
echo "🔐 Haciendo login..."
TOKEN=$(curl -s -X POST http://localhost:8004/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "dgomezes96@gmail.com", "password": "temp123"}' | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "🏦 Obteniendo transacciones de cuenta 5..."
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8004/bank-movements/account/5" | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Total transacciones: {len(data)}')
for i, txn in enumerate(data[:10]):
    print(f'{i+1:2d}. {txn[\"date\"]} - {txn[\"description\"][:40]} - \${txn[\"amount\"]}')
"
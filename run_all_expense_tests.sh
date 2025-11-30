#!/bin/bash
# Script para ejecutar todos los ejemplos de testing de gastos

echo "════════════════════════════════════════════════════════════════"
echo "🧪 SUITE DE PRUEBAS - Sistema de Gastos PostgreSQL"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Obtener token de autenticación
echo "🔐 Paso 1: Autenticación..."
TOKEN_RESPONSE=$(curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@test.com&password=test123" \
  -s)

TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>&1)

if [[ "$TOKEN" == *"error"* ]] || [[ -z "$TOKEN" ]]; then
  echo "❌ Error de autenticación"
  exit 1
fi

echo "✅ Token obtenido"
echo ""

# Función para ejecutar un test
run_test() {
    local test_name=$1
    local test_file=$2
    local expected_status=$3

    echo "────────────────────────────────────────────────────────────────"
    echo "📝 $test_name"
    echo "────────────────────────────────────────────────────────────────"

    RESPONSE=$(curl -X POST http://localhost:8000/expenses \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d @$test_file \
      -s -w "\nHTTP_STATUS:%{http_code}")

    # Separar respuesta y status code
    BODY=$(echo "$RESPONSE" | sed -n '1,/HTTP_STATUS:/p' | sed '$d')
    STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)

    echo "HTTP Status: $STATUS"

    if [[ "$STATUS" == "$expected_status" ]]; then
        echo "✅ Test PASÓ (esperado: $expected_status)"
    else
        echo "❌ Test FALLÓ (esperado: $expected_status, obtenido: $STATUS)"
    fi

    echo ""
    echo "Respuesta:"
    echo "$BODY" | python3 -m json.tool 2>&1 | head -30
    echo ""
}

# EJEMPLO 1: Gasto mínimo
run_test "EJEMPLO 1: Gasto Mínimo (solo campos requeridos)" \
         "test_minimal_expense.json" \
         "200"

# EJEMPLO 2: Gasto completo
run_test "EJEMPLO 2: Gasto Completo (todos los campos)" \
         "test_complete_expense.json" \
         "200"

# EJEMPLO 3: Gasto con gasolina
run_test "EJEMPLO 3: Gasto de Gasolina" \
         "test_gasoline_expense.json" \
         "200"

# EJEMPLO 4: Validación de datos inválidos
run_test "EJEMPLO 4: Validación de Datos Inválidos (debe fallar)" \
         "test_invalid_expense.json" \
         "422"

echo "════════════════════════════════════════════════════════════════"
echo "📊 RESUMEN DE PRUEBAS"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Verificar gastos en la base de datos
echo "🗄️  Últimos gastos creados en PostgreSQL:"
docker exec mcp-postgres psql -U mcp_user -d mcp_system -c \
  "SELECT id, description, amount, category, expense_date, created_at
   FROM manual_expenses
   ORDER BY id DESC
   LIMIT 5"

echo ""
echo "✅ Suite de pruebas completada"

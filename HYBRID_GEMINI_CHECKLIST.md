# ✅ Hybrid Gemini Implementation - Checklist

**Fecha**: 2025-11-25

---

## 📋 ESTADO DE IMPLEMENTACIÓN

### ✅ COMPLETADO

- [x] **Módulo de similitud creado** - [`core/concept_similarity.py`](core/concept_similarity.py)
  - Funciones de string matching (Jaccard, Levenshtein, números)
  - Integración con Gemini LLM
  - Sistema híbrido con decisión inteligente
  - Cache LRU para optimizar llamadas a Gemini

- [x] **API actualizado** - [`api/invoice_to_expense_matching_api.py`](api/invoice_to_expense_matching_api.py)
  - Importa `calculate_concept_match_score_hybrid`
  - Calcula concept_score para cada match
  - Aplica boost/penalización según similitud
  - Retorna metadata detallada (método, scores, llamadas)

- [x] **Migración de base de datos** - [`migrations/add_ticket_extracted_concepts.sql`](migrations/add_ticket_extracted_concepts.sql)
  - Columna `ticket_extracted_concepts JSONB`
  - Columna `ticket_extracted_data JSONB`
  - Columna `ticket_folio VARCHAR(100)`
  - Índices GIN para JSONB
  - **Estado**: ✅ Aplicada exitosamente

- [x] **Dependencias instaladas**
  - `google-generativeai==0.8.5` ✅ Instalado
  - **Estado**: Verificado con `pip3 list`

- [x] **Configuración de entorno**
  - `GEMINI_API_KEY` en `.env` ✅ Configurado
  - **Valor**: `AIzaSyDhpkT7IcePCcb3SSsdz7AZxWUSgZm6Z8I`

- [x] **Modelo Gemini corregido**
  - **Problema**: `gemini-pro` no disponible (404 error)
  - **Solución**: Actualizado a `gemini-2.5-flash`
  - **Estado**: ✅ Funcionando correctamente

- [x] **Tests unitarios**
  - Test de similitud de conceptos ✅
  - Test híbrido con Gemini ✅
  - **Resultado**: Score 85/100, método hybrid_gemini, 1 llamada Gemini

- [x] **Documentación**
  - [QUICK_START_CONCEPT_SIMILARITY.md](QUICK_START_CONCEPT_SIMILARITY.md) ✅
  - [CONCEPT_SIMILARITY_TECHNICAL_GUIDE.md](CONCEPT_SIMILARITY_TECHNICAL_GUIDE.md) ✅
  - [CONCEPT_SIMILARITY_IMPLEMENTATION_SUMMARY.md](CONCEPT_SIMILARITY_IMPLEMENTATION_SUMMARY.md) ✅
  - [HYBRID_GEMINI_IMPLEMENTATION.md](HYBRID_GEMINI_IMPLEMENTATION.md) ✅
  - [HYBRID_GEMINI_SUCCESS_SUMMARY.md](HYBRID_GEMINI_SUCCESS_SUMMARY.md) ✅

---

## 🔄 PENDIENTE (TESTING END-TO-END)

### Paso 1: Reiniciar Servidor ⏳

```bash
# Matar servidores existentes
pkill -f "uvicorn main:app"

# Esperar 2 segundos
sleep 2

# Iniciar servidor limpio
python3 -m uvicorn main:app --reload --port 8000 --host 0.0.0.0
```

**Verificar**:
```bash
curl http://localhost:8000/health
# Debería retornar: {"status":"ok"}
```

---

### Paso 2: Obtener Token de Autenticación ⏳

**Opción A: Si ya tienes usuario**:
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"test@test.com","password":"test123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "Token obtenido: $TOKEN"
```

**Opción B: Crear nuevo usuario**:
```bash
# 1. Crear usuario
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@example.com",
    "password": "demo123",
    "full_name": "Demo User",
    "tenant_id": 2
  }'

# 2. Obtener token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"demo@example.com","password":"demo123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "Token: $TOKEN"
```

---

### Paso 3: Crear Gasto con Conceptos Extraídos ⏳

```bash
curl -X POST http://localhost:8000/expenses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "descripcion": "Gasolina auto empresa",
    "monto_total": 860.00,
    "fecha_gasto": "2025-11-20",
    "categoria": "combustible_gasolina",
    "proveedor": {
      "nombre": "Pemex",
      "rfc": "PRE850101ABC"
    },
    "ticket_extracted_concepts": ["MAGNA 40 LITROS"],
    "ticket_extracted_data": {
      "merchant_name": "Pemex",
      "rfc": "PRE850101ABC",
      "total": 860.00,
      "litros": 40.0,
      "precio_litro": 21.50,
      "extraction_method": "ocr_claude"
    },
    "company_id": "2",
    "payment_account_id": 1
  }' | python3 -m json.tool
```

**Respuesta esperada**:
```json
{
  "expense_id": 123,
  "status": "pending_invoice",
  "descripcion": "Gasolina auto empresa",
  "monto_total": 860.0,
  "proveedor_rfc": "PRE850101ABC",
  "ticket_extracted_concepts": ["MAGNA 40 LITROS"]
}
```

**Guardar expense_id para el siguiente paso**:
```bash
EXPENSE_ID=123  # Reemplazar con el ID real
```

---

### Paso 4: Crear/Cargar Factura CFDI ⏳

**Opción A: Si ya tienes una factura**:
```bash
# Listar facturas existentes
curl -X GET "http://localhost:8000/invoices?company_id=2" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Seleccionar una factura con RFC PRE850101ABC
INVOICE_UUID="ABC-123-456..."  # Reemplazar con UUID real
```

**Opción B: Crear factura de prueba**:
```bash
# Crear factura sintética para testing
curl -X POST http://localhost:8000/invoices/synthetic \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "emisor": {
      "rfc": "PRE850101ABC",
      "nombre": "Pemex Refinación S.A. de C.V."
    },
    "total": 860.00,
    "fecha": "2025-11-20",
    "conceptos": [
      {
        "descripcion": "Combustible Magna sin plomo",
        "cantidad": "40",
        "unidad": "litros",
        "precio_unitario": "21.50"
      }
    ],
    "company_id": "2"
  }' | python3 -m json.tool

# Guardar UUID de respuesta
INVOICE_UUID="..."  # Obtener de respuesta
```

---

### Paso 5: Ejecutar Matching con Híbrido Gemini ⏳

```bash
curl -X POST "http://localhost:8000/invoice-matching/match-invoice/$INVOICE_UUID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  | python3 -m json.tool
```

**Respuesta esperada (Auto-match)**:
```json
{
  "status": "success",
  "action": "auto_matched",
  "case": 1,
  "expense_id": 123,
  "invoice_uuid": "ABC-123-456...",
  "match_score": 100,
  "concept_score": 85,
  "concept_confidence": "high",
  "concept_boost": "high",
  "concept_method": "hybrid_gemini",
  "concept_gemini_calls": 1,
  "concept_string_score": 53,
  "concept_gemini_score": 100,
  "match_reason": "High confidence match with RFC + amount + date + concepts (high similarity)",
  "best_match": {
    "ticket": "MAGNA 40 LITROS",
    "invoice": "Combustible Magna sin plomo"
  }
}
```

**Validaciones**:
- ✅ `action`: `auto_matched` (matching automático)
- ✅ `concept_method`: `hybrid_gemini` (Gemini fue usado)
- ✅ `concept_gemini_calls`: 1 (una llamada a Gemini)
- ✅ `concept_gemini_score`: 100 (Gemini identificó correctamente)
- ✅ `concept_string_score`: 53 (string matching moderado)
- ✅ `concept_score`: 85 (combinación híbrida)

---

### Paso 6: Verificar Gasto Actualizado ⏳

```bash
curl -X GET "http://localhost:8000/expenses/$EXPENSE_ID" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool
```

**Validar**:
```json
{
  "expense_id": 123,
  "status": "invoiced",  // ← Debe estar "invoiced" ahora
  "invoice_uuid": "ABC-123-456...",  // ← UUID de la factura asignada
  "ticket_extracted_concepts": ["MAGNA 40 LITROS"],
  ...
}
```

---

## 📊 RESULTADOS ESPERADOS

### Test Exitoso Debe Mostrar:

1. **Gemini fue llamado** cuando string score estaba en rango ambiguo (30-70%)
2. **Score combinado** es mejor que string solo
3. **Metadata completa** incluye todos los scores individuales
4. **Auto-match** ocurrió con alta confianza
5. **Gasto vinculado** a factura correcta

### Ejemplo de Output Final:

```json
{
  "status": "success",
  "action": "auto_matched",
  "match_score": 100,
  "concept_score": 85,
  "concept_method": "hybrid_gemini",
  "concept_gemini_calls": 1,
  "concept_string_score": 53,
  "concept_gemini_score": 100
}
```

---

## 🐛 TROUBLESHOOTING

### Error: "401 Unauthorized"
```bash
# Regenerar token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"test@test.com","password":"test123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
```

### Error: "Gemini API error: 404"
```bash
# Verificar modelo en core/concept_similarity.py línea 35
# Debe ser: genai.GenerativeModel('gemini-2.5-flash')
grep -n "GenerativeModel" core/concept_similarity.py
```

### Error: "ticket_extracted_concepts not found"
```bash
# Verificar migración aplicada
docker exec mcp-postgres psql -U mcp_user -d mcp_system -c \
  "SELECT column_name FROM information_schema.columns WHERE table_name='manual_expenses' AND column_name='ticket_extracted_concepts'"
```

### Error: "payment_account_id required"
```bash
# Agregar payment_account_id al JSON de creación de gasto
# Ver Paso 3 arriba
```

---

## 📚 DOCUMENTACIÓN DE REFERENCIA

- **Quick Start**: [QUICK_START_CONCEPT_SIMILARITY.md](QUICK_START_CONCEPT_SIMILARITY.md)
- **Guía Técnica**: [CONCEPT_SIMILARITY_TECHNICAL_GUIDE.md](CONCEPT_SIMILARITY_TECHNICAL_GUIDE.md)
- **Resumen de Implementación**: [CONCEPT_SIMILARITY_IMPLEMENTATION_SUMMARY.md](CONCEPT_SIMILARITY_IMPLEMENTATION_SUMMARY.md)
- **Guía Híbrido Gemini**: [HYBRID_GEMINI_IMPLEMENTATION.md](HYBRID_GEMINI_IMPLEMENTATION.md)
- **Resumen de Éxito**: [HYBRID_GEMINI_SUCCESS_SUMMARY.md](HYBRID_GEMINI_SUCCESS_SUMMARY.md)

---

## ✅ CHECKLIST FINAL

- [x] Módulo de similitud creado
- [x] API actualizado con híbrido
- [x] Migración aplicada
- [x] Gemini API key configurado
- [x] Modelo Gemini corregido (2.5-flash)
- [x] Tests unitarios pasando
- [x] Documentación completa
- [ ] Test end-to-end completado
- [ ] Gasto creado con concepts
- [ ] Matching ejecutado exitosamente
- [ ] Gasto vinculado a factura

**Estado General**: 70% Completo ✅

**Próximo Paso**: Ejecutar Pasos 1-6 de testing end-to-end

---

**Última actualización**: 2025-11-25
**Preparado por**: Claude Code

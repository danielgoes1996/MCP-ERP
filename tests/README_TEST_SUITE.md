# Suite de Tests para Sistema de Gastos

Esta documentación describe la suite completa de tests creada para validar el flujo de creación de gastos y sus mejoras.

## Archivos de Tests

### 1. `test_expense_models.py` - Tests Unitarios de Modelos

**Líneas:** ~700
**Tests:** 80+
**Cobertura:** Validadores Pydantic de `ExpenseCreate`, `ExpenseCreateEnhanced`, `ExpenseResponse`

#### Clases de Tests:

##### `TestProveedorDataModel`
- Creación válida de proveedor
- RFC opcional
- Validación de nombre requerido

##### `TestExpenseCreateRFCValidation`
- RFC válido de 12 y 13 caracteres
- Normalización a mayúsculas
- Limpieza de espacios
- Rechazo de RFC muy corto/largo
- Rechazo de RFC con caracteres especiales
- RFC None como válido

**Casos de prueba:**
```python
✅ PEM840212XY1    # 12 chars - válido
✅ GOMD8901011A3   # 13 chars - válido
✅ pem840212xy1    # Se normaliza a mayúsculas
❌ ABC123          # Muy corto
❌ PEM-840212-XY1  # Contiene guiones
```

##### `TestExpenseCreateFechaValidation`
- Fechas válidas (hoy, ayer, pasadas)
- Rechazo de fechas futuras (+7 días)
- Rechazo de formatos inválidos (DD/MM/YYYY, DD.MM.YYYY)

**Casos de prueba:**
```python
✅ 2025-01-15      # Fecha pasada - válido
✅ [hoy]           # Fecha actual - válido
❌ 2025-12-31      # Fecha futura - rechazado
❌ 15/01/2025      # Formato incorrecto - rechazado
```

##### `TestExpenseCreateMontoValidation`
- Montos positivos válidos
- Montos grandes válidos (< 10M)
- Montos decimales pequeños
- Rechazo de monto cero
- Rechazo de monto negativo
- Rechazo de monto > 10M MXN

**Casos de prueba:**
```python
✅ 100.50          # Válido
✅ 9,999,999.99    # Válido (< 10M)
✅ 0.01            # Válido (pequeño)
❌ 0               # Rechazado
❌ -100            # Rechazado
❌ 15,000,000      # Rechazado (> 10M)
```

##### `TestExpenseCreateCategoriaNormalization`
- Normalización a minúsculas
- Limpieza de espacios
- Categoría None como válida

##### `TestExpenseCreateDefaultValues`
- `workflow_status = "draft"`
- `estado_factura = "pendiente"`
- `estado_conciliacion = "pendiente"`
- `paid_by = "company_account"`
- `will_have_cfdi = True`
- `company_id = "default"`

##### `TestExpenseCreateComplexScenarios`
- Gastos completos con proveedor
- Gastos con información fiscal (tax_info)
- Gastos con metadata adicional

##### `TestExpenseCreateEnhanced`
- Herencia de ExpenseCreate
- check_duplicates = True por defecto
- ml_features opcional

---

### 2. `test_category_mappings.py` - Tests de Mapeo de Categorías

**Líneas:** ~550
**Tests:** 65+
**Cobertura:** Módulo `core/category_mappings.py`

#### Clases de Tests:

##### `TestGetAccountCodeForCategory`
Verifica mapeos de todas las categorías principales:

| Categoría | Cuenta SAT | Test |
|-----------|-----------|------|
| combustibles, gasolina | 6140 | ✅ |
| viajes, viaticos | 6150 | ✅ |
| alimentos, comida | 6150 | ✅ |
| servicios | 6130 | ✅ |
| oficina, papeleria | 6180 | ✅ |
| honorarios, freelance | 6110 | ✅ |
| renta, arrendamiento | 6120 | ✅ |
| publicidad, marketing | 6160 | ✅ |
| software, licencias | 6180 | ✅ |
| mantenimiento | 6170 | ✅ |

**Normalización:**
- Case insensitive (COMBUSTIBLES → combustibles)
- Limpia espacios ("  viajes  " → "viajes")
- Soporta acentos ("viáticos" → válido)

**Categorías desconocidas:**
- Retorna `DEFAULT_ACCOUNT_CODE` (6180)

##### `TestGetAllCategories`
- Retorna diccionario completo
- Contiene todas las categorías esperadas
- Todos los valores son strings de 4 dígitos
- Retorna copia, no referencia

##### `TestGetCategoriesForAccount`
- Búsqueda inversa: 6140 → ["combustibles", "gasolina", "diesel", ...]
- Cuenta desconocida retorna lista vacía

##### `TestRegisterCustomCategoryMapping`
- Registra nuevas categorías custom
- Normaliza al registrar
- Permite sobrescribir existentes
- Mapeos persisten entre llamadas

##### `TestCategoryMappingIntegration`
- Consistencia entre funciones
- Workflow típico de usuario
- Reverse lookup completo

##### `TestCoverageOfKnownCategories`
- 100% de cobertura de categorías de:
  - Combustibles (4 variantes)
  - Viajes (5 variantes)
  - Alimentos (5 variantes)
  - Servicios profesionales (4 variantes)
  - Renta (3 variantes)
  - Marketing (4 variantes)

---

### 3. `test_expense_endpoints.py` - Tests de Integración

**Líneas:** ~650
**Tests:** 45+
**Cobertura:** Endpoints `/expenses`, `/expenses/enhanced`, `/api/expenses/simple`

#### Clases de Tests:

##### `TestPOSTExpensesBasicCreation`
- Creación con campos mínimos
- Creación con campos completos
- Creación con metadata

**Ejemplo:**
```python
async def test_create_minimal_expense(self, client):
    payload = {
        "descripcion": "Gasto de prueba",
        "monto_total": 100.50,
        "fecha_gasto": "2025-01-15"
    }
    resp = await client.post('/expenses', json=payload)
    assert resp.status_code == 200
```

##### `TestPOSTExpensesValidations`
- Rechazo de monto zero/negativo/excesivo
- Rechazo de fecha futura
- Rechazo de formato de fecha incorrecto
- Rechazo de RFC inválido
- Rechazo de descripción vacía

**Códigos de estado esperados:**
- `200` - Creación exitosa
- `422` - Error de validación (Unprocessable Entity)

##### `TestPOSTExpensesCategoryMapping`
- Verificación de mapeo automático
- Normalización de categoría a minúsculas
- Categorías desconocidas no bloquean creación

##### `TestPOSTExpensesDefaults`
- Aplicación de valores por defecto
- Posibilidad de sobrescribir defaults

##### `TestPOSTExpensesRFCNormalization`
- Normalización a mayúsculas en respuesta
- Limpieza de espacios

##### `TestPOSTExpensesEnhanced`
- Creación con detección de duplicados
- Posibilidad de deshabilitar check

##### `TestPOSTExpensesSimple`
- Endpoint simplificado para voz/OCR

##### `TestPOSTExpensesMultipleCreation`
- Creación secuencial múltiple
- Aislamiento por company_id

##### `TestPOSTExpensesErrorHandling`
- Manejo de campos faltantes
- JSON inválido
- Content-Type incorrecto

##### `TestPOSTExpensesResponseStructure`
- Verificación de campos en respuesta
- Timestamps de creación

---

## Ejecutar Tests

### Ejecutar Suite Completa
```bash
pytest tests/test_expense_models.py tests/test_category_mappings.py tests/test_expense_endpoints.py -v
```

### Ejecutar Solo Tests Unitarios
```bash
pytest tests/test_expense_models.py tests/test_category_mappings.py -v
```

### Ejecutar Solo Tests de Integración
```bash
pytest tests/test_expense_endpoints.py -v
```

### Ejecutar Tests Específicos
```bash
# Solo tests de validación de RFC
pytest tests/test_expense_models.py::TestExpenseCreateRFCValidation -v

# Solo tests de mapeo de categorías
pytest tests/test_category_mappings.py::TestGetAccountCodeForCategory -v

# Solo tests de validaciones del endpoint
pytest tests/test_expense_endpoints.py::TestPOSTExpensesValidations -v
```

### Con Cobertura
```bash
pytest tests/test_expense_*.py --cov=core.api_models --cov=core.category_mappings --cov-report=html
```

### Con Output Detallado
```bash
pytest tests/test_expense_*.py -vv --tb=short
```

---

## Estadísticas de Cobertura

### Archivos Cubiertos

| Archivo | Tests | Líneas | Cobertura Estimada |
|---------|-------|--------|-------------------|
| `core/api_models.py` | 80+ | ~385 | ~95% |
| `core/category_mappings.py` | 65+ | ~180 | ~98% |
| `main.py` (endpoints) | 45+ | ~100 | ~85% |

### Total
- **Tests:** 190+
- **Líneas de código de tests:** ~1,900
- **Tiempo de ejecución:** ~5-10 segundos

---

## Casos de Prueba Destacados

### 1. Validación de RFC Completa
```python
✅ Casos válidos:
   - PEM840212XY1 (12 chars, moral)
   - GOMD8901011A3 (13 chars, física)
   - pem840212xy1 (normalizado)
   - "  PEM840212XY1  " (con espacios)

❌ Casos inválidos:
   - ABC123 (muy corto)
   - PEM840212XY123456 (muy largo)
   - PEM-840212-XY1 (con guiones)
```

### 2. Validación de Montos
```python
✅ Casos válidos:
   - 0.01 (mínimo razonable)
   - 9,999,999.99 (justo bajo el límite)

❌ Casos inválidos:
   - 0 (cero)
   - -100 (negativo)
   - 15,000,000 (excede 10M)
```

### 3. Mapeo de Categorías
```python
✅ Variantes soportadas:
   Combustible:
   - combustible, combustibles, gasolina, diesel, transporte → 6140

   Viajes:
   - viajes, viaticos, viáticos, hospedaje, hotel → 6150

   Alimentos:
   - alimentos, comida, restaurante, alimentacion, alimentación → 6150
```

---

## Beneficios de esta Suite

### 1. Detección Temprana de Errores
- Validaciones Pydantic se prueban antes de deployment
- Cambios en modelos causan fallos inmediatos en tests

### 2. Documentación Viva
- Tests sirven como ejemplos de uso
- Casos límite documentados en código

### 3. Refactoring Seguro
- Cambios en `category_mappings.py` verificados automáticamente
- Modificaciones en validadores detectadas inmediatamente

### 4. Regresión Prevención
- Suite completa se ejecuta en CI/CD
- Nuevos features no rompen funcionalidad existente

### 5. Cobertura Exhaustiva
- 190+ casos de prueba
- Todos los validadores cubiertos
- Todos los mapeos verificados
- Todos los endpoints probados

---

## Próximos Pasos

### Tests Adicionales Recomendados

1. **Tests de Performance**
   - Creación de 1000+ gastos
   - Tiempo de respuesta bajo carga

2. **Tests de Concurrencia**
   - Múltiples requests simultáneos
   - Race conditions en creación

3. **Tests de BD**
   - Verificar integridad de datos guardados
   - Verificar transacciones

4. **Tests E2E**
   - Flujo completo desde frontend
   - Integración con sistemas externos

5. **Tests de Seguridad**
   - SQL injection prevention
   - XSS prevention en campos de texto

---

## Mantenimiento

### Actualizar Tests Cuando:

1. **Agregar nueva categoría:**
   - Añadir test en `TestCoverageOfKnownCategories`
   - Verificar mapeo en `TestGetAccountCodeForCategory`

2. **Cambiar validación:**
   - Actualizar tests en `TestExpenseCreate*Validation`
   - Verificar que endpoints reflejen cambio

3. **Agregar campo al modelo:**
   - Añadir test en `TestExpenseCreateRequiredFields` si es requerido
   - Añadir test en `TestExpenseCreateDefaultValues` si tiene default

4. **Modificar endpoint:**
   - Actualizar tests en `TestPOSTExpenses*`
   - Verificar códigos de estado

---

## Comandos Útiles

### Ver tests que fallan
```bash
pytest tests/test_expense_*.py --lf  # Last failed
```

### Ver solo nombres de tests
```bash
pytest tests/test_expense_*.py --collect-only
```

### Ejecutar con debugger
```bash
pytest tests/test_expense_*.py --pdb
```

### Generar reporte HTML
```bash
pytest tests/test_expense_*.py --html=report.html --self-contained-html
```

---

## Integración con CI/CD

### GitHub Actions
```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov
      - name: Run test suite
        run: |
          pytest tests/test_expense_*.py -v --cov --cov-report=term
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

---

**Última actualización:** 2025-01-15
**Mantenido por:** Equipo de Backend
**Versión:** 1.0

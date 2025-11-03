# Guía de Endpoints de Gastos (Expenses)

Esta guía documenta los endpoints disponibles para la creación y gestión de gastos en el sistema.

## Tabla de Contenidos
- [Endpoints Disponibles](#endpoints-disponibles)
- [¿Cuál Endpoint Usar?](#cuál-endpoint-usar)
- [Modelos de Datos](#modelos-de-datos)
- [Validaciones Automáticas](#validaciones-automáticas)
- [Ejemplos de Uso](#ejemplos-de-uso)

---

## Endpoints Disponibles

### 1. `POST /expenses` - Creación Estándar de Gastos

**Descripción:** Endpoint principal para crear gastos con validaciones automáticas.

**Ubicación en código:** `main.py:2935`

**Características:**
- ✅ Validaciones automáticas de Pydantic (monto, RFC, fecha)
- ✅ Mapeo automático de categoría → cuenta contable
- ✅ Soporte completo para información fiscal (CFDI)
- ✅ Integración con sistema de tenencia multi-empresa
- ❌ NO verifica duplicados automáticamente

**Request Body:**
```json
{
  "descripcion": "Gasolina para vehículo de reparto",
  "monto_total": 850.50,
  "fecha_gasto": "2025-01-15",
  "proveedor": {
    "nombre": "Gasolinera PEMEX",
    "rfc": "PEM840212XY1"
  },
  "rfc": "PEM840212XY1",
  "categoria": "combustibles",
  "forma_pago": "tarjeta",
  "paid_by": "company_account",
  "will_have_cfdi": true,
  "workflow_status": "draft",
  "estado_factura": "pendiente",
  "estado_conciliacion": "pendiente",
  "company_id": "default"
}
```

**Response:** `ExpenseResponse` (ver [Modelos de Datos](#modelos-de-datos))

**Códigos de Estado:**
- `200` - Gasto creado exitosamente
- `400` - Error de validación (datos inválidos)
- `500` - Error interno del servidor

---

### 2. `POST /expenses/enhanced` - Creación con Detección de Duplicados

**Descripción:** Versión extendida del endpoint estándar con detección automática de duplicados.

**Ubicación en código:** `main.py:2603`

**Características:**
- ✅ Todas las características de `/expenses`
- ✅ Detección automática de duplicados
- ✅ Cálculo de score de similitud
- ✅ Nivel de riesgo automático (low/medium/high)
- ✅ Guardado de features ML para análisis

**Request Body:**
Igual que `/expenses` más estos campos opcionales:
```json
{
  // ... campos de ExpenseCreate
  "check_duplicates": true,           // default: true
  "ml_features": { ... },             // opcional
  "auto_action_on_duplicates": "warn" // opcional: "warn" | "block" | "ignore"
}
```

**Response:** `ExpenseResponseEnhanced`
```json
{
  // ... campos de ExpenseResponse
  "duplicate_ids": [123, 456],      // IDs de posibles duplicados
  "similarity_score": 0.87,         // Score 0-1
  "risk_level": "high"              // "low" | "medium" | "high"
}
```

**¿Cuándo usar este endpoint?**
- Cuando quieras evitar gastos duplicados
- En integraciones automáticas (scrapers, imports)
- Cuando proceses muchos gastos en batch

---

### 3. `POST /api/expenses/simple` - Creación Simplificada (Voz/OCR)

**Descripción:** Endpoint simplificado para interfaces de voz y OCR.

**Ubicación en código:** `main.py:1114`

**Características:**
- ✅ Acepta formato simplificado de campos
- ✅ Integración directa con Odoo
- ✅ Mapeo automático de campos
- ❌ Menos validaciones que endpoints principales
- ❌ No retorna modelo estructurado

**Request Body:**
```json
{
  "descripcion": "Comida en restaurante",
  "monto_total": 450.00,
  "fecha_gasto": "2025-01-15",
  "categoria": "alimentacion"
}
```

**Response:** `JSONResponse` genérica

**¿Cuándo usar este endpoint?**
- En la interfaz de voz (voice-expenses.jsx)
- En procesamiento de tickets con OCR
- Cuando necesites rapidez sobre validación exhaustiva

---

## ¿Cuál Endpoint Usar?

```
┌─────────────────────────────────────────────────────────────┐
│                     Flujo de Decisión                       │
└─────────────────────────────────────────────────────────────┘

¿Necesitas detección de duplicados?
    │
    ├─ Sí ────────────────────► POST /expenses/enhanced
    │
    └─ No ─► ¿Tienes todos los campos validados?
                │
                ├─ Sí ─────────► POST /expenses
                │
                └─ No ─────────► POST /api/expenses/simple
```

### Matriz de Decisión

| Caso de Uso | Endpoint Recomendado | Razón |
|-------------|---------------------|-------|
| Captura manual web | `/expenses` | Validación completa |
| Import masivo de facturas | `/expenses/enhanced` | Evita duplicados |
| Interfaz de voz | `/api/expenses/simple` | Menos fricción |
| Procesamiento OCR de tickets | `/api/expenses/simple` | Datos parciales |
| Integración ERP | `/expenses` | Modelo estándar |
| Script de migración | `/expenses/enhanced` | Previene duplicados |

---

## Modelos de Datos

### ExpenseCreate (Request)

**Ubicación:** `core/api_models.py:261`

**Campos obligatorios:**
- `descripcion` (string, min 1 char) - Descripción del gasto
- `monto_total` (float, > 0, < 10M) - Monto total
- `fecha_gasto` (string, ISO date) - Fecha del gasto

**Campos opcionales importantes:**
- `proveedor` (ProveedorData) - Datos del proveedor
  - `nombre` (string, requerido en objeto)
  - `rfc` (string, opcional)
- `rfc` (string, 12-13 chars) - RFC del proveedor
- `categoria` (string) - Categoría del gasto
- `tax_info` (dict) - Información fiscal (UUID, totales)
- `workflow_status` (string, default: "draft")
- `estado_factura` (string, default: "pendiente")
- `estado_conciliacion` (string, default: "pendiente")
- `forma_pago` (string) - Método de pago
- `paid_by` (string, default: "company_account")
- `will_have_cfdi` (bool, default: true)
- `company_id` (string, default: "default")

### ExpenseResponse (Response)

**Ubicación:** `core/api_models.py:9`

Incluye todos los campos de `ExpenseCreate` más:
- `id` (int) - ID del gasto creado
- `payment_account_id` (int) - ID de cuenta de pago
- `payment_account_nombre` (string) - Nombre de la cuenta
- `moneda` (string, default: "MXN")
- `tipo_cambio` (float, default: 1.0)
- `subtotal`, `iva_16`, `iva_8`, etc. - Desglose fiscal
- `cfdi_uuid`, `cfdi_pdf_url`, etc. - URLs de CFDI
- `created_at`, `updated_at` (ISO timestamps)

---

## Validaciones Automáticas

### Validaciones de Pydantic (Antes de llegar al endpoint)

Implementadas en `ExpenseCreate` (`core/api_models.py:300-347`):

#### 1. Validación de Fecha
```python
@validator('fecha_gasto')
def validate_fecha_gasto(cls, value: str) -> str:
    # - Formato ISO válido (YYYY-MM-DD)
    # - No puede ser más de 1 día en el futuro
```

**Errores comunes:**
- ❌ `"fecha_gasto": "15/01/2025"` → Formato inválido
- ❌ `"fecha_gasto": "2025-12-31"` → Fecha futura
- ✅ `"fecha_gasto": "2025-01-15"` → Válido

#### 2. Validación de RFC
```python
@validator('rfc')
def validate_rfc(cls, value: Optional[str]) -> Optional[str]:
    # - Solo alfanumérico
    # - 12 caracteres (persona moral) o 13 (física)
    # - Se normaliza a MAYÚSCULAS automáticamente
```

**Ejemplos:**
- ❌ `"rfc": "ABC123"` → Muy corto
- ❌ `"rfc": "PEM-840212-XY1"` → Contiene guiones
- ✅ `"rfc": "PEM840212XY1"` → Válido (12 chars)
- ✅ `"rfc": "GOMD8901011A3"` → Válido (13 chars)

#### 3. Validación de Monto
```python
@validator('monto_total')
def validate_monto_total(cls, value: float) -> float:
    # - Debe ser > 0
    # - Límite máximo: 10,000,000 MXN
```

**Ejemplos:**
- ❌ `"monto_total": 0` → Debe ser mayor a cero
- ❌ `"monto_total": -100` → No puede ser negativo
- ❌ `"monto_total": 15000000` → Excede límite
- ✅ `"monto_total": 850.50` → Válido

#### 4. Normalización de Categoría
```python
@validator('categoria')
def validate_categoria(cls, value: Optional[str]) -> Optional[str]:
    # - Se convierte a minúsculas
    # - Se eliminan espacios extra
```

**Ejemplos:**
- `"categoria": "COMBUSTIBLES"` → Se normaliza a `"combustibles"`
- `"categoria": " Viajes "` → Se normaliza a `"viajes"`

---

### Mapeo de Categorías a Cuentas Contables

**Ubicación:** `core/category_mappings.py`

El sistema mapea automáticamente categorías a códigos de cuenta contable SAT:

| Categoría | Código Cuenta | Descripción |
|-----------|---------------|-------------|
| combustibles, gasolina, diesel | 6140 | Combustibles y lubricantes |
| viajes, viaticos, hospedaje | 6150 | Viáticos y gastos de viaje |
| alimentos, comida, restaurante | 6150 | Gastos de alimentación |
| servicios, consultoria | 6110-6130 | Servicios profesionales |
| oficina, papeleria | 6180 | Material de oficina |
| honorarios, freelance | 6110 | Honorarios profesionales |
| renta, arrendamiento | 6120 | Arrendamientos |
| publicidad, marketing | 6160 | Publicidad y promoción |
| software, licencias | 6180 | Licencias de software |
| mantenimiento, limpieza | 6170 | Mantenimiento |

**Cuenta por defecto:** `6180` (Otros gastos)

**Función:** `get_account_code_for_category(categoria)`

**Ejemplo de uso:**
```python
from core.category_mappings import get_account_code_for_category

account = get_account_code_for_category("combustibles")
# Retorna: "6140"
```

---

## Ejemplos de Uso

### Ejemplo 1: Crear Gasto de Gasolina (cURL)

```bash
curl -X POST "http://localhost:8000/expenses" \
  -H "Content-Type: application/json" \
  -d '{
    "descripcion": "Gasolina para camioneta de reparto",
    "monto_total": 1250.00,
    "fecha_gasto": "2025-01-15",
    "proveedor": {
      "nombre": "Gasolinera PEMEX Insurgentes"
    },
    "categoria": "combustibles",
    "forma_pago": "tarjeta",
    "paid_by": "company_account",
    "will_have_cfdi": true,
    "company_id": "empresa_demo_123"
  }'
```

**Response:**
```json
{
  "id": 1234,
  "descripcion": "Gasolina para camioneta de reparto",
  "monto_total": 1250.00,
  "fecha_gasto": "2025-01-15",
  "categoria": "combustibles",
  "proveedor": {
    "nombre": "Gasolinera PEMEX Insurgentes"
  },
  "workflow_status": "draft",
  "estado_factura": "pendiente",
  "estado_conciliacion": "pendiente",
  "moneda": "MXN",
  "created_at": "2025-01-15T14:30:00Z",
  "updated_at": "2025-01-15T14:30:00Z"
}
```

---

### Ejemplo 2: Crear Gasto con Detección de Duplicados (Python)

```python
import requests

url = "http://localhost:8000/expenses/enhanced"
headers = {"Content-Type": "application/json"}

payload = {
    "descripcion": "Pago de renta oficina enero 2025",
    "monto_total": 15000.00,
    "fecha_gasto": "2025-01-01",
    "proveedor": {
        "nombre": "Inmobiliaria Centro SA de CV",
        "rfc": "ICE990101ABC"
    },
    "rfc": "ICE990101ABC",
    "categoria": "renta",
    "forma_pago": "transferencia",
    "check_duplicates": True,
    "company_id": "mi_empresa"
}

response = requests.post(url, json=payload, headers=headers)

if response.status_code == 200:
    data = response.json()

    if data.get("duplicate_ids"):
        print(f"⚠️  Posibles duplicados encontrados: {data['duplicate_ids']}")
        print(f"   Similitud: {data['similarity_score']:.2%}")
        print(f"   Nivel de riesgo: {data['risk_level']}")
    else:
        print(f"✅ Gasto creado exitosamente - ID: {data['id']}")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.json())
```

---

### Ejemplo 3: Crear Gasto desde Voz (JavaScript/React)

```javascript
// En voice-expenses.source.jsx
const createExpenseFromVoice = async (transcription) => {
  // 1. Parsear transcripción
  const parsedData = parseGasto(transcription);

  // 2. Construir payload simplificado
  const payload = {
    descripcion: parsedData.descripcion || "Gasto desde voz",
    monto_total: parsedData.monto,
    fecha_gasto: parsedData.fecha || new Date().toISOString().split('T')[0],
    categoria: parsedData.categoria,
    proveedor: parsedData.proveedor ? { nombre: parsedData.proveedor } : null
  };

  // 3. Enviar a endpoint simple
  const response = await fetch('/api/expenses/simple', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (response.ok) {
    const result = await response.json();
    console.log('✅ Gasto creado:', result);
    return result;
  } else {
    console.error('❌ Error creando gasto');
    throw new Error('Failed to create expense');
  }
};
```

---

### Ejemplo 4: Manejo de Errores de Validación

```python
import requests

url = "http://localhost:8000/expenses"

# Payload con errores intencionales
payload = {
    "descripcion": "",  # ❌ Vacío (min 1 char)
    "monto_total": -500,  # ❌ Negativo
    "fecha_gasto": "2026-12-31",  # ❌ Fecha futura
    "rfc": "ABC123"  # ❌ RFC inválido (muy corto)
}

response = requests.post(url, json=payload)

if response.status_code == 400:
    errors = response.json()["detail"]
    print("Errores de validación:")
    for error in errors:
        field = error["loc"][-1]
        message = error["msg"]
        print(f"  - {field}: {message}")
else:
    print(f"Status code inesperado: {response.status_code}")
```

**Output:**
```
Errores de validación:
  - descripcion: ensure this value has at least 1 characters
  - monto_total: El monto debe ser mayor a cero
  - fecha_gasto: La fecha del gasto no puede ser futura
  - rfc: RFC debe tener 12 (moral) o 13 (física) caracteres
```

---

## Endpoints Auxiliares

### `POST /expenses/check-duplicates` - Verificar Duplicados

**Descripción:** Verifica si un gasto es duplicado sin crearlo.

**Ubicación:** `main.py:3211`

```bash
curl -X POST "http://localhost:8000/expenses/check-duplicates" \
  -H "Content-Type: application/json" \
  -d '{
    "new_expense": {
      "descripcion": "Gasolina PEMEX",
      "monto_total": 850.50,
      "fecha_gasto": "2025-01-15"
    },
    "check_existing": true
  }'
```

**Response:**
```json
{
  "has_duplicates": true,
  "total_found": 2,
  "risk_level": "high",
  "recommendation": "Revisar antes de crear",
  "duplicates": [
    {
      "expense_id": 1234,
      "similarity_score": 0.92,
      "match_reasons": ["Monto exacto", "Fecha cercana", "Proveedor similar"]
    }
  ]
}
```

---

### `POST /expenses/predict-category` - Predecir Categoría

**Descripción:** Predice la categoría de un gasto usando ML/LLM.

**Ubicación:** `main.py:3279`

```bash
curl -X POST "http://localhost:8000/expenses/predict-category" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Gasolina en PEMEX Reforma",
    "merchant_name": "PEMEX",
    "amount": 850.50,
    "prediction_method": "hybrid"
  }'
```

**Response:**
```json
{
  "prediction": {
    "category": "combustibles",
    "confidence": 0.95,
    "reasoning": "Keyword 'gasolina' y merchant 'PEMEX' indican combustible",
    "alternatives": [
      {"category": "transporte", "confidence": 0.75}
    ],
    "prediction_method": "hybrid"
  },
  "processing_time_ms": 45,
  "user_preferences_used": true,
  "historical_matches": 12
}
```

---

## Mejores Prácticas

### 1. Siempre valida en el cliente antes de enviar
```javascript
if (!descripcion || monto_total <= 0) {
  // Mostrar error al usuario antes de hacer request
  return;
}
```

### 2. Maneja errores 400 específicamente
```python
try:
    response = requests.post(url, json=payload)
    response.raise_for_status()
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 400:
        # Errores de validación - mostrar al usuario
        validation_errors = e.response.json()["detail"]
    else:
        # Otros errores HTTP
        pass
```

### 3. Usa el endpoint adecuado según el contexto
- Formularios web → `/expenses`
- Imports masivos → `/expenses/enhanced`
- Voz/OCR → `/api/expenses/simple`

### 4. Aprovecha las validaciones automáticas
No necesitas validar RFC o fechas manualmente - Pydantic lo hace por ti.

### 5. Guarda los IDs de duplicados
Si usas `/expenses/enhanced`, guarda los `duplicate_ids` para permitir al usuario revisar.

---

## Changelog

### v2.0 (2025-01-15)
- ✨ Añadido modelo `ExpenseCreate` completo con validadores Pydantic
- ✨ Centralizados mapeos de categorías en `core/category_mappings.py`
- ✨ Validaciones automáticas de RFC, fechas y montos
- 🐛 Eliminada validación duplicada de monto en endpoint
- 📝 Documentación completa de endpoints

### v1.0 (2024-10-01)
- Versión inicial con 3 endpoints de creación

---

## Soporte

Para reportar issues o sugerir mejoras:
- Crear issue en GitHub
- Contactar al equipo de backend
- Revisar logs en: `/logs/expenses_endpoint.log`

---

**Última actualización:** 2025-01-15
**Mantenido por:** Equipo de Backend
**Versión:** 2.0

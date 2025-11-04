# 🖥️ Interfaces y Endpoints - Mapeo Completo

**Fecha:** 2025-01-15
**Estado:** Documentación Técnica

---

## 📋 Resumen

ContaFlow tiene **2 interfaces principales** para captura de gastos/tickets. Cada una usa endpoints DIFERENTES.

---

## 🎯 Interface 1: Voice Expenses

### URL de Acceso
```
http://localhost:8000/voice-expenses
```

### Archivo Servido
- **Backend:** `main.py:740-749` - Route `@app.get("/voice-expenses")`
- **Frontend:** `static/voice-expenses.html` (que carga `voice-expenses.source.jsx`)

### Propósito
Interfaz avanzada multicanal para **captura de gastos** con 3 modos:
1. ✅ **Texto (Manual)** - Formulario completo
2. ✅ **Voz (Dictado)** - Whisper STT
3. ✅ **Subir Ticket (OCR)** - Google Vision

---

## 📍 Endpoints que USA Voice Expenses

### 1. Creación de Gastos (Principal)

```javascript
// Archivo: voice-expenses.source.jsx:4695
const response = await fetch('/expenses', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        descripcion: "Gasolina PEMEX",
        monto_total: 850.50,
        fecha_gasto: "2025-01-15",
        categoria: "combustibles",
        proveedor: { nombre: "PEMEX", rfc: "PEM840212XY1" },
        rfc: "PEM840212XY1",
        forma_pago: "tarjeta",
        paid_by: "company_account",
        will_have_cfdi: true,
        company_id: "default"
    })
});
```

**Endpoint Backend:** `POST /expenses` (main.py:2935-2973)
**Modelo:** `ExpenseCreate` (core/api_models.py:261-370)
**Usa IA:** ❌ NO (solo validaciones Pydantic)

---

### 2. Captura por OCR (Tickets/Fotos)

```javascript
// Archivo: voice-expenses.source.jsx:4068
const formData = new FormData();
formData.append('file', file);

const response = await fetch('http://localhost:8000/ocr/intake', {
    method: 'POST',
    body: formData
});
```

**Endpoint Backend:** `POST /ocr/intake` (main.py:1610-1700)
**Proceso:**
1. Google Vision OCR extrae texto
2. Regex parsea RFC, total, fecha, folio
3. **Retorna JSON con campos extraídos (NO crea gasto)**
4. Frontend pre-llena formulario
5. Usuario revisa/edita campos
6. Usuario hace click "Guardar"
7. **ENTONCES llama POST /expenses para crear gasto**

**Usa IA:** ✅ SÍ (Google Vision OCR)
**Costo:** ~$0.0015 por ticket
**⚠️ Importante:** NO crea gasto automáticamente, solo extrae datos

---

### 3. Otros Endpoints que USA Voice Expenses

| Endpoint | Método | Propósito | IA |
|----------|--------|-----------|-----|
| `/expenses/query` | POST | Buscar/filtrar gastos | ❌ |
| `/expenses/{id}` | GET | Obtener detalles de gasto | ❌ |
| `/expenses/{id}` | PUT | Actualizar gasto | ❌ |
| `/expenses/{id}/invoice` | POST | Registrar factura asociada | ❌ |
| `/expenses/{id}/mark-invoiced` | POST | Marcar como facturado | ❌ |
| `/expenses/{id}/close-no-invoice` | POST | Cerrar sin factura | ❌ |
| `/expenses/{id}/mark-non-reconcilable` | POST | Marcar no conciliable | ❌ |
| `/expenses/predict-category` | POST | Predecir categoría con IA | ✅ Claude |
| `/expenses/check-duplicates` | POST | Detectar duplicados con ML | ✅ Embeddings |
| `/expenses/non-reconciliation-reasons` | GET | Obtener razones de no conciliación | ❌ |
| `/invoices/parse` | POST | Parsear CFDI XML | ✅ Claude |
| `/invoices/bulk-match` | POST | Match masivo de facturas | ✅ Embeddings |
| `/bank_reconciliation/suggestions` | POST | Sugerencias de conciliación | ✅ Claude Sonnet |
| `/bank_reconciliation/feedback` | POST | Feedback de match | ❌ |

---

## 🎯 Interface 2: Advanced Ticket Dashboard

### URL de Acceso
```
http://localhost:8000/advanced-ticket-dashboard.html
```

### Archivo Servido
- **Backend:** `main.py:752-761` - Route `@app.get("/advanced-ticket-dashboard.html")`
- **Frontend:** `static/advanced-ticket-dashboard.html`

### Propósito
Dashboard especializado para **procesamiento de tickets con RPA** (Robotic Process Automation):
1. ✅ Upload de tickets (OCR)
2. ✅ Análisis automático con IA
3. ✅ Descarga automática de facturas desde portales SAT
4. ✅ Monitoreo de jobs de automatización

---

## 📍 Endpoints que USA Advanced Ticket Dashboard

### 1. Upload de Tickets (Principal)

```javascript
// Archivo: advanced-ticket-dashboard.html:401
const formData = new FormData();
formData.append('file', file);
formData.append('company_id', 'default');

const response = await fetch('/invoicing/tickets', {
    method: 'POST',
    body: formData
});
```

**Endpoint Backend:** `POST /invoicing/tickets`
**API Base:** `/invoicing` (advanced-ticket-dashboard.html:323)

**Proceso:**
1. Recibe archivo (imagen/PDF)
2. Extrae texto con OCR
3. Analiza merchant, categoría, monto
4. **NO crea gasto directamente - solo ticket**
5. Retorna `ticket_id` para procesamiento posterior

**Usa IA:** ✅ SÍ (Google Vision OCR)

---

### 2. Obtener Lista de Tickets

```javascript
// Archivo: advanced-ticket-dashboard.html:610
const response = await fetch('/invoicing/tickets?company_id=default');
```

**Endpoint Backend:** `GET /invoicing/tickets`
**Usa IA:** ❌ NO

---

### 3. Procesar Ticket (RPA - Descargar Factura)

```javascript
// Archivo: advanced-ticket-dashboard.html:794
const response = await fetch(`/invoicing/jobs/${jobId}/process`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
});
```

**Endpoint Backend:** `POST /invoicing/jobs/{job_id}/process`
**Proceso:**
1. Inicia job de automatización RPA
2. Gemini Computer Use analiza portal SAT
3. Playwright navega y descarga factura
4. Parsea CFDI con Claude Haiku
5. **Crea gasto después de obtener factura**

**Usa IA:** ✅ SÍ (Gemini Pro + Claude Haiku)

---

### 4. Monitorear Status de Job

```javascript
// Archivo: advanced-ticket-dashboard.html:831
const response = await fetch(`/invoicing/jobs/${jobId}/status`);
```

**Endpoint Backend:** `GET /invoicing/jobs/{job_id}/status`
**Usa IA:** ❌ NO

---

## 🔄 Comparación de Flujos

### Flujo en Voice Expenses (Captura Manual)

```
Usuario (Voice Expenses)
    ↓
Llena formulario manual
    ↓
Click "Guardar"
    ↓
POST /expenses
    ↓
Validaciones Pydantic (NO IA)
    ↓
Gasto guardado en DB ✅
    ↓
Claude Haiku clasifica categoría SAT (IA en background)
```

**Tiempo:** ~500ms
**IA en captura:** ❌ NO
**IA después:** ✅ SÍ (clasificación SAT)

---

### Flujo en Voice Expenses (OCR)

```
Usuario (Voice Expenses)
    ↓
Sube foto de ticket
    ↓
POST /ocr/intake
    ↓
Google Vision OCR extrae texto (IA) 🤖
    ↓
Regex parsea campos fiscales
    ↓
Claude Haiku clasifica categoría (IA) 🤖
    ↓
Crea gasto automáticamente → POST /expenses interno
    ↓
Gasto guardado en DB ✅
```

**Tiempo:** ~3-5 segundos
**IA en captura:** ✅ SÍ (Google Vision + Claude)
**Costo:** ~$0.0015 + $0.0002 = $0.0017

---

### Flujo en Advanced Ticket Dashboard

```
Usuario (Advanced Ticket Dashboard)
    ↓
Sube ticket/imagen
    ↓
POST /invoicing/tickets
    ↓
Google Vision OCR extrae texto (IA) 🤖
    ↓
Análisis inicial (merchant, categoría)
    ↓
Ticket guardado (NO gasto aún) ⏸️
    ↓
Usuario hace click "Auto Invoice"
    ↓
POST /invoicing/jobs/{id}/process
    ↓
Gemini Computer Use + Playwright (RPA) 🤖
    ↓
Descarga CFDI desde portal SAT
    ↓
Claude Haiku parsea CFDI XML (IA) 🤖
    ↓
Crea gasto con factura completa ✅
```

**Tiempo:** ~30-60 segundos (RPA)
**IA en captura:** ✅ SÍ (Google Vision + Gemini + Claude)
**Costo:** ~$0.0015 (OCR) + $0.00 (Gemini free) + $0.001 (CFDI parsing) = ~$0.0025

---

## 🎯 Tabla Resumen: ¿Cuál interfaz usa qué endpoint?

| Endpoint | Voice Expenses | Advanced Ticket Dashboard | Propósito |
|----------|----------------|---------------------------|-----------|
| **POST /expenses** | ✅ SÍ (principal) | ❌ NO | Crear gasto manualmente |
| **POST /ocr/intake** | ✅ SÍ (modo OCR) | ❌ NO | OCR + crear gasto automático |
| **POST /invoicing/tickets** | ❌ NO | ✅ SÍ (principal) | Upload ticket + OCR (sin crear gasto) |
| **GET /invoicing/tickets** | ❌ NO | ✅ SÍ | Lista de tickets |
| **POST /invoicing/jobs/{id}/process** | ❌ NO | ✅ SÍ | RPA + descargar factura + crear gasto |
| **GET /invoicing/jobs/{id}/status** | ❌ NO | ✅ SÍ | Monitor job RPA |
| **POST /expenses/query** | ✅ SÍ | ❌ NO | Buscar gastos |
| **POST /invoices/parse** | ✅ SÍ | ❌ NO | Parsear CFDI XML |
| **POST /bank_reconciliation/suggestions** | ✅ SÍ | ❌ NO | Sugerencias conciliación |

---

## 🤔 Preguntas Frecuentes

### 1. ¿Ambas interfaces pueden crear gastos?

**Respuesta:** SÍ, pero de forma diferente:

- **Voice Expenses:**
  - Crea gastos directamente con `POST /expenses`
  - O crea gastos desde foto con `POST /ocr/intake`
  - Usuario ve el gasto inmediatamente

- **Advanced Ticket Dashboard:**
  - NO crea gastos directamente al subir
  - Primero crea "ticket" con `POST /invoicing/tickets`
  - Usuario debe disparar RPA con `POST /invoicing/jobs/{id}/process`
  - Gasto se crea después de descargar factura

---

### 2. ¿Por qué hay dos interfaces?

**Respuesta:** Diferentes casos de uso:

**Voice Expenses:**
- ✅ Captura rápida de gastos día a día
- ✅ Múltiples modos: texto, voz, foto
- ✅ Gasto creado inmediatamente
- ✅ Usuario controla todo el proceso
- 👥 **Para:** Empleados capturando gastos cotidianos

**Advanced Ticket Dashboard:**
- ✅ Procesamiento masivo con automatización
- ✅ Descarga automática desde portales SAT
- ✅ RPA para evitar login manual
- ✅ Gestión de jobs de larga duración
- 👥 **Para:** Contadores procesando facturas en lote

---

### 3. ¿Puedo usar ambas al mismo tiempo?

**Respuesta:** ✅ SÍ, son completamente independientes.

Ambas escriben a la misma base de datos de gastos, pero:
- Voice Expenses crea gastos con `estado_factura: "pendiente"`
- Advanced Ticket Dashboard crea gastos con `estado_factura: "facturado"` (porque ya tiene CFDI)

---

### 4. ¿El OCR es el mismo en ambas?

**Respuesta:** ❌ NO exactamente:

**Voice Expenses (`/ocr/intake`):**
- Google Vision OCR
- Regex extrae campos fiscales
- Claude clasifica categoría
- **Crea gasto automáticamente**
- Retorna gasto completo

**Advanced Ticket Dashboard (`/invoicing/tickets`):**
- Google Vision OCR
- Análisis de merchant/categoría
- **NO crea gasto**
- Retorna ticket para posterior procesamiento

---

### 5. ¿Cuál debo usar para mi caso?

| Caso de Uso | Interfaz Recomendada | Razón |
|-------------|---------------------|-------|
| Empleado captura gasto de gasolina | Voice Expenses | Rápido, simple, inmediato |
| Empleado tiene foto de ticket sin factura | Voice Expenses (OCR) | Crea gasto desde foto |
| Contador tiene RFC y quiere descargar factura automática | Advanced Ticket Dashboard | RPA automatizado |
| Importar 100 facturas en lote | Advanced Ticket Dashboard | Jobs paralelos |
| Captura por voz mientras manejas | Voice Expenses | Whisper STT integrado |
| Necesitas conciliación bancaria | Voice Expenses | Tiene módulo de conciliación |

---

## 🔗 Referencias

**Código Fuente:**
- Voice Expenses UI: `static/voice-expenses.source.jsx` (13,500 líneas)
- Advanced Ticket Dashboard UI: `static/advanced-ticket-dashboard.html` (900 líneas)
- Backend Routes: `main.py`
  - Voice Expenses route: línea 740-749
  - Advanced Ticket Dashboard route: línea 752-761
  - POST /expenses: línea 2935-2973
  - POST /ocr/intake: línea 1610-1700

**Documentación Relacionada:**
- Uso de IA completo: `docs/architecture/AI_USAGE_MAPPING.md`
- Endpoints de gastos: `docs/api/EXPENSE_ENDPOINTS_GUIDE.md`

---

**Última actualización:** 2025-01-15
**Mantenido por:** Equipo de Backend
**Versión:** 1.0

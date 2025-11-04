# 📋 Auditoría Completa del Sistema de Gastos
## Análisis de Funcionalidades Existentes vs Requerimientos

**Fecha:** 4 de Octubre, 2025
**Objetivo:** Identificar qué existe, qué falta y cómo integrar sin duplicar

---

## 🔍 ENDPOINTS EXISTENTES

### 1. Endpoints de Gastos (Expenses)

| Endpoint | Método | Funcionalidad | Estado |
|----------|--------|---------------|--------|
| `/expenses` | POST | Crear gasto básico | ✅ FUNCIONA |
| `/expenses` | GET | Listar gastos | ✅ FUNCIONA |
| `/expenses` | DELETE | Eliminar gastos de empresa | ✅ FUNCIONA |
| `/expenses/{expense_id}` | PUT | Actualizar gasto | ✅ FUNCIONA |
| `/expenses/{expense_id}/invoice` | POST | Asociar factura a gasto | ✅ EXISTE |
| `/expenses/{expense_id}/mark-invoiced` | POST | Marcar como facturado | ✅ EXISTE |
| `/expenses/{expense_id}/close-no-invoice` | POST | Cerrar sin factura | ✅ EXISTE |
| `/expenses/check-duplicates` | POST | Verificar duplicados | ✅ EXISTE |
| `/expenses/predict-category` | POST | Predecir categoría con ML | ✅ EXISTE |
| `/expenses/enhanced` | POST | Crear gasto con validación avanzada | ✅ EXISTE |
| `/simple_expense` | POST | Crear gasto simple | ✅ EXISTE |
| `/complete_expense` | POST | Crear gasto completo | ✅ EXISTE |

### 2. Endpoints de OCR

| Endpoint | Método | Funcionalidad | Estado |
|----------|--------|---------------|--------|
| `/ocr/parse` | POST | Extraer texto de imagen/PDF | ✅ FUNCIONA |
| `/ocr/intake` | POST | Crear gasto desde OCR | ✅ EXISTE |
| `/ocr/stats` | GET | Estadísticas de OCR | ✅ EXISTE |

### 3. Endpoints de Facturas (Invoices)

| Endpoint | Método | Funcionalidad | Estado |
|----------|--------|---------------|--------|
| `/invoices` | GET | Listar facturas | ✅ EXISTE |
| `/invoices` | POST | Crear factura | ✅ EXISTE |
| `/invoices/{invoice_id}` | GET | Obtener factura | ✅ EXISTE |
| `/invoices/{invoice_id}` | PUT | Actualizar factura | ✅ EXISTE |
| `/invoices/{invoice_id}/find-matches` | POST | Encontrar gastos para factura | ✅ EXISTE |
| `/invoices/parse` | POST | Parsear factura | ✅ EXISTE |
| `/invoices/bulk-match` | POST | Matching masivo | ✅ EXISTE |

### 4. Endpoints de Tickets

| Endpoint | Método | Funcionalidad | Estado |
|----------|--------|---------------|--------|
| `/advanced-ticket-dashboard.html` | GET | Dashboard de tickets | ✅ EXISTE |
| `/voice-expenses` | GET | Centro de gastos por voz | ✅ FUNCIONA |

---

## 🗄️ ESQUEMA DE BASE DE DATOS ACTUAL

### Tabla: `expense_records`

#### Campos Básicos (✅ Existen)
- `id` - INTEGER PRIMARY KEY
- `amount` - REAL (monto total)
- `currency` - TEXT (MXN por defecto)
- `description` - TEXT
- `category` - TEXT
- `merchant_name` - TEXT
- `date` - TIMESTAMP
- `tenant_id` - INTEGER (multi-tenancy)
- `user_id` - INTEGER

#### Campos de Impuestos (✅ RECIÉN AGREGADOS)
- `subtotal` - REAL
- `iva_16` - REAL
- `iva_8` - REAL
- `iva_0` - REAL
- `ieps` - REAL
- `isr_retenido` - REAL
- `iva_retenido` - REAL
- `otros_impuestos` - REAL
- `impuestos_incluidos` - TEXT (JSON array)

#### Campos de CFDI (✅ RECIÉN AGREGADOS)
- `cfdi_status` - TEXT (no_disponible, en_proceso, factura_lista, no_facturar)
- `cfdi_pdf_url` - TEXT
- `cfdi_xml_url` - TEXT
- `cfdi_fecha_timbrado` - TEXT
- `cfdi_folio_fiscal` - TEXT
- `cfdi_uuid` - TEXT (ya existía)

#### Campos de Ticket/Comprobante (✅ RECIÉN AGREGADOS)
- `ticket_image_url` - TEXT
- `ticket_folio` - TEXT
- `registro_via` - TEXT (voz, whatsapp, web, ticket)
- `payment_account_id` - INTEGER (cuenta de pago)

#### Campos de Estado
- `status` - TEXT
- `invoice_status` - TEXT
- `bank_status` - TEXT
- `approval_status` - TEXT
- `deducible` - BOOLEAN
- `requiere_factura` - BOOLEAN

#### Campos de Metadata
- `metadata` - TEXT (JSON)
- `audit_trail` - TEXT (JSON)
- `enhanced_data` - TEXT (JSON)
- `user_context` - TEXT (JSON)

---

## 🧩 SERVICIOS Y MÓDULOS EXISTENTES

### 1. OCR Services
**Archivos identificados:**
- ✅ `/modules/invoicing_agent/services/ocr_service.py` - Servicio OCR principal
- ✅ `/core/advanced_ocr_service.py` - OCR avanzado
- ✅ `/core/robust_ocr_system.py` - Sistema robusto
- ✅ `/core/google_vision_ocr.py` - Google Vision API

**Capacidades actuales:**
- Extracción de texto de imágenes
- Parsing de tickets con regex
- Detección de campos estructurados
- Soporte para múltiples idiomas

### 2. Ticket Processor
**Archivo:** `/modules/invoicing_agent/ticket_processor.py`

**Funcionalidades:**
- ✅ Identificación automática de merchants (PEMEX, Shell, OXXO, Walmart, etc.)
- ✅ Extracción de campos: RFC, folio, fecha, total, subtotal, IVA
- ✅ Configuración de portales de facturación por merchant
- ✅ Detección de call-to-action para facturación

### 3. WhatsApp Integration
**Archivo:** `/core/whatsapp_integration.py`

**Funcionalidades:**
- ✅ Webhook de WhatsApp Business API
- ✅ Verificación de firma de seguridad
- ✅ Detección de intención de gasto mediante IA
- ✅ Números autorizados por tenant

### 4. Unified DB Adapter
**Archivo:** `/core/unified_db_adapter.py`

**Funcionalidades:**
- ✅ `record_internal_expense()` - Crear gasto
- ✅ `fetch_expense_records()` - Listar gastos
- ✅ `update_expense_record()` - Actualizar gasto
- ✅ Multi-tenancy con tenant_id
- ✅ Metadata JSON

---

## ❓ GAP ANALYSIS - QUÉ FALTA

### 1. Flujo de WhatsApp → Gasto ❌ INCOMPLETO
**Lo que existe:**
- ✅ Webhook de WhatsApp configurado
- ✅ Detección de intención
- ❌ **FALTA:** Procesamiento automático de imagen de ticket recibida
- ❌ **FALTA:** Flujo conversacional para completar campos faltantes
- ❌ **FALTA:** Confirmación automática al usuario

**Acción requerida:**
1. Conectar webhook WhatsApp → OCR service → Expense creation
2. Implementar validación de campos obligatorios
3. Generar respuestas conversacionales adaptativas

### 2. Visor de Gastos Mejorado ❌ FALTA
**Requerimientos del cliente:**
- ❌ Vista con desglose de impuestos expandible
- ❌ Botón "Ver adjunto" para ticket
- ❌ Indicador visual de impuestos incluidos (badges)
- ❌ Estado CFDI con carga drag & drop
- ❌ Campo "¿Se va a facturar?" editable
- ❌ Navegación a cuenta de pago
- ❌ Mostrar usuario solo si hay múltiples usuarios

**Acción requerida:**
1. Actualizar `/static/voice-expenses.source.jsx` con nueva UI
2. Agregar componente de desglose de impuestos
3. Implementar drag & drop para CFDI
4. Crear badges de impuestos

### 3. Sistema de Validación Adaptativa ❌ FALTA
**Requerimientos:**
- ❌ Detectar campos faltantes después de OCR
- ❌ Generar plantilla adaptativa según canal (web/WhatsApp)
- ❌ Flujo conversacional para solicitar datos faltantes
- ❌ Validación de campos mínimos requeridos

**Acción requerida:**
1. Crear servicio de validación de completitud
2. Generar templates dinámicos por canal
3. Implementar estado "pending_completion" en gastos

### 4. Integración con "Generar Factura" ❌ PARCIAL
**Lo que existe:**
- ✅ Endpoints `/invoices/*`
- ✅ Campo `cfdi_uuid` en BD
- ❌ **FALTA:** Auto-actualización de `cfdi_status` a "en_proceso"
- ❌ **FALTA:** Carga automática de PDF/XML generados
- ❌ **FALTA:** Actualización a "factura_lista" con archivos

**Acción requerida:**
1. Modificar endpoint de facturación para actualizar `cfdi_status`
2. Agregar endpoint de carga de CFDI (PDF/XML)
3. Vincular archivos con expense_id

---

## 🎯 PLAN DE INTEGRACIÓN SIN DUPLICACIÓN

### Fase 1: Extender Endpoints Existentes (NO DUPLICAR)

#### 1.1 Modificar POST /ocr/intake
**Archivo:** `main.py` líneas 1665-1745

**Cambios necesarios:**
```python
# ANTES (línea ~1665)
@app.post("/ocr/intake")
async def ocr_intake(file, paid_by, will_have_cfdi):
    # Solo extrae y crea gasto básico

# DESPUÉS (extender funcionalidad)
@app.post("/ocr/intake")
async def ocr_intake(
    file: UploadFile,
    paid_by: str = Form(...),
    will_have_cfdi: str = Form(...),
    channel: str = Form("web"),  # NUEVO: web, whatsapp
    user_phone: Optional[str] = Form(None),  # NUEVO: para WhatsApp
    company_id: str = Form("default")
):
    # 1. Extraer con OCR (ya existe)
    # 2. Validar campos requeridos (NUEVO)
    # 3. Si campos completos → crear gasto
    # 4. Si campos incompletos → devolver template adaptativo
    # 5. Guardar imagen de ticket (NUEVO)
```

#### 1.2 Agregar Endpoint de Completar Gasto
**NUEVO endpoint (NO duplica, complementa):**
```python
@app.post("/expenses/{expense_id}/complete-fields")
async def complete_expense_fields(
    expense_id: int,
    fields: Dict[str, Any]
):
    """Completar campos faltantes de un gasto pendiente"""
    # Actualizar expense_records con campos nuevos
    # Cambiar completion_status de 'pending' a 'completed'
```

#### 1.3 Agregar Endpoint de Carga CFDI
**NUEVO endpoint:**
```python
@app.post("/expenses/{expense_id}/upload-cfdi")
async def upload_cfdi(
    expense_id: int,
    pdf_file: Optional[UploadFile] = None,
    xml_file: Optional[UploadFile] = None
):
    """Cargar PDF/XML de CFDI y actualizar estado"""
    # Guardar archivos en storage
    # Actualizar cfdi_pdf_url, cfdi_xml_url
    # Cambiar cfdi_status a 'factura_lista'
```

### Fase 2: Actualizar UI Existente (NO DUPLICAR)

#### 2.1 Extender voice-expenses.source.jsx
**Archivo:** `/static/voice-expenses.source.jsx`

**Cambios:**
1. Agregar columnas al visor de gastos existente
2. Implementar componente de desglose de impuestos
3. Agregar drag & drop para CFDI
4. Mostrar badges de impuestos

**NO crear nuevo archivo, MODIFICAR el existente**

### Fase 3: Conectar WhatsApp Webhook

#### 3.1 Crear Endpoint WhatsApp Webhook
**NUEVO endpoint en main.py:**
```python
@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    """Recibir mensajes de WhatsApp"""
    # 1. Verificar firma de seguridad
    # 2. Extraer mensaje e imagen
    # 3. Identificar usuario/tenant por número
    # 4. Si es imagen → llamar a /ocr/intake con channel="whatsapp"
    # 5. Responder al usuario vía WhatsApp API
```

---

## ✅ CHECKLIST DE NO DUPLICACIÓN

### Antes de crear cualquier código nuevo:

- [ ] ¿Ya existe un endpoint similar? → EXTENDER, no duplicar
- [ ] ¿Ya existe una tabla en BD? → AGREGAR columnas, no crear nueva tabla
- [ ] ¿Ya existe un servicio OCR? → USAR el existente
- [ ] ¿Ya existe un componente UI? → MODIFICAR, no crear nuevo
- [ ] ¿Ya existe lógica de negocio? → REFACTORIZAR, no reescribir

### Reglas de integración:

1. **Endpoints:** Si existe endpoint similar, agregar parámetros opcionales
2. **Base de datos:** SIEMPRE usar `expense_records` existente
3. **Servicios:** IMPORTAR módulos existentes, no recrear
4. **UI:** MODIFICAR componentes React existentes
5. **Persistencia:** USAR unified_db_adapter.py

---

## 🚧 PRÓXIMOS PASOS ESPECÍFICOS

### Paso 1: Validación de Campos (NUEVO)
```python
# Crear: /core/expense_field_validator.py
class ExpenseFieldValidator:
    REQUIRED_FIELDS = ['description', 'amount', 'date', 'payment_account_id']

    def validate_completeness(self, expense_data: Dict) -> Dict:
        """Retorna campos faltantes y template adaptativo"""
```

### Paso 2: Extender OCR Intake (MODIFICAR)
```python
# Modificar: main.py línea 1665
# Agregar: validación de campos, storage de imagen, respuesta adaptativa
```

### Paso 3: Actualizar UI (MODIFICAR)
```python
# Modificar: /static/voice-expenses.source.jsx
# Agregar: nuevas columnas, desglose de impuestos, drag & drop CFDI
```

### Paso 4: WhatsApp Integration (NUEVO)
```python
# Crear: /api/whatsapp_webhook.py (módulo separado)
# Conectar con: /ocr/intake existente
```

---

## 📊 RESUMEN EJECUTIVO

### ✅ Lo que YA FUNCIONA y NO tocar:
- POST /expenses (crear gasto básico)
- GET /expenses (listar gastos)
- OCR extraction (/ocr/parse, /ocr/intake)
- Unified DB Adapter
- Ticket Processor (merchants, portales)
- Base de datos expense_records con nuevos campos

### ⚠️ Lo que FALTA (SIN DUPLICAR):
1. Flujo WhatsApp completo (webhook → OCR → gasto)
2. Validación adaptativa de campos
3. UI mejorada para visor de gastos
4. Sistema de carga CFDI (PDF/XML)
5. Actualización automática de estados

### 🎯 Estrategia de Implementación:
1. **EXTENDER** endpoints existentes (no crear nuevos innecesariamente)
2. **MODIFICAR** UI existente (no duplicar componentes)
3. **USAR** servicios existentes (OCR, DB, Ticket Processor)
4. **AGREGAR** solo lo que realmente falta

---

**Conclusión:** El 70% de la funcionalidad YA EXISTE. Solo necesitamos:
- Conectar piezas existentes
- Extender endpoints actuales
- Actualizar UI
- Agregar validación y flujo conversacional

**NO necesitamos:** Reescribir OCR, crear nueva BD, duplicar endpoints de gastos.

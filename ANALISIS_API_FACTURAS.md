# Análisis Completo de API de Facturas

## 🧩 1. ENDPOINTS Y RUTAS DISPONIBLES

### Módulo de Invoicing (`/invoicing/*`)

#### Tickets (Facturas XML)
```
GET    /invoicing/tickets
       - Query params: page, page_size, status, merchant, company_id, user_id ✅
       - Respuesta: { success, total, tickets[], filters }
       - Paginado: ❌ (devuelve todos con limit)
       - User isolation: ✅ (user_id filter implementado)

POST   /invoicing/tickets
       - FormData: file, text_content, user_id, company_id
       - Respuesta: { ticket_id, status, invoice_data?, llm_analysis? }
       - Procesamiento: Automático con threading

GET    /invoicing/tickets/{ticket_id}
       - Respuesta: Ticket completo con invoice_data parseado

POST   /invoicing/tickets/{ticket_id}/process
       - Trigger: Re-procesar ticket con IA
       - Respuesta: { status, analysis }

GET    /invoicing/tickets/{ticket_id}/invoice-status
       - Consulta: Estado SAT del CFDI
       - Respuesta: { uuid, status, fecha_timbrado }

GET    /invoicing/tickets/{ticket_id}/image
       - Respuesta: Imagen original (si existe)

GET    /invoicing/tickets/{ticket_id}/ocr-text
       - Respuesta: Texto extraído por OCR
```

#### Expenses (desde tickets)
```
GET    /invoicing/expenses
       - Respuesta: Lista de expenses (modelo reducido)
       - ⚠️ No está implementado completamente
```

#### Merchants & Stats
```
GET    /invoicing/merchants
       - Respuesta: Lista de proveedores únicos

GET    /invoicing/stats
       - Respuesta: Estadísticas generales { total_tickets, by_status, by_category }

GET    /invoicing/health
       - Health check del módulo
```

### Módulo de Finance (`/finance/*`)

```
POST   /finance/reports/iva
GET    /finance/reports/poliza-electronica/xml
GET    /finance/reports/gastos-revision
GET    /finance/reports/resumen-fiscal
GET    /finance/reports/disponibles
```

### Módulo de Bank (`/bank/*`)
```
GET    /bank/accounts
GET    /bank/transactions
POST   /bank/upload-statement
GET    /bank/reconciliation-status
```

### ❌ ENDPOINTS FALTANTES (no existen actualmente)

```
# Expense Records (gestión completa de gastos)
GET    /api/expenses
POST   /api/expenses
GET    /api/expenses/{id}
PATCH  /api/expenses/{id}
DELETE /api/expenses/{id}

# Expense Invoices (facturas CFDI completas)
GET    /api/expense-invoices
POST   /api/expense-invoices
GET    /api/expense-invoices/{id}

# Relaciones
GET    /api/expenses/by-ticket/{ticket_id}
GET    /api/tickets/{id}/expense
POST   /api/tickets/{id}/convert-to-expense

# Workflows
POST   /api/expenses/{id}/approve
POST   /api/expenses/{id}/reject
POST   /api/expenses/{id}/attach-invoice
```

---

## 🧠 2. RELACIONES Y LLAVES

### Estructura actual

```python
# tickets table
{
  "id": 123,
  "tipo": "texto",  # texto (XML) o imagen
  "estado": "procesado",  # pendiente, procesado, error
  "raw_data": "<?xml version...",  # XML completo
  "invoice_data": {  # JSON parseado del CFDI
    "uuid": "ABC123...",
    "rfc_emisor": "AAA010101AAA",
    "nombre_emisor": "ACME SA DE CV",
    "total": 1160.0,
    "fecha": "2024-01-15T10:30:00",
    "metodoPago": "PUE",
    "moneda": "MXN"
  },
  "llm_analysis": {  # Análisis de IA
    "category": "Papelería",
    "merchant_name": "ACME",
    "confidence": 0.95,
    "suggested_account": "5101"
  },
  "merchant_id": 45,
  "merchant_name": "ACME SA DE CV",
  "category": "Papelería",
  "confidence": 0.95,
  "user_id": 1,  # ✅ Aislamiento por usuario
  "company_id": "default",
  "tenant_id": 1,
  "expense_id": null,  # ⚠️ Relación a expense_records (nullable)
  "created_at": "2024-01-15T10:35:00"
}
```

```python
# expense_records table (actualmente SIN API dedicada)
{
  "id": 789,
  "amount": 1160.0,
  "currency": "MXN",
  "description": "Compra de papelería",
  "category": "Papelería",
  "merchant_name": "ACME SA DE CV",
  "date": "2024-01-15",
  "user_id": 1,
  "tenant_id": 1,
  "status": "approved",  # pending, approved, rejected
  "ticket_id": 123,  # ✅ Relación inversa a tickets
  "cfdi_uuid": "ABC123...",
  "workflow_status": "completed",
  "approval_status": "approved",
  "created_at": "2024-01-15T11:00:00"
}
```

```python
# expense_invoices table (actualmente SIN API)
{
  "id": 456,
  "expense_id": 789,  # ✅ Relación 1:1 con expense_records
  "tenant_id": 1,
  "filename": "factura_ABC123.xml",
  "file_path": "/uploads/2024/01/factura_ABC123.xml",
  "uuid": "ABC123...",
  "rfc_emisor": "AAA010101AAA",
  "nombre_emisor": "ACME SA DE CV",
  "fecha_emision": "2024-01-15T10:30:00",
  "total": 1160.0,
  "cfdi_status": "vigente",  # vigente, cancelada
  "xml_content": "<?xml version...",
  "parsed_data": { ... },
  "validation_status": "validated",
  "quality_score": 0.98,
  "created_at": "2024-01-15T11:05:00"
}
```

### Relaciones visuales

```
┌─────────────────┐
│   tickets       │
│   id: 123       │
│   user_id: 1    │ ← Inbox de clasificación
│   expense_id: ? │
└────────┬────────┘
         │
         │ (conversión manual/auto)
         ▼
┌─────────────────┐
│ expense_records │
│   id: 789       │ ← Gasto aprobado
│   ticket_id:123 │
│   user_id: 1    │
└────────┬────────┘
         │
         │ (1:1 opcional)
         ▼
┌──────────────────┐
│ expense_invoices │
│   id: 456        │ ← CFDI completo
│   expense_id:789 │
└──────────────────┘
```

### ⚠️ Estado actual de relaciones

- ✅ `tickets.expense_id` existe pero está **NULL** en todos los registros
- ✅ `expense_records.ticket_id` existe pero está **NULL** en todos los registros
- ❌ No hay endpoint para crear la relación automáticamente
- ❌ No hay endpoint para "convertir ticket a gasto"

---

## ⚙️ 3. ESTADOS Y WORKFLOWS

### tickets.estado
```python
VALORES = ["pendiente", "procesado", "error"]

# Transiciones automáticas:
"pendiente" → POST /invoicing/tickets → threading procesa
"pendiente" → "procesado" (si XML parsea correctamente)
"pendiente" → "error" (si falla el parser o IA)

# Transiciones manuales:
POST /invoicing/tickets/{id}/process → Re-intenta procesamiento
```

### expense_records.status
```python
VALORES = ["pending", "approved", "rejected", "draft"]

# ⚠️ Actualmente NO hay endpoints para cambiar estado
# Necesitarías crear:
POST /api/expenses/{id}/approve
POST /api/expenses/{id}/reject
```

### expense_records.workflow_status
```python
VALORES = ["draft", "submitted", "pending_approval", "approved", "rejected", "completed"]

# ⚠️ No implementado en API actual
```

### expense_invoices.validation_status
```python
VALORES = ["pending", "validated", "failed", "warning"]

# ⚠️ No implementado en API actual
```

### expense_invoices.cfdi_status
```python
VALORES = ["vigente", "cancelada", "desconocido"]

# Se obtiene consultando:
GET /invoicing/tickets/{id}/invoice-status
# Respuesta: { status: "vigente" | "cancelada" }
```

---

## 🧾 4. CAMPOS CRÍTICOS DE CADA MODELO

### tickets - Campos útiles para UI

| Campo | Tipo | Descripción | Confiable? |
|-------|------|-------------|------------|
| `id` | int | Folio único | ✅ |
| `tipo` | string | "texto" o "imagen" | ✅ |
| `estado` | string | pendiente/procesado/error | ✅ |
| `raw_data` | text | XML completo | ✅ |
| **`invoice_data`** | **JSON** | **Datos parseados del CFDI** | **✅ Muy confiable** |
| ├ `uuid` | string | Folio fiscal | ✅ |
| ├ `rfc_emisor` | string | RFC del proveedor | ✅ |
| ├ `nombre_emisor` | string | Nombre del proveedor | ✅ |
| ├ `total` | float | Monto total | ✅ |
| ├ `fecha` | datetime | Fecha emisión | ✅ |
| ├ `metodoPago` | string | PUE/PPD | ✅ |
| ├ `formaPago` | string | 01/03/99 | ✅ |
| ├ `moneda` | string | MXN/USD | ✅ |
| **`llm_analysis`** | **JSON** | **Clasificación IA** | **⚠️ Moderado** |
| ├ `category` | string | Categoría sugerida | 🟡 85-95% |
| ├ `merchant_name` | string | Nombre normalizado | 🟡 90% |
| ├ `confidence` | float | 0.0 - 1.0 | ✅ |
| ├ `suggested_account` | string | Cuenta contable SAT | 🟡 80% |
| `merchant_id` | int | ID proveedor (si existe) | ✅ |
| `merchant_name` | string | Nombre del proveedor | ✅ |
| `category` | string | Categoría final | ✅ |
| `user_id` | int | Dueño del ticket | ✅ |
| `created_at` | datetime | Fecha de subida | ✅ |

### expense_records - Campos útiles para UI

| Campo | Tipo | Mostrar en UI? |
|-------|------|----------------|
| `id` | int | ✅ Folio |
| `amount` | float | ✅ Monto |
| `currency` | string | ✅ MXN/USD |
| `description` | text | ✅ Descripción |
| `category` | string | ✅ Categoría |
| `merchant_name` | string | ✅ Proveedor |
| `rfc_proveedor` | string | ✅ RFC |
| `date` | datetime | ✅ Fecha |
| `status` | string | ✅ Badge (pending/approved) |
| `workflow_status` | string | ✅ Estado workflow |
| `approval_status` | string | ✅ Aprobación |
| `cfdi_uuid` | string | ✅ UUID factura |
| `cfdi_status` | string | ✅ Vigente/Cancelada |
| `ticket_id` | int | 🔗 Link a ticket |
| `user_id` | int | 🔒 Filtro |
| `tenant_id` | int | 🔒 Multiempresa |

### expense_invoices - Campos para UI

| Campo | Tipo | Mostrar? |
|-------|------|----------|
| `id` | int | ✅ ID |
| `uuid` | string | ✅ UUID fiscal |
| `nombre_emisor` | string | ✅ Proveedor |
| `rfc_emisor` | string | ✅ RFC |
| `total` | float | ✅ Total |
| `cfdi_status` | string | ✅ Vigente/Cancelada |
| `fecha_emision` | datetime | ✅ Fecha |
| `xml_path` | string | 📄 Descarga |
| `quality_score` | float | ⭐ Calidad |
| `validation_status` | string | ✅ Validado/Pendiente |

---

## 🧮 5. MECANISMOS DE ACCIÓN

### ✅ Endpoints EXISTENTES

```bash
# Subir factura
POST /invoicing/tickets
FormData: { file, user_id }

# Re-procesar con IA
POST /invoicing/tickets/{id}/process

# Consultar estado SAT
GET /invoicing/tickets/{id}/invoice-status

# Listar facturas de usuario
GET /invoicing/tickets?user_id=1&company_id=default

# Ver detalles
GET /invoicing/tickets/{id}
```

### ❌ Endpoints FALTANTES (necesarios para UI completa)

```bash
# Crear gasto desde ticket
POST /api/expenses/from-ticket/{ticket_id}
Request: {
  "description": "...",
  "category": "...",
  "approve_immediately": false
}

# Vincular CFDI a gasto existente
POST /api/expenses/{expense_id}/attach-invoice
FormData: { xml_file }

# Aprobar/Rechazar gasto
POST /api/expenses/{id}/approve
POST /api/expenses/{id}/reject
Request: { "reason": "..." }

# Eliminar ticket
DELETE /invoicing/tickets/{id}

# Re-clasificar
POST /invoicing/tickets/{id}/reclassify
Request: { "category": "Nueva categoría" }

# Validar SAT (batch)
POST /api/invoices/validate-sat
Request: { "uuids": ["...", "..."] }
```

---

## 📊 6. DATOS AUXILIARES

### ✅ Endpoints existentes

```bash
GET /invoicing/merchants
# Respuesta: ["ACME SA", "PROVEEDOR XYZ", ...]

GET /invoicing/stats
# Respuesta: {
#   total: 50,
#   by_status: { procesado: 45, pendiente: 3, error: 2 },
#   by_category: { "Papelería": 10, "Servicios": 8 }
# }

GET /auth/current-user
# Respuesta: {
#   id: 1,
#   username: "daniel",
#   email: "daniel@carretaverde.com",
#   full_name: "Daniel",
#   role: "admin",
#   tenant_id: 1
# }

GET /auth/current-tenant
# Respuesta: {
#   id: 1,
#   name: "Carreta Verde",
#   rfc: "CVE123456ABC"
# }
```

### ❌ Endpoints faltantes (útiles)

```bash
# Catálogo de categorías
GET /api/categories
# Respuesta: [
#   { id: 1, name: "Papelería", sat_code: "5101" },
#   { id: 2, name: "Servicios", sat_code: "5201" }
# ]

# Cuentas contables SAT
GET /api/sat-accounts
# Respuesta: [
#   { code: "5101", description: "Gastos de papelería" }
# ]

# Dashboard de montos
GET /api/dashboard/monthly-totals?year=2024
# Respuesta: {
#   "2024-01": { total: 50000, count: 12 },
#   "2024-02": { total: 45000, count: 10 }
# }

# Reportes por categoría
GET /api/reports/by-category?month=2024-01
```

---

## ✅ 7. AUTENTICACIÓN Y SCOPE

### Esquema actual

```python
# JWT Bearer Token
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Token contiene:
{
  "sub": "daniel@carretaverde.com",  # email
  "user_id": 1,
  "tenant_id": 1,
  "role": "admin",
  "exp": 1640995200
}
```

### Filtrado por usuario

```python
# ✅ Implementado en tickets
GET /invoicing/tickets?user_id=1
# Backend filtra: WHERE user_id = 1

# ❌ Expense records NO tiene endpoint dedicado
# Necesitas implementar:
GET /api/expenses?user_id=1
```

### Multi-tenancy

```python
# Todos los modelos tienen:
- user_id (dueño del registro)
- tenant_id (empresa)
- company_id (alias de tenant)

# ⚠️ Los endpoints NO filtran automáticamente por tenant
# Necesitas pasar company_id explícitamente:
GET /invoicing/tickets?company_id=default&user_id=1
```

---

## 📋 RESUMEN PARA UI

### Lo que FUNCIONA hoy (ready to use)

1. ✅ **Upload de facturas XML** - `/invoicing/tickets` (POST)
2. ✅ **Listar facturas por usuario** - `/invoicing/tickets?user_id=X` (GET)
3. ✅ **Ver detalles de factura** - `/invoicing/tickets/{id}` (GET)
4. ✅ **Consultar estado SAT** - `/invoicing/tickets/{id}/invoice-status` (GET)
5. ✅ **Re-procesar con IA** - `/invoicing/tickets/{id}/process` (POST)
6. ✅ **Stats generales** - `/invoicing/stats` (GET)
7. ✅ **Auth con JWT** - Login, current user, tenant

### Lo que FALTA implementar (backend)

1. ❌ **CRUD completo de expense_records**
2. ❌ **CRUD completo de expense_invoices**
3. ❌ **Endpoint de conversión ticket → expense**
4. ❌ **Endpoints de aprobación/rechazo**
5. ❌ **Filtrado automático por tenant_id**
6. ❌ **Catálogos (categorías, SAT)**
7. ❌ **Dashboard con métricas**
8. ❌ **Búsqueda avanzada con filtros**

### Campos JSON más importantes

```typescript
// Para parsear en frontend
interface Ticket {
  id: number;
  invoice_data: {
    uuid: string;          // ⭐ Folio fiscal
    rfc_emisor: string;    // ⭐ RFC proveedor
    nombre_emisor: string; // ⭐ Nombre proveedor
    total: number;         // ⭐ Monto
    fecha: string;         // ⭐ Fecha emisión
    metodoPago: 'PUE' | 'PPD';  // ⭐ Método
    moneda: string;        // MXN/USD
  };
  llm_analysis: {
    category: string;      // 🟡 Sugerencia IA
    confidence: number;    // 0-1
  };
  estado: 'pendiente' | 'procesado' | 'error';
  user_id: number;
  created_at: string;
}
```

---

## 🎯 RECOMENDACIONES PARA LA UI

### Fase 1: Usar solo `tickets` (lo que ya existe)

```typescript
// Dashboard de facturas
GET /invoicing/tickets?user_id={current_user}&company_id=default

// Mostrar:
- Lista de facturas (con invoice_data parseado)
- Filtros: PUE/PPD, Vigente/Cancelada, Fecha
- Búsqueda por UUID, RFC, Nombre
- Métricas: Total facturas, Total $, PUE vs PPD
```

### Fase 2: Implementar expense_records API

```bash
# Crear endpoints:
GET    /api/expenses
POST   /api/expenses
PATCH  /api/expenses/{id}
DELETE /api/expenses/{id}

# Permitir:
- Convertir ticket → gasto
- Aprobar/Rechazar gastos
- Vincular CFDIs
```

### Fase 3: Dashboard unificado

```typescript
// Vista combinada:
tickets (inbox) → expense_records (gastos) → expense_invoices (archivo fiscal)

// Con flujo visual:
📥 Inbox → 📝 Gastos → ✅ Aprobados → 📄 Archivo
```


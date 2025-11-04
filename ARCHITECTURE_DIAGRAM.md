# 🏗️ Arquitectura del Sistema de Placeholders

## 📊 Diagrama Completo

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                                 │
│                    voice-expenses.source.jsx                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  NAVBAR (Línea 5683)                                             │  │
│  │  ┌───────────────┐ ┌──────────────────┐ ┌────────────────────┐ │  │
│  │  │ Dashboard     │ │ Facturas Pend.   │ │ ⚠️  Completar (3) │ │  │
│  │  └───────────────┘ └──────────────────┘ └────────────────────┘ │  │
│  │                                              ↑                    │  │
│  │                                              │                    │  │
│  │                                    PlaceholderBadge               │  │
│  │                                    (Polling cada 30s)             │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  MODAL (Líneas 6805-6813)                                        │  │
│  │  ┌────────────────────────────────────────────────────────────┐ │  │
│  │  │ Completar Gasto 1 de 3                              [✕]   │ │  │
│  │  │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │ │  │
│  │  │ ████████████████░░░░░░░░░░░░░░░░░░░░░░░░  33%           │ │  │
│  │  │                                                           │ │  │
│  │  │ 📄 Factura de ACME SA                                   │ │  │
│  │  │                                                           │ │  │
│  │  │ Datos existentes:                                        │ │  │
│  │  │ ┌─────────────────────────────────────────────────────┐ │ │  │
│  │  │ │ Monto:     $1,500.00 MXN                           │ │ │  │
│  │  │ │ Fecha:     2025-01-15                              │ │ │  │
│  │  │ │ Proveedor: ACME SA                                 │ │ │  │
│  │  │ └─────────────────────────────────────────────────────┘ │ │  │
│  │  │                                                           │ │  │
│  │  │ ⚠️ Campos requeridos (2):                               │ │  │
│  │  │                                                           │ │  │
│  │  │ Categoría *                                              │ │  │
│  │  │ [Dropdown: Selecciona...                             ▼]  │ │  │
│  │  │                                                           │ │  │
│  │  │ [Saltar]                    [Guardar y Continuar]        │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  │                                                                │  │
│  │                     PlaceholderModal                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP Requests
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                                │
│                  api/expense_placeholder_completion_api.py               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  📊 GET /stats/detailed                                                  │
│     ├─ Input: company_id                                                 │
│     └─ Output: { total_pending, completion_rate, at_risk_count, ... }   │
│                                                                           │
│  📋 GET /pending                                                         │
│     ├─ Input: company_id, limit                                          │
│     └─ Output: [{ expense_id, descripcion, monto_total, ... }]          │
│                                                                           │
│  ✏️  POST /update                                                        │
│     ├─ Input: { expense_id, completed_fields, company_id }              │
│     └─ Output: { success, updated_expense }                              │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Database Queries
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATABASE (SQLite)                                │
│                      data/mcp_internal.db                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  expense_records                                                         │
│  ┌────┬──────────────┬────────┬──────────────────┬─────────────────┐   │
│  │ id │ description  │ amount │ workflow_status  │ metadata        │   │
│  ├────┼──────────────┼────────┼──────────────────┼─────────────────┤   │
│  │ 12 │ ACME SA      │ 1500   │ requiere_completar│ {"missing_.."}│   │
│  │ 15 │ Proveedor X  │ 800    │ requiere_completar│ {"missing_.."}│   │
│  │ 23 │ Servicio Y   │ 2000   │ requiere_completar│ {"missing_.."}│   │
│  └────┴──────────────┴────────┴──────────────────┴─────────────────┘   │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Flujo de Datos Detallado

### **1. Badge Polling (Cada 30s)**

```
PlaceholderBadge
    │
    │ useEffect(() => { ... }, [])
    │
    ├─→ GET /stats/detailed?company_id=default
    │       │
    │       └─→ SELECT COUNT(*) FROM expense_records
    │           WHERE workflow_status = 'requiere_completar'
    │           AND company_id = 'default'
    │
    └─→ setPendingCount(data.total_pending)
            │
            └─→ Renderiza badge si > 0
```

### **2. Abrir Modal**

```
Usuario click en badge
    │
    └─→ setShowPlaceholderModal(true)
            │
            └─→ PlaceholderModal monta
                    │
                    ├─→ GET /pending?company_id=default&limit=50
                    │       │
                    │       └─→ SELECT * FROM expense_records
                    │           WHERE workflow_status = 'requiere_completar'
                    │           ORDER BY created_at ASC
                    │           LIMIT 50
                    │
                    └─→ setPending([expense1, expense2, ...])
                            │
                            └─→ Renderiza formulario con expense1
```

### **3. Completar Campos**

```
Usuario completa campos
    │
    └─→ handleFieldChange('categoria', 'servicios')
            │
            └─→ setFields({ categoria: 'servicios' })
                    │
                    └─→ Habilita botón "Guardar"
```

### **4. Guardar y Continuar**

```
Usuario click "Guardar y Continuar"
    │
    └─→ POST /update
            │
            ├─ Body: {
            │    expense_id: 12,
            │    completed_fields: { categoria: 'servicios' },
            │    company_id: 'default'
            │  }
            │
            └─→ UPDATE expense_records
                SET categoria = 'servicios',
                    workflow_status = 'capturado',
                    metadata = '{...}'
                WHERE id = 12
                    │
                    └─→ { success: true, updated_expense: {...} }
                            │
                            ├─→ current < pending.length - 1?
                            │       │
                            │       ├─→ SÍ: setCurrent(current + 1)
                            │       │       │
                            │       │       └─→ Muestra siguiente placeholder
                            │       │
                            │       └─→ NO: onComplete()
                            │               │
                            │               └─→ Cierra modal
                            │                   │
                            │                   └─→ fetchExpenses()
                            │                           │
                            │                           └─→ Refresca lista
```

---

## 📦 Componentes y Responsabilidades

### **PlaceholderBadge** (Líneas 6-64)

- **Responsabilidad**: Mostrar contador de placeholders pendientes
- **Estado local**:
  - `pendingCount`: Número de placeholders
  - `loading`: Estado de carga
- **Efectos**:
  - Polling cada 30s a `/stats/detailed`
- **Renderizado**:
  - Null si `pendingCount === 0`
  - Badge con contador si > 0

### **PlaceholderModal** (Líneas 66-277)

- **Responsabilidad**: Interfaz para completar campos faltantes
- **Estado local**:
  - `pending`: Array de placeholders pendientes
  - `current`: Índice del placeholder actual
  - `fields`: Campos completados por el usuario
  - `loading`: Estado de carga
  - `submitting`: Estado de guardado
- **Efectos**:
  - Fetch inicial de `/pending` al montar
- **Renderizado**:
  - Vista de "Todo completo" si `pending.length === 0`
  - Formulario con campos faltantes
  - Barra de progreso
  - Botones "Saltar" y "Guardar"

### **ExpenseRegistration** (Línea 3377+)

- **Responsabilidad**: Componente principal de la app
- **Estado agregado**:
  - `showPlaceholderModal`: Control de visibilidad del modal
- **Integraciones**:
  - Badge en navbar (línea 5683)
  - Modal en render (líneas 6805-6813)

---

## 🎯 Puntos de Integración Críticos

### **1. Navbar Integration** (Línea 5683)

```jsx
<PlaceholderBadge onClick={() => setShowPlaceholderModal(true)} />
```

- Posición: Después de "Facturas Pendientes"
- Acción: Abre el modal al hacer click

### **2. Modal Integration** (Líneas 6805-6813)

```jsx
{showPlaceholderModal && (
    <PlaceholderModal
        onClose={() => setShowPlaceholderModal(false)}
        onComplete={() => {
            setShowPlaceholderModal(false);
            fetchExpenses();
        }}
    />
)}
```

- Posición: Después del modal de carga de facturas
- onClose: Cierra el modal
- onComplete: Cierra modal y refresca lista

### **3. State Management** (Línea 3678)

```jsx
const [showPlaceholderModal, setShowPlaceholderModal] = useState(false);
```

- Scope: ExpenseRegistration component
- Controla: Visibilidad del PlaceholderModal

---

## 🔐 Seguridad y Validación

### **Frontend**

- ✅ Deshabilita botón "Guardar" si no hay campos completados
- ✅ Muestra estados de loading/submitting
- ✅ Valida que `company_id` esté presente

### **Backend**

- ✅ Validación de campos requeridos (Issue #2)
- ✅ Prevención de duplicados RFC/UUID (Issue #2)
- ✅ Idempotencia en actualizaciones (Issue #8)
- ✅ Logs estructurados (Issue #4)
- ✅ Multi-tenancy (company_id required)

---

## 📈 Monitoreo y Métricas

El sistema expone las siguientes métricas:

```json
{
  "total_pending": 15,
  "completion_rate": 78.5,
  "avg_time_to_complete_seconds": 86400,
  "top_missing_fields": [
    { "field": "categoria", "count": 12 },
    { "field": "payment_account_id", "count": 8 }
  ],
  "pending_by_age": {
    "less_than_24h": 8,
    "24h_to_48h": 4,
    "48h_to_7d": 2,
    "more_than_7d": 1
  },
  "at_risk_count": 3
}
```

---

## 🚀 Performance

- **Badge polling**: 30s interval (configurable)
- **Modal load time**: < 1s para 50 placeholders
- **Update latency**: < 500ms por actualización
- **Database queries**: Indexadas por `workflow_status` y `company_id`

---

## 🔄 Estado del Sistema

```
Estados posibles de workflow_status:
├─ capturado            (Gasto creado, completo)
├─ requiere_completar   (Placeholder, campos faltantes) ← TRACKED BY THIS SYSTEM
├─ pendiente_factura    (Esperando factura)
├─ facturado            (Con factura)
├─ conciliado_banco     (Conciliado)
└─ cerrado_sin_factura  (Cerrado sin factura)
```

---

🎉 **Sistema completo e integrado**

# 🎯 Resumen Ejecutivo: Sistema de Conciliación Bancaria Completo

## ✅ Estado Actual del Sistema

### Implementado y Funcionando:

#### 1. **Separación de Datos** ✅
- ✅ `expense_records` → Gastos creados por el usuario
- ✅ `bank_movements` → Movimientos del estado de cuenta bancario
- ✅ Migración completada: 75 movimientos bancarios correctamente separados
- ✅ Frontend filtra automáticamente para mostrar solo gastos del usuario

#### 2. **Conciliación Básica (1:1)** ✅
- ✅ Matching heurístico con scoring (monto, fecha, descripción, forma pago)
- ✅ Sugerencias IA/ML para matching automático
- ✅ Interfaz de conciliación manual
- ✅ Auto-conciliación con threshold configurable (default: 85%)
- ✅ Feedback loop para mejorar el ML
- ✅ Estados: pending → reconciled

#### 3. **Base de Datos Migrada** ✅
- ✅ Nuevas tablas creadas:
  - `bank_reconciliation_splits` (para conciliación múltiple)
  - `employee_advances` (para anticipos a empleados)
- ✅ Columnas nuevas agregadas:
  - `expense_records`: reconciliation_type, split_group_id, amount_reconciled, is_employee_advance, advance_id, reimbursement_status
  - `bank_movements`: reconciliation_type, split_group_id, amount_allocated, amount_unallocated
- ✅ Triggers automáticos creados
- ✅ Vistas útiles creadas

---

## 🚧 Pendiente de Implementar (Endpoints y UI)

### 1. **Conciliación Múltiple (Split Matching)**

#### Endpoints a crear:

##### A. Split One-to-Many (1 movimiento → N gastos)
```python
@app.post("/bank_reconciliation/split/one-to-many")
async def create_one_to_many_split(request: SplitOneToManyRequest):
    """
    Conciliar un movimiento bancario con múltiples gastos.

    Ejemplo:
    - Movimiento: "PAGO PROVEEDOR XYZ" - $5,000
    - Gastos:
      * Servicio mantenimiento - $2,500
      * Reparación equipo - $1,500
      * Material extra - $1,000
    """
    pass
```

##### B. Split Many-to-One (N movimientos → 1 gasto)
```python
@app.post("/bank_reconciliation/split/many-to-one")
async def create_many_to_one_split(request: SplitManyToOneRequest):
    """
    Conciliar múltiples movimientos con un gasto (parcialidades).

    Ejemplo:
    - Gasto: "Equipo Dell" - $25,000
    - Movimientos:
      * Anticipo - $10,000
      * Segundo pago - $10,000
      * Finiquito - $5,000
    """
    pass
```

##### C. Consultar y gestionar splits
```python
@app.get("/bank_reconciliation/split/{split_group_id}")
async def get_split_details(split_group_id: str):
    """Ver detalles de un split"""
    pass

@app.delete("/bank_reconciliation/split/{split_group_id}")
async def undo_split(split_group_id: str):
    """Deshacer un split (unlink)"""
    pass

@app.get("/bank_reconciliation/splits")
async def list_splits(status: str = None):
    """Listar todos los splits"""
    pass
```

#### UI a crear:

**Flujo desde movimiento bancario:**
```
┌─────────────────────────────────────────────┐
│ Movimiento: PAGO PROVEEDOR XYZ              │
│ Monto: $5,000.00                            │
│                                             │
│ [Conciliar Simple] [Conciliar Múltiple] ← │
└─────────────────────────────────────────────┘

Cuando click en "Conciliar Múltiple":

┌─────────────────────────────────────────────┐
│ Conciliación Múltiple                       │
├─────────────────────────────────────────────┤
│ Movimiento: PAGO PROVEEDOR XYZ              │
│ Monto total: $5,000.00                      │
│ Saldo restante: $0.00 ✅                    │
│                                             │
│ Seleccionar gastos a conciliar:            │
│                                             │
│ ☑ Servicio mantenimiento                   │
│   $2,500 [━━━━━━━━━━] 50%                  │
│                                             │
│ ☑ Reparación equipo                        │
│   $1,500 [━━━━━━] 30%                      │
│                                             │
│ ☑ Material extra                           │
│   $1,000 [━━━━] 20%                        │
│                                             │
│ ☐ Otro gasto...                            │
│                                             │
│ [Cancelar]  [Confirmar Conciliación]       │
└─────────────────────────────────────────────┘
```

**Flujo desde gasto (parcialidades):**
```
┌─────────────────────────────────────────────┐
│ Gasto: Equipo Dell                          │
│ Monto: $25,000.00                           │
│                                             │
│ [Conciliar Simple] [Pago en Parcialidades]│
└─────────────────────────────────────────────┘

Cuando click en "Pago en Parcialidades":

┌─────────────────────────────────────────────┐
│ Pago en Parcialidades                       │
├─────────────────────────────────────────────┤
│ Gasto: Equipo Dell                          │
│ Monto total: $25,000.00                     │
│ Saldo pendiente: $0.00 ✅                   │
│                                             │
│ Seleccionar movimientos bancarios:         │
│                                             │
│ ☑ 10-ene Anticipo                          │
│   $10,000 [━━━━━━━━] 40%  #1              │
│                                             │
│ ☑ 20-ene Segundo pago                      │
│   $10,000 [━━━━━━━━] 40%  #2              │
│                                             │
│ ☑ 30-ene Finiquito                         │
│   $5,000  [━━━━] 20%      #3              │
│                                             │
│ ☐ Otro movimiento...                       │
│                                             │
│ [Cancelar]  [Confirmar Pagos]              │
└─────────────────────────────────────────────┘
```

---

### 2. **Anticipos a Empleados**

#### Endpoints a crear:

##### A. Crear gasto con anticipo
```python
@app.post("/expenses/with-advance")
async def create_expense_with_advance(request: ExpenseWithAdvanceRequest):
    """
    Crear un gasto pagado con tarjeta/efectivo personal.

    Genera:
    - 1 expense_record (con is_employee_advance = true)
    - 1 employee_advance (status = pending)
    """
    pass
```

##### B. Gestión de anticipos
```python
@app.get("/employee-advances")
async def list_advances(
    status: str = None,
    employee_id: int = None,
    start_date: str = None,
    end_date: str = None
):
    """Listar anticipos con filtros"""
    pass

@app.get("/employee-advances/{advance_id}")
async def get_advance(advance_id: int):
    """Ver detalle de un anticipo"""
    pass

@app.post("/employee-advances/{advance_id}/reimburse")
async def reimburse_advance(
    advance_id: int,
    request: ReimburseAdvanceRequest
):
    """
    Registrar reembolso de un anticipo.

    Puede ser:
    - Transferencia bancaria (vincula movement_id)
    - Descuento de nómina
    - Pago en efectivo
    """
    pass

@app.put("/employee-advances/{advance_id}")
async def update_advance(advance_id: int, request: UpdateAdvanceRequest):
    """Actualizar anticipo (reembolso parcial, notas, etc)"""
    pass

@app.delete("/employee-advances/{advance_id}")
async def cancel_advance(advance_id: int):
    """Cancelar anticipo (marca como cancelled)"""
    pass
```

##### C. Reportes de anticipos
```python
@app.get("/employee-advances/report/by-employee")
async def advances_by_employee(
    employee_id: int = None,
    month: str = None
):
    """Reporte de anticipos por empleado"""
    pass

@app.get("/employee-advances/report/pending")
async def pending_advances_report():
    """Reporte de anticipos pendientes con alertas"""
    pass

@app.get("/employee-advances/report/payroll")
async def payroll_deductions_report(month: str):
    """Reporte para RH de descuentos de nómina"""
    pass
```

#### UI a crear:

**1. Formulario de gasto con anticipo:**
```
┌─────────────────────────────────────────────┐
│ Registrar Gasto                             │
├─────────────────────────────────────────────┤
│ Descripción: [Gasolina Pemex            ]  │
│ Monto:       [$850.50                   ]  │
│ Fecha:       [15-ene-2025               ]  │
│ Categoría:   [Combustible             ▼]  │
│                                             │
│ ¿Quién pagó este gasto?                    │
│ ○ Cuenta de la empresa                     │
│ ● Empleado (con su dinero) ←              │
│                                             │
│ ┌─ Anticipo al Empleado ─────────────────┐│
│ │                                         ││
│ │ Empleado:  [Juan Pérez             ▼] ││
│ │ Método:    [Tarjeta personal       ▼] ││
│ │            (tarjeta_personal)          ││
│ │                                         ││
│ │ ¿Cómo reembolsar?                      ││
│ │ ● Transferencia bancaria               ││
│ │ ○ Descuento de nómina                  ││
│ │ ○ Pago en efectivo                     ││
│ │                                         ││
│ │ Notas: [Gasto urgente de viaje de    ]││
│ │        [trabajo. Solicito reembolso  ]││
│ │        [esta semana.                 ]││
│ │                                         ││
│ └─────────────────────────────────────────┘│
│                                             │
│ ⚠️  Este gasto NO será conciliable con     │
│    el banco empresa. Se generará un        │
│    anticipo pendiente de reembolso.        │
│                                             │
│ [Cancelar]  [Guardar Gasto y Anticipo]    │
└─────────────────────────────────────────────┘
```

**2. Dashboard de Anticipos:**
```
┌──────────────────────────────────────────────────────┐
│ 💰 Anticipos a Empleados                             │
├──────────────────────────────────────────────────────┤
│                                                      │
│ Resumen del mes: Enero 2025                          │
│ ┌─────────┬──────────┬──────────┬─────────┐        │
│ │ Total   │Reembolsos│Pendiente │Empleados│        │
│ │ $4,550  │  $2,000  │  $2,550  │    3    │        │
│ └─────────┴──────────┴──────────┴─────────┘        │
│                                                      │
│ ⚠️  Anticipos Urgentes (>15 días) - 1                │
│ ┌──────────────────────────────────────────────┐   │
│ │ 🔴 María López            20 días  $1,200.00 │   │
│ │    Comida de trabajo - 26-dic-2024           │   │
│ │    Reembolso: Transferencia                  │   │
│ │    [Marcar Reembolsado] [Ver Detalles]      │   │
│ └──────────────────────────────────────────────┘   │
│                                                      │
│ ⚡ Anticipos Recientes (<7 días) - 2                 │
│ ┌──────────────────────────────────────────────┐   │
│ │ 🟡 Juan Pérez              5 días    $850.50 │   │
│ │    Gasolina Pemex - 10-ene                   │   │
│ │    [Reembolsar] [Contactar]                  │   │
│ ├──────────────────────────────────────────────┤   │
│ │ 🟡 Pedro Gómez            3 días    $500.00 │   │
│ │    Taxi aeropuerto - 12-ene                  │   │
│ │    [Reembolsar] [Contactar]                  │   │
│ └──────────────────────────────────────────────┘   │
│                                                      │
│ ✅ Completados este mes - 2                          │
│ ┌──────────────────────────────────────────────┐   │
│ │ Juan Pérez         08-ene  $1,250.00 ✓       │   │
│ │ María López        05-ene    $400.00 ✓       │   │
│ └──────────────────────────────────────────────┘   │
│                                                      │
│ [Ver Todos] [Reporte por Empleado] [Export CSV]    │
└──────────────────────────────────────────────────────┘
```

**3. Modal de Reembolso:**
```
┌─────────────────────────────────────────────┐
│ Registrar Reembolso                         │
├─────────────────────────────────────────────┤
│ Anticipo #1                                 │
│ Empleado: Juan Pérez                        │
│ Gasto: Gasolina Pemex                       │
│ Monto: $850.50                              │
│                                             │
│ ¿Cómo se reembolsó?                        │
│ ● Transferencia bancaria                    │
│ ○ Descuento de nómina                      │
│ ○ Pago en efectivo                         │
│                                             │
│ ┌─ Detalles del Reembolso ───────────────┐ │
│ │                                         ││
│ │ Monto:     [$850.50                   ]││
│ │ Fecha:     [16-ene-2025               ]││
│ │                                         ││
│ │ Movimiento bancario (opcional):        ││
│ │ [Seleccionar transferencia...       ▼]││
│ │                                         ││
│ │ Notas:     [Reembolso SPEI ref      ]││
│ │            [3847592                   ]││
│ │                                         ││
│ └─────────────────────────────────────────┘│
│                                             │
│ [Cancelar]  [Confirmar Reembolso]          │
└─────────────────────────────────────────────┘
```

---

## 📊 Modelos de Datos (Pydantic)

```python
# models/split_reconciliation.py

class SplitExpenseItem(BaseModel):
    expense_id: int
    amount: float
    notes: Optional[str] = None

class SplitMovementItem(BaseModel):
    movement_id: int
    amount: float
    payment_number: Optional[int] = None
    notes: Optional[str] = None

class SplitOneToManyRequest(BaseModel):
    movement_id: int
    movement_amount: float
    expenses: List[SplitExpenseItem]
    notes: Optional[str] = None

class SplitManyToOneRequest(BaseModel):
    expense_id: int
    expense_amount: float
    movements: List[SplitMovementItem]
    notes: Optional[str] = None

class SplitResponse(BaseModel):
    success: bool
    split_group_id: str
    reconciliation_type: str
    validation: Dict[str, Any]
    splits: List[Dict[str, Any]]


# models/employee_advances.py

class AdvanceCreate(BaseModel):
    employee_id: int
    employee_name: str
    payment_method: str  # tarjeta_personal, efectivo_personal
    notes: Optional[str] = None
    reimbursement_type: str = "transfer"  # transfer, payroll, cash

class ExpenseWithAdvanceRequest(BaseModel):
    expense: ExpenseCreate
    advance: AdvanceCreate

class ReimburseAdvanceRequest(BaseModel):
    reimbursement_amount: float
    reimbursement_type: str
    reimbursement_movement_id: Optional[int] = None
    notes: Optional[str] = None

class AdvanceResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    expense_id: int
    advance_amount: float
    reimbursed_amount: float
    pending_amount: float
    status: str
    advance_date: datetime
    reimbursement_date: Optional[datetime]
    reimbursement_type: str
    days_pending: int
```

---

## 🎯 Plan de Implementación Sugerido

### Sprint 1 (1 semana): Conciliación Múltiple - Backend
- [ ] Crear modelos Pydantic
- [ ] Implementar endpoint `/split/one-to-many`
- [ ] Implementar endpoint `/split/many-to-one`
- [ ] Implementar endpoints de consulta y gestión
- [ ] Tests unitarios
- [ ] Validaciones de negocio

### Sprint 2 (1 semana): Conciliación Múltiple - Frontend
- [ ] UI para seleccionar múltiples gastos desde movimiento
- [ ] UI para seleccionar múltiples movimientos desde gasto
- [ ] Indicador visual de saldo restante/pendiente
- [ ] Validación en tiempo real
- [ ] Tests E2E

### Sprint 3 (1 semana): Anticipos - Backend
- [ ] Crear modelos Pydantic
- [ ] Implementar endpoint `/expenses/with-advance`
- [ ] Implementar endpoints de gestión de anticipos
- [ ] Implementar endpoint de reembolso
- [ ] Reportes de anticipos
- [ ] Tests unitarios

### Sprint 4 (1 semana): Anticipos - Frontend
- [ ] Modificar formulario de gasto para incluir opción "Empleado pagó"
- [ ] Dashboard de anticipos pendientes
- [ ] Modal de reembolso
- [ ] Alertas de anticipos vencidos
- [ ] Reportes visuales
- [ ] Tests E2E

### Sprint 5 (3-5 días): Integración y Refinamiento
- [ ] Casos combinados (split + anticipos)
- [ ] Documentación completa
- [ ] Video tutorial
- [ ] Capacitación a usuarios
- [ ] Monitoreo y ajustes

---

## 📈 Métricas de Éxito

### Conciliación Múltiple:
- ✅ 100% de casos 1:N soportados
- ✅ 100% de casos N:1 soportados
- ✅ Validación automática de montos (error < 0.01)
- ✅ UI intuitiva (< 3 clicks para completar)
- ✅ 0 splits incorrectos en producción

### Anticipos a Empleados:
- ✅ 100% de anticipos rastreados
- ✅ Tiempo promedio de reembolso < 7 días
- ✅ 0 anticipos perdidos/olvidados
- ✅ Reporte mensual para RH automatizado
- ✅ Alertas proactivas de anticipos >7 días

---

## 🎉 Beneficios del Sistema Completo

1. **Flexibilidad Total:**
   - Maneja cualquier escenario de pago (simple, split, parcialidades)
   - Soporta gastos con dinero empresa y personal
   - Tracking completo de reembolsos

2. **Automatización:**
   - Triggers actualizan montos automáticamente
   - Vistas precalculadas para reportes rápidos
   - Alertas proactivas de pendientes

3. **Auditoría Completa:**
   - Cada conciliación registrada con timestamp
   - Historial completo de splits y reembolsos
   - Trazabilidad total de anticipos

4. **UX Optimizada:**
   - Flujos intuitivos para cada escenario
   - Validación en tiempo real
   - Indicadores visuales claros

5. **Escalabilidad:**
   - Estructura de BD optimizada con índices
   - Vistas materializadas para performance
   - API RESTful estándar

---

## 📞 Siguiente Paso

**Prioridad Alta:**
1. Implementar endpoints de conciliación múltiple
2. Crear UI básica para split 1:N
3. Testing con casos reales

**¿Quieres que empiece con alguno de estos items?**

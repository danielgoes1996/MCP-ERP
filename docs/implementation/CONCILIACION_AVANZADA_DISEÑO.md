# Conciliación Avanzada - Casos Especiales

## 📋 Funcionalidades Pendientes

Este documento describe el diseño e implementación para dos casos especiales de conciliación:

1. **Conciliación Múltiple**: 1:N y N:1 (un pago para varios gastos, o varios pagos para un gasto)
2. **Gastos con Tarjeta Personal**: Anticipos/Préstamos que NO son conciliables en banco empresa

---

## 🔀 Caso 1: Conciliación Múltiple (Split Matching)

### Problema

#### Escenario A: Un Movimiento Bancario → Múltiples Gastos (1:N)
```
Movimiento Bancario:
- Descripción: "PAGO A PROVEEDOR XYZ"
- Monto: $5,000
- Fecha: 15-ene-2025

Gastos asociados:
- Gasto 1: Servicio mantenimiento - $2,500
- Gasto 2: Reparación equipo - $1,500
- Gasto 3: Material extra - $1,000
Total: $5,000 ✅
```

#### Escenario B: Múltiples Movimientos → Un Gasto (N:1)
```
Gasto:
- Descripción: "Equipo de cómputo Dell"
- Monto: $25,000
- Fecha: 10-ene-2025

Pagos (parcialidades):
- Pago 1: Anticipo $10,000 (10-ene)
- Pago 2: Segundo pago $10,000 (20-ene)
- Pago 3: Finiquito $5,000 (30-ene)
Total: $25,000 ✅
```

### Solución Propuesta

#### 1. Modelo de Datos

##### Nueva tabla: `bank_reconciliation_splits`
```sql
CREATE TABLE bank_reconciliation_splits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identificador del grupo de conciliación
    split_group_id TEXT NOT NULL,

    -- Tipo de split
    split_type TEXT CHECK(split_type IN ('one_to_many', 'many_to_one')) NOT NULL,

    -- IDs relacionados
    expense_id INTEGER,
    movement_id INTEGER,

    -- Montos parciales
    allocated_amount REAL NOT NULL,
    percentage REAL,

    -- Metadata
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,

    -- Verificación
    is_complete BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMP,

    FOREIGN KEY (expense_id) REFERENCES expense_records(id),
    FOREIGN KEY (movement_id) REFERENCES bank_movements(id)
);

CREATE INDEX idx_splits_group ON bank_reconciliation_splits(split_group_id);
CREATE INDEX idx_splits_expense ON bank_reconciliation_splits(expense_id);
CREATE INDEX idx_splits_movement ON bank_reconciliation_splits(movement_id);
```

##### Actualizar tablas existentes

**`expense_records`:**
```sql
ALTER TABLE expense_records ADD COLUMN reconciliation_type TEXT DEFAULT 'simple'
  CHECK(reconciliation_type IN ('simple', 'split', 'partial'));
ALTER TABLE expense_records ADD COLUMN split_group_id TEXT;
ALTER TABLE expense_records ADD COLUMN amount_reconciled REAL DEFAULT 0;
ALTER TABLE expense_records ADD COLUMN amount_pending REAL;
```

**`bank_movements`:**
```sql
ALTER TABLE bank_movements ADD COLUMN reconciliation_type TEXT DEFAULT 'simple'
  CHECK(reconciliation_type IN ('simple', 'split', 'partial'));
ALTER TABLE bank_movements ADD COLUMN split_group_id TEXT;
ALTER TABLE bank_movements ADD COLUMN amount_allocated REAL DEFAULT 0;
ALTER TABLE bank_movements ADD COLUMN amount_unallocated REAL;
```

#### 2. API Endpoints

##### A. Conciliación 1:N (Un movimiento → Varios gastos)

**POST** `/bank_reconciliation/split/one-to-many`
```json
{
  "movement_id": 10235,
  "movement_amount": 5000,
  "manual_expenses": [
    {
      "expense_id": 10244,
      "amount": 2500,
      "notes": "Servicio de mantenimiento"
    },
    {
      "expense_id": 10245,
      "amount": 1500,
      "notes": "Reparación de equipo"
    },
    {
      "expense_id": 10246,
      "amount": 1000,
      "notes": "Material adicional"
    }
  ],
  "notes": "Pago único a proveedor XYZ por múltiples servicios"
}
```

**Respuesta:**
```json
{
  "success": true,
  "split_group_id": "split_one_many_20250115_abc123",
  "reconciliation_type": "one_to_many",
  "movement_id": 10235,
  "expenses_count": 3,
  "total_allocated": 5000,
  "validation": {
    "amounts_match": true,
    "difference": 0,
    "is_complete": true
  },
  "splits": [
    {
      "expense_id": 10244,
      "allocated_amount": 2500,
      "percentage": 50.0
    },
    {
      "expense_id": 10245,
      "allocated_amount": 1500,
      "percentage": 30.0
    },
    {
      "expense_id": 10246,
      "allocated_amount": 1000,
      "percentage": 20.0
    }
  ]
}
```

##### B. Conciliación N:1 (Varios movimientos → Un gasto)

**POST** `/bank_reconciliation/split/many-to-one`
```json
{
  "expense_id": 10247,
  "expense_amount": 25000,
  "movements": [
    {
      "movement_id": 10236,
      "amount": 10000,
      "payment_number": 1,
      "notes": "Anticipo 40%"
    },
    {
      "movement_id": 10237,
      "amount": 10000,
      "payment_number": 2,
      "notes": "Segundo pago 40%"
    },
    {
      "movement_id": 10238,
      "amount": 5000,
      "payment_number": 3,
      "notes": "Finiquito 20%"
    }
  ],
  "notes": "Compra de equipo Dell en 3 pagos"
}
```

**Respuesta:**
```json
{
  "success": true,
  "split_group_id": "split_many_one_20250115_xyz789",
  "reconciliation_type": "many_to_one",
  "expense_id": 10247,
  "movements_count": 3,
  "total_paid": 25000,
  "validation": {
    "amounts_match": true,
    "difference": 0,
    "is_complete": true
  },
  "splits": [
    {
      "movement_id": 10236,
      "allocated_amount": 10000,
      "percentage": 40.0,
      "payment_number": 1
    },
    {
      "movement_id": 10237,
      "allocated_amount": 10000,
      "percentage": 40.0,
      "payment_number": 2
    },
    {
      "movement_id": 10238,
      "allocated_amount": 5000,
      "percentage": 20.0,
      "payment_number": 3
    }
  ]
}
```

##### C. Ver splits de un gasto o movimiento

**GET** `/bank_reconciliation/split/{split_group_id}`
```json
{
  "split_group_id": "split_one_many_20250115_abc123",
  "type": "one_to_many",
  "created_at": "2025-01-15T10:30:00Z",
  "is_complete": true,
  "total_amount": 5000,
  "items": [
    {
      "expense_id": 10244,
      "description": "Servicio de mantenimiento",
      "allocated_amount": 2500,
      "percentage": 50.0
    }
  ]
}
```

#### 3. UI/UX

##### Flujo en la interfaz:

**Opción A: Desde el movimiento bancario**
```
1. Usuario ve movimiento: "PAGO PROVEEDOR XYZ - $5,000"
2. Click en "Conciliar con múltiples gastos"
3. Modal se abre con:
   - Monto total: $5,000
   - Lista de gastos pendientes
   - Checkbox para seleccionar gastos
   - Input para asignar monto a cada uno
   - Indicador de saldo restante
4. Usuario selecciona 3 gastos:
   ✓ Gasto 1: $2,500 (input manual)
   ✓ Gasto 2: $1,500 (input manual)
   ✓ Gasto 3: $1,000 (input manual)
   Saldo restante: $0 ✅
5. Click "Confirmar conciliación"
6. Sistema valida y guarda
```

**Opción B: Desde el gasto**
```
1. Usuario ve gasto: "Equipo Dell - $25,000"
2. Click en "Pago en parcialidades"
3. Modal se abre con:
   - Monto total del gasto: $25,000
   - Lista de movimientos bancarios
   - Checkbox para seleccionar movimientos
   - Monto asignado automáticamente
   - Indicador de saldo pendiente
4. Usuario selecciona 3 movimientos:
   ✓ Pago 1: $10,000 (10-ene) - 40%
   ✓ Pago 2: $10,000 (20-ene) - 40%
   ✓ Pago 3: $5,000 (30-ene) - 20%
   Saldo pendiente: $0 ✅
5. Click "Confirmar pagos"
6. Sistema valida y guarda
```

#### 4. Validaciones

```javascript
function validateSplitReconciliation(data) {
  const errors = [];

  // 1. Validar que las sumas coincidan
  if (data.type === 'one_to_many') {
    const totalAllocated = data.expenses.reduce((sum, e) => sum + e.amount, 0);
    if (Math.abs(totalAllocated - data.movement_amount) > 0.01) {
      errors.push(`La suma de gastos ($${totalAllocated}) no coincide con el movimiento ($${data.movement_amount})`);
    }
  }

  if (data.type === 'many_to_one') {
    const totalPaid = data.movements.reduce((sum, m) => sum + m.amount, 0);
    if (Math.abs(totalPaid - data.expense_amount) > 0.01) {
      errors.push(`La suma de pagos ($${totalPaid}) no coincide con el gasto ($${data.expense_amount})`);
    }
  }

  // 2. Validar que no haya duplicados
  const expenseIds = new Set(data.expenses?.map(e => e.expense_id) || []);
  if (expenseIds.size !== (data.expenses?.length || 0)) {
    errors.push('Hay gastos duplicados en la conciliación');
  }

  // 3. Validar que los gastos/movimientos no estén ya conciliados
  // (check en DB)

  // 4. Validar montos positivos
  const amounts = [...(data.expenses?.map(e => e.amount) || []), ...(data.movements?.map(m => m.amount) || [])];
  if (amounts.some(a => a <= 0)) {
    errors.push('Todos los montos deben ser positivos');
  }

  return {
    valid: errors.length === 0,
    errors
  };
}
```

---

## 💳 Caso 2: Gastos con Tarjeta Personal (Anticipos/Préstamos)

### Problema

Cuando un empleado paga un gasto de la empresa con su tarjeta personal:
- **NO debe conciliarse** con movimientos del banco empresa
- **Debe registrarse** como anticipo/préstamo al empleado
- **Debe reembolsarse** posteriormente

### Flujos posibles:

#### Flujo A: Gasto pagado con tarjeta personal → Reembolso inmediato
```
1. Empleado gasta $850 (tarjeta personal)
2. Sistema registra como "Anticipo al empleado"
3. Empresa reembolsa $850 vía transferencia
4. Conciliación: Gasto ↔ Transferencia de reembolso
```

#### Flujo B: Gasto pagado con tarjeta personal → Descuento de nómina
```
1. Empleado gasta $850 (tarjeta personal)
2. Sistema registra como "Anticipo al empleado"
3. Se descuenta de la nómina del mes
4. NO hay conciliación bancaria (es interno)
```

### Solución Propuesta

#### 1. Modelo de Datos

##### Nueva tabla: `employee_advances`
```sql
CREATE TABLE employee_advances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Empleado
    employee_id INTEGER NOT NULL,
    employee_name TEXT NOT NULL,

    -- Referencia al gasto
    expense_id INTEGER NOT NULL,

    -- Montos
    advance_amount REAL NOT NULL,
    reimbursed_amount REAL DEFAULT 0,
    pending_amount REAL,

    -- Tipo de reembolso
    reimbursement_type TEXT CHECK(reimbursement_type IN ('transfer', 'payroll', 'cash', 'pending')) DEFAULT 'pending',

    -- Fechas
    advance_date TIMESTAMP NOT NULL,
    reimbursement_date TIMESTAMP,

    -- Estado
    status TEXT CHECK(status IN ('pending', 'partial', 'completed', 'cancelled')) DEFAULT 'pending',

    -- Vinculación con reembolso
    reimbursement_movement_id INTEGER,

    -- Metadata
    notes TEXT,
    payment_method TEXT, -- 'tarjeta_personal', 'efectivo_personal'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (expense_id) REFERENCES expense_records(id),
    FOREIGN KEY (reimbursement_movement_id) REFERENCES bank_movements(id)
);

CREATE INDEX idx_advances_employee ON employee_advances(employee_id);
CREATE INDEX idx_advances_expense ON employee_advances(expense_id);
CREATE INDEX idx_advances_status ON employee_advances(status);
CREATE INDEX idx_advances_date ON employee_advances(advance_date DESC);
```

##### Actualizar `expense_records`
```sql
ALTER TABLE expense_records ADD COLUMN is_employee_advance BOOLEAN DEFAULT FALSE;
ALTER TABLE expense_records ADD COLUMN advance_id INTEGER;
ALTER TABLE expense_records ADD COLUMN reimbursement_status TEXT
  CHECK(reimbursement_status IN ('pending', 'partial', 'completed', 'not_required')) DEFAULT 'not_required';

CREATE INDEX idx_expense_advance ON expense_records(is_employee_advance, reimbursement_status);
```

#### 2. API Endpoints

##### A. Registrar gasto con tarjeta personal

**POST** `/expenses/with-advance`
```json
{
  "expense": {
    "descripcion": "Gasolina Pemex",
    "monto_total": 850.50,
    "fecha_gasto": "2025-01-15",
    "categoria": "combustible",
    "proveedor": {
      "nombre": "Gasolinera Pemex"
    }
  },
  "advance": {
    "employee_id": 42,
    "employee_name": "Juan Pérez",
    "payment_method": "tarjeta_personal",
    "notes": "Pago con tarjeta Banamex personal",
    "reimbursement_type": "transfer" // o "payroll"
  }
}
```

**Respuesta:**
```json
{
  "success": true,
  "expense": {
    "id": 10248,
    "descripcion": "Gasolina Pemex",
    "monto_total": 850.50,
    "is_employee_advance": true,
    "reimbursement_status": "pending",
    "bank_status": "non_reconcilable" // ← No se puede conciliar en banco empresa
  },
  "advance": {
    "id": 1,
    "expense_id": 10248,
    "employee_id": 42,
    "advance_amount": 850.50,
    "pending_amount": 850.50,
    "status": "pending"
  }
}
```

##### B. Registrar reembolso

**POST** `/employee-advances/{advance_id}/reimburse`
```json
{
  "reimbursement_amount": 850.50,
  "reimbursement_type": "transfer",
  "reimbursement_movement_id": 10350, // ID del movimiento bancario de transferencia
  "notes": "Reembolso vía SPEI"
}
```

**Respuesta:**
```json
{
  "success": true,
  "advance": {
    "id": 1,
    "expense_id": 10248,
    "advance_amount": 850.50,
    "reimbursed_amount": 850.50,
    "pending_amount": 0,
    "status": "completed",
    "reimbursement_date": "2025-01-16T10:00:00Z"
  },
  "expense": {
    "id": 10248,
    "reimbursement_status": "completed",
    "bank_status": "non_reconcilable"
  }
}
```

##### C. Listar anticipos pendientes

**GET** `/employee-advances?status=pending`
```json
{
  "advances": [
    {
      "id": 1,
      "employee_name": "Juan Pérez",
      "expense": {
        "id": 10248,
        "descripcion": "Gasolina Pemex",
        "monto_total": 850.50,
        "fecha_gasto": "2025-01-15"
      },
      "advance_amount": 850.50,
      "pending_amount": 850.50,
      "days_pending": 5,
      "reimbursement_type": "transfer",
      "status": "pending"
    }
  ],
  "total_pending": 850.50,
  "count": 1
}
```

##### D. Reporte de anticipos por empleado

**GET** `/employee-advances/report?employee_id=42&month=2025-01`
```json
{
  "employee": {
    "id": 42,
    "name": "Juan Pérez"
  },
  "period": "2025-01",
  "summary": {
    "total_advances": 3,
    "total_amount": 2500.50,
    "reimbursed_amount": 1650.00,
    "pending_amount": 850.50
  },
  "advances": [
    {
      "date": "2025-01-15",
      "description": "Gasolina Pemex",
      "amount": 850.50,
      "status": "pending"
    },
    {
      "date": "2025-01-10",
      "description": "Comida de trabajo",
      "amount": 1250.00,
      "status": "completed",
      "reimbursed_date": "2025-01-12"
    },
    {
      "date": "2025-01-05",
      "description": "Taxi",
      "amount": 400.00,
      "status": "completed",
      "reimbursed_date": "2025-01-08"
    }
  ]
}
```

#### 3. UI/UX

##### Flujo de registro:

```
┌─────────────────────────────────────┐
│  Registrar Gasto                    │
├─────────────────────────────────────┤
│ Descripción: [Gasolina Pemex    ]  │
│ Monto:       [$850.50           ]  │
│ Fecha:       [15-ene-2025       ]  │
│                                     │
│ ¿Quién pagó?                        │
│ ○ Cuenta empresa                    │
│ ● Empleado (tarjeta/efectivo)      │
│                                     │
│ ┌─ Datos del Anticipo ────────────┐│
│ │ Empleado: [Juan Pérez        ▼]││
│ │ Método:   [Tarjeta personal  ▼]││
│ │                                 ││
│ │ Reembolso:                      ││
│ │ ○ Transferencia bancaria        ││
│ │ ○ Descuento de nómina          ││
│ │ ○ Efectivo                      ││
│ │                                 ││
│ │ Notas: [Pago urgente, solicito ││
│ │         reembolso esta semana] ││
│ └─────────────────────────────────┘│
│                                     │
│  [Cancelar]  [Guardar Gasto]       │
└─────────────────────────────────────┘
```

##### Dashboard de anticipos:

```
┌────────────────────────────────────────────────────┐
│ 💰 Anticipos a Empleados                           │
├────────────────────────────────────────────────────┤
│                                                    │
│ Resumen del mes:                                   │
│ ┌─────────┬─────────┬─────────┬─────────┐        │
│ │ Total   │Reembolso│Pendiente│Empleados│        │
│ │ $2,500  │ $1,650  │  $850   │    3    │        │
│ └─────────┴─────────┴─────────┴─────────┘        │
│                                                    │
│ ⚠️  Anticipos Pendientes (1)                       │
│ ┌────────────────────────────────────────────┐   │
│ │ Juan Pérez              5 días    $850.50  │   │
│ │ Gasolina Pemex                             │   │
│ │ 15-ene-2025                                │   │
│ │                                            │   │
│ │ Reembolso: Transferencia                   │   │
│ │ [Marcar como Reembolsado] [Ver Detalles]  │   │
│ └────────────────────────────────────────────┘   │
│                                                    │
│ ✅ Completados Recientemente (2)                   │
│ ┌────────────────────────────────────────────┐   │
│ │ Juan Pérez         12-ene  $1,250.00 ✓     │   │
│ │ María López        08-ene    $400.00 ✓     │   │
│ └────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────┘
```

#### 4. Reglas de Negocio

1. **No conciliación bancaria automática:**
   - Gastos con `is_employee_advance = true` tienen `bank_status = 'non_reconcilable'`
   - No aparecen en sugerencias de matching
   - Solo se concilian cuando hay un movimiento de reembolso

2. **Tracking de reembolsos:**
   - Cada anticipo tiene un `status` (pending/partial/completed)
   - Se puede hacer reembolso parcial
   - El sistema calcula `pending_amount` automáticamente

3. **Alertas de anticipos pendientes:**
   - Si un anticipo tiene > 7 días pendiente → Alerta amarilla
   - Si un anticipo tiene > 15 días pendiente → Alerta roja
   - Notificación automática al admin

4. **Integración con nómina:**
   - Si `reimbursement_type = 'payroll'`, se marca para descuento
   - Se genera reporte mensual para RH
   - Una vez procesado en nómina, se marca como `completed`

#### 5. Estados del Anticipo

```
┌─────────────┐
│   PENDING   │ → Anticipo registrado, esperando reembolso
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   PARTIAL   │ → Reembolso parcial realizado
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  COMPLETED  │ → Reembolso completo ✅
└─────────────┘

       ⊗
┌─────────────┐
│  CANCELLED  │ → Anticipo cancelado (error)
└─────────────┘
```

---

## 🎯 Casos de Uso Combinados

### Caso 1: Comida de equipo pagada por empleado
```
1. Juan paga comida $1,500 con su tarjeta personal
2. Sistema registra:
   - Gasto: Comida de trabajo - $1,500
   - Anticipo: Juan Pérez - $1,500 (pending)
   - bank_status: non_reconcilable
3. Empresa reembolsa por transferencia
4. Sistema detecta transferencia $1,500 a Juan
5. Admin confirma: "Este pago es reembolso de anticipo"
6. Sistema marca:
   - Anticipo: completed
   - Transferencia: linked to advance (no como gasto)
```

### Caso 2: Múltiples gastos de un viaje pagados personalmente
```
1. María paga en viaje de trabajo:
   - Gasolina: $850
   - Hotel: $2,500
   - Comidas: $1,200
   Total: $4,550
2. Sistema registra 3 gastos + 3 anticipos
3. Empresa hace UN pago de $4,550 a María
4. Admin usa "Conciliación múltiple":
   - 1 movimiento bancario → 3 anticipos
   - Split automático por monto de cada anticipo
5. Todos los anticipos se marcan como completed
```

---

## 📊 Reportes Necesarios

### 1. Reporte de Anticipos por Empleado
```sql
SELECT
    employee_name,
    COUNT(*) as total_advances,
    SUM(advance_amount) as total_advanced,
    SUM(reimbursed_amount) as total_reimbursed,
    SUM(pending_amount) as total_pending,
    AVG(JULIANDAY('now') - JULIANDAY(advance_date)) as avg_days_to_reimburse
FROM employee_advances
WHERE status IN ('pending', 'partial')
GROUP BY employee_id, employee_name
ORDER BY total_pending DESC;
```

### 2. Reporte de Conciliaciones Split
```sql
SELECT
    split_group_id,
    split_type,
    COUNT(DISTINCT expense_id) as expenses_count,
    COUNT(DISTINCT movement_id) as movements_count,
    SUM(allocated_amount) as total_amount,
    created_at
FROM bank_reconciliation_splits
WHERE is_complete = 1
GROUP BY split_group_id
ORDER BY created_at DESC;
```

### 3. Dashboard de Pendientes
```sql
-- Anticipos pendientes por empleado
SELECT employee_name, SUM(pending_amount) as pending
FROM employee_advances
WHERE status = 'pending'
GROUP BY employee_id, employee_name;

-- Movimientos bancarios sin asignar completamente
SELECT description, amount, amount_unallocated
FROM bank_movements
WHERE reconciliation_type = 'split'
  AND amount_unallocated > 0;
```

---

## 🚀 Plan de Implementación

### Fase 1: Conciliación Múltiple (Sprint 1-2)
- [ ] Crear tabla `bank_reconciliation_splits`
- [ ] Implementar endpoints de split
- [ ] UI para conciliación múltiple
- [ ] Validaciones y tests
- [ ] Documentación

### Fase 2: Anticipos a Empleados (Sprint 3-4)
- [ ] Crear tabla `employee_advances`
- [ ] Implementar endpoints de anticipos
- [ ] UI para registro y reembolso
- [ ] Dashboard de anticipos
- [ ] Reportes y alertas
- [ ] Integración con nómina (opcional)

### Fase 3: Casos Avanzados (Sprint 5)
- [ ] Reembolsos parciales
- [ ] Conciliación de reembolsos con múltiples anticipos
- [ ] Workflow de aprobación de anticipos
- [ ] Límites de anticipo por empleado
- [ ] Historial y auditoría completa

---

## ✅ Checklist de Features

### Conciliación Múltiple
- [ ] Split 1:N (un movimiento, varios gastos)
- [ ] Split N:1 (varios movimientos, un gasto)
- [ ] Validación de montos
- [ ] UI drag-and-drop para asignación
- [ ] Historial de splits
- [ ] Deshacer split (unlink)
- [ ] Reportes de splits

### Anticipos a Empleados
- [ ] Registro de anticipo con gasto
- [ ] Dashboard de anticipos pendientes
- [ ] Proceso de reembolso
- [ ] Alertas de anticipos vencidos
- [ ] Reporte por empleado
- [ ] Reporte por período
- [ ] Integración con nómina (export)
- [ ] Límites y políticas

---

## 📌 Notas Importantes

1. **Separación clara:**
   - Gastos empresa → Conciliables con banco
   - Gastos personales → NO conciliables, generan anticipos

2. **Validación de montos:**
   - En splits, suma DEBE ser exacta
   - Tolerancia: 0.01 centavos

3. **Auditoría:**
   - Todo cambio registra quién, cuándo, por qué
   - Splits no se pueden editar, solo deshacer y recrear

4. **Performance:**
   - Índices en split_group_id
   - Paginación en listados
   - Caché de reportes frecuentes


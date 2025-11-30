# 💳 Sistema de Cuentas de Pago - Explicación Completa

**Fecha**: 2025-11-26

---

## 🔍 TUS PREGUNTAS

### 1. ¿Por qué no funciona el dropdown de cuenta de pago?

### 2. ¿Está conectado con el flujo que los usuarios tienen para subir cuentas de banco?

---

## ✅ RESPUESTA 1: Problema del Dropdown - SOLUCIONADO

### 🔴 Problema Identificado:

Había un **conflicto de rutas** en `main.py`:

```python
# ANTES (CONFLICTO):

# Línea 293 - SE REGISTRA PRIMERO
@app.get("/payment-accounts")  # ❌ Retorna HTML
async def payment_accounts():
    return FileResponse("static/payment-accounts.html")

# Líneas 490-492 - SE REGISTRA DESPUÉS
from api.payment_accounts_api import router as payment_accounts_router
app.include_router(payment_accounts_router)  # prefix="/payment-accounts"
# ✅ Retorna JSON con cuentas del usuario
```

**FastAPI matchea el primer endpoint** que coincida → siempre retornaba HTML en lugar de JSON!

### ✅ Solución Aplicada:

```python
# DESPUÉS (ARREGLADO):

# Cambié la ruta del HTML estático
@app.get("/payment-accounts-ui")  # ✅ Ya no conflictúa
async def payment_accounts_ui():
    return FileResponse("static/payment-accounts.html")

# Ahora el router de API puede manejar /payment-accounts/
from api.payment_accounts_api import router as payment_accounts_router
app.include_router(payment_accounts_router)
# ✅ GET /payment-accounts/ → Retorna JSON correctamente
```

### 📍 Endpoints Ahora Disponibles:

| Endpoint | Método | Retorna | Uso |
|----------|--------|---------|-----|
| `/payment-accounts/` | GET | JSON | API - Lista de cuentas del usuario |
| `/payment-accounts/{id}` | GET | JSON | API - Detalles de una cuenta |
| `/payment-accounts/` | POST | JSON | API - Crear nueva cuenta |
| `/payment-accounts/{id}` | PUT | JSON | API - Actualizar cuenta |
| `/payment-accounts/{id}` | DELETE | JSON | API - Desactivar cuenta |
| `/payment-accounts-ui` | GET | HTML | UI - Página de gestión |

---

## ✅ RESPUESTA 2: ¿Está Conectado con el Flujo de Usuarios?

### 🎯 **SÍ, está 100% integrado**

El sistema de `payment_accounts` está **completamente conectado** con el flujo de gestión de cuentas bancarias de los usuarios.

### 🏗️ Arquitectura del Sistema:

```
┌─────────────────────────────────────────────────────────────┐
│              FLUJO DE CUENTAS DE PAGO                       │
└─────────────────────────────────────────────────────────────┘

1. USUARIO CREA CUENTAS
   ↓
   POST /payment-accounts/
   {
     "nombre": "Santander Débito",
     "tipo": "bancaria",
     "subtipo": "debito",
     "banco_nombre": "Santander",
     "saldo_inicial": 50000,
     "moneda": "MXN"
   }
   ↓

2. CUENTA SE GUARDA EN BD
   ↓
   Tabla: user_payment_accounts
   - id
   - user_id  ← Del usuario autenticado
   - tenant_id ← Multi-tenancy
   - tipo: bancaria, efectivo, terminal, tarjeta_credito
   - subtipo: debito, credito
   - banco_nombre
   - saldo_actual (calculado)
   - activo: true/false
   ↓

3. USUARIO CREA GASTO
   ↓
   POST /expenses
   {
     "descripcion": "Comida cliente",
     "monto_total": 450.50,
     "forma_pago": "04",  ← SAT code
     "payment_account_id": 123,  ← ID de la cuenta
     ...
   }
   ↓

4. BACKEND VALIDA
   ↓
   - ✅ Cuenta existe?
   - ✅ Pertenece al usuario?
   - ✅ Está activa?
   - ✅ Tiene saldo? (para débito/efectivo)
   - ✅ Tiene crédito disponible? (para tarjetas crédito)
   ↓

5. GASTO SE VINCULA A CUENTA
   ↓
   expense_records.payment_account_id = 123
   ↓

6. SALDO SE ACTUALIZA AUTOMÁTICAMENTE
   ↓
   cuenta.saldo_actual -= 450.50
```

---

## 🔗 Conexión con Módulos del Sistema

### 1. **Conciliación Bancaria**

```python
# core/reconciliation/bank/bank_file_parser.py

# Cuando se sube un estado de cuenta (PDF/Excel):
user_payment_accounts  ←→  bank_statements  ←→  bank_movements
        ↑                        ↑                    ↑
        │                        │                    │
    Cuenta del             Archivo subido      Movimientos
    usuario                   por user          detectados
```

**Flujo**:
1. Usuario sube PDF de banco
2. Parser detecta movimientos
3. Sistema busca cuenta de pago asociada
4. Concilia movimientos con gastos registrados

### 2. **Clasificación Contable**

```python
# main.py:3840 - Cuando se crea gasto

payment_account = get_payment_account(payment_account_id)
→ account_code = map_payment_method_to_account(
    forma_pago,
    payment_account.tipo,
    payment_account.subtipo
)

# Ejemplos:
# Tarjeta crédito → Cuenta 11001 (Bancos - Tarjeta)
# Efectivo → Cuenta 10001 (Caja)
# Transferencia → Cuenta 11002 (Bancos - Cuenta corriente)
```

### 3. **Multi-Tenancy**

```python
# api/payment_accounts_api.py:54

accounts = payment_account_service.get_user_accounts(
    current_user.id,        # ← Usuario autenticado
    current_user.tenant_id, # ← Empresa/Tenant
    active_only=True
)

# ✅ Solo ve sus cuentas
# ✅ Solo de su empresa
# ✅ No puede ver cuentas de otros usuarios/empresas
```

---

## 📊 Tipos de Cuentas Soportados

### 1. **Cuentas Bancarias** (`tipo: "bancaria"`)

#### a) Débito (`subtipo: "debito"`)
```json
{
  "nombre": "Santander Débito Empresarial",
  "tipo": "bancaria",
  "subtipo": "debito",
  "banco_nombre": "Santander",
  "numero_cuenta_enmascarado": "****1234",
  "saldo_inicial": 100000,
  "moneda": "MXN"
}
```

**Características**:
- Saldo disminuye con gastos
- No tiene límite de crédito
- Alertas cuando saldo < $1,000

#### b) Crédito (`subtipo: "credito"`)
```json
{
  "nombre": "Amex Platinum",
  "tipo": "bancaria",
  "subtipo": "credito",
  "banco_nombre": "American Express",
  "numero_tarjeta": "1234",  // últimos 4 dígitos
  "limite_credito": 50000,
  "fecha_corte": 15,  // día del mes
  "fecha_pago": 25,   // día del mes
  "saldo_inicial": 0,
  "moneda": "MXN"
}
```

**Características**:
- Saldo aumenta con gastos (es deuda)
- Tiene límite de crédito
- Calcula crédito disponible automáticamente
- Alertas cuando crédito disponible < 20%

### 2. **Efectivo** (`tipo: "efectivo"`)

```json
{
  "nombre": "Caja Chica Oficina",
  "tipo": "efectivo",
  "saldo_inicial": 5000,
  "moneda": "MXN"
}
```

**Características**:
- No requiere banco
- Ideal para gastos menores
- Alertas cuando saldo < $500

### 3. **Terminales de Pago** (`tipo: "terminal"`)

```json
{
  "nombre": "Clip Ventas Mostrador",
  "tipo": "terminal",
  "proveedor_terminal": "Clip",
  "numero_cuenta_enmascarado": "****5678",
  "saldo_inicial": 0,
  "moneda": "MXN"
}
```

**Características**:
- Para registrar cobros recibidos
- Proveedores: Clip, MercadoPago, Square, Zettle
- Saldo refleja cobros pendientes de depositar

---

## 💻 Cómo los Usuarios Gestionan sus Cuentas

### Opción 1: API REST (Programático)

```bash
# 1. Obtener lista de cuentas
GET /payment-accounts/
Headers: Authorization: Bearer {token}

# Response:
[
  {
    "id": 123,
    "nombre": "Santander Débito",
    "tipo": "bancaria",
    "subtipo": "debito",
    "banco_nombre": "Santander",
    "saldo_actual": 45500.00,
    "moneda": "MXN",
    "activo": true
  },
  {
    "id": 124,
    "nombre": "Amex Platinum",
    "tipo": "bancaria",
    "subtipo": "credito",
    "limite_credito": 50000,
    "saldo_actual": 12000,
    "credito_disponible": 38000,
    "activo": true
  }
]

# 2. Crear nueva cuenta
POST /payment-accounts/
{
  "nombre": "BBVA Nomina",
  "tipo": "bancaria",
  "subtipo": "debito",
  "banco_nombre": "BBVA",
  "saldo_inicial": 75000,
  "moneda": "MXN"
}

# 3. Actualizar cuenta
PUT /payment-accounts/123
{
  "nombre": "Santander Débito Empresarial" ,
  "saldo_inicial": 50000
}

# 4. Desactivar cuenta
DELETE /payment-accounts/123
# (Soft delete - mantiene histórico)
```

### Opción 2: UI Web (Manual)

```
http://localhost:8000/payment-accounts-ui  ← HTML estático
```

**Funcionalidades UI**:
- ✅ Lista todas las cuentas del usuario
- ✅ Filtrar por tipo (banco, efectivo, terminal)
- ✅ Ver detalles completos
- ✅ Crear nueva cuenta (formulario)
- ✅ Editar cuenta existente
- ✅ Activar/Desactivar cuentas
- ✅ Ver resumen: saldo total, crédito disponible
- ✅ Alertas: saldos bajos, límites excedidos

---

## 🔐 Seguridad y Validaciones

### 1. **Autenticación Requerida**

```python
@router.get("/", response_model=List[UserPaymentAccount])
async def get_user_payment_accounts(
    current_user: User = Depends(get_current_active_user),  # ← Requiere auth
    ...
):
```

**Sin token válido** → HTTP 401 Unauthorized

### 2. **Aislamiento Multi-Tenant**

```python
accounts = payment_account_service.get_user_accounts(
    current_user.id,        # Solo cuentas del usuario
    current_user.tenant_id, # Solo de su empresa
    active_only=True
)
```

**No puede ver/modificar** cuentas de otros usuarios/empresas

### 3. **Validaciones de Negocio**

```python
# Al crear tarjeta de crédito
if request.tipo == TipoCuenta.BANCARIA and request.subtipo == SubtipoCuenta.CREDITO:
    if not all([
        request.limite_credito,
        request.fecha_corte,
        request.fecha_pago,
        request.numero_tarjeta
    ]):
        raise HTTPException(400, "Faltan campos requeridos")

# Al crear gasto
if payment_account.tipo == TipoCuenta.BANCARIA:
    if payment_account.subtipo == SubtipoCuenta.CREDITO:
        if expense.monto_total > payment_account.credito_disponible:
            raise HTTPException(400, "Crédito insuficiente")
    else:  # débito
        if expense.monto_total > payment_account.saldo_actual:
            raise HTTPException(400, "Saldo insuficiente")
```

---

## 🚀 Resumen: ¿Cómo se Conecta Todo?

```
USUARIO
  ↓
1. Crea cuentas bancarias vía /payment-accounts/ (POST)
  ↓
2. Cuentas se guardan en BD con user_id + tenant_id
  ↓
3. Al crear gasto manual → selecciona cuenta del dropdown
  ↓
4. Frontend llama GET /payment-accounts/ → obtiene lista
  ↓
5. Usuario selecciona cuenta → payment_account_id: 123
  ↓
6. Envía POST /expenses con payment_account_id
  ↓
7. Backend valida que cuenta existe y pertenece al usuario
  ↓
8. Gasto se vincula a cuenta
  ↓
9. Saldo se actualiza automáticamente
  ↓
10. Conciliación bancaria usa estas cuentas para matching
```

---

## ✅ CONCLUSIÓN

### 1. **Dropdown arreglado** ✅
- Conflicto de rutas solucionado
- API ahora retorna JSON correctamente

### 2. **Sí está conectado** ✅
- Payment accounts es el **corazón** del sistema
- Se usa en:
  - ✅ Creación de gastos
  - ✅ Conciliación bancaria
  - ✅ Clasificación contable
  - ✅ Multi-tenancy
  - ✅ Reportes financieros

### 3. **Flujo completo funcional** ✅
- Usuario crea cuentas
- Usuario crea gastos
- Sistema vincula automáticamente
- Saldos se actualizan
- Conciliación funciona

---

**Creado**: 2025-11-26
**Por**: Claude Code

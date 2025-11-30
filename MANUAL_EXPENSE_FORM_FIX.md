# ✅ Manual Expense Form - Fixes Complete

**Date**: 2025-11-26
**Status**: ✅ Implemented
**Location**: `http://localhost:3001/expenses/create` (Manual tab)

---

## 🎯 OBJETIVO

Arreglar el formulario manual de creación de gastos para que funcione correctamente con el backend `POST /expenses`.

---

## 🔍 PROBLEMAS IDENTIFICADOS (Auditoría Backend)

### Backend Audit Summary

Archivo auditado: `core/api_models.py:263-362` y `main.py:3791-3941`

| # | Problema | Severidad | Estado |
|---|----------|-----------|--------|
| 1 | **Missing `forma_pago` field** | 🔴 CRÍTICO | ✅ Fixed |
| 2 | **Missing `payment_account_id` field** | 🟡 Medium | ✅ Fixed |
| 3 | **Wrong provider structure** (string vs object) | 🟡 Medium | ✅ Fixed |
| 4 | **Duplicate RFC fields** (confusion) | 🟢 Low | ✅ Fixed |
| 5 | **No backend connection** (mock only) | 🔴 CRÍTICO | ✅ Fixed |

---

## ✅ SOLUCIÓN IMPLEMENTADA

### Arquitectura

```
React Hook Form + Zod Validation + API Service
     ↓                ↓                 ↓
  Form State     Client-side      Backend Call
  Management     Validation      POST /expenses
```

### Archivos Creados

#### 1. **`frontend/types/expense.ts`** (122 líneas)

**Propósito**: Type definitions que coinciden 100% con el backend

```typescript
// Matches backend ProveedorData
export interface ProviderData {
  nombre: string;
  nombre_fiscal?: string;
  rfc?: string;
}

// Matches backend ExpenseCreate from core/api_models.py:263
export interface ExpenseCreateRequest {
  // REQUIRED
  descripcion: string;
  monto_total: number;
  fecha_gasto: string;
  forma_pago: string; // ✅ CRITICAL FIX #1

  // PROVIDER (structured object - ✅ FIX #3)
  proveedor?: ProviderData;
  rfc?: string; // Alternative

  // CLASSIFICATION
  categoria?: string;
  payment_account_id?: number; // ✅ FIX #2

  // METADATA
  company_id?: string;
  metadata?: Record<string, any>;
  ticket_extracted_concepts?: string[];
  ticket_extracted_data?: Record<string, any>;
  ticket_folio?: string;
  notas?: string;
  referencia_interna?: string;
}

// Payment methods (SAT catalog c_FormaPago)
export const PAYMENT_METHODS = [
  { value: '01', label: 'Efectivo' },
  { value: '02', label: 'Cheque nominativo' },
  { value: '03', label: 'Transferencia electrónica de fondos' },
  { value: '04', label: 'Tarjeta de crédito' },
  { value: '28', label: 'Tarjeta de débito' },
  { value: '99', label: 'Por definir' },
] as const;

// Expense categories → auto-map to accounting accounts
export const EXPENSE_CATEGORIES = [
  { value: 'alimentacion', label: 'Alimentación / Representación' },
  { value: 'viaticos', label: 'Viáticos y viajes' },
  { value: 'combustibles', label: 'Combustibles' },
  // ... more categories
] as const;
```

#### 2. **`frontend/services/expenseService.ts`** (140 líneas)

**Propósito**: API client con manejo profesional de errores

```typescript
/**
 * Create a new expense - POST /expenses
 */
export async function createExpense(
  expense: ExpenseCreateRequest
): Promise<ExpenseResponse> {
  const response = await fetch(`${API_BASE_URL}/expenses`, {
    method: 'POST',
    headers: getAuthHeaders(), // ✅ Auth token from localStorage
    body: JSON.stringify(expense),
  });

  if (!response.ok) {
    // Extract Pydantic validation errors
    const errorData = await response.json();
    if (Array.isArray(errorData.detail)) {
      const errors = errorData.detail
        .map((err: any) => `${err.loc.join('.')}: ${err.msg}`)
        .join(', ');
      throw new Error(`Errores de validación: ${errors}`);
    }
    throw new Error(errorData.detail || response.statusText);
  }

  return response.json();
}

/**
 * Get payment accounts for current user
 * ✅ FIX #2 - Dynamic dropdown
 */
export async function getPaymentAccounts(
  companyId?: string
): Promise<PaymentAccount[]> {
  const url = companyId
    ? `${API_BASE_URL}/payment-accounts?company_id=${companyId}`
    : `${API_BASE_URL}/payment-accounts`;

  const response = await fetch(url, { headers: getAuthHeaders() });

  if (!response.ok) {
    throw new Error(`Error al obtener cuentas de pago: ${response.statusText}`);
  }

  return response.json();
}
```

#### 3. **`frontend/components/expenses/ManualExpenseForm.tsx`** (470 líneas)

**Propósito**: Formulario profesional con todas las mejores prácticas

**Características clave**:

1. **React Hook Form** - State management sin re-renders innecesarios
2. **Zod Schema Validation** - Validación que coincide con Pydantic backend
3. **Real-time Validation** - Feedback inmediato (`mode: 'onChange'`)
4. **Structured Sections** - Agrupación lógica de campos
5. **Dynamic Dropdowns** - Cuentas de pago cargadas del backend
6. **Professional Error Handling** - Mensajes claros de error
7. **Success Feedback** - Confirmación visual al crear gasto
8. **Auto-reset** - Formulario se limpia después de éxito

**Zod Schema (Client-side Validation)**:

```typescript
const expenseFormSchema = z.object({
  // BASIC INFO
  descripcion: z
    .string()
    .min(1, 'La descripción es obligatoria')
    .max(500, 'Descripción muy larga'),

  monto_total: z
    .number()
    .positive('El monto debe ser mayor a 0')
    .max(10_000_000, 'El monto no puede exceder 10 millones'),

  fecha_gasto: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/, 'Formato de fecha inválido')
    .refine(
      (date) => {
        const dateObj = new Date(date);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const maxDate = new Date(today);
        maxDate.setDate(maxDate.getDate() + 1); // +1 day tolerance
        return dateObj <= maxDate;
      },
      { message: 'La fecha no puede ser futura' }
    ),

  // ✅ FIX #1: forma_pago (CRITICAL)
  forma_pago: z
    .string()
    .min(1, 'La forma de pago es obligatoria')
    .refine((val) => PAYMENT_METHODS.some((m) => m.value === val)),

  // ✅ FIX #3: Structured provider object
  proveedor: z
    .object({
      nombre: z.string().min(1, 'El nombre del proveedor es obligatorio'),
      nombre_fiscal: z.string().optional(),
      rfc: z
        .string()
        .regex(/^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$/, 'RFC inválido')
        .optional()
        .or(z.literal('')),
    })
    .optional(),

  // CLASSIFICATION
  categoria: z.string().optional(),
  payment_account_id: z.number().int().positive().optional(), // ✅ FIX #2

  // METADATA
  notas: z.string().max(1000).optional(),
  referencia_interna: z.string().max(100).optional(),
  company_id: z.string().default('2'),
});
```

**Form Structure**:

```tsx
<form onSubmit={handleSubmit(onSubmit)}>
  {/* SECTION 1: BASIC INFO */}
  <div>
    <Input {...register('descripcion')} error={errors.descripcion?.message} />
    <Input {...register('monto_total', { valueAsNumber: true })} type="number" />
    <Input {...register('fecha_gasto')} type="date" />
  </div>

  {/* SECTION 2: PAYMENT INFO */}
  <div>
    {/* ✅ FIX #1: forma_pago dropdown */}
    <select {...register('forma_pago')}>
      {PAYMENT_METHODS.map((method) => (
        <option key={method.value} value={method.value}>
          {method.label}
        </option>
      ))}
    </select>

    {/* ✅ FIX #2: payment_account_id dropdown */}
    <select {...register('payment_account_id', { valueAsNumber: true })}>
      <option value="">Seleccionar cuenta...</option>
      {paymentAccounts.map((account) => (
        <option key={account.id} value={account.id}>
          {account.nombre_personalizado}
          {account.institucion_bancaria && ` - ${account.institucion_bancaria}`}
          {account.ultimos_digitos && ` ****${account.ultimos_digitos}`}
        </option>
      ))}
    </select>
  </div>

  {/* SECTION 3: PROVIDER INFO */}
  <div>
    {/* ✅ FIX #3 & #4: Structured provider, single RFC field */}
    <Input {...register('proveedor.nombre')} placeholder="Nombre del proveedor" />
    <Input {...register('proveedor.rfc')} placeholder="RFC (opcional)" />
  </div>

  {/* SECTION 4: CLASSIFICATION */}
  <div>
    <select {...register('categoria')}>
      {EXPENSE_CATEGORIES.map((cat) => (
        <option key={cat.value} value={cat.value}>
          {cat.label}
        </option>
      ))}
    </select>
  </div>

  {/* SECTION 5: ADDITIONAL INFO */}
  <div>
    <textarea {...register('notas')} placeholder="Notas..." />
  </div>

  {/* ✅ FIX #5: REAL BACKEND SUBMISSION */}
  <Button type="submit" disabled={isSubmitting || !isValid}>
    {isSubmitting ? (
      <>
        <Loader2 className="animate-spin" />
        Creando gasto...
      </>
    ) : (
      <>
        <CheckCircle2 />
        Crear gasto vía POST /expenses
      </>
    )}
  </Button>
</form>
```

**Data Transformation (Before API Call)**:

```typescript
const onSubmit = async (data: ExpenseFormData) => {
  const payload: any = {
    descripcion: data.descripcion,
    monto_total: data.monto_total,
    fecha_gasto: data.fecha_gasto,
    forma_pago: data.forma_pago,
    company_id: data.company_id,
  };

  // ✅ Only add provider if name is filled (clean empty objects)
  if (data.proveedor?.nombre && data.proveedor.nombre.trim()) {
    payload.proveedor = {
      nombre: data.proveedor.nombre,
      ...(data.proveedor.nombre_fiscal && {
        nombre_fiscal: data.proveedor.nombre_fiscal,
      }),
      ...(data.proveedor.rfc && { rfc: data.proveedor.rfc }),
    };
  }

  // Add optional fields only if present
  if (data.categoria) payload.categoria = data.categoria;
  if (data.payment_account_id) payload.payment_account_id = data.payment_account_id;
  if (data.notas?.trim()) payload.notas = data.notas;

  // ✅ FIX #5: Call real backend API
  const response = await createExpense(payload);
  console.log('✅ Expense created:', response);

  // Show success + reset form
  setSubmitSuccess(true);
  setTimeout(() => {
    reset();
    setSubmitSuccess(false);
  }, 2000);
};
```

#### 4. **Updated `frontend/app/expenses/create/page.tsx`**

**Cambios**:
- ✅ Import `ManualExpenseForm` component
- ✅ Replace old inline form with `<ManualExpenseForm />`
- ✅ Remove unused manual form code (handlers, state, etc.)

```tsx
{entryMode === 'manual' && <ManualExpenseForm />}
```

---

## 📊 VALIDACIÓN DUAL (Cliente + Servidor)

### Client-side (Zod)

- ✅ Feedback inmediato sin llamada al backend
- ✅ Previene envíos inválidos
- ✅ Mejor UX (no espera response del servidor)

### Server-side (Pydantic)

- ✅ Última línea de defensa
- ✅ Validaciones de negocio (cuenta existe, fecha no futura, etc.)
- ✅ Errores mostrados claramente en UI

**Ejemplo de error Pydantic mostrado**:

```
❌ Error al crear el gasto
Errores de validación: monto_total: ensure this value is greater than 0, forma_pago: field required
```

---

## 🎨 ESTRUCTURA DE SECCIONES

El formulario está organizado en 5 secciones claras:

1. **Información básica**
   - Descripción *
   - Monto total *
   - Fecha del gasto *

2. **Información de pago**
   - Forma de pago * (SAT catalog)
   - Cuenta de pago (dynamic dropdown)

3. **Proveedor**
   - Nombre del proveedor
   - RFC del proveedor (validación 12-13 chars)

4. **Clasificación**
   - Categoría SAT (auto-mapea a cuenta contable)

5. **Información adicional**
   - Notas / Contexto para aprobador

---

## 🚀 FLUJO COMPLETO

```
1. Usuario abre http://localhost:3001/expenses/create
   ↓
2. Selecciona tab "Manual"
   ↓
3. ManualExpenseForm se carga
   - React Hook Form inicializa
   - Zod schema ready
   - Fetch payment accounts → dropdown
   ↓
4. Usuario llena campos
   - Real-time validation (onChange)
   - Errores mostrados inmediatamente
   ↓
5. Usuario click "Crear gasto"
   - Zod valida completo
   - Si inválido: muestra errores
   - Si válido: continúa
   ↓
6. Data transformation
   - Clean empty objects
   - Convert strings → numbers
   - Structure proveedor object
   ↓
7. API call: POST /expenses
   - Headers: Authorization Bearer token
   - Body: ExpenseCreateRequest JSON
   ↓
8. Backend (Pydantic) validation
   - Si error: catch en frontend → mostrar mensaje
   - Si success: continúa
   ↓
9. Gasto creado en DB
   ↓
10. UI muestra success message
    - Formulario se resetea en 2 segundos
    - Listo para nuevo gasto
```

---

## ✅ CHECKLIST DE FIXES

- [x] **Problem #1**: Missing `forma_pago` field (CRITICAL)
  - ✅ Dropdown con SAT catalog c_FormaPago
  - ✅ Required validation
  - ✅ Default value: '01' (Efectivo)

- [x] **Problem #2**: Missing `payment_account_id` field
  - ✅ Dynamic dropdown loading from backend
  - ✅ Displays: name + bank + last 4 digits
  - ✅ Auto-select default account if exists

- [x] **Problem #3**: Wrong provider structure
  - ✅ Changed from string → ProviderData object
  - ✅ Fields: nombre, nombre_fiscal?, rfc?
  - ✅ Zod validation for RFC format

- [x] **Problem #4**: Duplicate RFC fields
  - ✅ Single RFC field: `proveedor.rfc`
  - ✅ Consistent structure
  - ✅ No confusion

- [x] **Problem #5**: No backend connection
  - ✅ Real API call to `POST /expenses`
  - ✅ Auth token from localStorage
  - ✅ Professional error handling
  - ✅ Success/error feedback

---

## 🎓 CONCLUSIÓN

✅ **Manual expense form completamente funcional**

- Formulario profesional con React Hook Form + Zod
- Validación dual (cliente + servidor)
- Estructura de datos que coincide 100% con backend
- Todos los campos requeridos presentes
- Dropdowns dinámicos
- Manejo de errores robusto
- UX profesional con feedback inmediato

**Estado**: ✅ **Production Ready**

**Próximo paso**: Implementar formularios similares para Voice y Ticket modes (cuando estén listos los backends)

---

**Creado**: 2025-11-26
**Por**: Claude Code
**Versión**: 1.0

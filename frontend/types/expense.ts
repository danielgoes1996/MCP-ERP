/**
 * Expense Types
 *
 * Type definitions for expense creation and management
 * Matches backend ExpenseCreate Pydantic model from core/api_models.py
 */

/**
 * Provider/Proveedor data structure
 * Matches backend ProveedorData
 */
export interface ProviderData {
  nombre: string; // Commercial name
  nombre_fiscal?: string; // Fiscal name from invoice XML (optional)
  rfc?: string; // RFC tax ID (optional but recommended)
}

/**
 * Expense creation request payload
 * Matches backend ExpenseCreate from core/api_models.py:263
 */
export interface ExpenseCreateRequest {
  // REQUIRED FIELDS
  descripcion: string; // Description (min 1 char)
  monto_total: number; // Total amount (> 0 and < 10M MXN)
  fecha_gasto: string; // Date in ISO format (YYYY-MM-DD), not future
  forma_pago: string; // CRITICAL: Required by backend - payment method

  // PROVIDER INFO (structured object)
  proveedor?: ProviderData; // Structured provider data
  rfc?: string; // Alternative: top-level RFC (used if proveedor.rfc not provided)

  // CLASSIFICATION
  categoria?: string; // Category → auto-maps to accounting account
  payment_account_id?: number; // Payment account (backend validates existence)

  // METADATA
  company_id?: string; // Default: "default"
  metadata?: Record<string, any>; // Additional metadata
  ticket_id?: number; // Reference to uploaded ticket

  // TICKET PROCESSING (from ticket parser)
  ticket_extracted_concepts?: string[]; // Concepts for matching
  ticket_extracted_data?: Record<string, any>; // Full ticket data
  ticket_folio?: string; // Ticket folio number

  // OPTIONAL FIELDS
  notas?: string; // Notes for approver
  referencia_interna?: string; // Internal reference
}

/**
 * Expense response from backend
 */
export interface ExpenseResponse {
  id: number;
  descripcion: string;
  monto_total: number;
  fecha_gasto: string;
  forma_pago: string;
  proveedor?: ProviderData;
  categoria?: string;
  cuenta_contable?: string; // Accounting account (auto-assigned)
  payment_account_id?: number;
  company_id: string;
  created_at: string;
  updated_at?: string;
  status?: string;
}

/**
 * Payment account structure
 * For dropdown selection in form
 */
export interface PaymentAccount {
  id: number;
  tipo: string; // "bancaria", "efectivo", "tarjeta_credito"
  subtipo: string; // "debito", "credito", etc.
  nombre_personalizado: string; // Display name
  institucion_bancaria?: string; // Bank name
  ultimos_digitos?: string; // Last 4 digits
  moneda?: string; // "MXN", "USD"
  saldo_actual?: number;
  es_default?: boolean; // Is default account
}

/**
 * Payment methods (forma_pago options)
 * SAT catalog c_FormaPago simplified
 */
export const PAYMENT_METHODS = [
  { value: '01', label: 'Efectivo' },
  { value: '02', label: 'Cheque nominativo' },
  { value: '03', label: 'Transferencia electrónica de fondos' },
  { value: '04', label: 'Tarjeta de crédito' },
  { value: '28', label: 'Tarjeta de débito' },
  { value: '99', label: 'Por definir' },
] as const;

/**
 * Expense categories
 * Maps to accounting accounts via backend
 */
export const EXPENSE_CATEGORIES = [
  { value: 'alimentacion', label: 'Alimentación / Representación' },
  { value: 'viaticos', label: 'Viáticos y viajes' },
  { value: 'combustibles', label: 'Combustibles' },
  { value: 'servicios', label: 'Servicios Profesionales' },
  { value: 'renta', label: 'Arrendamiento / Renta' },
  { value: 'telefonia', label: 'Telefonía e Internet' },
  { value: 'papeleria', label: 'Papelería y útiles de oficina' },
  { value: 'mantenimiento', label: 'Mantenimiento y reparaciones' },
  { value: 'publicidad', label: 'Publicidad y marketing' },
  { value: 'otros', label: 'Otros gastos operativos' },
] as const;

/**
 * Form validation errors
 */
export interface FormErrors {
  descripcion?: string;
  monto_total?: string;
  fecha_gasto?: string;
  forma_pago?: string;
  proveedor?: {
    nombre?: string;
    rfc?: string;
  };
  payment_account_id?: string;
  _form?: string; // General form error
}

/**
 * AUTO-FILL LOGIC: Account Type to Forma de Pago Mapping
 *
 * This mapping automatically infers the correct SAT forma_pago code
 * based on the payment account type and subtype selected by the user.
 *
 * Benefits:
 * - Reduces user input errors
 * - Ensures fiscal compliance
 * - Improves UX (one less field to fill manually)
 * - Prevents inconsistencies (e.g., "Efectivo" with bank account)
 */
export function inferFormaPago(tipo: string, subtipo?: string): string {
  const key = subtipo ? `${tipo}_${subtipo}` : tipo;

  const mapping: Record<string, string> = {
    // Banking accounts
    'bancaria_debito': '28',   // Tarjeta de débito
    'bancaria_credito': '04',  // Tarjeta de crédito
    'bancaria': '03',          // Default: Transferencia electrónica

    // Cash
    'efectivo': '01',          // Efectivo

    // Payment terminals (Clip, MercadoPago, etc.)
    'terminal': '04',          // Tarjeta de crédito (most common for terminals)

    // Fallback
    'default': '99',           // Por definir
  };

  return mapping[key] || mapping[tipo] || mapping.default;
}

/**
 * Get forma_pago label for display
 */
export function getFormaPagoLabel(code: string): string {
  const method = PAYMENT_METHODS.find((m) => m.value === code);
  return method?.label || 'Por definir';
}

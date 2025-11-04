/**
 * Configuración de completitud de gastos
 * Define los pesos para calcular el porcentaje de avance
 */

export interface ExpenseField {
  name: string;
  weight: number;
  required: boolean;
  type: 'text' | 'number' | 'date' | 'select' | 'email';
  validation?: (value: any) => boolean;
  placeholder?: string;
  options?: { value: string; label: string }[];
}

export const COMPLETENESS_WEIGHTS = {
  // Requeridos (80% del total)
  descripcion: 0.12,
  monto_total: 0.12,
  fecha_gasto: 0.10,
  "proveedor.nombre": 0.10,
  "proveedor.rfc": 0.10,
  "empleado.id": 0.10,
  pagado_por: 0.08,
  forma_pago: 0.08,

  // Opcionales (20% del total)
  subtotal: 0.04,
  iva: 0.04,
  categoria: 0.04,
  cuenta_contable: 0.03,
  centro_costos: 0.03,
  moneda: 0.03
} as const;

export const EXPENSE_FIELDS: Record<string, ExpenseField> = {
  descripcion: {
    name: 'Descripción',
    weight: COMPLETENESS_WEIGHTS.descripcion,
    required: true,
    type: 'text',
    placeholder: 'Ej: Gasolina para vehículo de empresa',
    validation: (value) => value && value.trim().length >= 3
  },
  monto_total: {
    name: 'Monto Total',
    weight: COMPLETENESS_WEIGHTS.monto_total,
    required: true,
    type: 'number',
    placeholder: '0.00',
    validation: (value) => value > 0
  },
  fecha_gasto: {
    name: 'Fecha del Gasto',
    weight: COMPLETENESS_WEIGHTS.fecha_gasto,
    required: true,
    type: 'date',
    placeholder: 'YYYY-MM-DD',
    validation: (value) => {
      if (!value) return false;
      const date = new Date(value);
      return !isNaN(date.getTime()) && date <= new Date();
    }
  },
  "proveedor.nombre": {
    name: 'Proveedor',
    weight: COMPLETENESS_WEIGHTS["proveedor.nombre"],
    required: true,
    type: 'text',
    placeholder: 'Ej: PEMEX, Walmart, etc.',
    validation: (value) => value && value.trim().length >= 2
  },
  "proveedor.rfc": {
    name: 'RFC del Proveedor',
    weight: COMPLETENESS_WEIGHTS["proveedor.rfc"],
    required: true,
    type: 'text',
    placeholder: 'Ej: AAA010101A00',
    validation: (value) => {
      if (!value) return false;
      const rfcRegex = /^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$/;
      return rfcRegex.test(value.toUpperCase());
    }
  },
  "empleado.id": {
    name: 'Empleado',
    weight: COMPLETENESS_WEIGHTS["empleado.id"],
    required: true,
    type: 'select',
    options: [
      { value: '1', label: 'Daniel Gómez' },
      { value: '2', label: 'Otro empleado' }
    ],
    validation: (value) => value && value !== ''
  },
  pagado_por: {
    name: 'Pagado por',
    weight: COMPLETENESS_WEIGHTS.pagado_por,
    required: true,
    type: 'select',
    options: [
      { value: 'own_account', label: 'Empleado (a reembolsar)' },
      { value: 'company_account', label: 'Empresa (pago directo)' }
    ],
    validation: (value) => ['own_account', 'company_account'].includes(value)
  },
  forma_pago: {
    name: 'Forma de Pago',
    weight: COMPLETENESS_WEIGHTS.forma_pago,
    required: true,
    type: 'select',
    options: [
      { value: 'efectivo', label: 'Efectivo' },
      { value: 'tarjeta_empresa', label: 'Tarjeta Empresa' },
      { value: 'tarjeta_empleado', label: 'Tarjeta Empleado' },
      { value: 'transferencia', label: 'Transferencia' }
    ],
    validation: (value) => ['efectivo', 'tarjeta_empresa', 'tarjeta_empleado', 'transferencia'].includes(value)
  },
  // Opcionales
  subtotal: {
    name: 'Subtotal',
    weight: COMPLETENESS_WEIGHTS.subtotal,
    required: false,
    type: 'number',
    placeholder: '0.00',
    validation: (value) => !value || value >= 0
  },
  iva: {
    name: 'IVA',
    weight: COMPLETENESS_WEIGHTS.iva,
    required: false,
    type: 'number',
    placeholder: '0.00',
    validation: (value) => !value || value >= 0
  },
  categoria: {
    name: 'Categoría',
    weight: COMPLETENESS_WEIGHTS.categoria,
    required: false,
    type: 'select',
    options: [
      { value: 'combustible', label: '⛽ Combustible' },
      { value: 'alimentos', label: '🍽️ Alimentos y Bebidas' },
      { value: 'transporte', label: '🚗 Transporte' },
      { value: 'hospedaje', label: '🏨 Hospedaje' },
      { value: 'comunicacion', label: '📞 Comunicación' },
      { value: 'materiales', label: '📋 Materiales de Oficina' },
      { value: 'marketing', label: '📢 Marketing y Publicidad' },
      { value: 'capacitacion', label: '🎓 Capacitación' },
      { value: 'representacion', label: '🤝 Gastos de Representación' },
      { value: 'otros', label: '📦 Otros Gastos' }
    ],
    validation: (value) => !value || value !== ''
  },
  cuenta_contable: {
    name: 'Cuenta Contable',
    weight: COMPLETENESS_WEIGHTS.cuenta_contable,
    required: false,
    type: 'text',
    placeholder: 'Ej: 601.01',
    validation: (value) => !value || value.trim().length > 0
  },
  centro_costos: {
    name: 'Centro de Costos',
    weight: COMPLETENESS_WEIGHTS.centro_costos,
    required: false,
    type: 'text',
    placeholder: 'Ej: Departamento de Ventas',
    validation: (value) => !value || value.trim().length > 0
  },
  moneda: {
    name: 'Moneda',
    weight: COMPLETENESS_WEIGHTS.moneda,
    required: false,
    type: 'select',
    options: [
      { value: 'MXN', label: '🇲🇽 Peso Mexicano (MXN)' },
      { value: 'USD', label: '🇺🇸 Dólar Americano (USD)' },
      { value: 'EUR', label: '🇪🇺 Euro (EUR)' }
    ],
    validation: (value) => !value || ['MXN', 'USD', 'EUR'].includes(value)
  }
};

export const REQUIRED_FIELDS = Object.keys(EXPENSE_FIELDS).filter(
  key => EXPENSE_FIELDS[key].required
);

export const OPTIONAL_FIELDS = Object.keys(EXPENSE_FIELDS).filter(
  key => !EXPENSE_FIELDS[key].required
);

export function calculateCompleteness(formData: Record<string, any>): {
  percentage: number;
  presentFields: string[];
  missingFields: string[];
  totalWeight: number;
  validWeight: number;
} {
  let validWeight = 0;
  const totalWeight = Object.values(COMPLETENESS_WEIGHTS).reduce((sum, weight) => sum + weight, 0);
  const presentFields: string[] = [];
  const missingFields: string[] = [];

  for (const [fieldKey, fieldConfig] of Object.entries(EXPENSE_FIELDS)) {
    const value = getNestedValue(formData, fieldKey);
    const isValid = fieldConfig.validation ? fieldConfig.validation(value) : Boolean(value);

    if (isValid) {
      validWeight += fieldConfig.weight;
      presentFields.push(fieldKey);
    } else {
      missingFields.push(fieldKey);
    }
  }

  return {
    percentage: Math.round((validWeight / totalWeight) * 100),
    presentFields,
    missingFields,
    totalWeight,
    validWeight
  };
}

function getNestedValue(obj: Record<string, any>, path: string): any {
  return path.split('.').reduce((current, key) => current?.[key], obj);
}

export function setNestedValue(obj: Record<string, any>, path: string, value: any): void {
  const keys = path.split('.');
  const lastKey = keys.pop()!;
  const target = keys.reduce((current, key) => {
    if (!current[key]) current[key] = {};
    return current[key];
  }, obj);
  target[lastKey] = value;
}
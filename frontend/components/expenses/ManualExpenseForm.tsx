/**
 * Manual Expense Form Component
 *
 * Professional expense creation form with:
 * - React Hook Form for state management
 * - Zod schema validation matching backend
 * - Proper provider structure (object, not string)
 * - All required fields including forma_pago
 * - Dynamic payment account dropdown
 * - Actual backend integration
 *
 * Fixes 5 critical problems identified in audit:
 * 1. ✅ Missing forma_pago field (CRITICAL)
 * 2. ✅ Missing payment_account_id field
 * 3. ✅ Wrong provider structure (string → object)
 * 4. ✅ Duplicate RFC fields
 * 5. ✅ No backend connection
 */

'use client';

import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import {
  PAYMENT_METHODS,
  EXPENSE_CATEGORIES,
  PaymentAccount,
  inferFormaPago,
  getFormaPagoLabel,
} from '@/types/expense';
import { createExpense, getPaymentAccounts } from '@/services/expenseService';
import { CheckCircle2, AlertCircle, Loader2, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils/cn';

// ============================================================================
// ZOD VALIDATION SCHEMA
// Matches backend ExpenseCreate validation from core/api_models.py:263
// ============================================================================

const expenseFormSchema = z.object({
  // BASIC INFO (Required)
  descripcion: z
    .string()
    .min(1, 'La descripción es obligatoria')
    .max(500, 'Descripción muy larga (máx 500 caracteres)'),

  monto_total: z
    .number()
    .positive('El monto debe ser mayor a 0')
    .max(10_000_000, 'El monto no puede exceder 10 millones de MXN'),

  fecha_gasto: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/, 'Formato de fecha inválido (YYYY-MM-DD)')
    .refine(
      (date) => {
        const dateObj = new Date(date);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        // Allow 1 day tolerance for timezone differences
        const maxDate = new Date(today);
        maxDate.setDate(maxDate.getDate() + 1);
        return dateObj <= maxDate;
      },
      { message: 'La fecha no puede ser futura' }
    ),

  // PAYMENT INFO (Required)
  forma_pago: z
    .string()
    .min(1, 'La forma de pago es obligatoria')
    .refine((val) => PAYMENT_METHODS.some((m) => m.value === val), {
      message: 'Forma de pago inválida',
    }),

  // PROVIDER (Structured object - fixes Problem #3)
  proveedor: z
    .object({
      nombre: z
        .string()
        .min(1, 'El nombre del proveedor es obligatorio')
        .max(200, 'Nombre muy largo'),
      nombre_fiscal: z.string().optional(),
      rfc: z
        .string()
        .regex(/^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$/, 'RFC inválido (12-13 caracteres)')
        .optional()
        .or(z.literal('')), // Allow empty string
    })
    .optional(),

  // CLASSIFICATION
  categoria: z.string().optional(),
  payment_account_id: z.number().int().positive().optional(),

  // METADATA
  notas: z.string().max(1000, 'Notas muy largas').optional(),
  referencia_interna: z.string().max(100).optional(),

  // COMPANY ID (from context)
  company_id: z.string().optional(),
});

type ExpenseFormData = z.infer<typeof expenseFormSchema>;

// ============================================================================
// COMPONENT
// ============================================================================

export function ManualExpenseForm() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [paymentAccounts, setPaymentAccounts] = useState<PaymentAccount[]>([]);
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(true);
  const [isFormaPagoAutoFilled, setIsFormaPagoAutoFilled] = useState(false);

  // Initialize form with React Hook Form + Zod validation
  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
    setValue,
    watch,
    reset,
  } = useForm<ExpenseFormData>({
    resolver: zodResolver(expenseFormSchema),
    mode: 'onChange', // Validate on change for real-time feedback
    defaultValues: {
      descripcion: '',
      monto_total: undefined,
      fecha_gasto: new Date().toISOString().split('T')[0],
      forma_pago: '01', // Default: Efectivo
      proveedor: {
        nombre: '',
        nombre_fiscal: '',
        rfc: '',
      },
      categoria: 'alimentacion',
      payment_account_id: undefined,
      notas: '',
      referencia_interna: '',
      company_id: '2',
    },
  });

  // Watch payment_account_id for auto-fill logic
  const selectedAccountId = watch('payment_account_id');

  // Load payment accounts on mount
  useEffect(() => {
    async function loadAccounts() {
      try {
        setIsLoadingAccounts(true);
        const accounts = await getPaymentAccounts('2'); // Company ID 2
        setPaymentAccounts(accounts);

        // Set default account if exists
        const defaultAccount = accounts.find((a) => a.es_default);
        if (defaultAccount) {
          setValue('payment_account_id', defaultAccount.id);
        }
      } catch (error) {
        console.error('Error loading payment accounts:', error);
        // Continue without accounts - field is optional
      } finally {
        setIsLoadingAccounts(false);
      }
    }

    loadAccounts();
  }, [setValue]);

  // Auto-fill forma_pago when payment account is selected
  useEffect(() => {
    if (selectedAccountId && paymentAccounts.length > 0) {
      const selectedAccount = paymentAccounts.find(
        (acc) => acc.id === selectedAccountId
      );

      if (selectedAccount) {
        // Infer the correct forma_pago based on account type
        const inferredFormaPago = inferFormaPago(
          selectedAccount.tipo,
          selectedAccount.subtipo
        );

        // Auto-set the forma_pago field
        setValue('forma_pago', inferredFormaPago);
        setIsFormaPagoAutoFilled(true);

        console.log('✨ Auto-filled forma_pago:', {
          account: selectedAccount.nombre_personalizado,
          tipo: selectedAccount.tipo,
          subtipo: selectedAccount.subtipo,
          inferredCode: inferredFormaPago,
          inferredLabel: getFormaPagoLabel(inferredFormaPago),
        });
      }
    } else {
      // Reset to default when no account is selected
      setIsFormaPagoAutoFilled(false);
    }
  }, [selectedAccountId, paymentAccounts, setValue]);

  // Form submission handler
  const onSubmit = async (data: ExpenseFormData) => {
    try {
      setIsSubmitting(true);
      setSubmitError(null);
      setSubmitSuccess(false);

      // Transform data for API
      // Clean empty provider object
      const payload: any = {
        descripcion: data.descripcion,
        monto_total: data.monto_total,
        fecha_gasto: data.fecha_gasto,
        forma_pago: data.forma_pago,
        company_id: data.company_id,
      };

      // Add provider only if name is filled
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
      if (data.payment_account_id)
        payload.payment_account_id = data.payment_account_id;
      if (data.notas && data.notas.trim()) payload.notas = data.notas;
      if (data.referencia_interna && data.referencia_interna.trim()) {
        payload.referencia_interna = data.referencia_interna;
      }

      // Call backend API
      const response = await createExpense(payload);

      console.log('✅ Expense created successfully:', response);

      // Show success message
      setSubmitSuccess(true);

      // Reset form after 2 seconds
      setTimeout(() => {
        reset();
        setSubmitSuccess(false);
      }, 2000);
    } catch (error) {
      console.error('❌ Error creating expense:', error);
      setSubmitError(
        error instanceof Error
          ? error.message
          : 'Error desconocido al crear el gasto'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card
      title="Captura manual de gasto"
      subtitle="Formulario profesional con validaciones backend (Zod + Pydantic)"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* SECTION 1: BASIC INFO */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Información básica
          </h3>
          <div className="grid gap-4 md:grid-cols-2">
            {/* Descripción */}
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Descripción del gasto{' '}
                <span className="text-red-500">*</span>
              </label>
              <Input
                {...register('descripcion')}
                placeholder="Ej. Comida con cliente ACME Corp"
                error={errors.descripcion?.message}
              />
            </div>

            {/* Monto */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Monto total (MXN) <span className="text-red-500">*</span>
              </label>
              <Input
                {...register('monto_total', { valueAsNumber: true })}
                type="number"
                step="0.01"
                placeholder="0.00"
                error={errors.monto_total?.message}
              />
            </div>

            {/* Fecha */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Fecha del gasto <span className="text-red-500">*</span>
              </label>
              <Input
                {...register('fecha_gasto')}
                type="date"
                error={errors.fecha_gasto?.message}
              />
            </div>
          </div>
        </div>

        {/* SECTION 2: PAYMENT INFO */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Información de pago
          </h3>
          <div className="grid gap-4 md:grid-cols-2">
            {/* Forma de pago (CRITICAL - Problem #1 fix) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Forma de pago <span className="text-red-500">*</span>
                {isFormaPagoAutoFilled && (
                  <span className="ml-2 inline-flex items-center gap-1 text-xs font-normal text-emerald-600">
                    <Sparkles className="w-3 h-3" />
                    Auto-inferido
                  </span>
                )}
              </label>
              <select
                {...register('forma_pago')}
                className={cn(
                  'w-full border rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary-500',
                  errors.forma_pago
                    ? 'border-red-300 bg-red-50'
                    : isFormaPagoAutoFilled
                    ? 'border-emerald-300 bg-emerald-50'
                    : 'border-gray-300'
                )}
                onChange={(e) => {
                  // Allow manual override
                  setValue('forma_pago', e.target.value);
                  if (isFormaPagoAutoFilled) {
                    setIsFormaPagoAutoFilled(false);
                  }
                }}
              >
                {PAYMENT_METHODS.map((method) => (
                  <option key={method.value} value={method.value}>
                    {method.label}
                  </option>
                ))}
              </select>
              {errors.forma_pago && (
                <p className="text-sm text-red-600 mt-1">
                  {errors.forma_pago.message}
                </p>
              )}
              {isFormaPagoAutoFilled && !errors.forma_pago && (
                <p className="text-xs text-emerald-600 mt-1 flex items-center gap-1">
                  <Sparkles className="w-3 h-3" />
                  Inferido automáticamente de la cuenta seleccionada. Puedes
                  cambiarlo si es necesario.
                </p>
              )}
            </div>

            {/* Payment Account (Problem #2 fix) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Cuenta de pago
                {isLoadingAccounts && (
                  <Loader2 className="inline w-4 h-4 ml-2 animate-spin text-gray-400" />
                )}
              </label>
              <select
                {...register('payment_account_id', { valueAsNumber: true })}
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary-500"
                disabled={isLoadingAccounts}
              >
                <option value="">Seleccionar cuenta...</option>
                {paymentAccounts.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.nombre_personalizado}
                    {account.institucion_bancaria &&
                      ` - ${account.institucion_bancaria}`}
                    {account.ultimos_digitos &&
                      ` ****${account.ultimos_digitos}`}
                  </option>
                ))}
              </select>
              {errors.payment_account_id && (
                <p className="text-sm text-red-600 mt-1">
                  {errors.payment_account_id.message}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* SECTION 3: PROVIDER INFO (Problem #3 & #4 fix) */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Proveedor
          </h3>
          <div className="grid gap-4 md:grid-cols-2">
            {/* Provider Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Nombre del proveedor
              </label>
              <Input
                {...register('proveedor.nombre')}
                placeholder="Ej. Restaurante La Hacienda"
                error={errors.proveedor?.nombre?.message}
              />
            </div>

            {/* Provider RFC (within proveedor object - fixes Problem #4) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                RFC del proveedor (opcional)
              </label>
              <Input
                {...register('proveedor.rfc')}
                placeholder="PEM840212XY1"
                maxLength={13}
                error={errors.proveedor?.rfc?.message}
              />
              <p className="text-xs text-gray-500 mt-1">
                12-13 caracteres alfanuméricos
              </p>
            </div>
          </div>
        </div>

        {/* SECTION 4: CLASSIFICATION */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Clasificación
          </h3>
          <div className="grid gap-4 md:grid-cols-2">
            {/* Category */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Categoría SAT
              </label>
              <select
                {...register('categoria')}
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {EXPENSE_CATEGORIES.map((cat) => (
                  <option key={cat.value} value={cat.value}>
                    {cat.label}
                  </option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">
                Se asignará automáticamente la cuenta contable
              </p>
            </div>
          </div>
        </div>

        {/* SECTION 5: ADDITIONAL INFO */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Información adicional
          </h3>
          <div className="grid gap-4">
            {/* Notes */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Notas / Contexto para el aprobador
              </label>
              <textarea
                {...register('notas')}
                rows={3}
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="Información adicional relevante..."
              />
              {errors.notas && (
                <p className="text-sm text-red-600 mt-1">
                  {errors.notas.message}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* SUBMIT SECTION */}
        <div className="border-t border-gray-200 pt-6">
          <div className="flex flex-wrap gap-3">
            <Button
              type="submit"
              disabled={isSubmitting || !isValid}
              className="min-w-[200px]"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Creando gasto...
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  Crear gasto vía POST /expenses
                </>
              )}
            </Button>

            <Button
              type="button"
              variant="ghost"
              onClick={() => reset()}
              disabled={isSubmitting}
            >
              Limpiar formulario
            </Button>
          </div>

          {/* Success Message */}
          {submitSuccess && (
            <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4 flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 mt-0.5 flex-shrink-0" />
              <div>
                <p className="font-semibold text-emerald-900">
                  ¡Gasto creado exitosamente!
                </p>
                <p className="text-sm text-emerald-700 mt-1">
                  El gasto ha sido registrado en el sistema.
                </p>
              </div>
            </div>
          )}

          {/* Error Message */}
          {submitError && (
            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" />
              <div>
                <p className="font-semibold text-red-900">
                  Error al crear el gasto
                </p>
                <p className="text-sm text-red-700 mt-1">{submitError}</p>
              </div>
            </div>
          )}
        </div>

        {/* VALIDATION STATUS */}
        <div className="rounded-xl border border-dashed border-gray-200 p-4 bg-gray-50">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <p className="text-sm font-semibold text-gray-700">
                Estado de validación
              </p>
              <p className="text-xs text-gray-500">
                Validaciones Zod (cliente) + Pydantic (servidor)
              </p>
            </div>
            <span
              className={cn(
                'inline-flex px-3 py-1 rounded-full text-xs font-semibold border',
                isValid
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-amber-50 text-amber-700 border-amber-200'
              )}
            >
              {isValid ? 'Formulario válido' : 'Faltan campos requeridos'}
            </span>
          </div>

          {/* Field validation checklist */}
          <div className="mt-4 grid gap-2 md:grid-cols-2">
            {[
              { label: 'Descripción', valid: !errors.descripcion },
              { label: 'Monto > 0', valid: !errors.monto_total },
              { label: 'Fecha válida', valid: !errors.fecha_gasto },
              { label: 'Forma de pago', valid: !errors.forma_pago },
            ].map((check) => (
              <div
                key={check.label}
                className="flex items-center gap-2 text-sm text-gray-600"
              >
                <CheckCircle2
                  className={cn(
                    'w-4 h-4',
                    check.valid ? 'text-emerald-500' : 'text-gray-300'
                  )}
                />
                <span>{check.label}</span>
              </div>
            ))}
          </div>
        </div>
      </form>
    </Card>
  );
}

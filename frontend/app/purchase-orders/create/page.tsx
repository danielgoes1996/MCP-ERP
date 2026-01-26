/**
 * Purchase Order Create Page
 * Professional form for creating new purchase orders
 */

'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { AppLayout } from '@/components/layout/AppLayout';
import {
  ArrowLeft,
  Save,
  Send,
  Building2,
  User,
  Mail,
  Phone,
  FileText,
  DollarSign,
  AlertCircle,
  CheckCircle2,
  Loader2,
  ShoppingCart,
  AlertTriangle,
  Plus,
  Calculator,
} from 'lucide-react';
import {
  createPurchaseOrder,
  PurchaseOrderCreate,
  submitPurchaseOrder,
} from '@/services/purchaseOrdersService';
import { getProjects, Project } from '@/services/projectsService';
import { getProjectBudgetSummary, BudgetSummary } from '@/services/purchaseOrdersService';
import { LineItemsTable, POLineItem } from '@/components/purchase-orders/LineItemsTable';

export default function PurchaseOrderCreatePage() {
  const router = useRouter();

  // Form state
  const [formData, setFormData] = useState<PurchaseOrderCreate>({
    vendor_name: '',
    vendor_rfc: '',
    vendor_email: '',
    vendor_phone: '',
    description: '',
    total_amount: 0,
    currency: 'MXN',
    notes: '',
    project_id: undefined,
  });

  // UI state
  const [projects, setProjects] = useState<Project[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [budgetSummary, setBudgetSummary] = useState<BudgetSummary | null>(null);
  const [loadingBudget, setLoadingBudget] = useState(false);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showSuccess, setShowSuccess] = useState(false);

  // Line items state
  const [lines, setLines] = useState<POLineItem[]>([]);
  const [showLineItems, setShowLineItems] = useState(false);
  const [lineErrors, setLineErrors] = useState<Record<number, string>>({});

  // Load projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

  // Load budget summary when project changes
  useEffect(() => {
    if (formData.project_id) {
      loadBudgetSummary(formData.project_id);
    } else {
      setBudgetSummary(null);
    }
  }, [formData.project_id]);

  // Auto-calculate total from line items
  useEffect(() => {
    if (lines.length > 0) {
      const total = lines.reduce((sum, line) => sum + (line.line_total || 0), 0);
      handleChange('total_amount', total);
    }
  }, [lines]);

  const loadProjects = async () => {
    try {
      setLoadingProjects(true);
      const data = await getProjects({ status_filter: 'active', limit: 100 });
      setProjects(data);
    } catch (error: any) {
      console.error('Error loading projects:', error);
    } finally {
      setLoadingProjects(false);
    }
  };

  const loadBudgetSummary = async (projectId: number) => {
    try {
      setLoadingBudget(true);
      const data = await getProjectBudgetSummary(projectId);
      setBudgetSummary(data);
    } catch (error: any) {
      console.error('Error loading budget:', error);
      setBudgetSummary(null);
    } finally {
      setLoadingBudget(false);
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.vendor_name?.trim()) {
      newErrors.vendor_name = 'El nombre del proveedor es requerido';
    }

    if (!formData.description?.trim()) {
      newErrors.description = 'La descripción es requerida';
    }

    if (!formData.total_amount || formData.total_amount <= 0) {
      newErrors.total_amount = 'El monto debe ser mayor a 0';
    }

    // Budget validation
    if (budgetSummary && formData.total_amount > budgetSummary.remaining_mxn) {
      newErrors.total_amount = `El monto excede el presupuesto disponible ($${budgetSummary.remaining_mxn.toLocaleString('es-MX')})`;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSaveDraft = async () => {
    if (!validateForm()) return;

    try {
      setSaving(true);

      // Include lines in the PO creation
      const poData = {
        ...formData,
        lines: lines.length > 0 ? lines : undefined,
      };

      const po = await createPurchaseOrder(poData as any);
      setShowSuccess(true);
      setTimeout(() => {
        router.push(`/purchase-orders/${po.id}`);
      }, 1500);
    } catch (error: any) {
      setErrors({ submit: error.message || 'Error al guardar la orden' });
    } finally {
      setSaving(false);
    }
  };

  const handleSubmitForApproval = async () => {
    if (!validateForm()) return;

    try {
      setSubmitting(true);

      // Include lines in the PO creation
      const poData = {
        ...formData,
        lines: lines.length > 0 ? lines : undefined,
      };

      const po = await createPurchaseOrder(poData as any);
      await submitPurchaseOrder(po.id);
      setShowSuccess(true);
      setTimeout(() => {
        router.push(`/purchase-orders/${po.id}`);
      }, 1500);
    } catch (error: any) {
      setErrors({ submit: error.message || 'Error al enviar para aprobación' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleChange = (field: keyof PurchaseOrderCreate, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    // Clear error for this field
    if (errors[field]) {
      setErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('es-MX', {
      style: 'currency',
      currency: 'MXN',
    }).format(amount);
  };

  const getBudgetWarningLevel = (): 'safe' | 'warning' | 'danger' | null => {
    if (!budgetSummary || !formData.total_amount) return null;

    const newRemaining = budgetSummary.remaining_mxn - formData.total_amount;
    const percentageUsed = budgetSummary.budget_total > 0
      ? ((budgetSummary.budget_total - newRemaining) / budgetSummary.budget_total) * 100
      : 0;

    if (newRemaining < 0) return 'danger';
    if (percentageUsed > 90) return 'warning';
    return 'safe';
  };

  const budgetWarningLevel = getBudgetWarningLevel();

  return (
    <ProtectedRoute>
      <AppLayout>
        <div className="max-w-5xl mx-auto space-y-8">
          {/* Modern Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="relative overflow-hidden bg-gradient-to-br from-[#0f172a] via-[#1e293b] to-[#0f172a] rounded-2xl p-8 shadow-2xl"
          >
            {/* Decorative elements */}
            <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-br from-[#60b97b]/20 to-transparent rounded-full blur-3xl" />
            <div className="absolute bottom-0 left-0 w-96 h-96 bg-gradient-to-tr from-[#11446e]/20 to-transparent rounded-full blur-3xl" />

            <div className="relative z-10">
              <div className="flex items-center gap-4 mb-4">
                <motion.button
                  whileHover={{ scale: 1.05, x: -4 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => router.push('/purchase-orders')}
                  className="p-2 bg-white/10 hover:bg-white/20 rounded-xl transition-colors backdrop-blur-sm"
                >
                  <ArrowLeft className="w-5 h-5 text-white" />
                </motion.button>
                <div className="p-3 bg-gradient-to-br from-[#60b97b] to-[#4a9460] rounded-xl shadow-lg">
                  <ShoppingCart className="w-8 h-8 text-white" />
                </div>
                <div>
                  <h1 className="text-3xl font-bold text-white">
                    Nueva Orden de Compra
                  </h1>
                  <p className="text-gray-300">
                    Crea una orden de compra para planificar tu gasto antes de recibir factura
                  </p>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Success Message */}
          {showSuccess && (
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-green-50 border border-green-200 rounded-xl p-4"
            >
              <div className="flex items-center gap-3">
                <CheckCircle2 className="w-6 h-6 text-green-600" />
                <div>
                  <h3 className="font-semibold text-green-900">
                    Orden creada exitosamente
                  </h3>
                  <p className="text-sm text-green-700">
                    Redirigiendo...
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {/* Error Message */}
          {errors.submit && (
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-red-50 border border-red-200 rounded-xl p-4"
            >
              <div className="flex items-center gap-3">
                <AlertCircle className="w-6 h-6 text-red-600" />
                <div>
                  <h3 className="font-semibold text-red-900">Error</h3>
                  <p className="text-sm text-red-700">{errors.submit}</p>
                </div>
              </div>
            </motion.div>
          )}

          {/* Form */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="bg-white rounded-2xl shadow-lg border border-gray-200 p-8 space-y-8"
          >
            {/* Vendor Information Section */}
            <div>
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-gradient-to-br from-[#11446e]/10 to-[#60b97b]/10 rounded-lg">
                  <Building2 className="w-5 h-5 text-[#11446e]" />
                </div>
                <h2 className="text-xl font-bold text-gray-900">
                  Información del Proveedor
                </h2>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Vendor Name */}
                <div className="md:col-span-2">
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Nombre del Proveedor *
                  </label>
                  <div className="relative">
                    <Building2 className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      value={formData.vendor_name}
                      onChange={(e) => handleChange('vendor_name', e.target.value)}
                      placeholder="Ej: Proveedor SA de CV"
                      className={`w-full pl-12 pr-4 py-3.5 bg-gradient-to-br from-gray-50 to-white border-2 rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:shadow-lg transition-all ${
                        errors.vendor_name
                          ? 'border-red-300 focus:border-red-500'
                          : 'border-gray-200 focus:border-[#11446e] focus:shadow-[#11446e]/10'
                      }`}
                    />
                  </div>
                  {errors.vendor_name && (
                    <p className="mt-1.5 text-sm text-red-600 flex items-center gap-1">
                      <AlertCircle className="w-4 h-4" />
                      {errors.vendor_name}
                    </p>
                  )}
                </div>

                {/* Vendor RFC */}
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    RFC (Opcional)
                  </label>
                  <input
                    type="text"
                    value={formData.vendor_rfc}
                    onChange={(e) => handleChange('vendor_rfc', e.target.value.toUpperCase())}
                    placeholder="ABC123456789"
                    maxLength={13}
                    className="w-full px-4 py-3.5 bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:border-[#11446e] focus:shadow-lg focus:shadow-[#11446e]/10 transition-all"
                  />
                </div>

                {/* Vendor Phone */}
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Teléfono (Opcional)
                  </label>
                  <div className="relative">
                    <Phone className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="tel"
                      value={formData.vendor_phone}
                      onChange={(e) => handleChange('vendor_phone', e.target.value)}
                      placeholder="+52 55 1234 5678"
                      className="w-full pl-12 pr-4 py-3.5 bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:border-[#11446e] focus:shadow-lg focus:shadow-[#11446e]/10 transition-all"
                    />
                  </div>
                </div>

                {/* Vendor Email */}
                <div className="md:col-span-2">
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Email (Opcional)
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="email"
                      value={formData.vendor_email}
                      onChange={(e) => handleChange('vendor_email', e.target.value)}
                      placeholder="contacto@proveedor.com"
                      className="w-full pl-12 pr-4 py-3.5 bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:border-[#11446e] focus:shadow-lg focus:shadow-[#11446e]/10 transition-all"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Project and Financial Section */}
            <div className="pt-8 border-t border-gray-200">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-gradient-to-br from-[#11446e]/10 to-[#60b97b]/10 rounded-lg">
                  <DollarSign className="w-5 h-5 text-[#11446e]" />
                </div>
                <h2 className="text-xl font-bold text-gray-900">
                  Detalles Financieros
                </h2>
              </div>

              <div className="space-y-6">
                {/* Project Selection */}
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Proyecto (Opcional)
                  </label>
                  {loadingProjects ? (
                    <div className="flex items-center gap-2 px-4 py-3.5 bg-gray-50 border-2 border-gray-200 rounded-xl">
                      <Loader2 className="w-5 h-5 text-gray-400 animate-spin" />
                      <span className="text-gray-500">Cargando proyectos...</span>
                    </div>
                  ) : (
                    <select
                      value={formData.project_id || ''}
                      onChange={(e) =>
                        handleChange('project_id', e.target.value ? parseInt(e.target.value) : undefined)
                      }
                      className="w-full px-4 py-3.5 bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-xl text-gray-900 focus:outline-none focus:border-[#11446e] focus:shadow-lg focus:shadow-[#11446e]/10 transition-all appearance-none cursor-pointer"
                    >
                      <option value="">Sin proyecto asignado</option>
                      {projects.map((project) => (
                        <option key={project.id} value={project.id}>
                          {project.code ? `[${project.code}] ` : ''}{project.name}
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                {/* Budget Summary Card */}
                {formData.project_id && budgetSummary && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    className={`p-5 rounded-xl border-2 ${
                      budgetWarningLevel === 'danger'
                        ? 'bg-red-50 border-red-200'
                        : budgetWarningLevel === 'warning'
                        ? 'bg-yellow-50 border-yellow-200'
                        : 'bg-blue-50 border-blue-200'
                    }`}
                  >
                    <div className="flex items-start gap-3 mb-4">
                      {budgetWarningLevel === 'danger' ? (
                        <AlertCircle className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5" />
                      ) : budgetWarningLevel === 'warning' ? (
                        <AlertTriangle className="w-6 h-6 text-yellow-600 flex-shrink-0 mt-0.5" />
                      ) : (
                        <CheckCircle2 className="w-6 h-6 text-blue-600 flex-shrink-0 mt-0.5" />
                      )}
                      <div className="flex-1">
                        <h3 className={`font-semibold mb-1 ${
                          budgetWarningLevel === 'danger'
                            ? 'text-red-900'
                            : budgetWarningLevel === 'warning'
                            ? 'text-yellow-900'
                            : 'text-blue-900'
                        }`}>
                          Resumen de Presupuesto: {budgetSummary.project_name}
                        </h3>
                        <p className={`text-sm ${
                          budgetWarningLevel === 'danger'
                            ? 'text-red-700'
                            : budgetWarningLevel === 'warning'
                            ? 'text-yellow-700'
                            : 'text-blue-700'
                        }`}>
                          {budgetWarningLevel === 'danger'
                            ? 'El monto excede el presupuesto disponible'
                            : budgetWarningLevel === 'warning'
                            ? 'El presupuesto está casi agotado (>90%)'
                            : 'Presupuesto disponible suficiente'}
                        </p>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-xs text-gray-600 mb-1">Presupuesto Total</p>
                        <p className="font-bold text-gray-900">
                          {formatCurrency(budgetSummary.budget_total)}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-600 mb-1">Gastado</p>
                        <p className="font-bold text-gray-900">
                          {formatCurrency(budgetSummary.spent_total_mxn)}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-600 mb-1">Disponible Actual</p>
                        <p className="font-bold text-gray-900">
                          {formatCurrency(budgetSummary.remaining_mxn)}
                        </p>
                      </div>
                      {formData.total_amount > 0 && (
                        <div>
                          <p className="text-xs text-gray-600 mb-1">
                            Disponible después de esta OC
                          </p>
                          <p className={`font-bold ${
                            budgetWarningLevel === 'danger' ? 'text-red-600' : 'text-gray-900'
                          }`}>
                            {formatCurrency(budgetSummary.remaining_mxn - formData.total_amount)}
                          </p>
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}

                {/* Amount and Currency */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="md:col-span-2">
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Monto Total *
                    </label>
                    <div className="relative">
                      <DollarSign className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type="number"
                        value={formData.total_amount || ''}
                        onChange={(e) =>
                          handleChange('total_amount', parseFloat(e.target.value) || 0)
                        }
                        placeholder="0.00"
                        step="0.01"
                        min="0"
                        className={`w-full pl-12 pr-4 py-3.5 bg-gradient-to-br from-gray-50 to-white border-2 rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:shadow-lg transition-all ${
                          errors.total_amount
                            ? 'border-red-300 focus:border-red-500'
                            : 'border-gray-200 focus:border-[#11446e] focus:shadow-[#11446e]/10'
                        }`}
                      />
                    </div>
                    {errors.total_amount && (
                      <p className="mt-1.5 text-sm text-red-600 flex items-center gap-1">
                        <AlertCircle className="w-4 h-4" />
                        {errors.total_amount}
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Moneda
                    </label>
                    <select
                      value={formData.currency}
                      onChange={(e) => handleChange('currency', e.target.value)}
                      className="w-full px-4 py-3.5 bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-xl text-gray-900 focus:outline-none focus:border-[#11446e] focus:shadow-lg focus:shadow-[#11446e]/10 transition-all appearance-none cursor-pointer"
                    >
                      <option value="MXN">MXN</option>
                      <option value="USD">USD</option>
                      <option value="EUR">EUR</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>

            {/* Description and Notes Section */}
            <div className="pt-8 border-t border-gray-200">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-gradient-to-br from-[#11446e]/10 to-[#60b97b]/10 rounded-lg">
                  <FileText className="w-5 h-5 text-[#11446e]" />
                </div>
                <h2 className="text-xl font-bold text-gray-900">Descripción</h2>
              </div>

              <div className="space-y-6">
                {/* Description */}
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Descripción de la Compra *
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => handleChange('description', e.target.value)}
                    placeholder="Describe qué se está comprando y para qué se usará..."
                    rows={4}
                    className={`w-full px-4 py-3.5 bg-gradient-to-br from-gray-50 to-white border-2 rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:shadow-lg transition-all resize-none ${
                      errors.description
                        ? 'border-red-300 focus:border-red-500'
                        : 'border-gray-200 focus:border-[#11446e] focus:shadow-[#11446e]/10'
                    }`}
                  />
                  {errors.description && (
                    <p className="mt-1.5 text-sm text-red-600 flex items-center gap-1">
                      <AlertCircle className="w-4 h-4" />
                      {errors.description}
                    </p>
                  )}
                </div>

                {/* Notes */}
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Notas Adicionales (Opcional)
                  </label>
                  <textarea
                    value={formData.notes}
                    onChange={(e) => handleChange('notes', e.target.value)}
                    placeholder="Información adicional, plazos de entrega, condiciones especiales..."
                    rows={3}
                    className="w-full px-4 py-3.5 bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:border-[#11446e] focus:shadow-lg focus:shadow-[#11446e]/10 transition-all resize-none"
                  />
                </div>
              </div>
            </div>

            {/* Line Items Section (Progressive Disclosure) */}
            <div className="pt-8 border-t border-gray-200">
              {!showLineItems && (
                <motion.button
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  onClick={() => setShowLineItems(true)}
                  className="w-full p-6 border-2 border-dashed border-gray-300 hover:border-[#11446e] rounded-xl text-center text-gray-600 hover:text-[#11446e] font-medium transition-all group"
                >
                  <div className="flex items-center justify-center gap-3">
                    <Plus className="w-6 h-6 group-hover:rotate-90 transition-transform" />
                    <div>
                      <div className="text-lg font-semibold">
                        Agregar detalles de línea (opcional)
                      </div>
                      <div className="text-sm text-gray-500">
                        Para órdenes complejas con múltiples productos o servicios
                      </div>
                    </div>
                  </div>
                </motion.button>
              )}

              {showLineItems && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  className="space-y-6"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-gradient-to-br from-[#11446e]/10 to-[#60b97b]/10 rounded-lg">
                        <Calculator className="w-5 h-5 text-[#11446e]" />
                      </div>
                      <h2 className="text-xl font-bold text-gray-900">
                        Líneas de Productos
                      </h2>
                    </div>
                    <button
                      onClick={() => setShowLineItems(false)}
                      className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
                    >
                      Ocultar líneas
                    </button>
                  </div>

                  <LineItemsTable
                    lines={lines}
                    onChange={setLines}
                    errors={lineErrors}
                  />
                </motion.div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="pt-8 border-t border-gray-200">
              <div className="flex flex-col sm:flex-row gap-4 justify-end">
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => router.push('/purchase-orders')}
                  disabled={saving || submitting}
                  className="px-6 py-3.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Cancelar
                </motion.button>

                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleSaveDraft}
                  disabled={saving || submitting}
                  className="flex items-center justify-center gap-2 px-6 py-3.5 bg-white hover:bg-gray-50 border-2 border-gray-300 text-gray-700 rounded-xl font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Guardando...
                    </>
                  ) : (
                    <>
                      <Save className="w-5 h-5" />
                      Guardar Borrador
                    </>
                  )}
                </motion.button>

                <motion.button
                  whileHover={{ scale: 1.02, y: -2 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleSubmitForApproval}
                  disabled={saving || submitting}
                  className="flex items-center justify-center gap-2 px-6 py-3.5 bg-gradient-to-r from-[#60b97b] to-[#4a9460] hover:from-[#4a9460] hover:to-[#60b97b] text-white rounded-xl font-semibold shadow-lg hover:shadow-xl hover:shadow-[#60b97b]/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Enviando...
                    </>
                  ) : (
                    <>
                      <Send className="w-5 h-5" />
                      Enviar para Aprobación
                    </>
                  )}
                </motion.button>
              </div>

              <p className="mt-4 text-sm text-gray-500 text-center">
                * Campos requeridos. Los borradores pueden editarse antes de enviar para aprobación.
              </p>
            </div>
          </motion.div>
        </div>
      </AppLayout>
    </ProtectedRoute>
  );
}

/**
 * Purchase Orders List Page
 * Professional list view with status filtering and workflow actions
 */

'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { AppLayout } from '@/components/layout/AppLayout';
import {
  FileText,
  Filter,
  Plus,
  Search,
  Calendar,
  DollarSign,
  User,
  Building2,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Eye,
  Loader2,
  X,
  ShoppingCart,
  Send,
  Package,
  Receipt,
  Ban,
} from 'lucide-react';
import { getPurchaseOrders, POStatus, PurchaseOrder } from '@/services/purchaseOrdersService';

const statusConfig: Record<POStatus, {
  label: string;
  color: string;
  bgColor: string;
  icon: React.ComponentType<{ className?: string }>;
}> = {
  draft: {
    label: 'Borrador',
    color: 'text-gray-700',
    bgColor: 'bg-gray-100',
    icon: FileText,
  },
  pending_approval: {
    label: 'Pendiente Aprobación',
    color: 'text-yellow-700',
    bgColor: 'bg-yellow-100',
    icon: Clock,
  },
  approved: {
    label: 'Aprobado',
    color: 'text-green-700',
    bgColor: 'bg-green-100',
    icon: CheckCircle2,
  },
  rejected: {
    label: 'Rechazado',
    color: 'text-red-700',
    bgColor: 'bg-red-100',
    icon: XCircle,
  },
  sent_to_vendor: {
    label: 'Enviado a Proveedor',
    color: 'text-blue-700',
    bgColor: 'bg-blue-100',
    icon: Send,
  },
  received: {
    label: 'Recibido',
    color: 'text-indigo-700',
    bgColor: 'bg-indigo-100',
    icon: Package,
  },
  invoiced: {
    label: 'Facturado',
    color: 'text-purple-700',
    bgColor: 'bg-purple-100',
    icon: Receipt,
  },
  cancelled: {
    label: 'Cancelado',
    color: 'text-gray-700',
    bgColor: 'bg-gray-100',
    icon: Ban,
  },
};

export default function PurchaseOrdersListPage() {
  const router = useRouter();
  const [pos, setPOs] = useState<PurchaseOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<POStatus | 'all'>('all');

  useEffect(() => {
    fetchPOs();
  }, [statusFilter]);

  const fetchPOs = async () => {
    try {
      setLoading(true);
      setError(null);

      const params: any = { limit: 50 };
      if (statusFilter !== 'all') {
        params.status_filter = statusFilter;
      }

      const data = await getPurchaseOrders(params);
      setPOs(data);
    } catch (err: any) {
      setError(err.message || 'Error al cargar órdenes de compra');
    } finally {
      setLoading(false);
    }
  };

  const filteredPOs = pos.filter((po) =>
    po.vendor_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    po.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
    po.po_number.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('es-MX', {
      style: 'currency',
      currency: 'MXN',
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('es-MX', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const totalAmount = filteredPOs.reduce((sum, po) => sum + po.total_amount, 0);
  const approvedAmount = pos
    .filter(po => po.status === 'approved')
    .reduce((sum, po) => sum + po.total_amount, 0);
  const invoicedAmount = pos
    .filter(po => po.status === 'invoiced')
    .reduce((sum, po) => sum + po.total_amount, 0);

  return (
    <ProtectedRoute>
      <AppLayout>
        <div className="space-y-8">
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
              <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6 mb-8">
                <div className="flex-1">
                  <motion.h1
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.1 }}
                    className="text-4xl font-bold mb-3 bg-gradient-to-r from-white to-gray-300 bg-clip-text text-transparent"
                  >
                    Órdenes de Compra
                  </motion.h1>
                  <motion.p
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.2 }}
                    className="text-gray-300 text-lg"
                  >
                    Planifica y da seguimiento a tus compras antes de recibir factura
                  </motion.p>
                </div>

                <motion.button
                  whileHover={{ scale: 1.05, y: -2 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => router.push('/purchase-orders/create')}
                  className="flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-[#60b97b] to-[#4a9460] text-white rounded-xl font-semibold shadow-lg hover:shadow-2xl transition-all hover:shadow-[#60b97b]/50"
                >
                  <Plus className="w-5 h-5" />
                  Nueva Orden
                </motion.button>
              </div>

              {/* Modern Stats Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  {
                    label: 'Total Órdenes',
                    value: filteredPOs.length,
                    icon: ShoppingCart,
                    gradient: 'from-blue-500 to-blue-600',
                    bg: 'bg-blue-500/10',
                    border: 'border-blue-500/20'
                  },
                  {
                    label: 'Monto Total',
                    value: formatCurrency(totalAmount),
                    icon: DollarSign,
                    gradient: 'from-emerald-500 to-emerald-600',
                    bg: 'bg-emerald-500/10',
                    border: 'border-emerald-500/20'
                  },
                  {
                    label: 'Aprobadas',
                    value: `${pos.filter(p => p.status === 'approved').length} (${formatCurrency(approvedAmount)})`,
                    icon: CheckCircle2,
                    gradient: 'from-green-500 to-green-600',
                    bg: 'bg-green-500/10',
                    border: 'border-green-500/20'
                  },
                  {
                    label: 'Facturadas',
                    value: `${pos.filter(p => p.status === 'invoiced').length} (${formatCurrency(invoicedAmount)})`,
                    icon: Receipt,
                    gradient: 'from-purple-500 to-purple-600',
                    bg: 'bg-purple-500/10',
                    border: 'border-purple-500/20'
                  },
                ].map((stat, index) => (
                  <motion.div
                    key={stat.label}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 + index * 0.05 }}
                    whileHover={{ y: -4, scale: 1.02 }}
                    className={`${stat.bg} ${stat.border} backdrop-blur-sm rounded-xl p-5 border hover:shadow-lg transition-all cursor-pointer`}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className={`p-3 bg-gradient-to-br ${stat.gradient} rounded-lg shadow-lg`}>
                        <stat.icon className="w-6 h-6 text-white" />
                      </div>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-white mb-1">
                        {stat.value}
                      </p>
                      <p className="text-sm text-gray-400 font-medium">
                        {stat.label}
                      </p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>

          {/* Filters */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-gray-200/50 p-6 space-y-5"
          >
            {/* Search and Main Filters Row */}
            <div className="flex flex-col md:flex-row gap-4">
              {/* Search */}
              <div className="flex-1 relative group">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-[#11446e] transition-colors" />
                <input
                  type="text"
                  placeholder="Buscar por proveedor, descripción o número PO..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-12 pr-4 py-3.5 bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:border-[#11446e] focus:shadow-lg focus:shadow-[#11446e]/10 transition-all"
                />
                {searchTerm && (
                  <motion.button
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    exit={{ scale: 0 }}
                    onClick={() => setSearchTerm('')}
                    className="absolute right-4 top-1/2 -translate-y-1/2 p-1 hover:bg-gray-100 rounded-full transition-colors"
                  >
                    <X className="w-4 h-4 text-gray-400" />
                  </motion.button>
                )}
              </div>

              {/* Status Filter */}
              <div className="relative group">
                <Filter className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none group-focus-within:text-[#11446e] transition-colors" />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value as POStatus | 'all')}
                  className="pl-12 pr-10 py-3.5 bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-xl text-gray-900 focus:outline-none focus:border-[#11446e] focus:shadow-lg focus:shadow-[#11446e]/10 transition-all appearance-none cursor-pointer min-w-[280px]"
                >
                  <option value="all">Todos los estados</option>
                  <option value="draft">Borradores</option>
                  <option value="pending_approval">Pendientes de Aprobación</option>
                  <option value="approved">Aprobadas</option>
                  <option value="rejected">Rechazadas</option>
                  <option value="sent_to_vendor">Enviadas a Proveedor</option>
                  <option value="received">Recibidas</option>
                  <option value="invoiced">Facturadas</option>
                  <option value="cancelled">Canceladas</option>
                </select>
                <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none">
                  <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </div>
            </div>

            {/* Active Filters Indicator */}
            {(searchTerm || statusFilter !== 'all') && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="flex items-center gap-2 pt-3 border-t border-gray-200"
              >
                <span className="text-sm font-medium text-gray-600">Filtros activos:</span>
                <div className="flex gap-2 flex-wrap">
                  {searchTerm && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-lg"
                    >
                      <Search className="w-3.5 h-3.5 text-blue-600" />
                      <span className="text-sm text-blue-700">&quot;{searchTerm}&quot;</span>
                      <button
                        onClick={() => setSearchTerm('')}
                        className="ml-1 hover:bg-blue-100 rounded-full p-0.5 transition-colors"
                      >
                        <X className="w-3.5 h-3.5 text-blue-600" />
                      </button>
                    </motion.div>
                  )}
                  {statusFilter !== 'all' && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="flex items-center gap-2 px-3 py-1.5 bg-purple-50 border border-purple-200 rounded-lg"
                    >
                      <Filter className="w-3.5 h-3.5 text-purple-600" />
                      <span className="text-sm text-purple-700 capitalize">{statusConfig[statusFilter].label}</span>
                      <button
                        onClick={() => setStatusFilter('all')}
                        className="ml-1 hover:bg-purple-100 rounded-full p-0.5 transition-colors"
                      >
                        <X className="w-3.5 h-3.5 text-purple-600" />
                      </button>
                    </motion.div>
                  )}
                  <button
                    onClick={() => {
                      setSearchTerm('');
                      setStatusFilter('all');
                    }}
                    className="text-sm text-gray-500 hover:text-gray-700 underline transition-colors"
                  >
                    Limpiar todos
                  </button>
                </div>
              </motion.div>
            )}
          </motion.div>

          {/* POs List */}
          <AnimatePresence mode="wait">
            {loading ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center justify-center py-20"
              >
                <Loader2 className="w-8 h-8 text-[#11446e] animate-spin" />
              </motion.div>
            ) : error ? (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="bg-red-50 border border-red-200 rounded-xl p-6"
              >
                <div className="flex items-center gap-3">
                  <AlertCircle className="w-6 h-6 text-red-600" />
                  <div>
                    <h3 className="font-semibold text-red-900">Error</h3>
                    <p className="text-sm text-red-700">{error}</p>
                  </div>
                </div>
              </motion.div>
            ) : filteredPOs.length === 0 ? (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center"
              >
                <ShoppingCart className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  No hay órdenes de compra
                </h3>
                <p className="text-gray-600 mb-6">
                  {searchTerm || statusFilter !== 'all'
                    ? 'No se encontraron órdenes con los filtros aplicados'
                    : 'Crea tu primera orden de compra para comenzar'}
                </p>
                <button
                  onClick={() => router.push('/purchase-orders/create')}
                  className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-[#11446e] to-[#0d3454] text-white rounded-xl font-semibold shadow-sm hover:shadow-md transition-all"
                >
                  <Plus className="w-5 h-5" />
                  Crear Orden de Compra
                </button>
              </motion.div>
            ) : (
              <div className="grid gap-4">
                {filteredPOs.map((po, index) => {
                  const StatusIcon = statusConfig[po.status].icon;

                  return (
                    <motion.div
                      key={po.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                      onClick={() => router.push(`/purchase-orders/${po.id}`)}
                      className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md hover:border-[#11446e]/30 transition-all cursor-pointer"
                    >
                      <div className="flex items-start justify-between gap-6">
                        {/* Left section: PO info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start gap-4">
                            <div className="flex-shrink-0 w-12 h-12 bg-gradient-to-br from-[#11446e]/10 to-[#60b97b]/10 rounded-xl flex items-center justify-center">
                              <ShoppingCart className="w-6 h-6 text-[#11446e]" />
                            </div>

                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-3 mb-2">
                                <h3 className="font-semibold text-gray-900 text-lg">
                                  {po.vendor_name}
                                </h3>
                                <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded-lg text-xs font-bold">
                                  {po.po_number}
                                </span>
                              </div>

                              <p className="text-gray-700 mb-3 line-clamp-2">
                                {po.description}
                              </p>

                              <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600 mb-3">
                                <div className="flex items-center gap-1.5">
                                  <Calendar className="w-4 h-4 text-gray-400" />
                                  {formatDate(po.created_at)}
                                </div>
                                {po.project_name && (
                                  <div className="flex items-center gap-1.5">
                                    <FileText className="w-4 h-4 text-gray-400" />
                                    {po.project_name}
                                  </div>
                                )}
                                {po.department_name && (
                                  <div className="flex items-center gap-1.5">
                                    <Building2 className="w-4 h-4 text-gray-400" />
                                    {po.department_name}
                                  </div>
                                )}
                                {po.requester_name && (
                                  <div className="flex items-center gap-1.5">
                                    <User className="w-4 h-4 text-gray-400" />
                                    {po.requester_name}
                                  </div>
                                )}
                              </div>

                              <div className="flex items-center gap-3">
                                <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold ${statusConfig[po.status].bgColor} ${statusConfig[po.status].color}`}>
                                  <StatusIcon className="w-4 h-4" />
                                  {statusConfig[po.status].label}
                                </span>

                                {po.approved_at && (
                                  <span className="text-xs text-gray-500">
                                    Aprobado {formatDate(po.approved_at)}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Right section: Amount and action */}
                        <div className="flex flex-col items-end gap-3 flex-shrink-0">
                          <div className="text-right">
                            <p className="text-2xl font-bold text-[#11446e]">
                              {formatCurrency(po.total_amount)}
                            </p>
                            <p className="text-xs text-gray-500">
                              {po.currency}
                            </p>
                          </div>

                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              router.push(`/purchase-orders/${po.id}`);
                            }}
                            className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-medium text-sm transition-colors"
                          >
                            <Eye className="w-4 h-4" />
                            Ver Detalle
                          </button>
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            )}
          </AnimatePresence>
        </div>
      </AppLayout>
    </ProtectedRoute>
  );
}

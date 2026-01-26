'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  FileText,
  Calendar,
  DollarSign,
  User,
  Building2,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Send,
  Ban,
  Loader2,
  Package,
} from 'lucide-react';
import { AppLayout } from '@/components/layout/AppLayout';
import { InvoiceLinkingPanel } from '@/components/purchase-orders/InvoiceLinkingPanel';
import {
  getPurchaseOrder,
  linkInvoiceToPO,
  unlinkInvoiceFromPO,
  approvePurchaseOrder,
  rejectPurchaseOrder,
  cancelPurchaseOrder,
  type PurchaseOrder,
  type POStatus,
} from '@/services/purchaseOrdersService';

export default function PurchaseOrderDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const [po, setPO] = useState<PurchaseOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    if (id) {
      loadPO();
    }
  }, [id]);

  const loadPO = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getPurchaseOrder(Number(id));
      setPO(data);
    } catch (error: any) {
      console.error('Error loading PO:', error);
      setError(error.message || 'Error al cargar la orden de compra');
    } finally {
      setLoading(false);
    }
  };

  const handleLinkInvoice = async (
    invoiceId: string,
    type: string,
    amount: number,
    notes?: string
  ) => {
    try {
      await linkInvoiceToPO(Number(id), {
        sat_invoice_id: invoiceId,
        invoice_type: type as any,
        invoice_amount: amount,
        notes,
      });
      await loadPO();
    } catch (error: any) {
      console.error('Error linking invoice:', error);
      throw error;
    }
  };

  const handleUnlinkInvoice = async (invoiceId: number) => {
    if (!confirm('¿Seguro que deseas desvincular esta factura?')) return;

    try {
      await unlinkInvoiceFromPO(Number(id), invoiceId);
      await loadPO();
    } catch (error: any) {
      console.error('Error unlinking invoice:', error);
      alert(error.message || 'Error al desvincular factura');
    }
  };

  const handleApprove = async () => {
    if (!confirm('¿Aprobar esta orden de compra?')) return;

    try {
      setActionLoading(true);
      await approvePurchaseOrder(Number(id), {});
      await loadPO();
    } catch (error: any) {
      console.error('Error approving PO:', error);
      alert(error.message || 'Error al aprobar la orden');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    const reason = prompt('Motivo del rechazo:');
    if (!reason) return;

    try {
      setActionLoading(true);
      await rejectPurchaseOrder(Number(id), { rejection_reason: reason });
      await loadPO();
    } catch (error: any) {
      console.error('Error rejecting PO:', error);
      alert(error.message || 'Error al rechazar la orden');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!confirm('¿Cancelar esta orden de compra? Esta acción no se puede deshacer.')) return;

    try {
      setActionLoading(true);
      await cancelPurchaseOrder(Number(id));
      await loadPO();
    } catch (error: any) {
      console.error('Error canceling PO:', error);
      alert(error.message || 'Error al cancelar la orden');
    } finally {
      setActionLoading(false);
    }
  };

  const getStatusBadge = (status: POStatus) => {
    const configs = {
      draft: {
        label: 'Borrador',
        icon: FileText,
        color: 'bg-gray-100 text-gray-700 border-gray-300',
      },
      pending_approval: {
        label: 'Pendiente Aprobación',
        icon: Clock,
        color: 'bg-yellow-100 text-yellow-700 border-yellow-300',
      },
      approved: {
        label: 'Aprobada',
        icon: CheckCircle2,
        color: 'bg-green-100 text-green-700 border-green-300',
      },
      rejected: {
        label: 'Rechazada',
        icon: XCircle,
        color: 'bg-red-100 text-red-700 border-red-300',
      },
      sent_to_vendor: {
        label: 'Enviada a Proveedor',
        icon: Send,
        color: 'bg-blue-100 text-blue-700 border-blue-300',
      },
      received: {
        label: 'Recibida',
        icon: Package,
        color: 'bg-purple-100 text-purple-700 border-purple-300',
      },
      invoiced: {
        label: 'Facturada',
        icon: FileText,
        color: 'bg-indigo-100 text-indigo-700 border-indigo-300',
      },
      cancelled: {
        label: 'Cancelada',
        icon: Ban,
        color: 'bg-gray-100 text-gray-500 border-gray-300',
      },
    };

    const config = configs[status] || configs.draft;
    const Icon = config.icon;

    return (
      <div
        className={`inline-flex items-center gap-2 px-4 py-2 rounded-full border-2 font-semibold ${config.color}`}
      >
        <Icon className="w-4 h-4" />
        {config.label}
      </div>
    );
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('es-MX', {
      style: 'currency',
      currency: 'MXN',
    }).format(amount);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('es-MX', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-center space-y-4">
            <Loader2 className="w-12 h-12 text-[#11446e] animate-spin mx-auto" />
            <p className="text-gray-600">Cargando orden de compra...</p>
          </div>
        </div>
      </AppLayout>
    );
  }

  if (error || !po) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-center space-y-4">
            <AlertCircle className="w-12 h-12 text-red-500 mx-auto" />
            <p className="text-red-600">{error || 'No se encontró la orden de compra'}</p>
            <button
              onClick={() => router.push('/purchase-orders')}
              className="px-4 py-2 bg-[#11446e] text-white rounded-lg hover:bg-[#0d3552] transition-colors"
            >
              Volver a órdenes
            </button>
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="max-w-6xl mx-auto space-y-8 p-6">
        {/* Header */}
        <div>
          <button
            onClick={() => router.push('/purchase-orders')}
            className="inline-flex items-center gap-2 text-gray-600 hover:text-[#11446e] transition-colors mb-6"
          >
            <ArrowLeft className="w-5 h-5" />
            Volver a órdenes
          </button>

          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-4 mb-2">
                <h1 className="text-3xl font-bold text-gray-900">
                  Orden #{po.po_number}
                </h1>
                {getStatusBadge(po.status)}
              </div>
              <p className="text-gray-600">
                Creada el {formatDate(po.created_at)}
              </p>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3">
              {po.status === 'pending_approval' && (
                <>
                  <button
                    onClick={handleApprove}
                    disabled={actionLoading}
                    className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-semibold transition-colors disabled:opacity-50"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    Aprobar
                  </button>
                  <button
                    onClick={handleReject}
                    disabled={actionLoading}
                    className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-semibold transition-colors disabled:opacity-50"
                  >
                    <XCircle className="w-4 h-4" />
                    Rechazar
                  </button>
                </>
              )}

              {po.status !== 'cancelled' && !['pending_approval', 'rejected'].includes(po.status) && (
                <button
                  onClick={handleCancel}
                  disabled={actionLoading}
                  className="flex items-center gap-2 px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg font-semibold transition-colors disabled:opacity-50"
                >
                  <Ban className="w-4 h-4" />
                  Cancelar Orden
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Details Card */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Vendor Info */}
          <div className="p-6 bg-white border-2 border-gray-200 rounded-2xl space-y-4">
            <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              <Building2 className="w-5 h-5 text-[#11446e]" />
              Información del Proveedor
            </h3>
            <div className="space-y-3">
              <div>
                <label className="text-sm font-semibold text-gray-500">Nombre</label>
                <p className="text-gray-900 font-medium">{po.vendor_name}</p>
              </div>
              {po.vendor_rfc && (
                <div>
                  <label className="text-sm font-semibold text-gray-500">RFC</label>
                  <p className="text-gray-900 font-mono">{po.vendor_rfc}</p>
                </div>
              )}
              {po.vendor_email && (
                <div>
                  <label className="text-sm font-semibold text-gray-500">Email</label>
                  <p className="text-gray-900">{po.vendor_email}</p>
                </div>
              )}
              {po.vendor_phone && (
                <div>
                  <label className="text-sm font-semibold text-gray-500">Teléfono</label>
                  <p className="text-gray-900">{po.vendor_phone}</p>
                </div>
              )}
            </div>
          </div>

          {/* Project & Financial Info */}
          <div className="p-6 bg-white border-2 border-gray-200 rounded-2xl space-y-4">
            <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-[#11446e]" />
              Información Financiera
            </h3>
            <div className="space-y-3">
              <div>
                <label className="text-sm font-semibold text-gray-500">Monto Total</label>
                <p className="text-2xl font-bold text-gray-900">
                  {formatCurrency(po.total_amount)}
                </p>
              </div>
              {po.project_name && (
                <div>
                  <label className="text-sm font-semibold text-gray-500">Proyecto</label>
                  <p className="text-gray-900">{po.project_name}</p>
                </div>
              )}
              {po.department_name && (
                <div>
                  <label className="text-sm font-semibold text-gray-500">Departamento</label>
                  <p className="text-gray-900">{po.department_name}</p>
                </div>
              )}
              {po.requester_name && (
                <div>
                  <label className="text-sm font-semibold text-gray-500">Solicitante</label>
                  <p className="text-gray-900">{po.requester_name}</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Description */}
        <div className="p-6 bg-white border-2 border-gray-200 rounded-2xl">
          <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
            <FileText className="w-5 h-5 text-[#11446e]" />
            Descripción
          </h3>
          <p className="text-gray-700 whitespace-pre-wrap">{po.description}</p>
          {po.notes && (
            <div className="mt-4 p-4 bg-gray-50 rounded-xl">
              <label className="text-sm font-semibold text-gray-500 block mb-2">Notas</label>
              <p className="text-gray-700 whitespace-pre-wrap">{po.notes}</p>
            </div>
          )}
        </div>

        {/* Line Items (Read-only) */}
        {po.lines && po.lines.length > 0 && (
          <div className="p-6 bg-white border-2 border-gray-200 rounded-2xl">
            <h3 className="text-lg font-bold text-gray-900 mb-6 flex items-center gap-2">
              <Package className="w-5 h-5 text-[#11446e]" />
              Líneas de Productos
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b-2 border-gray-200">
                    <th className="text-left py-3 px-4 text-sm font-semibold text-gray-600">#</th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-gray-600">Descripción</th>
                    <th className="text-right py-3 px-4 text-sm font-semibold text-gray-600">Cantidad</th>
                    <th className="text-right py-3 px-4 text-sm font-semibold text-gray-600">Precio Unit.</th>
                    <th className="text-right py-3 px-4 text-sm font-semibold text-gray-600">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {po.lines.map((line: any, index: number) => (
                    <tr key={index} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-3 px-4 text-gray-600">{line.line_number}</td>
                      <td className="py-3 px-4">
                        <div>
                          <p className="font-medium text-gray-900">{line.description}</p>
                          {line.sku && (
                            <p className="text-sm text-gray-500">SKU: {line.sku}</p>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-4 text-right text-gray-900">
                        {line.quantity} {line.unit_of_measure}
                      </td>
                      <td className="py-3 px-4 text-right text-gray-900">
                        {formatCurrency(line.unit_price)}
                      </td>
                      <td className="py-3 px-4 text-right font-semibold text-gray-900">
                        {formatCurrency(line.line_total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Invoice Linking Panel */}
        {po.status !== 'cancelled' && po.status !== 'draft' && po.vendor_rfc && (
          <InvoiceLinkingPanel
            poId={po.id}
            poTotal={po.total_amount}
            vendorRFC={po.vendor_rfc}
            linkedInvoices={(po as any).linked_invoices || []}
            onLinkInvoice={handleLinkInvoice}
            onUnlinkInvoice={handleUnlinkInvoice}
          />
        )}

        {/* Timeline */}
        <div className="p-6 bg-white border-2 border-gray-200 rounded-2xl">
          <h3 className="text-lg font-bold text-gray-900 mb-6 flex items-center gap-2">
            <Calendar className="w-5 h-5 text-[#11446e]" />
            Historial
          </h3>
          <div className="space-y-4">
            <div className="flex items-start gap-4">
              <div className="p-2 bg-gray-100 rounded-lg">
                <FileText className="w-4 h-4 text-gray-600" />
              </div>
              <div>
                <p className="font-semibold text-gray-900">Orden creada</p>
                <p className="text-sm text-gray-500">{formatDate(po.created_at)}</p>
              </div>
            </div>

            {po.approved_at && (
              <div className="flex items-start gap-4">
                <div className="p-2 bg-green-100 rounded-lg">
                  <CheckCircle2 className="w-4 h-4 text-green-600" />
                </div>
                <div>
                  <p className="font-semibold text-gray-900">Orden aprobada</p>
                  <p className="text-sm text-gray-500">{formatDate(po.approved_at)}</p>
                  {po.approver_name && (
                    <p className="text-sm text-gray-600">por {po.approver_name}</p>
                  )}
                </div>
              </div>
            )}

            {po.rejected_at && (
              <div className="flex items-start gap-4">
                <div className="p-2 bg-red-100 rounded-lg">
                  <XCircle className="w-4 h-4 text-red-600" />
                </div>
                <div>
                  <p className="font-semibold text-gray-900">Orden rechazada</p>
                  <p className="text-sm text-gray-500">{formatDate(po.rejected_at)}</p>
                  {po.rejection_reason && (
                    <p className="text-sm text-gray-600 mt-1">
                      Motivo: {po.rejection_reason}
                    </p>
                  )}
                </div>
              </div>
            )}

            {po.sent_at && (
              <div className="flex items-start gap-4">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <Send className="w-4 h-4 text-blue-600" />
                </div>
                <div>
                  <p className="font-semibold text-gray-900">Enviada a proveedor</p>
                  <p className="text-sm text-gray-500">{formatDate(po.sent_at)}</p>
                </div>
              </div>
            )}

            {po.received_at && (
              <div className="flex items-start gap-4">
                <div className="p-2 bg-purple-100 rounded-lg">
                  <Package className="w-4 h-4 text-purple-600" />
                </div>
                <div>
                  <p className="font-semibold text-gray-900">Mercancía recibida</p>
                  <p className="text-sm text-gray-500">{formatDate(po.received_at)}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

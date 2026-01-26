/**
 * Smart Invoice Linking Panel
 * Auto-detects unlinked invoices from same vendor
 * Modern UX for B2B partial invoicing (anticipo/finiquito)
 */

'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileText,
  Plus,
  CheckCircle2,
  AlertCircle,
  Loader2,
  X,
  TrendingUp,
  Link as LinkIcon,
  ExternalLink,
} from 'lucide-react';

interface LinkedInvoice {
  id: number;
  sat_invoice_id: string;
  invoice_type: 'anticipo' | 'parcial' | 'finiquito' | 'total';
  invoice_amount: number;
  linked_at: string;
  notes?: string;
}

interface SuggestedInvoice {
  id: string;
  folio?: string;
  total: number;
  fecha: string;
  emisor_nombre: string;
}

interface InvoiceLinkingPanelProps {
  poId?: number;
  poTotal: number;
  vendorRFC?: string;
  linkedInvoices: LinkedInvoice[];
  onLinkInvoice?: (invoiceId: string, type: string, amount: number, notes?: string) => Promise<void>;
  onUnlinkInvoice?: (invoiceId: number) => Promise<void>;
}

export function InvoiceLinkingPanel({
  poId,
  poTotal,
  vendorRFC,
  linkedInvoices = [],
  onLinkInvoice,
  onUnlinkInvoice,
}: InvoiceLinkingPanelProps) {
  const [suggestedInvoices, setSuggestedInvoices] = useState<SuggestedInvoice[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [showLinkForm, setShowLinkForm] = useState(false);
  const [linkingInvoice, setLinkingInvoice] = useState(false);

  // Link form state
  const [selectedInvoiceId, setSelectedInvoiceId] = useState('');
  const [invoiceType, setInvoiceType] = useState<'anticipo' | 'parcial' | 'finiquito' | 'total'>('finiquito');
  const [linkAmount, setLinkAmount] = useState(0);
  const [linkNotes, setLinkNotes] = useState('');

  const totalInvoiced = linkedInvoices.reduce((sum, inv) => sum + inv.invoice_amount, 0);
  const pendingAmount = poTotal - totalInvoiced;
  const invoicingProgress = poTotal > 0 ? (totalInvoiced / poTotal) * 100 : 0;

  useEffect(() => {
    if (vendorRFC && poId) {
      loadSuggestedInvoices();
    }
  }, [vendorRFC, poId]);

  const loadSuggestedInvoices = async () => {
    try {
      setLoadingSuggestions(true);
      // TODO: Fetch unlinked invoices from same vendor
      // const response = await fetch(`/api/invoices/unlinked?vendor_rfc=${vendorRFC}`);
      // const data = await response.json();
      // setSuggestedInvoices(data);

      // Mock data for now
      setSuggestedInvoices([
        {
          id: 'ABC-123-456',
          folio: 'A1234',
          total: pendingAmount,
          fecha: '2024-12-15',
          emisor_nombre: 'PROVEEDOR SA',
        },
      ]);
    } catch (error) {
      console.error('Error loading suggested invoices:', error);
    } finally {
      setLoadingSuggestions(false);
    }
  };

  const handleLinkClick = (invoice?: SuggestedInvoice) => {
    if (invoice) {
      setSelectedInvoiceId(invoice.id);
      setLinkAmount(invoice.total);

      // Smart default: if this is the first invoice and covers 30-60% of PO, it's probably an anticipo
      if (linkedInvoices.length === 0 && invoice.total >= poTotal * 0.3 && invoice.total < poTotal * 0.8) {
        setInvoiceType('anticipo');
      } else if (invoice.total >= poTotal * 0.95) {
        setInvoiceType('total');
      } else {
        setInvoiceType('finiquito');
      }
    }
    setShowLinkForm(true);
  };

  const handleLink = async () => {
    if (!onLinkInvoice || !selectedInvoiceId) return;

    try {
      setLinkingInvoice(true);
      await onLinkInvoice(selectedInvoiceId, invoiceType, linkAmount, linkNotes);

      // Reset form
      setShowLinkForm(false);
      setSelectedInvoiceId('');
      setLinkAmount(0);
      setLinkNotes('');

      // Refresh suggestions
      loadSuggestedInvoices();
    } catch (error) {
      console.error('Error linking invoice:', error);
    } finally {
      setLinkingInvoice(false);
    }
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
      month: 'short',
      day: 'numeric',
    });
  };

  const getInvoiceTypeLabel = (type: string) => {
    const labels = {
      anticipo: 'Anticipo',
      parcial: 'Pago Parcial',
      finiquito: 'Finiquito',
      total: 'Pago Total',
    };
    return labels[type as keyof typeof labels] || type;
  };

  const getInvoiceTypeBadgeColor = (type: string) => {
    const colors = {
      anticipo: 'bg-blue-100 text-blue-700 border-blue-200',
      parcial: 'bg-yellow-100 text-yellow-700 border-yellow-200',
      finiquito: 'bg-green-100 text-green-700 border-green-200',
      total: 'bg-purple-100 text-purple-700 border-purple-200',
    };
    return colors[type as keyof typeof colors] || 'bg-gray-100 text-gray-700 border-gray-200';
  };

  return (
    <div className="space-y-6">
      {/* Progress Header */}
      <div className="p-6 bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-2xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-gray-900">
              Facturación de la Orden
            </h3>
            <p className="text-sm text-gray-500">
              {linkedInvoices.length === 0
                ? 'Sin facturas vinculadas'
                : `${linkedInvoices.length} ${linkedInvoices.length === 1 ? 'factura vinculada' : 'facturas vinculadas'}`}
            </p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-gray-900">
              {formatCurrency(totalInvoiced)}
            </div>
            <div className="text-sm text-gray-500">
              de {formatCurrency(poTotal)}
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="relative h-3 bg-gray-200 rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${invoicingProgress}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            className={`absolute inset-y-0 left-0 rounded-full ${
              invoicingProgress >= 100
                ? 'bg-gradient-to-r from-green-500 to-green-600'
                : invoicingProgress >= 50
                ? 'bg-gradient-to-r from-yellow-500 to-yellow-600'
                : 'bg-gradient-to-r from-blue-500 to-blue-600'
            }`}
          />
        </div>

        <div className="flex items-center justify-between mt-2 text-xs">
          <span className="text-gray-600">
            {invoicingProgress.toFixed(0)}% facturado
          </span>
          {pendingAmount > 0 && (
            <span className="font-semibold text-gray-700">
              Pendiente: {formatCurrency(pendingAmount)}
            </span>
          )}
        </div>
      </div>

      {/* Linked Invoices */}
      {linkedInvoices.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-semibold text-gray-700">
            Facturas Vinculadas
          </h4>

          {linkedInvoices.map((invoice) => (
            <motion.div
              key={invoice.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center justify-between p-4 bg-white border-2 border-gray-200 rounded-xl hover:border-[#11446e]/30 transition-colors group"
            >
              <div className="flex items-center gap-4 flex-1">
                <div className="p-2 bg-green-50 rounded-lg">
                  <CheckCircle2 className="w-5 h-5 text-green-600" />
                </div>

                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-sm font-semibold text-gray-900">
                      {invoice.sat_invoice_id.substring(0, 8)}...
                    </span>
                    <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${getInvoiceTypeBadgeColor(invoice.invoice_type)}`}>
                      {getInvoiceTypeLabel(invoice.invoice_type)}
                    </span>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    <span>{formatDate(invoice.linked_at)}</span>
                    {invoice.notes && (
                      <span className="truncate max-w-xs">• {invoice.notes}</span>
                    )}
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-lg font-bold text-gray-900">
                    {formatCurrency(invoice.invoice_amount)}
                  </div>
                  <div className="text-xs text-gray-500">
                    {((invoice.invoice_amount / poTotal) * 100).toFixed(0)}% del total
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 ml-4">
                <button className="p-2 text-gray-400 hover:text-[#11446e] transition-colors opacity-0 group-hover:opacity-100">
                  <ExternalLink className="w-4 h-4" />
                </button>
                {onUnlinkInvoice && (
                  <button
                    onClick={() => onUnlinkInvoice(invoice.id)}
                    className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Suggested Invoices */}
      {pendingAmount > 0 && !showLinkForm && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-gray-700">
              Facturas Sugeridas
            </h4>
            {loadingSuggestions && (
              <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />
            )}
          </div>

          {suggestedInvoices.length > 0 ? (
            <div className="space-y-2">
              {suggestedInvoices.map((invoice) => (
                <motion.div
                  key={invoice.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex items-center justify-between p-4 bg-blue-50 border-2 border-blue-200 rounded-xl hover:border-blue-300 transition-colors cursor-pointer"
                  onClick={() => handleLinkClick(invoice)}
                >
                  <div className="flex items-center gap-4">
                    <div className="p-2 bg-blue-100 rounded-lg">
                      <FileText className="w-5 h-5 text-blue-600" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-sm font-semibold text-gray-900">
                          {invoice.id.substring(0, 8)}...
                        </span>
                        {invoice.folio && (
                          <span className="text-xs text-gray-500">
                            Folio: {invoice.folio}
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-gray-600">
                        {formatDate(invoice.fecha)} • {invoice.emisor_nombre}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <div className="text-lg font-bold text-gray-900">
                        {formatCurrency(invoice.total)}
                      </div>
                    </div>
                    <button className="p-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
                      <LinkIcon className="w-4 h-4" />
                    </button>
                  </div>
                </motion.div>
              ))}
            </div>
          ) : (
            <div className="p-8 bg-gray-50 border-2 border-dashed border-gray-300 rounded-xl text-center">
              <FileText className="w-8 h-8 text-gray-400 mx-auto mb-3" />
              <p className="text-sm text-gray-500 mb-4">
                No se encontraron facturas sin vincular del mismo proveedor
              </p>
              <button
                onClick={() => handleLinkClick()}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-[#11446e] hover:bg-gray-100 rounded-lg transition-colors"
              >
                <Plus className="w-4 h-4" />
                Vincular factura manualmente
              </button>
            </div>
          )}
        </div>
      )}

      {/* Link Form (Modal-like) */}
      <AnimatePresence>
        {showLinkForm && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="p-6 bg-white border-2 border-[#11446e] rounded-2xl shadow-xl space-y-4"
          >
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-lg font-bold text-gray-900">
                Vincular Factura SAT
              </h4>
              <button
                onClick={() => setShowLinkForm(false)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            {/* Invoice UUID */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                UUID de Factura SAT
              </label>
              <input
                type="text"
                value={selectedInvoiceId}
                onChange={(e) => setSelectedInvoiceId(e.target.value)}
                placeholder="1FD2B97C-1CE0-4A0D-8497-DE8B7C98D416"
                className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-[#11446e] focus:ring-2 focus:ring-[#11446e]/20 transition-all font-mono text-sm"
              />
            </div>

            {/* Invoice Type (Smart Radio Buttons) */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-3">
                Tipo de Factura
              </label>
              <div className="grid grid-cols-2 gap-3">
                {(['anticipo', 'parcial', 'finiquito', 'total'] as const).map((type) => (
                  <button
                    key={type}
                    onClick={() => setInvoiceType(type)}
                    className={`p-4 border-2 rounded-xl text-left transition-all ${
                      invoiceType === type
                        ? 'border-[#11446e] bg-[#11446e]/5 ring-2 ring-[#11446e]/20'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                        invoiceType === type
                          ? 'border-[#11446e]'
                          : 'border-gray-300'
                      }`}>
                        {invoiceType === type && (
                          <div className="w-2 h-2 rounded-full bg-[#11446e]" />
                        )}
                      </div>
                      <span className="font-semibold text-sm text-gray-900">
                        {getInvoiceTypeLabel(type)}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 ml-6">
                      {type === 'anticipo' && 'Pago adelantado (30-50%)'}
                      {type === 'parcial' && 'Pago en partes'}
                      {type === 'finiquito' && 'Pago final restante'}
                      {type === 'total' && 'Pago completo (100%)'}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            {/* Amount */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Monto a Vincular
              </label>
              <div className="relative">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500">$</span>
                <input
                  type="number"
                  value={linkAmount}
                  onChange={(e) => setLinkAmount(parseFloat(e.target.value) || 0)}
                  min="0"
                  step="0.01"
                  className="w-full pl-8 pr-4 py-3 border-2 border-gray-200 rounded-xl focus:border-[#11446e] focus:ring-2 focus:ring-[#11446e]/20 transition-all"
                />
              </div>
              <div className="mt-2 flex items-center justify-between text-xs">
                <span className="text-gray-500">
                  Pendiente: {formatCurrency(pendingAmount)}
                </span>
                {linkAmount > 0 && (
                  <button
                    onClick={() => setLinkAmount(pendingAmount)}
                    className="text-[#11446e] hover:text-[#60b97b] font-medium"
                  >
                    Usar monto pendiente
                  </button>
                )}
              </div>
            </div>

            {/* Notes */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Notas (Opcional)
              </label>
              <textarea
                value={linkNotes}
                onChange={(e) => setLinkNotes(e.target.value)}
                placeholder="Información adicional sobre esta vinculación..."
                rows={2}
                className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-[#11446e] focus:ring-2 focus:ring-[#11446e]/20 transition-all resize-none"
              />
            </div>

            {/* Actions */}
            <div className="flex gap-3 pt-4">
              <button
                onClick={() => setShowLinkForm(false)}
                className="flex-1 px-4 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl font-semibold transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleLink}
                disabled={!selectedInvoiceId || linkAmount <= 0 || linkingInvoice}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-[#60b97b] to-[#4a9460] hover:from-[#4a9460] hover:to-[#60b97b] text-white rounded-xl font-semibold shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {linkingInvoice ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Vinculando...
                  </>
                ) : (
                  <>
                    <LinkIcon className="w-5 h-5" />
                    Vincular Factura
                  </>
                )}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

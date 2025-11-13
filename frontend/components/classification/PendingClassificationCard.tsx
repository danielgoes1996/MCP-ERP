/**
 * Pending Classification Card Component
 *
 * Displays a single invoice with pending AI classification
 */

'use client';

import { useState } from 'react';
import type { PendingInvoice } from '@/services/classificationService';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';

interface PendingClassificationCardProps {
  invoice: PendingInvoice;
  onConfirm: (sessionId: string) => void;
  onCorrect: (sessionId: string) => void;
  loading?: boolean;
}

/**
 * Get confidence badge color based on percentage
 */
function getConfidenceBadgeClass(confidence: number): string {
  if (confidence >= 0.9) return 'bg-success-100 text-success-700 border-success-300';
  if (confidence >= 0.7) return 'bg-warning-100 text-warning-700 border-warning-300';
  return 'bg-error-100 text-error-700 border-error-300';
}

/**
 * Format currency in MXN
 */
function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('es-MX', {
    style: 'currency',
    currency: 'MXN',
  }).format(amount);
}

/**
 * Format date to readable format
 */
function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('es-MX', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function PendingClassificationCard({
  invoice,
  onConfirm,
  onCorrect,
  loading = false,
}: PendingClassificationCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const confidencePercent = Math.round(invoice.confidence * 100);
  const badgeClass = getConfidenceBadgeClass(invoice.confidence);

  return (
    <Card className="p-6 hover:shadow-lg transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-neutral-800 mb-1">
            {invoice.provider.nombre || invoice.provider.rfc}
          </h3>
          <p className="text-sm text-neutral-600">{invoice.filename}</p>
        </div>

        <div className="flex flex-col items-end gap-2">
          <span className="text-lg font-bold text-neutral-900">
            {formatCurrency(invoice.invoice_total)}
          </span>
          <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${badgeClass}`}>
            {confidencePercent}% Confianza
          </span>
        </div>
      </div>

      {/* Invoice Description */}
      <div className="mb-4 p-3 bg-neutral-50 rounded-lg">
        <p className="text-sm text-neutral-700 font-medium">
          {invoice.description}
        </p>
      </div>

      {/* Classification Result */}
      <div className="mb-4 p-4 bg-primary-50 rounded-lg border border-primary-200">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-primary-600 uppercase tracking-wide">
            Clasificación Sugerida por IA
          </span>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-primary-600 hover:text-primary-700 text-xs font-medium"
          >
            {isExpanded ? 'Ocultar detalles' : 'Ver detalles'}
          </button>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-2xl font-bold text-primary-700">
            {invoice.sat_code}
          </span>
          <span className="text-sm text-neutral-600">
            (Familia {invoice.family_code})
          </span>
        </div>

        <p className="text-sm text-neutral-700 mt-2">
          {invoice.explanation}
        </p>

        {/* Expanded Details */}
        {isExpanded && (
          <div className="mt-4 pt-4 border-t border-primary-200 space-y-2">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="font-medium text-neutral-700">RFC Proveedor:</span>
                <p className="text-neutral-600">{invoice.provider.rfc}</p>
              </div>
              <div>
                <span className="font-medium text-neutral-700">Fecha Subida:</span>
                <p className="text-neutral-600">{formatDate(invoice.created_at)}</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3">
        <Button
          onClick={() => onConfirm(invoice.session_id)}
          disabled={loading}
          className="flex-1 bg-success-600 hover:bg-success-700 text-white"
        >
          {loading ? 'Procesando...' : 'Confirmar Clasificación'}
        </Button>

        <Button
          onClick={() => onCorrect(invoice.session_id)}
          disabled={loading}
          variant="outline"
          className="flex-1 border-warning-600 text-warning-700 hover:bg-warning-50"
        >
          Corregir
        </Button>
      </div>
    </Card>
  );
}

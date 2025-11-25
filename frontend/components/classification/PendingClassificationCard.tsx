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
  onConfirm: (sessionId: string, alternativeCode?: string) => void;
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
  const [showAlternatives, setShowAlternatives] = useState(false);
  const [selectedAlternative, setSelectedAlternative] = useState<string | null>(null);

  const confidencePercent = Math.round(invoice.confidence * 100);
  const badgeClass = getConfidenceBadgeClass(invoice.confidence);
  const hasAlternatives = invoice.alternative_candidates && invoice.alternative_candidates.length > 0;

  return (
    <Card className="p-6 hover:shadow-lg transition-shadow">
      {/* Source Badge */}
      {invoice.source === 'sat_auto_sync' && (
        <div className="mb-3 flex items-center gap-2">
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-800 border border-green-300">
            <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
            </svg>
            Descargada automáticamente del SAT
          </span>
        </div>
      )}

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

      {/* Alternative Candidates Section */}
      {hasAlternatives && (
        <div className="mb-4">
          <button
            onClick={() => setShowAlternatives(!showAlternatives)}
            className="w-full flex items-center justify-between p-3 bg-neutral-50 rounded-lg hover:bg-neutral-100 transition-colors"
          >
            <span className="text-sm font-semibold text-neutral-700">
              Ver clasificaciones alternativas ({invoice.alternative_candidates!.length})
            </span>
            <svg
              className={`w-5 h-5 text-neutral-600 transition-transform ${showAlternatives ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {showAlternatives && (
            <div className="mt-2 p-4 bg-neutral-50 rounded-lg border border-neutral-200 space-y-3">
              <p className="text-xs text-neutral-600 mb-3">
                Otras opciones sugeridas por el sistema. Elige una si es más apropiada:
              </p>

              {invoice.alternative_candidates!.map((candidate, index) => (
                <div
                  key={candidate.code}
                  className={`p-3 rounded-lg border transition-all ${
                    selectedAlternative === candidate.code
                      ? 'bg-primary-50 border-primary-400 shadow-sm'
                      : 'bg-white border-neutral-200 hover:border-primary-300'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-lg font-bold text-neutral-800">
                          {candidate.code}
                        </span>
                        <span className="text-xs text-neutral-500">
                          (Familia {candidate.family_code})
                        </span>
                        <span className="text-xs px-2 py-0.5 bg-neutral-200 text-neutral-700 rounded">
                          {Math.round(candidate.score * 100)}% match
                        </span>
                      </div>
                      <p className="text-sm text-neutral-700 font-medium mb-1">
                        {candidate.name}
                      </p>
                      {candidate.description && (
                        <p className="text-xs text-neutral-600">
                          {candidate.description}
                        </p>
                      )}
                    </div>

                    <Button
                      onClick={() => {
                        setSelectedAlternative(candidate.code);
                      }}
                      variant={selectedAlternative === candidate.code ? 'primary' : 'outline'}
                      className={`ml-3 ${
                        selectedAlternative === candidate.code
                          ? 'bg-primary-600 text-white'
                          : 'border-primary-600 text-primary-700 hover:bg-primary-50'
                      }`}
                      disabled={loading}
                    >
                      {selectedAlternative === candidate.code ? 'Seleccionada' : 'Elegir'}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-col gap-3">
        {selectedAlternative && (
          <div className="p-3 bg-primary-50 border border-primary-300 rounded-lg">
            <p className="text-sm text-primary-800 font-medium">
              Confirmarás con clasificación alternativa: <span className="font-bold">{selectedAlternative}</span>
            </p>
          </div>
        )}

        <div className="flex gap-3">
          <Button
            onClick={() => onConfirm(invoice.session_id, selectedAlternative || undefined)}
            disabled={loading}
            className="flex-1 bg-success-600 hover:bg-success-700 text-white"
          >
            {loading ? 'Procesando...' : selectedAlternative ? 'Confirmar Alternativa' : 'Confirmar Clasificación'}
          </Button>

          <Button
            onClick={() => onCorrect(invoice.session_id)}
            disabled={loading}
            variant="outline"
            className="flex-1 border-warning-600 text-warning-700 hover:bg-warning-50"
          >
            Corregir Manualmente
          </Button>
        </div>
      </div>
    </Card>
  );
}

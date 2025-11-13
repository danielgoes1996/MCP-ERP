/**
 * Classification Correction Modal Component
 *
 * Allows accountants to correct an AI classification with the proper SAT code
 */

'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

interface ClassificationCorrectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (correctedCode: string, notes?: string) => void;
  originalCode: string;
  originalExplanation: string;
  invoiceDescription: string;
  loading?: boolean;
}

export function ClassificationCorrectionModal({
  isOpen,
  onClose,
  onSubmit,
  originalCode,
  originalExplanation,
  invoiceDescription,
  loading = false,
}: ClassificationCorrectionModalProps) {
  const [correctedCode, setCorrectedCode] = useState('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setCorrectedCode('');
      setNotes('');
      setError('');
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Validate SAT code format (basic validation)
    if (!correctedCode.trim()) {
      setError('El código SAT es requerido');
      return;
    }

    // SAT codes are typically in format XXX.XX or XXX.XX.XX
    const satCodePattern = /^\d{3}(\.\d{2}(\.\d{2})?)?$/;
    if (!satCodePattern.test(correctedCode.trim())) {
      setError('Formato de código SAT inválido (ej: 601.84 o 601.84.01)');
      return;
    }

    setError('');
    onSubmit(correctedCode.trim(), notes.trim() || undefined);
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 z-40"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="px-6 py-4 border-b border-neutral-200">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-neutral-800">
                Corregir Clasificación Contable
              </h2>
              <button
                onClick={onClose}
                disabled={loading}
                className="text-neutral-400 hover:text-neutral-600 transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Content */}
          <form onSubmit={handleSubmit} className="px-6 py-4">
            {/* Invoice Description */}
            <div className="mb-6 p-4 bg-neutral-50 rounded-lg">
              <label className="block text-sm font-semibold text-neutral-700 mb-2">
                Descripción de la Factura
              </label>
              <p className="text-neutral-800">{invoiceDescription}</p>
            </div>

            {/* Original Classification */}
            <div className="mb-6 p-4 bg-warning-50 rounded-lg border border-warning-200">
              <label className="block text-sm font-semibold text-warning-700 mb-2">
                Clasificación Original (IA)
              </label>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xl font-bold text-warning-900">
                  {originalCode}
                </span>
              </div>
              <p className="text-sm text-neutral-700">{originalExplanation}</p>
            </div>

            {/* Corrected SAT Code Input */}
            <div className="mb-4">
              <label htmlFor="correctedCode" className="block text-sm font-semibold text-neutral-700 mb-2">
                Código SAT Correcto <span className="text-error-600">*</span>
              </label>
              <Input
                id="correctedCode"
                type="text"
                value={correctedCode}
                onChange={(e) => {
                  setCorrectedCode(e.target.value);
                  setError('');
                }}
                placeholder="Ej: 601.84.01"
                disabled={loading}
                className={error ? 'border-error-500' : ''}
              />
              {error && (
                <p className="mt-1 text-sm text-error-600">{error}</p>
              )}
              <p className="mt-1 text-xs text-neutral-500">
                Formato: XXX.XX o XXX.XX.XX
              </p>
            </div>

            {/* Notes Input */}
            <div className="mb-6">
              <label htmlFor="notes" className="block text-sm font-semibold text-neutral-700 mb-2">
                Notas (Opcional)
              </label>
              <textarea
                id="notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Explica por qué corregiste esta clasificación..."
                disabled={loading}
                rows={3}
                className="w-full px-4 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
              />
              <p className="mt-1 text-xs text-neutral-500">
                Estas notas ayudarán a mejorar el sistema de IA
              </p>
            </div>

            {/* Comparison Preview */}
            {correctedCode && (
              <div className="mb-6 p-4 bg-success-50 rounded-lg border border-success-200">
                <label className="block text-sm font-semibold text-success-700 mb-2">
                  Vista Previa de Corrección
                </label>
                <div className="flex items-center gap-4">
                  <div>
                    <span className="text-xs text-neutral-600">Original:</span>
                    <p className="text-lg font-bold text-neutral-700 line-through">
                      {originalCode}
                    </p>
                  </div>
                  <svg className="w-6 h-6 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                  </svg>
                  <div>
                    <span className="text-xs text-neutral-600">Correcto:</span>
                    <p className="text-lg font-bold text-success-700">
                      {correctedCode}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-3 pt-4 border-t border-neutral-200">
              <Button
                type="button"
                onClick={onClose}
                disabled={loading}
                variant="outline"
                className="flex-1"
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={loading || !correctedCode}
                className="flex-1 bg-success-600 hover:bg-success-700"
              >
                {loading ? 'Guardando...' : 'Guardar Corrección'}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </>
  );
}

/**
 * Invoice Classification Page
 *
 * Displays pending AI classifications for accountant review
 */

'use client';

import { useState, useEffect } from 'react';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import { useRouter } from 'next/navigation';
import {
  getPendingClassifications,
  getSATSyncPendingCount,
  confirmClassification,
  correctClassification,
  type PendingInvoice,
} from '@/services/classificationService';
import { PendingClassificationCard } from '@/components/classification/PendingClassificationCard';
import { ClassificationCorrectionModal } from '@/components/classification/ClassificationCorrectionModal';
import { ClassificationStats } from '@/components/classification/ClassificationStats';
import { Button } from '@/components/ui/Button';

export default function ClassificationPage() {
  const router = useRouter();
  const { user, tenant, isAuthenticated } = useAuthStore();

  const [pendingInvoices, setPendingInvoices] = useState<PendingInvoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const limit = 10;

  // Filter by source (manual vs SAT auto-sync)
  const [sourceFilter, setSourceFilter] = useState<'all' | 'manual' | 'sat_auto_sync'>('all');
  const [satPendingCount, setSatPendingCount] = useState(0);

  // Modal state
  const [correctionModal, setCorrectionModal] = useState<{
    isOpen: boolean;
    invoice: PendingInvoice | null;
  }>({
    isOpen: false,
    invoice: null,
  });

  // Show stats toggle
  const [showStats, setShowStats] = useState(false);

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  // Fetch SAT pending count
  useEffect(() => {
    async function fetchSATCount() {
      const companyId = tenant?.company_id;
      if (!companyId) return;

      try {
        const data = await getSATSyncPendingCount(parseInt(companyId));
        setSatPendingCount(data.pending_count);
      } catch (err) {
        console.error('Error fetching SAT pending count:', err);
      }
    }

    fetchSATCount();
  }, [tenant?.company_id]);

  // Fetch pending classifications
  useEffect(() => {
    async function fetchPending() {
      // Use company_id from tenant, or fallback to 'carreta_verde' for testing
      const companyId = tenant?.company_id || 'carreta_verde';

      if (!companyId) return;

      try {
        setLoading(true);
        setError(null);

        // Pass source filter if not 'all'
        const source = sourceFilter === 'all' ? undefined : sourceFilter;
        const data = await getPendingClassifications(companyId, limit, offset, source);

        setPendingInvoices(data.invoices);
        setTotal(data.total);
      } catch (err) {
        console.error('Error fetching pending classifications:', err);
        setError('Error al cargar clasificaciones pendientes');
      } finally {
        setLoading(false);
      }
    }

    fetchPending();
  }, [tenant?.company_id, offset, sourceFilter]);

  /**
   * Handle confirm classification
   * If alternativeCode is provided, treat it as a correction
   */
  const handleConfirm = async (sessionId: string, alternativeCode?: string) => {
    if (!user?.id) return;

    try {
      setActionLoading(true);

      // If alternative code provided, use correction endpoint
      if (alternativeCode) {
        await correctClassification(
          sessionId,
          alternativeCode,
          'Seleccionado de candidatos alternativos',
          user.id.toString()
        );
        alert('Clasificación alternativa confirmada exitosamente');
      } else {
        // Otherwise, use normal confirmation
        await confirmClassification(sessionId, user.id.toString());
        alert('Clasificación confirmada exitosamente');
      }

      // Remove from pending list
      setPendingInvoices((prev) => prev.filter((inv) => inv.session_id !== sessionId));
      setTotal((prev) => prev - 1);
    } catch (err) {
      console.error('Error confirming classification:', err);
      alert('Error al confirmar clasificación');
    } finally {
      setActionLoading(false);
    }
  };

  /**
   * Handle open correction modal
   */
  const handleCorrect = (sessionId: string) => {
    const invoice = pendingInvoices.find((inv) => inv.session_id === sessionId);
    if (!invoice) return;

    setCorrectionModal({
      isOpen: true,
      invoice,
    });
  };

  /**
   * Handle submit correction
   */
  const handleSubmitCorrection = async (correctedCode: string, notes?: string) => {
    if (!correctionModal.invoice || !user?.id) return;

    try {
      setActionLoading(true);
      await correctClassification(
        correctionModal.invoice.session_id,
        correctedCode,
        notes,
        user.id.toString()
      );

      // Remove from pending list
      setPendingInvoices((prev) =>
        prev.filter((inv) => inv.session_id !== correctionModal.invoice?.session_id)
      );
      setTotal((prev) => prev - 1);

      // Close modal
      setCorrectionModal({ isOpen: false, invoice: null });

      // Show success message
      alert('Clasificación corregida exitosamente');
    } catch (err) {
      console.error('Error correcting classification:', err);
      alert('Error al corregir clasificación');
    } finally {
      setActionLoading(false);
    }
  };

  /**
   * Handle pagination
   */
  const handleNextPage = () => {
    if (offset + limit < total) {
      setOffset((prev) => prev + limit);
    }
  };

  const handlePrevPage = () => {
    if (offset > 0) {
      setOffset((prev) => Math.max(0, prev - limit));
    }
  };

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-3xl font-bold text-neutral-900">
              Clasificación de Facturas
            </h1>
            <Button
              onClick={() => setShowStats(!showStats)}
              variant="outline"
              className="border-primary-600 text-primary-700 hover:bg-primary-50"
            >
              {showStats ? 'Ocultar Estadísticas' : 'Ver Estadísticas'}
            </Button>
          </div>
          <p className="text-neutral-600">
            Revisa y confirma las clasificaciones automáticas generadas por IA
          </p>
        </div>

        {/* Statistics Section (toggleable) */}
        {showStats && tenant?.company_id && (
          <div className="mb-8">
            <ClassificationStats companyId={tenant.company_id} days={30} />
          </div>
        )}

        {/* Source Filter Tabs */}
        <div className="mb-6">
          <div className="border-b border-neutral-200">
            <nav className="-mb-px flex space-x-8">
              {/* All Invoices Tab */}
              <button
                onClick={() => {
                  setSourceFilter('all');
                  setOffset(0);
                }}
                className={`
                  whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm
                  ${
                    sourceFilter === 'all'
                      ? 'border-primary-600 text-primary-700'
                      : 'border-transparent text-neutral-600 hover:text-neutral-800 hover:border-neutral-300'
                  }
                `}
              >
                Todas las facturas
                {!loading && sourceFilter === 'all' && (
                  <span className="ml-2 py-0.5 px-2.5 rounded-full text-xs font-medium bg-primary-100 text-primary-800">
                    {total}
                  </span>
                )}
              </button>

              {/* Manual Invoices Tab */}
              <button
                onClick={() => {
                  setSourceFilter('manual');
                  setOffset(0);
                }}
                className={`
                  whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm
                  ${
                    sourceFilter === 'manual'
                      ? 'border-primary-600 text-primary-700'
                      : 'border-transparent text-neutral-600 hover:text-neutral-800 hover:border-neutral-300'
                  }
                `}
              >
                Cargadas manualmente
                {!loading && sourceFilter === 'manual' && (
                  <span className="ml-2 py-0.5 px-2.5 rounded-full text-xs font-medium bg-neutral-100 text-neutral-800">
                    {total}
                  </span>
                )}
              </button>

              {/* SAT Auto-Sync Tab */}
              <button
                onClick={() => {
                  setSourceFilter('sat_auto_sync');
                  setOffset(0);
                }}
                className={`
                  whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm
                  ${
                    sourceFilter === 'sat_auto_sync'
                      ? 'border-primary-600 text-primary-700'
                      : 'border-transparent text-neutral-600 hover:text-neutral-800 hover:border-neutral-300'
                  }
                `}
              >
                Del SAT
                {satPendingCount > 0 && (
                  <span className="ml-2 py-0.5 px-2.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                    {satPendingCount}
                  </span>
                )}
                {!loading && sourceFilter === 'sat_auto_sync' && satPendingCount === 0 && (
                  <span className="ml-2 py-0.5 px-2.5 rounded-full text-xs font-medium bg-neutral-100 text-neutral-800">
                    {total}
                  </span>
                )}
              </button>
            </nav>
          </div>
        </div>

        {/* Pending Count */}
        {!loading && (
          <div className="mb-6 p-4 bg-primary-50 border-l-4 border-primary-600 rounded">
            <p className="text-primary-900 font-semibold">
              {total > 0
                ? `${total} factura${total > 1 ? 's' : ''} pendiente${total > 1 ? 's' : ''} de revisión`
                : 'No hay facturas pendientes de revisión'}
            </p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="mb-6 p-4 bg-error-50 border-l-4 border-error-600 rounded">
            <p className="text-error-900 font-semibold">{error}</p>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-white p-6 rounded-lg shadow animate-pulse">
                <div className="h-6 bg-neutral-300 rounded w-1/3 mb-4"></div>
                <div className="h-4 bg-neutral-200 rounded w-2/3 mb-2"></div>
                <div className="h-4 bg-neutral-200 rounded w-1/2"></div>
              </div>
            ))}
          </div>
        )}

        {/* Pending Invoices List */}
        {!loading && pendingInvoices.length > 0 && (
          <div className="space-y-4">
            {pendingInvoices.map((invoice) => (
              <PendingClassificationCard
                key={invoice.session_id}
                invoice={invoice}
                onConfirm={handleConfirm}
                onCorrect={handleCorrect}
                loading={actionLoading}
              />
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && pendingInvoices.length === 0 && !error && (
          <div className="text-center py-16 bg-white rounded-lg shadow">
            <svg
              className="mx-auto h-16 w-16 text-neutral-400 mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <h3 className="text-xl font-semibold text-neutral-900 mb-2">
              ¡Todo al día!
            </h3>
            <p className="text-neutral-600">
              No hay clasificaciones pendientes de revisión
            </p>
          </div>
        )}

        {/* Pagination */}
        {!loading && total > limit && (
          <div className="mt-8 flex items-center justify-between">
            <p className="text-sm text-neutral-600">
              Mostrando {offset + 1} - {Math.min(offset + limit, total)} de {total}
            </p>

            <div className="flex gap-2">
              <Button
                onClick={handlePrevPage}
                disabled={offset === 0}
                variant="outline"
              >
                Anterior
              </Button>
              <Button
                onClick={handleNextPage}
                disabled={offset + limit >= total}
                variant="outline"
              >
                Siguiente
              </Button>
            </div>
          </div>
        )}

        {/* Correction Modal */}
        {correctionModal.invoice && (
          <ClassificationCorrectionModal
            isOpen={correctionModal.isOpen}
            onClose={() => setCorrectionModal({ isOpen: false, invoice: null })}
            onSubmit={handleSubmitCorrection}
            originalCode={correctionModal.invoice.sat_code}
            originalExplanation={correctionModal.invoice.explanation}
            invoiceDescription={correctionModal.invoice.description}
            loading={actionLoading}
          />
        )}
      </div>
    </div>
  );
}

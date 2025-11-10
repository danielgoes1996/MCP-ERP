/**
 * Bank Reconciliation Page
 *
 * Página de conciliación bancaria AI-Driven para la demo del VC
 * Muestra CFDIs, transacciones bancarias y matching automático
 */

'use client';

import { useState, useEffect } from 'react';
import { Header } from '@/components/layout/Header';
import { Card } from '@/components/shared/Card';
import { Button } from '@/components/shared/Button';
import {
  CheckCircle,
  AlertCircle,
  TrendingUp,
  FileText,
  CreditCard,
  Sparkles,
  ArrowRight,
} from 'lucide-react';

// API Base URL
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

interface ReconciliationStats {
  tasa_conciliacion: number;
  cfdis_conciliados: number;
  cfdis_pendientes: number;
  monto_conciliado: number;
  monto_pendiente: number;
}

interface PendingCFDI {
  id: number;
  nombre_emisor: string;
  total: number;
  fecha_emision: string;
  serie?: string;
  folio?: string;
}

interface MatchSuggestion {
  cfdi_id: number;
  bank_tx_id: number;
  score: number;
  cfdi_emisor: string;
  tx_description: string;
  amount_diff: number;
}

export default function ReconciliationPage() {
  const [stats, setStats] = useState<ReconciliationStats | null>(null);
  const [pendingCFDIs, setPendingCFDIs] = useState<PendingCFDI[]>([]);
  const [suggestions, setSuggestions] = useState<MatchSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [applyingMatch, setApplyingMatch] = useState<number | null>(null);

  // Fetch data on mount
  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      // Fetch stats
      const statsRes = await fetch(`${API_BASE}/api/v1/reconciliation/stats?mes=1&año=2025`);
      const statsData = await statsRes.json();
      setStats(statsData);

      // Fetch pending CFDIs
      const cfdisRes = await fetch(`${API_BASE}/api/v1/cfdis/pending?mes=1&año=2025&limit=10`);
      const cfdisData = await cfdisRes.json();
      setPendingCFDIs(cfdisData.cfdis || []);

      // Fetch match suggestions
      const suggestionsRes = await fetch(`${API_BASE}/api/v1/reconciliation/suggestions?threshold=0.85&limit=10`);
      const suggestionsData = await suggestionsRes.json();
      setSuggestions(suggestionsData.sugerencias || []);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const applyMatch = async (cfdiId: number, bankTxId: number) => {
    setApplyingMatch(cfdiId);
    try {
      const res = await fetch(`${API_BASE}/api/v1/reconciliation/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cfdi_id: cfdiId, bank_tx_id: bankTxId }),
      });

      if (res.ok) {
        // Refresh data
        await fetchData();
        alert('✅ Conciliación aplicada exitosamente');
      } else {
        const error = await res.json();
        alert(`❌ Error: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error applying match:', error);
      alert('❌ Error al aplicar conciliación');
    } finally {
      setApplyingMatch(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Cargando datos...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="container mx-auto px-4 py-8">
        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            🏦 Conciliación Bancaria AI-Driven
          </h1>
          <p className="text-gray-600">
            Sistema automático de conciliación entre CFDIs y transacciones bancarias
          </p>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-8">
            <Card className="hover:shadow-md transition-shadow">
              <div className="text-center">
                <div className={`text-4xl font-bold mb-2 ${
                  stats.tasa_conciliacion >= 50 ? 'text-success-600' :
                  stats.tasa_conciliacion >= 30 ? 'text-warning-600' :
                  'text-error-600'
                }`}>
                  {stats.tasa_conciliacion.toFixed(1)}%
                </div>
                <p className="text-sm text-gray-600">Tasa Conciliación</p>
                <div className="mt-2 flex items-center justify-center gap-1 text-xs text-gray-500">
                  <TrendingUp className="w-3 h-3" />
                  Meta: 85%
                </div>
              </div>
            </Card>

            <Card className="hover:shadow-md transition-shadow">
              <div className="text-center">
                <div className="text-4xl font-bold text-success-600 mb-2">
                  {stats.cfdis_conciliados}
                </div>
                <p className="text-sm text-gray-600">CFDIs Conciliados</p>
                <div className="mt-2 text-xs text-gray-500">
                  ${stats.monto_conciliado.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                </div>
              </div>
            </Card>

            <Card className="hover:shadow-md transition-shadow">
              <div className="text-center">
                <div className="text-4xl font-bold text-warning-600 mb-2">
                  {stats.cfdis_pendientes}
                </div>
                <p className="text-sm text-gray-600">CFDIs Pendientes</p>
                <div className="mt-2 text-xs text-gray-500">
                  ${stats.monto_pendiente.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                </div>
              </div>
            </Card>

            <Card className="hover:shadow-md transition-shadow">
              <div className="text-center">
                <div className="text-4xl font-bold text-primary-600 mb-2">
                  {suggestions.length}
                </div>
                <p className="text-sm text-gray-600">Sugerencias AI</p>
                <div className="mt-2 flex items-center justify-center gap-1 text-xs text-primary-600">
                  <Sparkles className="w-3 h-3" />
                  Auto-match
                </div>
              </div>
            </Card>

            <Card className="hover:shadow-md transition-shadow bg-gradient-to-br from-primary-50 to-accent-50">
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900 mb-1">
                  ${(stats.monto_conciliado + stats.monto_pendiente).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                </div>
                <p className="text-sm text-gray-600">Total Procesado</p>
                <div className="mt-2 text-xs text-gray-500">
                  Enero 2025
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* Match Suggestions */}
        {suggestions.length > 0 && (
          <Card
            title="🎯 Sugerencias de Conciliación AI"
            subtitle={`${suggestions.length} matches detectados automáticamente con alta confianza`}
            className="mb-8"
          >
            <div className="space-y-3">
              {suggestions.map((suggestion) => (
                <div
                  key={`${suggestion.cfdi_id}-${suggestion.bank_tx_id}`}
                  className="flex items-center justify-between p-4 bg-gradient-to-r from-primary-50 to-accent-50 rounded-lg border border-primary-200 hover:shadow-md transition-shadow"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <FileText className="w-4 h-4 text-gray-600" />
                      <span className="font-medium text-gray-900">
                        CFDI-{suggestion.cfdi_id}: {suggestion.cfdi_emisor}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <CreditCard className="w-4 h-4" />
                      <span>TX-{suggestion.bank_tx_id}: {suggestion.tx_description}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <div className={`text-lg font-bold ${
                        suggestion.score >= 0.95 ? 'text-success-600' :
                        suggestion.score >= 0.90 ? 'text-primary-600' :
                        'text-warning-600'
                      }`}>
                        {(suggestion.score * 100).toFixed(0)}%
                      </div>
                      <div className="text-xs text-gray-500">
                        Diferencia: ${suggestion.amount_diff.toFixed(2)}
                      </div>
                    </div>

                    <Button
                      size="sm"
                      onClick={() => applyMatch(suggestion.cfdi_id, suggestion.bank_tx_id)}
                      disabled={applyingMatch === suggestion.cfdi_id}
                      className="whitespace-nowrap"
                    >
                      {applyingMatch === suggestion.cfdi_id ? (
                        <>
                          <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2"></div>
                          Aplicando...
                        </>
                      ) : (
                        <>
                          <CheckCircle className="w-4 h-4 mr-2" />
                          Aplicar Match
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Pending CFDIs */}
        <Card
          title="📄 CFDIs Pendientes de Conciliar"
          subtitle={`${pendingCFDIs.length} facturas sin conciliar`}
        >
          {pendingCFDIs.length === 0 ? (
            <div className="text-center py-12">
              <CheckCircle className="w-12 h-12 text-success-600 mx-auto mb-4" />
              <p className="text-gray-600 mb-2">¡Todos los CFDIs están conciliados!</p>
              <p className="text-sm text-gray-500">
                Tasa de conciliación: {stats?.tasa_conciliacion.toFixed(1)}%
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      ID
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Emisor
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Serie/Folio
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Fecha
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Monto
                    </th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Estado
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {pendingCFDIs.map((cfdi) => (
                    <tr key={cfdi.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {cfdi.id}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900">
                        {cfdi.nombre_emisor}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {cfdi.serie || ''} {cfdi.folio || ''}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(cfdi.fecha_emision).toLocaleDateString('es-MX')}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-right font-medium text-gray-900">
                        ${cfdi.total.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-center">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-warning-100 text-warning-800">
                          <AlertCircle className="w-3 h-3 mr-1" />
                          Pendiente
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Info Footer */}
        <div className="mt-8 p-4 bg-gradient-to-r from-primary-50 to-accent-50 rounded-lg border border-primary-200">
          <div className="flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-primary-600 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-medium text-gray-900 mb-1">
                Sistema AI-Driven de Conciliación
              </h3>
              <p className="text-sm text-gray-600">
                Utilizamos Gemini Vision 2.5 Pro para extracción de PDFs y embeddings de OpenAI
                para matching semántico inteligente. El sistema detecta automáticamente pagos diferidos (MSI)
                y propone conciliaciones con 95%+ de confianza.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

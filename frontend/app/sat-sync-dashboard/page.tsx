/**
 * SAT Sync Dashboard
 *
 * Visualiza métricas e historial de sincronizaciones del SAT
 */

'use client';

import { useState, useEffect } from 'react';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import { useRouter } from 'next/navigation';
import { Card } from '@/components/ui/Card';
import {
  CheckCircle,
  XCircle,
  Clock,
  Download,
  TrendingUp,
  Calendar,
  AlertTriangle
} from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

interface SyncHistory {
  id: number;
  company_id: number;
  sync_started_at: string;
  sync_completed_at: string | null;
  duration_seconds: number | null;
  status: 'running' | 'success' | 'error';
  invoices_downloaded: number;
  invoices_classified: number;
  invoices_failed: number;
  error_message: string | null;
}

interface SyncStats {
  total_syncs: number;
  successful_syncs: number;
  failed_syncs: number;
  total_invoices: number;
  avg_duration_seconds: number;
  last_7_days: number;
  success_rate: number;
}

export default function SATSyncDashboard() {
  const router = useRouter();
  const { user, tenant, isAuthenticated } = useAuthStore();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<SyncHistory[]>([]);
  const [stats, setStats] = useState<SyncStats | null>(null);

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  // Load data
  useEffect(() => {
    async function loadData() {
      const companyId = tenant?.company_id;
      if (!companyId) return;

      try {
        setLoading(true);
        setError(null);

        // Fetch history and stats in parallel
        const [historyRes, statsRes] = await Promise.all([
          fetch(`${API_BASE_URL}/sat/sync-dashboard/history/${companyId}?limit=20`),
          fetch(`${API_BASE_URL}/sat/sync-dashboard/stats/${companyId}`)
        ]);

        if (!historyRes.ok || !statsRes.ok) {
          throw new Error('Error al cargar datos del dashboard');
        }

        const historyData = await historyRes.json();
        const statsData = await statsRes.json();

        setHistory(historyData.history || []);
        setStats(statsData);

      } catch (err: any) {
        console.error('Error loading dashboard:', err);
        setError(err.message || 'Error al cargar dashboard');
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [tenant?.company_id]);

  if (!isAuthenticated) {
    return null;
  }

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return 'N/A';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success': return 'text-success-600 bg-success-50';
      case 'error': return 'text-error-600 bg-error-50';
      case 'running': return 'text-warning-600 bg-warning-50';
      default: return 'text-neutral-600 bg-neutral-50';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success': return <CheckCircle className="w-5 h-5" />;
      case 'error': return <XCircle className="w-5 h-5" />;
      case 'running': return <Clock className="w-5 h-5" />;
      default: return <AlertTriangle className="w-5 h-5" />;
    }
  };

  return (
    <div className="min-h-screen bg-neutral-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-neutral-900 mb-2">
            Dashboard de Sincronización SAT
          </h1>
          <p className="text-neutral-600">
            Métricas e historial de descargas automáticas del SAT
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-error-50 border-l-4 border-error-600 rounded">
            <p className="text-error-900 font-semibold">{error}</p>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            {[...Array(4)].map((_, i) => (
              <Card key={i} className="p-6 animate-pulse">
                <div className="h-4 bg-neutral-300 rounded w-1/2 mb-3"></div>
                <div className="h-8 bg-neutral-200 rounded w-3/4"></div>
              </Card>
            ))}
          </div>
        )}

        {/* Stats Cards */}
        {!loading && stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {/* Total Syncs */}
            <Card className="p-6 bg-gradient-to-br from-primary-50 to-white border-primary-100">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-neutral-600">Total Sincronizaciones</p>
                <Calendar className="w-5 h-5 text-primary-600" />
              </div>
              <p className="text-3xl font-bold text-neutral-900">{stats.total_syncs}</p>
              <p className="text-xs text-neutral-500 mt-1">
                {stats.last_7_days} en últimos 7 días
              </p>
            </Card>

            {/* Success Rate */}
            <Card className="p-6 bg-gradient-to-br from-success-50 to-white border-success-100">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-neutral-600">Tasa de Éxito</p>
                <TrendingUp className="w-5 h-5 text-success-600" />
              </div>
              <p className="text-3xl font-bold text-neutral-900">
                {stats.success_rate.toFixed(1)}%
              </p>
              <p className="text-xs text-neutral-500 mt-1">
                {stats.successful_syncs} exitosas / {stats.failed_syncs} fallidas
              </p>
            </Card>

            {/* Total Invoices */}
            <Card className="p-6 bg-gradient-to-br from-secondary-50 to-white border-secondary-100">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-neutral-600">Facturas Descargadas</p>
                <Download className="w-5 h-5 text-secondary-600" />
              </div>
              <p className="text-3xl font-bold text-neutral-900">{stats.total_invoices}</p>
              <p className="text-xs text-neutral-500 mt-1">
                Total histórico
              </p>
            </Card>

            {/* Avg Duration */}
            <Card className="p-6 bg-gradient-to-br from-warning-50 to-white border-warning-100">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-neutral-600">Duración Promedio</p>
                <Clock className="w-5 h-5 text-warning-600" />
              </div>
              <p className="text-3xl font-bold text-neutral-900">
                {formatDuration(stats.avg_duration_seconds)}
              </p>
              <p className="text-xs text-neutral-500 mt-1">
                Por sincronización
              </p>
            </Card>
          </div>
        )}

        {/* History Table */}
        {!loading && (
          <Card className="overflow-hidden">
            <div className="px-6 py-4 border-b border-neutral-200">
              <h2 className="text-lg font-semibold text-neutral-900">
                Historial de Sincronizaciones
              </h2>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-neutral-50 border-b border-neutral-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                      Fecha
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                      Estado
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                      Duración
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                      Facturas
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                      Clasificadas
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                      Errores
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-neutral-200">
                  {history.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-6 py-8 text-center text-neutral-500">
                        No hay sincronizaciones registradas
                      </td>
                    </tr>
                  )}

                  {history.map((sync) => (
                    <tr key={sync.id} className="hover:bg-neutral-50 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-neutral-900">
                        {new Date(sync.sync_started_at).toLocaleString('es-MX')}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${getStatusColor(sync.status)}`}
                        >
                          {getStatusIcon(sync.status)}
                          {sync.status === 'success' && 'Exitosa'}
                          {sync.status === 'error' && 'Error'}
                          {sync.status === 'running' && 'En curso'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-neutral-600">
                        {formatDuration(sync.duration_seconds)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-neutral-900">
                        {sync.invoices_downloaded}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-success-600">
                        {sync.invoices_classified}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-error-600">
                        {sync.invoices_failed > 0 ? sync.invoices_failed : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {history.length > 0 && (
              <div className="px-6 py-4 bg-neutral-50 border-t border-neutral-200">
                <p className="text-xs text-neutral-500">
                  Mostrando últimas {history.length} sincronizaciones
                </p>
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}

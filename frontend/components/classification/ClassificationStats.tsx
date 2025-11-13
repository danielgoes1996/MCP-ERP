/**
 * Classification Stats Component
 *
 * Displays statistics and metrics about AI classification performance
 */

'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { getClassificationStats, type ClassificationStats as StatsType } from '@/services/classificationService';

interface ClassificationStatsProps {
  companyId: string;
  days?: number;
}

/**
 * Stat Card Component
 */
function StatCard({
  label,
  value,
  subValue,
  color = 'primary',
  loading = false,
}: {
  label: string;
  value: string | number;
  subValue?: string;
  color?: 'primary' | 'success' | 'warning' | 'error';
  loading?: boolean;
}) {
  const colorClasses = {
    primary: 'bg-primary-50 border-primary-200 text-primary-700',
    success: 'bg-success-50 border-success-200 text-success-700',
    warning: 'bg-warning-50 border-warning-200 text-warning-700',
    error: 'bg-error-50 border-error-200 text-error-700',
  };

  return (
    <div className={`p-4 rounded-lg border ${colorClasses[color]}`}>
      <p className="text-sm font-medium text-neutral-600 mb-1">{label}</p>
      {loading ? (
        <div className="animate-pulse">
          <div className="h-8 bg-neutral-300 rounded w-20 mb-1"></div>
          {subValue && <div className="h-4 bg-neutral-200 rounded w-16"></div>}
        </div>
      ) : (
        <>
          <p className="text-2xl font-bold text-neutral-900">{value}</p>
          {subValue && <p className="text-xs text-neutral-600 mt-1">{subValue}</p>}
        </>
      )}
    </div>
  );
}

/**
 * Progress Bar Component
 */
function ProgressBar({
  label,
  percentage,
  color = 'primary',
  loading = false,
}: {
  label: string;
  percentage: number;
  color?: 'primary' | 'success' | 'warning' | 'error';
  loading?: boolean;
}) {
  const colorClasses = {
    primary: 'bg-primary-600',
    success: 'bg-success-600',
    warning: 'bg-warning-600',
    error: 'bg-error-600',
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-2">
        <span className="text-sm font-medium text-neutral-700">{label}</span>
        <span className="text-sm font-bold text-neutral-900">{percentage.toFixed(1)}%</span>
      </div>
      {loading ? (
        <div className="animate-pulse">
          <div className="h-2 bg-neutral-300 rounded"></div>
        </div>
      ) : (
        <div className="w-full bg-neutral-200 rounded-full h-2">
          <div
            className={`${colorClasses[color]} h-2 rounded-full transition-all duration-500`}
            style={{ width: `${Math.min(percentage, 100)}%` }}
          ></div>
        </div>
      )}
    </div>
  );
}

export function ClassificationStats({ companyId, days = 30 }: ClassificationStatsProps) {
  const [stats, setStats] = useState<StatsType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchStats() {
      try {
        setLoading(true);
        setError(null);
        const data = await getClassificationStats(companyId, days);
        setStats(data);
      } catch (err) {
        console.error('Error fetching classification stats:', err);
        setError('Error al cargar estadísticas');
      } finally {
        setLoading(false);
      }
    }

    if (companyId) {
      fetchStats();
    }
  }, [companyId, days]);

  if (error) {
    return (
      <Card className="p-6">
        <div className="text-center text-error-600">
          <p>{error}</p>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-neutral-900 mb-1">
          Estadísticas de Clasificación
        </h2>
        <p className="text-neutral-600">
          Últimos {days} días
        </p>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Facturas"
          value={stats?.total_invoices || 0}
          loading={loading}
          color="primary"
        />
        <StatCard
          label="Clasificadas por IA"
          value={stats?.classified || 0}
          subValue={`${stats?.classification_rate || 0}% del total`}
          loading={loading}
          color="primary"
        />
        <StatCard
          label="Confirmadas"
          value={stats?.confirmed || 0}
          subValue={`${stats?.confirmation_rate || 0}% de clasificadas`}
          loading={loading}
          color="success"
        />
        <StatCard
          label="Corregidas"
          value={stats?.corrected || 0}
          subValue={`${stats?.correction_rate || 0}% de clasificadas`}
          loading={loading}
          color="warning"
        />
      </div>

      {/* Performance Metrics */}
      <Card className="p-6">
        <h3 className="text-lg font-bold text-neutral-900 mb-4">
          Rendimiento del Sistema
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Left Column */}
          <div className="space-y-4">
            <ProgressBar
              label="Tasa de Clasificación"
              percentage={stats?.classification_rate || 0}
              color="primary"
              loading={loading}
            />
            <ProgressBar
              label="Tasa de Confirmación"
              percentage={stats?.confirmation_rate || 0}
              color="success"
              loading={loading}
            />
            <ProgressBar
              label="Tasa de Corrección"
              percentage={stats?.correction_rate || 0}
              color="warning"
              loading={loading}
            />
          </div>

          {/* Right Column */}
          <div className="space-y-4">
            <div className="p-4 bg-neutral-50 rounded-lg">
              <p className="text-sm font-medium text-neutral-600 mb-1">
                Confianza Promedio
              </p>
              {loading ? (
                <div className="animate-pulse">
                  <div className="h-8 bg-neutral-300 rounded w-20"></div>
                </div>
              ) : (
                <p className="text-2xl font-bold text-neutral-900">
                  {stats?.avg_confidence ? `${(stats.avg_confidence * 100).toFixed(1)}%` : 'N/A'}
                </p>
              )}
            </div>

            <div className="p-4 bg-neutral-50 rounded-lg">
              <p className="text-sm font-medium text-neutral-600 mb-1">
                Tiempo Promedio de Clasificación
              </p>
              {loading ? (
                <div className="animate-pulse">
                  <div className="h-8 bg-neutral-300 rounded w-20"></div>
                </div>
              ) : (
                <p className="text-2xl font-bold text-neutral-900">
                  {stats?.avg_duration_seconds ? `${stats.avg_duration_seconds.toFixed(1)}s` : 'N/A'}
                </p>
              )}
            </div>
          </div>
        </div>
      </Card>

      {/* Status Breakdown */}
      <Card className="p-6">
        <h3 className="text-lg font-bold text-neutral-900 mb-4">
          Desglose por Estado
        </h3>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center p-3 bg-warning-50 rounded-lg">
            <p className="text-sm text-neutral-600 mb-1">Pendientes</p>
            <p className="text-3xl font-bold text-warning-700">
              {stats?.pending_confirmation || 0}
            </p>
          </div>

          <div className="text-center p-3 bg-success-50 rounded-lg">
            <p className="text-sm text-neutral-600 mb-1">Confirmadas</p>
            <p className="text-3xl font-bold text-success-700">
              {stats?.confirmed || 0}
            </p>
          </div>

          <div className="text-center p-3 bg-primary-50 rounded-lg">
            <p className="text-sm text-neutral-600 mb-1">Corregidas</p>
            <p className="text-3xl font-bold text-primary-700">
              {stats?.corrected || 0}
            </p>
          </div>

          <div className="text-center p-3 bg-neutral-50 rounded-lg">
            <p className="text-sm text-neutral-600 mb-1">Sin Clasificar</p>
            <p className="text-3xl font-bold text-neutral-700">
              {stats?.not_classified || 0}
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}

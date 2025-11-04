/**
 * Componente para mostrar métricas generales del sistema
 * Dashboard ejecutivo con KPIs principales
 */
import React from 'react';
import {
  ChartBarIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon
} from '@heroicons/react/24/outline';
import { StatCard } from '../ui';

const SystemMetrics = ({ data, categoryStats }) => {
  const getMetricStatus = (current, target) => {
    const percentage = (current / target) * 100;
    if (percentage >= 90) return 'success';
    if (percentage >= 70) return 'warning';
    return 'danger';
  };

  const getStatusIcon = (status) => {
    switch(status) {
      case 'success': return <CheckCircleIcon className="h-5 w-5 text-emerald-500" />;
      case 'warning': return <ExclamationTriangleIcon className="h-5 w-5 text-amber-500" />;
      case 'danger': return <ExclamationTriangleIcon className="h-5 w-5 text-red-500" />;
      default: return <ChartBarIcon className="h-5 w-5 text-gray-500" />;
    }
  };

  const getRiskColor = (risk) => {
    switch(risk) {
      case 'high': return 'text-red-600 bg-red-100';
      case 'medium': return 'text-yellow-600 bg-yellow-100';
      case 'low': return 'text-green-600 bg-green-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const metrics = [
    {
      title: 'Funcionalidades Identificadas',
      value: data.totalFunctionalities,
      target: 23,
      suffix: '',
      description: 'Total de funcionalidades auditadas'
    },
    {
      title: 'Coherencia Global',
      value: data.globalCoherence,
      target: 91,
      suffix: '%',
      description: 'Alineación BD ↔ API ↔ UI'
    },
    {
      title: 'Dependencias Mapeadas',
      value: data.mappedDependencies,
      target: 147,
      suffix: '+',
      description: 'Relaciones entre funcionalidades'
    },
    {
      title: 'SPOFs Críticos',
      value: data.criticalSPOFs,
      target: 0,
      suffix: '',
      description: 'Puntos únicos de falla',
      reverse: true // Para SPOFs, menos es mejor
    },
    {
      title: 'Archivos Python',
      value: data.pythonFiles,
      target: 173,
      suffix: '',
      description: 'Archivos de código auditados'
    },
    {
      title: 'Endpoints API',
      value: data.apiEndpoints,
      target: 38,
      suffix: '+',
      description: 'Endpoints documentados'
    },
    {
      title: 'Campos sin BD',
      value: data.missingBDFields,
      target: 0,
      suffix: '',
      description: 'Campos API sin persistencia',
      reverse: true
    },
    {
      title: 'Campos sin UI/API',
      value: data.missingUIFields,
      target: 0,
      suffix: '',
      description: 'Campos BD sin exposición',
      reverse: true
    }
  ];

  return (
    <div className="space-y-6">
      {/* Métricas principales */}
      <div className="bg-white rounded-lg shadow-card-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          📊 Indicadores Clave del Sistema
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {metrics.map((metric, index) => {
            const status = metric.reverse
              ? (metric.value === 0 ? 'success' : 'danger')
              : getMetricStatus(metric.value, metric.target);

            const intent = status === 'success' ? 'success' : status === 'warning' ? 'warning' : status === 'danger' ? 'danger' : 'neutral';

            const progress = metric.reverse
              ? Math.max(0, 100 - (metric.value / Math.max(metric.target || 1, metric.value || 1)) * 100)
              : Math.min((metric.value / (metric.target || 1)) * 100, 100);

            return (
              <StatCard
                key={index}
                label={metric.title}
                value={
                  <span>
                    {metric.value}
                    {metric.suffix}
                  </span>
                }
                meta={metric.description}
                icon={getStatusIcon(status)}
                intent={intent}
              >
                <div className="mt-2">
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all ${
                      intent === 'success' ? 'bg-emerald-500' :
                      intent === 'warning' ? 'bg-amber-500' : intent === 'danger' ? 'bg-red-500' : 'bg-brand-400'
                      }`}
                      style={{ width: `${Math.max(0, Math.min(progress, 100))}%` }}
                    />
                  </div>
                  <p className="stat-card__meta">Objetivo: {metric.target}{metric.suffix}</p>
                </div>
              </StatCard>
            );
          })}
        </div>
      </div>

      {/* Dashboard por categorías */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          🏗️ Estado por Capa Arquitectónica
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {Object.entries(categoryStats).map(([key, category]) => (
            <div
              key={key}
              className="border border-gray-200 rounded-lg p-4"
            >
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-medium text-gray-900 capitalize">
                  {key === 'core' ? '🎯 Capa Core' :
                   key === 'business' ? '💼 Capa Business' :
                   '🤖 Capa Intelligence'}
                </h4>
                <div className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getRiskColor(category.risk)}`}>
                  {category.risk.toUpperCase()}
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Funcionalidades</span>
                  <span className="font-semibold text-gray-900">{category.functionalities}</span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Coherencia Promedio</span>
                  <span className={`font-semibold ${
                    category.averageCoherence >= 80 ? 'text-green-600' :
                    category.averageCoherence >= 70 ? 'text-yellow-600' : 'text-red-600'
                  }`}>
                    {category.averageCoherence}%
                  </span>
                </div>

                {/* Barra de coherencia */}
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${
                      category.averageCoherence >= 80 ? 'bg-green-500' :
                      category.averageCoherence >= 70 ? 'bg-yellow-500' : 'bg-red-500'
                    }`}
                    style={{ width: `${category.averageCoherence}%` }}
                  ></div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Alertas del sistema */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          🚨 Alertas del Sistema
        </h3>

        <div className="space-y-3">
          {data.criticalSPOFs > 0 && (
            <div className="flex items-center p-3 bg-red-50 border border-red-200 rounded-lg">
              <ExclamationTriangleIcon className="h-5 w-5 text-red-500 mr-3" />
              <div>
                <div className="font-medium text-red-800">SPOFs Críticos Detectados</div>
                <div className="text-sm text-red-600">
                  {data.criticalSPOFs} puntos únicos de falla afectan la disponibilidad del sistema
                </div>
              </div>
            </div>
          )}

          {data.globalCoherence < 80 && (
            <div className="flex items-center p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <ClockIcon className="h-5 w-5 text-yellow-500 mr-3" />
              <div>
                <div className="font-medium text-yellow-800">Coherencia por Debajo del Objetivo</div>
                <div className="text-sm text-yellow-600">
                  Coherencia actual {data.globalCoherence}% - Objetivo: 91%
                </div>
              </div>
            </div>
          )}

          {(data.missingBDFields > 0 || data.missingUIFields > 0) && (
            <div className="flex items-center p-3 bg-orange-50 border border-orange-200 rounded-lg">
              <ExclamationTriangleIcon className="h-5 w-5 text-orange-500 mr-3" />
              <div>
                <div className="font-medium text-orange-800">Campos Desalineados</div>
                <div className="text-sm text-orange-600">
                  {data.missingBDFields} campos sin BD, {data.missingUIFields} campos sin UI/API
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SystemMetrics;

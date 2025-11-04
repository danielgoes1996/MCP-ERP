/**
 * Dashboard Principal de Auditoría de Funcionalidades
 * Sistema MCP Server - Vista ejecutiva y técnica
 */
import React, { useState, useEffect } from 'react';
import { ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline';
import FunctionalityCard from './FunctionalityCard';
import SystemMetrics from './SystemMetrics';
import SPOFPanel from './SPOFPanel';
import CircularDependencies from './CircularDependencies';
import MissingFieldsPanel from './MissingFieldsPanel';
import ContextWizard from './ContextWizard';
import { PageHeader, SegmentedControl } from '../ui';

const Dashboard = () => {
  const [auditData, setAuditData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [expandedFunctionality, setExpandedFunctionality] = useState(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [onboardingCompleted, setOnboardingCompleted] = useState(() => {
    if (typeof window === 'undefined') return false;
    try {
      return localStorage.getItem('onboarding_completed') === 'true';
    } catch (error) {
      console.warn('No fue posible leer onboarding_completed desde localStorage', error);
      return false;
    }
  });

  useEffect(() => {
    // Simular carga de datos - en producción vendría de API
    const loadAuditData = async () => {
      try {
        // En un entorno real, esto sería: const response = await fetch('/api/audit-data');
        const response = await import('../auditData.json');
        setAuditData(response.default);
        setLoading(false);
      } catch (error) {
        console.error('Error cargando datos de auditoría:', error);
        setLoading(false);
      }
    };

    loadAuditData();
  }, []);

  useEffect(() => {
    if (!auditData) return;
    const attr = auditData?.user?.onboarding_completed;
    if (attr === true) {
      setOnboardingCompleted(true);
      try {
        localStorage.setItem('onboarding_completed', 'true');
      } catch (error) {
        console.warn('No fue posible persistir onboarding_completed', error);
      }
    }
  }, [auditData]);

  const getCoherenceColor = (coherence) => {
    if (coherence >= 80) return 'text-green-600 bg-green-100';
    if (coherence >= 70) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  const getCriticalityColor = (criticality) => {
    switch(criticality) {
      case 'maxima': return 'bg-red-500 text-white';
      case 'alta': return 'bg-orange-500 text-white';
      case 'media': return 'bg-yellow-500 text-white';
      default: return 'bg-gray-500 text-white';
    }
  };

  const filteredFunctionalities = auditData?.functionalities.filter(func => {
    if (selectedCategory === 'all') return true;
    return func.category === selectedCategory;
  }) || [];

  const categoryOptions = [
    {
      value: 'all',
      label: (
        <span className="flex items-center gap-2">
          Todas
          <span className="text-xs text-gray-500">({auditData?.functionalities.length || 0})</span>
        </span>
      ),
    },
    {
      value: 'core',
      label: (
        <span className="flex items-center gap-2">
          Core
          <span className="text-xs text-gray-500">({auditData?.categoryStats?.core?.functionalities || 0})</span>
        </span>
      ),
    },
    {
      value: 'business',
      label: (
        <span className="flex items-center gap-2">
          Business
          <span className="text-xs text-gray-500">({auditData?.categoryStats?.business?.functionalities || 0})</span>
        </span>
      ),
    },
    {
      value: 'intelligence',
      label: (
        <span className="flex items-center gap-2">
          Intelligence
          <span className="text-xs text-gray-500">({auditData?.categoryStats?.intelligence?.functionalities || 0})</span>
        </span>
      ),
    },
  ];

  if (!onboardingCompleted) {
    return (
      <ContextWizard
        companyId={auditData?.companyId || 1}
        onCompleted={() => {
          setOnboardingCompleted(true);
          try {
            localStorage.setItem('onboarding_completed', 'true');
          } catch (error) {
            console.warn('No fue posible persistir onboarding_completed', error);
          }
        }}
      />
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Cargando Dashboard de Auditoría...</p>
        </div>
      </div>
    );
  }

  if (!auditData) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600">Error cargando datos de auditoría</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6 space-y-8">
      <PageHeader
        title="🔍 Dashboard de Auditoría - Sistema MCP Server"
        subtitle="Análisis integral de funcionalidades, coherencia arquitectónica y dependencias críticas"
      />

      {/* Métricas del Sistema */}
      <SystemMetrics data={auditData.systemMetrics} categoryStats={auditData.categoryStats} />

      {/* Panel de SPOFs y Dependencias Circulares */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <SPOFPanel spofs={auditData.spofs} />
        <CircularDependencies dependencies={auditData.circularDependencies} />
      </div>

      {/* Controles de Filtro */}
      <div className="bg-white rounded-lg shadow-sm p-6 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <SegmentedControl
            options={categoryOptions}
            value={selectedCategory}
            onChange={setSelectedCategory}
          />
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="btn btn--ghost"
          >
            Vista Avanzada {showAdvanced ? <ChevronUpIcon className="ml-2 h-4 w-4" /> : <ChevronDownIcon className="ml-2 h-4 w-4" />}
          </button>
        </div>

        {showAdvanced && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <MissingFieldsPanel missingFields={auditData.missingFields} />
          </div>
        )}
      </div>

      {/* Grid de Funcionalidades */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">
            Funcionalidades del Sistema ({filteredFunctionalities.length})
          </h2>
          <div className="flex items-center space-x-4 text-sm text-gray-600">
            <div className="flex items-center space-x-1">
              <div className="w-3 h-3 bg-green-100 rounded-full"></div>
              <span>Alta coherencia (80%+)</span>
            </div>
            <div className="flex items-center space-x-1">
              <div className="w-3 h-3 bg-yellow-100 rounded-full"></div>
              <span>Media coherencia (70-79%)</span>
            </div>
            <div className="flex items-center space-x-1">
              <div className="w-3 h-3 bg-red-100 rounded-full"></div>
              <span>Baja coherencia (&lt;70%)</span>
            </div>
          </div>
        </div>

        {/* Lista de funcionalidades */}
        <div className="grid grid-cols-1 gap-4">
          {filteredFunctionalities.map((functionality) => (
            <FunctionalityCard
              key={functionality.id}
              functionality={functionality}
              isExpanded={expandedFunctionality === functionality.id}
              onToggle={() => setExpandedFunctionality(
                expandedFunctionality === functionality.id ? null : functionality.id
              )}
              getCoherenceColor={getCoherenceColor}
              getCriticalityColor={getCriticalityColor}
            />
          ))}
        </div>
      </div>

      {/* Plan de Fortalecimiento */}
      <div className="mt-12 bg-white rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          📋 Plan de Fortalecimiento del Sistema
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {Object.entries(auditData.strengtheningPlan).map(([key, phase]) => (
            <div key={key} className="border border-gray-200 rounded-lg p-4">
              <h4 className="font-medium text-gray-900 mb-2">{phase.name}</h4>
              <p className="text-sm text-gray-600 mb-2">⏱️ {phase.duration}</p>
              <p className="text-sm font-medium text-blue-600 mb-3">{phase.objective}</p>
              <ul className="text-xs text-gray-500 space-y-1">
                {phase.tasks.slice(0, 2).map((task, index) => (
                  <li key={index}>• {task}</li>
                ))}
                {phase.tasks.length > 2 && (
                  <li className="text-gray-400">+{phase.tasks.length - 2} más...</li>
                )}
              </ul>
            </div>
          ))}
        </div>
      </div>

      {/* Footer con timestamp */}
      <div className="mt-8 pt-6 border-t border-gray-200 text-center text-sm text-gray-500">
        <p>
          📅 Última actualización: {new Date().toLocaleString('es-ES')} |
          🔄 Sistema de auditoría en tiempo real
        </p>
      </div>
    </div>
  );
};

export default Dashboard;

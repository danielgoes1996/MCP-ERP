/**
 * Componente para renderizar una funcionalidad individual
 * Muestra trazabilidad BD ↔ API ↔ UI, estado y dependencias
 */
import React from 'react';
import {
  ChevronDownIcon,
  ChevronRightIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon
} from '@heroicons/react/24/outline';
import FieldTraceability from './FieldTraceability';

const FunctionalityCard = ({
  functionality,
  isExpanded,
  onToggle,
  getCoherenceColor,
  getCriticalityColor
}) => {

  const getStatusIcon = (status) => {
    switch(status) {
      case 'complete':
        return <CheckCircleIcon className="h-4 w-4 text-green-500" />;
      case 'missing_bd':
      case 'missing_api':
      case 'missing_ui':
      case 'missing_bd_ui':
        return <ExclamationTriangleIcon className="h-4 w-4 text-yellow-500" />;
      case 'intentional':
        return <CheckCircleIcon className="h-4 w-4 text-blue-500" />;
      default:
        return <XCircleIcon className="h-4 w-4 text-red-500" />;
    }
  };

  const getStatusText = (status) => {
    switch(status) {
      case 'complete': return 'Completo';
      case 'missing_bd': return 'Falta en BD';
      case 'missing_api': return 'Falta en API';
      case 'missing_ui': return 'Falta en UI';
      case 'missing_bd_ui': return 'Falta BD y UI';
      case 'missing_api_ui': return 'Falta API y UI';
      case 'intentional': return 'Intencional';
      default: return 'Error';
    }
  };

  const getPerformanceColor = (performance) => {
    switch(performance) {
      case 'alta': return 'text-green-600 bg-green-100';
      case 'media': return 'text-yellow-600 bg-yellow-100';
      case 'baja': return 'text-orange-600 bg-orange-100';
      case 'muy_baja': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getSecurityColor = (security) => {
    switch(security) {
      case 'alta': return 'text-green-600 bg-green-100';
      case 'media': return 'text-yellow-600 bg-yellow-100';
      case 'baja': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      {/* Header de la funcionalidad */}
      <div
        className="p-4 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            {/* Icono y nombre */}
            <div className="flex items-center space-x-3">
              <span className="text-2xl">{functionality.icon}</span>
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  {functionality.name}
                </h3>
                <p className="text-sm text-gray-600">{functionality.description}</p>
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* SPOF Badge */}
            {functionality.isSPOF && (
              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
                🚨 SPOF
              </span>
            )}

            {/* Criticidad */}
            <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getCriticalityColor(functionality.criticality)}`}>
              {functionality.criticality.toUpperCase()}
            </span>

            {/* Coherencia */}
            <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getCoherenceColor(functionality.coherence)}`}>
              {functionality.coherence}%
            </div>

            {/* Indicador de expansión */}
            <div className="text-gray-400">
              {isExpanded ? (
                <ChevronDownIcon className="h-5 w-5" />
              ) : (
                <ChevronRightIcon className="h-5 w-5" />
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Contenido expandido */}
      {isExpanded && (
        <div className="border-t border-gray-200 p-4 space-y-6">
          {/* Estado actual */}
          <div>
            <h4 className="text-sm font-semibold text-gray-900 mb-3">📊 Estado Actual</h4>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center">
                <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getSecurityColor(functionality.status.security)}`}>
                  🔒 {functionality.status.security.toUpperCase()}
                </div>
                <p className="text-xs text-gray-500 mt-1">Seguridad</p>
              </div>
              <div className="text-center">
                <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getPerformanceColor(functionality.status.performance)}`}>
                  ⚡ {functionality.status.performance.toUpperCase()}
                </div>
                <p className="text-xs text-gray-500 mt-1">Performance</p>
              </div>
              <div className="text-center">
                <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getCoherenceColor(functionality.status.coherence)}`}>
                  🔄 {functionality.status.coherence}%
                </div>
                <p className="text-xs text-gray-500 mt-1">Coherencia</p>
              </div>
            </div>
          </div>

          {/* Trazabilidad de campos */}
          <div>
            <h4 className="text-sm font-semibold text-gray-900 mb-3">
              🔗 Trazabilidad BD ↔ API ↔ UI
            </h4>
            <FieldTraceability fields={functionality.fields} />
          </div>

          {/* Dependencias críticas */}
          <div>
            <h4 className="text-sm font-semibold text-gray-900 mb-3">⚡ Dependencias Críticas</h4>
            <div className="flex flex-wrap gap-2">
              {functionality.dependencies.map((dep, index) => (
                <span
                  key={index}
                  className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800"
                >
                  {dep}
                </span>
              ))}
            </div>
          </div>

          {/* Flujos principales */}
          <div>
            <h4 className="text-sm font-semibold text-gray-900 mb-3">🔄 Flujos Principales</h4>
            <ul className="text-sm text-gray-600 space-y-1">
              {functionality.mainFlows.map((flow, index) => (
                <li key={index} className="flex items-start space-x-2">
                  <span className="text-blue-500 mt-1">•</span>
                  <span>{flow}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Archivos relacionados y endpoints */}
          {(functionality.relatedFiles || functionality.endpoints) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {functionality.relatedFiles && (
                <div>
                  <h5 className="text-xs font-medium text-gray-700 mb-2">📁 Archivos Relacionados</h5>
                  <div className="space-y-1">
                    {functionality.relatedFiles.map((file, index) => (
                      <code key={index} className="block text-xs bg-gray-100 px-2 py-1 rounded">
                        {file}
                      </code>
                    ))}
                  </div>
                </div>
              )}

              {functionality.endpoints && (
                <div>
                  <h5 className="text-xs font-medium text-gray-700 mb-2">🌐 Endpoints API</h5>
                  <div className="space-y-1">
                    {functionality.endpoints.map((endpoint, index) => (
                      <code key={index} className="block text-xs bg-gray-100 px-2 py-1 rounded">
                        {endpoint}
                      </code>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Sample Request/Response para funcionalidades clave */}
          {(functionality.sampleRequest || functionality.sampleResponse) && (
            <div>
              <h4 className="text-sm font-semibold text-gray-900 mb-3">
                💻 Ejemplos de Request/Response
              </h4>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {functionality.sampleRequest && (
                  <div>
                    <h5 className="text-xs font-medium text-gray-700 mb-2">📤 Sample Request</h5>
                    <pre className="text-xs bg-gray-900 text-gray-100 p-3 rounded overflow-x-auto">
                      {JSON.stringify(functionality.sampleRequest, null, 2)}
                    </pre>
                  </div>
                )}

                {functionality.sampleResponse && (
                  <div>
                    <h5 className="text-xs font-medium text-gray-700 mb-2">📥 Sample Response</h5>
                    <pre className="text-xs bg-gray-900 text-gray-100 p-3 rounded overflow-x-auto">
                      {JSON.stringify(functionality.sampleResponse, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* SQL Issues para funcionalidades con problemas de BD */}
          {functionality.sqlIssues && (
            <div>
              <h4 className="text-sm font-semibold text-gray-900 mb-3 text-red-600">
                🔧 Correcciones SQL Requeridas
              </h4>
              <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                <div className="space-y-2">
                  {functionality.sqlIssues.map((sql, index) => (
                    <code key={index} className="block text-xs bg-red-900 text-red-100 px-2 py-1 rounded">
                      {sql}
                    </code>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default FunctionalityCard;
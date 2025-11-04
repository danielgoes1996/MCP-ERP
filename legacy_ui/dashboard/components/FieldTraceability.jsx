/**
 * Componente para mostrar la trazabilidad de campos BD ↔ API ↔ UI
 * Visualización clara del estado de cada campo en las 3 capas
 */
import React from 'react';
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon
} from '@heroicons/react/24/outline';

const FieldTraceability = ({ fields }) => {
  const getFieldStatusIcon = (field) => {
    switch(field.status) {
      case 'complete':
        return <CheckCircleIcon className="h-4 w-4 text-green-500" />;
      case 'missing_bd':
      case 'missing_api':
      case 'missing_ui':
      case 'missing_bd_ui':
      case 'missing_api_ui':
        return <ExclamationTriangleIcon className="h-4 w-4 text-yellow-500" />;
      case 'intentional':
        return <InformationCircleIcon className="h-4 w-4 text-blue-500" />;
      default:
        return <XCircleIcon className="h-4 w-4 text-red-500" />;
    }
  };

  const getFieldStatusColor = (field) => {
    switch(field.status) {
      case 'complete': return 'bg-green-50 border-green-200';
      case 'missing_bd':
      case 'missing_api':
      case 'missing_ui':
      case 'missing_bd_ui':
      case 'missing_api_ui': return 'bg-yellow-50 border-yellow-200';
      case 'intentional': return 'bg-blue-50 border-blue-200';
      default: return 'bg-red-50 border-red-200';
    }
  };

  const getLayerStatus = (field, layer) => {
    const hasLayer = field[layer];
    if (hasLayer) {
      return 'bg-green-100 text-green-800 border-green-300';
    } else {
      return 'bg-red-100 text-red-800 border-red-300';
    }
  };

  const getStatusDescription = (status) => {
    switch(status) {
      case 'complete': return 'Campo presente en todas las capas';
      case 'missing_bd': return 'Falta implementación en Base de Datos';
      case 'missing_api': return 'Falta exposición en API';
      case 'missing_ui': return 'Falta en interfaz de usuario';
      case 'missing_bd_ui': return 'Falta en BD y UI';
      case 'missing_api_ui': return 'Falta en API y UI';
      case 'intentional': return 'Ausencia intencional por diseño';
      default: return 'Estado desconocido';
    }
  };

  if (!fields || Object.keys(fields).length === 0) {
    return (
      <div className="text-center py-4 text-gray-500 text-sm">
        No hay campos definidos para esta funcionalidad
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Leyenda */}
      <div className="flex items-center justify-between text-xs text-gray-600">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-1">
            <div className="w-3 h-3 bg-green-100 border border-green-300 rounded"></div>
            <span>Presente</span>
          </div>
          <div className="flex items-center space-x-1">
            <div className="w-3 h-3 bg-red-100 border border-red-300 rounded"></div>
            <span>Ausente</span>
          </div>
        </div>
        <div className="text-gray-500">
          BD = Base de Datos | API = Endpoints | UI = Interfaz
        </div>
      </div>

      {/* Lista de campos */}
      <div className="space-y-2">
        {Object.entries(fields).map(([fieldName, field]) => (
          <div
            key={fieldName}
            className={`border rounded-lg p-3 ${getFieldStatusColor(field)}`}
          >
            <div className="flex items-center justify-between">
              {/* Nombre del campo y estado general */}
              <div className="flex items-center space-x-3">
                {getFieldStatusIcon(field)}
                <div>
                  <code className="text-sm font-medium text-gray-900">
                    {fieldName}
                  </code>
                  <p className="text-xs text-gray-600 mt-1">
                    {getStatusDescription(field.status)}
                  </p>
                </div>
              </div>

              {/* Estado por capa: BD | API | UI */}
              <div className="flex items-center space-x-2">
                <div className={`px-2 py-1 rounded text-xs font-medium border ${getLayerStatus(field, 'bd')}`}>
                  BD {field.bd ? '✓' : '✗'}
                </div>
                <div className={`px-2 py-1 rounded text-xs font-medium border ${getLayerStatus(field, 'api')}`}>
                  API {field.api ? '✓' : '✗'}
                </div>
                <div className={`px-2 py-1 rounded text-xs font-medium border ${getLayerStatus(field, 'ui')}`}>
                  UI {field.ui ? '✓' : '✗'}
                </div>
              </div>
            </div>

            {/* Trazabilidad visual con flechas */}
            <div className="mt-2 flex items-center justify-center space-x-2 text-xs text-gray-500">
              <span className={field.bd ? 'text-green-600' : 'text-red-600'}>BD</span>
              <span>↔</span>
              <span className={field.api ? 'text-green-600' : 'text-red-600'}>API</span>
              <span>↔</span>
              <span className={field.ui ? 'text-green-600' : 'text-red-600'}>UI</span>
            </div>
          </div>
        ))}
      </div>

      {/* Resumen estadístico */}
      <div className="mt-4 pt-3 border-t border-gray-200">
        <div className="grid grid-cols-4 gap-4 text-center text-sm">
          <div>
            <div className="font-medium text-gray-900">
              {Object.values(fields).filter(f => f.status === 'complete').length}
            </div>
            <div className="text-xs text-green-600">Completos</div>
          </div>
          <div>
            <div className="font-medium text-gray-900">
              {Object.values(fields).filter(f => f.status.includes('missing')).length}
            </div>
            <div className="text-xs text-yellow-600">Con faltantes</div>
          </div>
          <div>
            <div className="font-medium text-gray-900">
              {Object.values(fields).filter(f => f.status === 'intentional').length}
            </div>
            <div className="text-xs text-blue-600">Intencionales</div>
          </div>
          <div>
            <div className="font-medium text-gray-900">
              {Math.round((Object.values(fields).filter(f => f.status === 'complete').length / Object.keys(fields).length) * 100)}%
            </div>
            <div className="text-xs text-gray-600">Coherencia</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FieldTraceability;
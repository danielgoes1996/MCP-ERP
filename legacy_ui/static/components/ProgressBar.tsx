import React, { useState } from 'react';
import { EXPENSE_FIELDS, calculateCompleteness } from '../config/expenseCompleteness';

interface ProgressBarProps {
  formData: Record<string, any>;
  className?: string;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  formData,
  className = ''
}) => {
  const [showDetail, setShowDetail] = useState(false);

  const completeness = calculateCompleteness(formData);
  const { percentage, presentFields, missingFields } = completeness;

  const getProgressColor = (percent: number) => {
    if (percent >= 80) return 'bg-green-500';
    if (percent >= 50) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getProgressBgColor = (percent: number) => {
    if (percent >= 80) return 'bg-green-50';
    if (percent >= 50) return 'bg-yellow-50';
    return 'bg-red-50';
  };

  const getFieldValue = (path: string) => {
    return path.split('.').reduce((current, key) => current?.[key], formData);
  };

  const getFieldConfidence = (fieldKey: string) => {
    return formData._confidence?.[fieldKey] || 0;
  };

  const getConfidenceBadge = (confidence: number) => {
    if (confidence >= 0.8) {
      return <span className="px-1.5 py-0.5 bg-green-100 text-green-700 text-xs rounded font-medium">Alta</span>;
    }
    if (confidence >= 0.5) {
      return <span className="px-1.5 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded font-medium">Media</span>;
    }
    if (confidence > 0) {
      return <span className="px-1.5 py-0.5 bg-red-100 text-red-700 text-xs rounded font-medium">Baja</span>;
    }
    return <span className="px-1.5 py-0.5 bg-gray-100 text-gray-700 text-xs rounded font-medium">N/A</span>;
  };

  return (
    <div className={`bg-white rounded-lg shadow-md p-4 ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-medium text-gray-900">Progreso de Completitud</h3>

          <button
            onClick={() => setShowDetail(!showDetail)}
            className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
            aria-label="Ver detalles del cálculo"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
            </svg>
          </button>
        </div>

        <div className="text-right">
          <div className="text-2xl font-bold text-gray-900">
            {percentage}%
          </div>
          <div className="text-sm text-gray-500">
            {presentFields.length}/{Object.keys(EXPENSE_FIELDS).length} campos
          </div>
        </div>
      </div>

      {/* Barra de progreso principal */}
      <div className="mb-4">
        <div className={`w-full h-3 rounded-full ${getProgressBgColor(percentage)}`}>
          <div
            className={`h-3 rounded-full transition-all duration-500 ease-out ${getProgressColor(percentage)}`}
            style={{ width: `${percentage}%` }}
          />
        </div>

        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>0%</span>
          <span className="font-medium">
            {percentage >= 80 ? 'Listo para enviar' :
             percentage >= 50 ? 'En progreso' :
             'Necesita más información'}
          </span>
          <span>100%</span>
        </div>
      </div>

      {/* Resumen rápido */}
      <div className="flex justify-between text-sm">
        <div className="text-green-600">
          ✓ {presentFields.length} completos
        </div>
        <div className="text-red-600">
          ✗ {missingFields.length} pendientes
        </div>
      </div>

      {/* Detalle expandible */}
      {showDetail && (
        <div className="mt-4 border-t pt-4">
          <div className="mb-3">
            <h4 className="text-sm font-medium text-gray-900 mb-2">
              ¿Cómo calculamos el porcentaje?
            </h4>
            <p className="text-xs text-gray-600">
              Cada campo tiene un peso específico. Los campos requeridos valen 80% del total y los opcionales 20%.
              Solo se cuentan los campos que tienen valores válidos.
            </p>
          </div>

          <div className="space-y-3">
            {/* Campos requeridos */}
            <div>
              <h5 className="text-sm font-medium text-gray-800 mb-2 flex items-center">
                <span className="w-2 h-2 bg-red-400 rounded-full mr-2"></span>
                Campos Requeridos (80% del total)
              </h5>
              <div className="space-y-1">
                {Object.entries(EXPENSE_FIELDS)
                  .filter(([_, field]) => field.required)
                  .map(([fieldKey, field]) => {
                    const value = getFieldValue(fieldKey);
                    const isValid = field.validation ? field.validation(value) : Boolean(value);
                    const confidence = getFieldConfidence(fieldKey);

                    return (
                      <div key={fieldKey} className="flex items-center justify-between py-1 px-2 rounded bg-gray-50">
                        <div className="flex items-center gap-2">
                          <span className={`w-4 h-4 rounded-full flex items-center justify-center ${
                            isValid ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'
                          }`}>
                            {isValid ? '✓' : '✗'}
                          </span>
                          <span className="text-sm text-gray-700">{field.name}</span>
                          {confidence > 0 && getConfidenceBadge(confidence)}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-500">
                            {Math.round(field.weight * 100)}%
                          </span>
                          {isValid && value && (
                            <span className="text-xs text-gray-600 max-w-24 truncate">
                              {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>

            {/* Campos opcionales */}
            <div>
              <h5 className="text-sm font-medium text-gray-800 mb-2 flex items-center">
                <span className="w-2 h-2 bg-blue-400 rounded-full mr-2"></span>
                Campos Opcionales (20% del total)
              </h5>
              <div className="space-y-1">
                {Object.entries(EXPENSE_FIELDS)
                  .filter(([_, field]) => !field.required)
                  .map(([fieldKey, field]) => {
                    const value = getFieldValue(fieldKey);
                    const isValid = field.validation ? field.validation(value) : Boolean(value);
                    const confidence = getFieldConfidence(fieldKey);

                    return (
                      <div key={fieldKey} className="flex items-center justify-between py-1 px-2 rounded bg-gray-50">
                        <div className="flex items-center gap-2">
                          <span className={`w-4 h-4 rounded-full flex items-center justify-center ${
                            isValid ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-400'
                          }`}>
                            {isValid ? '✓' : '○'}
                          </span>
                          <span className="text-sm text-gray-700">{field.name}</span>
                          {confidence > 0 && getConfidenceBadge(confidence)}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-500">
                            {Math.round(field.weight * 100)}%
                          </span>
                          {isValid && value && (
                            <span className="text-xs text-gray-600 max-w-24 truncate">
                              {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          </div>

          {/* Ejemplo de cálculo */}
          <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <h6 className="text-sm font-medium text-blue-900 mb-1">Ejemplo del cálculo actual:</h6>
            <p className="text-xs text-blue-700">
              {presentFields.length} campos válidos con peso total de {Math.round(completeness.validWeight * 100)}%
              ÷ peso total de {Math.round(completeness.totalWeight * 100)}% = {percentage}%
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
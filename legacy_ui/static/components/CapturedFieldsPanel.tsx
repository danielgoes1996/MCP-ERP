import React from 'react';
import { EXPENSE_FIELDS } from '../config/expenseCompleteness';

interface CapturedFieldsPanelProps {
  formData: Record<string, any>;
  onEditField: (fieldKey: string, value: any) => void;
  className?: string;
}

export const CapturedFieldsPanel: React.FC<CapturedFieldsPanelProps> = ({
  formData,
  onEditField,
  className = ''
}) => {
  const getFieldValue = (path: string) => {
    return path.split('.').reduce((current, key) => current?.[key], formData);
  };

  const getFieldConfidence = (fieldKey: string) => {
    return formData._confidence?.[fieldKey] || 0;
  };

  const getConfidenceBadge = (confidence: number) => {
    if (confidence >= 0.8) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
          <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          Alta
        </span>
      );
    }
    if (confidence >= 0.5) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
          <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
          Media
        </span>
      );
    }
    if (confidence > 0) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
          <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
          Baja
        </span>
      );
    }
    return null;
  };

  const formatValue = (value: any, fieldType: string) => {
    if (!value) return '';

    switch (fieldType) {
      case 'number':
        if (typeof value === 'number') {
          return value.toLocaleString('es-MX', {
            style: 'currency',
            currency: 'MXN'
          });
        }
        return String(value);
      case 'date':
        if (value) {
          const date = new Date(value);
          if (!isNaN(date.getTime())) {
            return date.toLocaleDateString('es-MX', {
              year: 'numeric',
              month: 'long',
              day: 'numeric'
            });
          }
        }
        return String(value);
      case 'select':
        // Buscar el label en las opciones
        const field = EXPENSE_FIELDS[Object.keys(EXPENSE_FIELDS).find(key =>
          Object.keys(EXPENSE_FIELDS).includes(key)
        ) || ''];
        if (field?.options) {
          const option = field.options.find(opt => opt.value === value);
          return option?.label || String(value);
        }
        return String(value);
      default:
        return String(value);
    }
  };

  const getCategoryIcon = (fieldKey: string) => {
    if (fieldKey.includes('monto') || fieldKey === 'monto_total' || fieldKey === 'subtotal' || fieldKey === 'iva') {
      return '💰';
    }
    if (fieldKey.includes('fecha') || fieldKey === 'fecha_gasto') {
      return '📅';
    }
    if (fieldKey.includes('proveedor')) {
      return '🏪';
    }
    if (fieldKey.includes('empleado')) {
      return '👤';
    }
    if (fieldKey.includes('pago') || fieldKey === 'forma_pago' || fieldKey === 'pagado_por') {
      return '💳';
    }
    if (fieldKey === 'categoria') {
      return '🏷️';
    }
    if (fieldKey === 'descripcion') {
      return '📝';
    }
    return '📋';
  };

  // Filtrar campos que tienen valor
  const capturedFields = Object.entries(EXPENSE_FIELDS).filter(([fieldKey, _]) => {
    const value = getFieldValue(fieldKey);
    return value !== undefined && value !== null && value !== '';
  });

  if (capturedFields.length === 0) {
    return (
      <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
        <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center gap-2">
          <svg className="w-5 h-5 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
          </svg>
          Campos Capturados
        </h3>

        <div className="text-center py-8">
          <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
            <svg className="w-8 h-8 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
            </svg>
          </div>
          <p className="text-gray-500 text-sm">
            Aún no se han capturado campos del gasto
          </p>
          <p className="text-gray-400 text-xs mt-1">
            Usa el micrófono para dictar la información
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-white rounded-lg shadow-md p-4 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900 flex items-center gap-2">
          <svg className="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
          </svg>
          Campos Capturados
        </h3>

        <div className="text-sm text-gray-500">
          {capturedFields.length} de {Object.keys(EXPENSE_FIELDS).length}
        </div>
      </div>

      <div className="space-y-3">
        {capturedFields.map(([fieldKey, fieldConfig]) => {
          const value = getFieldValue(fieldKey);
          const confidence = getFieldConfidence(fieldKey);
          const isManuallyEdited = formData._manualEdits?.[fieldKey];

          return (
            <div
              key={fieldKey}
              className={`
                border rounded-lg p-3 transition-all duration-200
                ${confidence < 0.5 ? 'border-red-200 bg-red-50' :
                  confidence < 0.8 ? 'border-yellow-200 bg-yellow-50' :
                  'border-green-200 bg-green-50'}
                hover:shadow-sm
              `}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-lg" role="img" aria-label={fieldConfig.name}>
                      {getCategoryIcon(fieldKey)}
                    </span>
                    <span className="text-sm font-medium text-gray-900">
                      {fieldConfig.name}
                    </span>
                    {fieldConfig.required && (
                      <span className="text-red-500 text-xs">*</span>
                    )}
                  </div>

                  <div className="mb-2">
                    <span className={`
                      text-base font-medium
                      ${confidence < 0.5 ? 'text-red-700' :
                        confidence < 0.8 ? 'text-yellow-700' :
                        'text-green-700'}
                    `}>
                      {formatValue(value, fieldConfig.type)}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {getConfidenceBadge(confidence)}

                    {isManuallyEdited && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
                        </svg>
                        Editado
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex flex-col gap-2">
                  <button
                    onClick={() => {
                      const newValue = prompt(`Editar ${fieldConfig.name}:`, String(value));
                      if (newValue !== null) {
                        onEditField(fieldKey, newValue);
                      }
                    }}
                    className="px-3 py-1 text-xs font-medium text-blue-600 bg-blue-50 border border-blue-200 rounded hover:bg-blue-100 transition-colors"
                  >
                    Editar
                  </button>

                  {confidence > 0 && (
                    <div className="text-center">
                      <div className={`
                        text-xs font-medium
                        ${confidence >= 0.8 ? 'text-green-600' :
                          confidence >= 0.5 ? 'text-yellow-600' :
                          'text-red-600'}
                      `}>
                        {Math.round(confidence * 100)}%
                      </div>
                      <div className="text-xs text-gray-500">confianza</div>
                    </div>
                  )}
                </div>
              </div>

              {/* Indicador de validación */}
              <div className="mt-2 pt-2 border-t border-gray-200">
                {fieldConfig.validation && fieldConfig.validation(value) ? (
                  <div className="flex items-center gap-1 text-xs text-green-600">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    Valor válido
                  </div>
                ) : (
                  <div className="flex items-center gap-1 text-xs text-red-600">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                    </svg>
                    Necesita corrección
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Resumen al final */}
      <div className="mt-4 pt-4 border-t border-gray-200">
        <div className="flex justify-between text-sm">
          <span className="text-gray-600">
            {capturedFields.filter(([key, _]) => {
              const field = EXPENSE_FIELDS[key];
              const value = getFieldValue(key);
              return field.validation ? field.validation(value) : Boolean(value);
            }).length} válidos, {capturedFields.filter(([key, _]) => {
              const field = EXPENSE_FIELDS[key];
              const value = getFieldValue(key);
              return !(field.validation ? field.validation(value) : Boolean(value));
            }).length} con errores
          </span>
          <span className="text-gray-600">
            {capturedFields.filter(([key, _]) => getFieldConfidence(key) < 0.5).length} baja confianza
          </span>
        </div>
      </div>
    </div>
  );
};
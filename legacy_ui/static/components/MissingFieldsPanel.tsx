import React from 'react';
import { EXPENSE_FIELDS, calculateCompleteness } from '../config/expenseCompleteness';

interface MissingFieldsPanelProps {
  formData: Record<string, any>;
  onFieldChange: (fieldKey: string, value: any) => void;
  showOnlyRequired?: boolean;
  className?: string;
}

export const MissingFieldsPanel: React.FC<MissingFieldsPanelProps> = ({
  formData,
  onFieldChange,
  showOnlyRequired = false,
  className = ''
}) => {
  const [showOptional, setShowOptional] = React.useState(!showOnlyRequired);

  const getFieldValue = (path: string) => {
    return path.split('.').reduce((current, key) => current?.[key], formData);
  };

  const setFieldValue = (path: string, value: any) => {
    onFieldChange(path, value);
  };

  const getFieldConfidence = (fieldKey: string) => {
    return formData._confidence?.[fieldKey] || 0;
  };

  const { missingFields } = calculateCompleteness(formData);

  // Separar campos por tipo y confianza
  const requiredMissing = missingFields.filter(key => EXPENSE_FIELDS[key]?.required);
  const optionalMissing = missingFields.filter(key => !EXPENSE_FIELDS[key]?.required);
  const lowConfidenceFields = Object.keys(EXPENSE_FIELDS).filter(key => {
    const value = getFieldValue(key);
    const confidence = getFieldConfidence(key);
    return value && confidence > 0 && confidence < 0.5;
  });

  const renderInput = (fieldKey: string, fieldConfig: any) => {
    const value = getFieldValue(fieldKey);
    const confidence = getFieldConfidence(fieldKey);
    const isLowConfidence = confidence > 0 && confidence < 0.5;

    const inputClasses = `
      mt-1 block w-full rounded-md border-gray-300 shadow-sm
      focus:border-blue-500 focus:ring-blue-500 sm:text-sm
      ${isLowConfidence ? 'border-red-300 bg-red-50' : ''}
      ${value ? 'bg-blue-50 border-blue-200' : ''}
    `;

    switch (fieldConfig.type) {
      case 'select':
        return (
          <select
            value={value || ''}
            onChange={(e) => setFieldValue(fieldKey, e.target.value)}
            className={inputClasses}
            aria-describedby={`${fieldKey}-help`}
          >
            <option value="">Selecciona una opción</option>
            {fieldConfig.options?.map((option: any) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        );

      case 'number':
        return (
          <input
            type="number"
            value={value || ''}
            onChange={(e) => setFieldValue(fieldKey, parseFloat(e.target.value) || 0)}
            placeholder={fieldConfig.placeholder}
            className={inputClasses}
            step="0.01"
            min="0"
            aria-describedby={`${fieldKey}-help`}
          />
        );

      case 'date':
        return (
          <input
            type="date"
            value={value || ''}
            onChange={(e) => setFieldValue(fieldKey, e.target.value)}
            className={inputClasses}
            max={new Date().toISOString().split('T')[0]}
            aria-describedby={`${fieldKey}-help`}
          />
        );

      default:
        return (
          <input
            type="text"
            value={value || ''}
            onChange={(e) => setFieldValue(fieldKey, e.target.value)}
            placeholder={fieldConfig.placeholder}
            className={inputClasses}
            aria-describedby={`${fieldKey}-help`}
          />
        );
    }
  };

  const renderField = (fieldKey: string, isLowConfidence = false) => {
    const fieldConfig = EXPENSE_FIELDS[fieldKey];
    if (!fieldConfig) return null;

    const value = getFieldValue(fieldKey);
    const confidence = getFieldConfidence(fieldKey);

    return (
      <div
        key={fieldKey}
        className={`
          p-4 border rounded-lg
          ${isLowConfidence ? 'border-red-200 bg-red-50' :
            fieldConfig.required ? 'border-orange-200 bg-orange-50' :
            'border-gray-200 bg-gray-50'}
        `}
      >
        <div className="flex items-start justify-between mb-2">
          <label
            htmlFor={fieldKey}
            className="block text-sm font-medium text-gray-700"
          >
            {fieldConfig.name}
            {fieldConfig.required && <span className="text-red-500 ml-1">*</span>}
          </label>

          <div className="flex items-center gap-2">
            {isLowConfidence && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                Revisar
              </span>
            )}

            {confidence > 0 && (
              <span className="text-xs text-gray-500">
                {Math.round(confidence * 100)}% confianza
              </span>
            )}
          </div>
        </div>

        {renderInput(fieldKey, fieldConfig)}

        {fieldConfig.help && (
          <p id={`${fieldKey}-help`} className="mt-1 text-xs text-gray-500">
            {fieldConfig.help}
          </p>
        )}

        {isLowConfidence && value && (
          <div className="mt-2 p-2 bg-yellow-50 border border-yellow-200 rounded">
            <p className="text-xs text-yellow-700">
              <strong>Valor detectado:</strong> {String(value)}
            </p>
            <p className="text-xs text-yellow-600">
              La confianza es baja ({Math.round(confidence * 100)}%).
              Verifica que sea correcto antes de continuar.
            </p>
          </div>
        )}

        {/* Validación en tiempo real */}
        {value && fieldConfig.validation && !fieldConfig.validation(value) && (
          <div className="mt-2 flex items-center gap-1 text-xs text-red-600">
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            {getValidationMessage(fieldKey, value)}
          </div>
        )}
      </div>
    );
  };

  const getValidationMessage = (fieldKey: string, value: any) => {
    if (fieldKey === 'proveedor.rfc') {
      return 'RFC inválido. Formato: 3-4 letras + 6 dígitos + 3 caracteres (ej: ABC123456ABC)';
    }
    if (fieldKey === 'monto_total' || fieldKey === 'subtotal' || fieldKey === 'iva') {
      return 'El monto debe ser mayor a 0';
    }
    if (fieldKey === 'fecha_gasto') {
      return 'Fecha inválida o posterior a hoy';
    }
    return 'Valor inválido';
  };

  const allFieldsToShow = [
    ...lowConfidenceFields,
    ...requiredMissing,
    ...(showOptional ? optionalMissing : [])
  ];

  const uniqueFields = [...new Set(allFieldsToShow)];

  if (uniqueFields.length === 0) {
    return (
      <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
        <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center gap-2">
          <svg className="w-5 h-5 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          Campos Pendientes
        </h3>

        <div className="text-center py-8">
          <div className="w-16 h-16 mx-auto mb-4 bg-green-100 rounded-full flex items-center justify-center">
            <svg className="w-8 h-8 text-green-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
          </div>
          <p className="text-green-600 font-medium">
            ¡Todos los campos requeridos están completos!
          </p>
          <p className="text-gray-500 text-sm mt-1">
            El gasto está listo para enviar a Odoo
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-white rounded-lg shadow-md p-4 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900 flex items-center gap-2">
          <svg className="w-5 h-5 text-orange-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
          </svg>
          Campos Pendientes
        </h3>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowOptional(!showOptional)}
            className="text-sm text-blue-600 hover:text-blue-700"
          >
            {showOptional ? 'Solo requeridos' : 'Mostrar opcionales'}
          </button>

          <span className="text-sm text-gray-500">
            {uniqueFields.length} pendientes
          </span>
        </div>
      </div>

      {/* Estadísticas rápidas */}
      <div className="grid grid-cols-3 gap-4 mb-6 p-3 bg-gray-50 rounded-lg">
        <div className="text-center">
          <div className="text-lg font-semibold text-red-600">
            {requiredMissing.length}
          </div>
          <div className="text-xs text-gray-600">Requeridos</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-semibold text-yellow-600">
            {lowConfidenceFields.length}
          </div>
          <div className="text-xs text-gray-600">Baja confianza</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-semibold text-gray-600">
            {optionalMissing.length}
          </div>
          <div className="text-xs text-gray-600">Opcionales</div>
        </div>
      </div>

      {/* Secciones organizadas */}
      <div className="space-y-6">
        {/* Campos de baja confianza */}
        {lowConfidenceFields.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-red-700 mb-3 flex items-center gap-2">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              Revisar - Baja Confianza
            </h4>
            <div className="space-y-3">
              {lowConfidenceFields.map(fieldKey => renderField(fieldKey, true))}
            </div>
          </div>
        )}

        {/* Campos requeridos faltantes */}
        {requiredMissing.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-orange-700 mb-3 flex items-center gap-2">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              Campos Requeridos ({requiredMissing.length})
            </h4>
            <div className="space-y-3">
              {requiredMissing.map(fieldKey => renderField(fieldKey))}
            </div>
          </div>
        )}

        {/* Campos opcionales */}
        {showOptional && optionalMissing.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" clipRule="evenodd" />
              </svg>
              Campos Opcionales ({optionalMissing.length})
            </h4>
            <div className="space-y-3">
              {optionalMissing.map(fieldKey => renderField(fieldKey))}
            </div>
          </div>
        )}
      </div>

      {/* Ayuda contextual */}
      <div className="mt-6 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <div className="flex items-start gap-2">
          <svg className="w-4 h-4 text-blue-500 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
          <div>
            <p className="text-sm text-blue-700 font-medium">Consejos</p>
            <ul className="text-xs text-blue-600 mt-1 space-y-1">
              <li>• Los campos marcados con * son obligatorios</li>
              <li>• Los valores con baja confianza necesitan verificación</li>
              <li>• Usa el formato correcto para RFC: ABC123456DEF</li>
              <li>• Las fechas no pueden ser futuras</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
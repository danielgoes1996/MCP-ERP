import React from 'react';
import { EXPENSE_FIELDS } from '../config/expenseCompleteness';

interface ExpenseFormFullProps {
  formData: Record<string, any>;
  onFieldChange: (fieldKey: string, value: any) => void;
  onToggleVoiceMode: () => void;
  className?: string;
}

export const ExpenseFormFull: React.FC<ExpenseFormFullProps> = ({
  formData,
  onFieldChange,
  onToggleVoiceMode,
  className = ''
}) => {
  const getFieldValue = (path: string) => {
    return path.split('.').reduce((current, key) => current?.[key], formData);
  };

  const setFieldValue = (path: string, value: any) => {
    onFieldChange(path, value);
  };

  const getFieldConfidence = (fieldKey: string) => {
    return formData._confidence?.[fieldKey] || 0;
  };

  const renderInput = (fieldKey: string, fieldConfig: any) => {
    const value = getFieldValue(fieldKey);
    const confidence = getFieldConfidence(fieldKey);
    const isLowConfidence = confidence > 0 && confidence < 0.5;
    const isManuallyEdited = formData._manualEdits?.[fieldKey];

    const inputClasses = `
      mt-1 block w-full rounded-md border-gray-300 shadow-sm
      focus:border-blue-500 focus:ring-blue-500 sm:text-sm
      ${isLowConfidence ? 'border-red-300 bg-red-50' : ''}
      ${value && !isManuallyEdited ? 'bg-blue-50 border-blue-200' : ''}
      ${isManuallyEdited ? 'bg-green-50 border-green-200' : ''}
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

  const renderField = (fieldKey: string, fieldConfig: any) => {
    const value = getFieldValue(fieldKey);
    const confidence = getFieldConfidence(fieldKey);
    const isLowConfidence = confidence > 0 && confidence < 0.5;
    const isManuallyEdited = formData._manualEdits?.[fieldKey];

    return (
      <div key={fieldKey} className="space-y-1">
        <div className="flex items-center justify-between">
          <label
            htmlFor={fieldKey}
            className="block text-sm font-medium text-gray-700"
          >
            {fieldConfig.name}
            {fieldConfig.required && <span className="text-red-500 ml-1">*</span>}
          </label>

          <div className="flex items-center gap-2">
            {isManuallyEdited && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
                </svg>
                Editado
              </span>
            )}

            {isLowConfidence && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                Revisar
              </span>
            )}

            {confidence > 0 && !isLowConfidence && !isManuallyEdited && (
              <span className="text-xs text-gray-500">
                {Math.round(confidence * 100)}% confianza
              </span>
            )}
          </div>
        </div>

        {renderInput(fieldKey, fieldConfig)}

        {fieldConfig.help && (
          <p id={`${fieldKey}-help`} className="text-xs text-gray-500">
            {fieldConfig.help}
          </p>
        )}

        {/* Validación en tiempo real */}
        {value && fieldConfig.validation && !fieldConfig.validation(value) && (
          <div className="flex items-center gap-1 text-xs text-red-600">
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            {getValidationMessage(fieldKey, value)}
          </div>
        )}

        {/* Información de baja confianza */}
        {isLowConfidence && value && (
          <div className="p-2 bg-yellow-50 border border-yellow-200 rounded text-xs">
            <p className="text-yellow-700">
              <strong>Valor detectado por voz:</strong> {String(value)}
            </p>
            <p className="text-yellow-600">
              Confianza: {Math.round(confidence * 100)}%. Verifica que sea correcto.
            </p>
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

  // Agrupar campos por categorías
  const fieldGroups = {
    'Información General': [
      'descripcion',
      'categoria',
      'fecha_gasto'
    ],
    'Montos': [
      'monto_total',
      'subtotal',
      'iva'
    ],
    'Proveedor': [
      'proveedor.nombre',
      'proveedor.rfc'
    ],
    'Empleado y Pago': [
      'empleado.id',
      'pagado_por',
      'forma_pago'
    ],
    'Información Adicional': [
      'notas'
    ]
  };

  return (
    <div className={`bg-white rounded-lg shadow-md ${className}`}>
      {/* Header con opción de cambiar a modo voz */}
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">
            Formulario Completo de Gasto
          </h2>

          <button
            onClick={onToggleVoiceMode}
            className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-blue-700 bg-blue-100 hover:bg-blue-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
          >
            <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z" clipRule="evenodd" />
            </svg>
            Cambiar a Modo Voz
          </button>
        </div>

        <p className="mt-1 text-sm text-gray-600">
          Completa todos los campos del gasto de manera tradicional
        </p>
      </div>

      {/* Formulario por secciones */}
      <div className="px-6 py-6 space-y-8">
        {Object.entries(fieldGroups).map(([groupName, fieldKeys]) => (
          <div key={groupName}>
            <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center">
              <span className="w-6 h-0.5 bg-blue-500 mr-3"></span>
              {groupName}
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {fieldKeys.map(fieldKey => {
                const fieldConfig = EXPENSE_FIELDS[fieldKey];
                if (!fieldConfig) return null;

                return (
                  <div
                    key={fieldKey}
                    className={`
                      ${fieldKey === 'descripcion' || fieldKey === 'notas' ? 'md:col-span-2' : ''}
                    `}
                  >
                    {renderField(fieldKey, fieldConfig)}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Información útil al final */}
      <div className="px-6 py-4 border-t border-gray-200 bg-gray-50">
        <div className="flex items-start gap-3">
          <svg className="w-5 h-5 text-blue-500 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
          <div>
            <h4 className="text-sm font-medium text-gray-900">Consejos para completar el formulario</h4>
            <ul className="mt-1 text-xs text-gray-600 space-y-1">
              <li>• Los campos marcados con * son obligatorios para enviar a Odoo</li>
              <li>• Los campos con fondo azul fueron detectados por voz</li>
              <li>• Los campos con fondo verde fueron editados manualmente</li>
              <li>• Los campos con fondo rojo tienen baja confianza y necesitan revisión</li>
              <li>• El RFC debe tener el formato: ABC123456DEF (3-4 letras + 6 dígitos + 3 caracteres)</li>
              <li>• Las fechas no pueden ser futuras</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
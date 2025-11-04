import React from 'react';
import { calculateCompleteness } from '../config/expenseCompleteness';

interface FooterActionsProps {
  formData: Record<string, any>;
  onSaveDraft: () => void;
  onSendToOdoo: () => void;
  isSaving?: boolean;
  isSending?: boolean;
  className?: string;
}

export const FooterActions: React.FC<FooterActionsProps> = ({
  formData,
  onSaveDraft,
  onSendToOdoo,
  isSaving = false,
  isSending = false,
  className = ''
}) => {
  const { percentage, missingRequiredFields } = calculateCompleteness(formData);
  const canSendToOdoo = missingRequiredFields.length === 0;
  const hasAnyData = Object.keys(formData).some(key =>
    key !== '_confidence' && key !== '_manualEdits' && formData[key]
  );

  return (
    <div className={`bg-white border-t border-gray-200 px-6 py-4 ${className}`}>
      <div className="flex items-center justify-between">
        {/* Estado y progreso */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${
              canSendToOdoo ? 'bg-green-500' :
              percentage >= 50 ? 'bg-yellow-500' : 'bg-red-500'
            }`} />
            <span className="text-sm text-gray-600">
              {canSendToOdoo ? 'Listo para enviar' :
               percentage >= 50 ? 'En progreso' : 'Necesita más información'}
            </span>
          </div>

          <div className="text-sm text-gray-500">
            {percentage}% completo
          </div>

          {missingRequiredFields.length > 0 && (
            <div className="text-sm text-red-600">
              {missingRequiredFields.length} campos requeridos faltantes
            </div>
          )}
        </div>

        {/* Acciones */}
        <div className="flex items-center gap-3">
          {/* Guardar borrador */}
          <button
            onClick={onSaveDraft}
            disabled={!hasAnyData || isSaving || isSending}
            className={`
              px-4 py-2 text-sm font-medium rounded-md border transition-colors
              ${hasAnyData && !isSaving && !isSending
                ? 'text-gray-700 bg-white border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500'
                : 'text-gray-400 bg-gray-100 border-gray-200 cursor-not-allowed'
              }
            `}
            aria-describedby="save-draft-help"
          >
            {isSaving ? (
              <div className="flex items-center gap-2">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Guardando...
              </div>
            ) : (
              <>
                <svg className="w-4 h-4 mr-2 inline" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M7.707 10.293a1 1 0 10-1.414 1.414l3 3a1 1 0 001.414 0l3-3a1 1 0 00-1.414-1.414L11 11.586V6a1 1 0 10-2 0v5.586l-1.293-1.293z" />
                  <path d="M5 18a1 1 0 001 1h8a1 1 0 001-1v-1a1 1 0 10-2 0H7a1 1 0 10-2 0v1z" />
                </svg>
                Guardar Borrador
              </>
            )}
          </button>

          {/* Enviar a Odoo */}
          <button
            onClick={onSendToOdoo}
            disabled={!canSendToOdoo || isSaving || isSending}
            className={`
              px-6 py-2 text-sm font-medium rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2
              ${canSendToOdoo && !isSaving && !isSending
                ? 'text-white bg-blue-600 hover:bg-blue-700 focus:ring-blue-500'
                : 'text-gray-400 bg-gray-200 cursor-not-allowed focus:ring-gray-300'
              }
            `}
            aria-describedby="send-odoo-help"
          >
            {isSending ? (
              <div className="flex items-center gap-2">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Enviando a Odoo...
              </div>
            ) : (
              <>
                <svg className="w-4 h-4 mr-2 inline" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-8.293l-3-3a1 1 0 00-1.414 0l-3 3a1 1 0 001.414 1.414L9 9.414V13a1 1 0 102 0V9.414l1.293 1.293a1 1 0 001.414-1.414z" clipRule="evenodd" />
                </svg>
                Enviar a Odoo
              </>
            )}
          </button>
        </div>
      </div>

      {/* Ayuda contextual */}
      <div className="mt-3 flex justify-between text-xs text-gray-500">
        <div id="save-draft-help">
          {hasAnyData ? 'Guarda tu progreso para continuar más tarde' : 'Agrega información para guardar borrador'}
        </div>
        <div id="send-odoo-help">
          {canSendToOdoo
            ? 'Todos los campos requeridos están completos'
            : `Completa ${missingRequiredFields.length} campos requeridos para enviar`}
        </div>
      </div>

      {/* Advertencias importantes */}
      {!canSendToOdoo && percentage >= 70 && (
        <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
          <div className="flex items-start gap-2">
            <svg className="w-4 h-4 text-amber-500 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <div>
              <p className="text-sm text-amber-700 font-medium">¡Casi listo!</p>
              <p className="text-xs text-amber-600 mt-1">
                Solo faltan {missingRequiredFields.length} campos requeridos para poder enviar el gasto a Odoo.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Confirmación de campos de baja confianza */}
      {canSendToOdoo && formData._confidence && (
        (() => {
          const lowConfidenceFields = Object.entries(formData._confidence)
            .filter(([_, confidence]) => confidence > 0 && confidence < 0.5)
            .length;

          if (lowConfidenceFields > 0) {
            return (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
                <div className="flex items-start gap-2">
                  <svg className="w-4 h-4 text-red-500 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  <div>
                    <p className="text-sm text-red-700 font-medium">Verifica antes de enviar</p>
                    <p className="text-xs text-red-600 mt-1">
                      Hay {lowConfidenceFields} campos con baja confianza. Revísalos antes de enviar a Odoo.
                    </p>
                  </div>
                </div>
              </div>
            );
          }
          return null;
        })()
      )}
    </div>
  );
};
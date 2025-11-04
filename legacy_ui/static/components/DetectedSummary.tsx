import React from 'react';

interface DetectedSummaryProps {
  summary: string;
  confidence: number;
  className?: string;
}

export const DetectedSummary: React.FC<DetectedSummaryProps> = ({
  summary,
  confidence,
  className = ''
}) => {
  const getConfidenceColor = (conf: number) => {
    if (conf >= 0.8) return 'text-green-600 bg-green-100';
    if (conf >= 0.5) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  const getConfidenceText = (conf: number) => {
    if (conf >= 0.8) return 'Alta confianza';
    if (conf >= 0.5) return 'Confianza media';
    return 'Baja confianza';
  };

  const getConfidenceIcon = (conf: number) => {
    if (conf >= 0.8) {
      return (
        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
        </svg>
      );
    }
    if (conf >= 0.5) {
      return (
        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
        </svg>
      );
    }
    return (
      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
      </svg>
    );
  };

  // Procesar el summary para renderizar con formato
  const renderSummary = (text: string) => {
    if (!text) return null;

    // Reemplazar texto en negrita (**texto**) con spans
    const parts = text.split(/(\*\*[^*]+\*\*)/g);

    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        const content = part.slice(2, -2);
        return (
          <span key={index} className="font-semibold text-blue-700">
            {content}
          </span>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  if (!summary) {
    return (
      <div className={`bg-gray-50 rounded-lg p-4 ${className}`}>
        <div className="flex items-center justify-center text-gray-400">
          <svg className="w-6 h-6 mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
          </svg>
          <span>Esperando información del gasto...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-white rounded-lg shadow-md p-4 border-l-4 border-blue-400 ${className}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <svg className="w-5 h-5 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
            </svg>
            <h3 className="text-lg font-medium text-gray-900">Resumen Detectado</h3>
          </div>

          <div className="text-gray-700 leading-relaxed mb-3">
            {renderSummary(summary)}
          </div>

          <div className="flex items-center gap-4">
            <div className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getConfidenceColor(confidence)}`}>
              {getConfidenceIcon(confidence)}
              <span className="ml-1">{getConfidenceText(confidence)}</span>
            </div>

            <div className="text-xs text-gray-500">
              Precisión: {Math.round(confidence * 100)}%
            </div>
          </div>
        </div>

        {/* Indicador visual de confianza */}
        <div className="flex flex-col items-center">
          <div className="relative w-12 h-12">
            <svg className="w-12 h-12 transform -rotate-90" viewBox="0 0 100 100">
              {/* Círculo de fondo */}
              <circle
                cx="50"
                cy="50"
                r="45"
                stroke="currentColor"
                strokeWidth="8"
                fill="none"
                className="text-gray-200"
              />
              {/* Círculo de progreso */}
              <circle
                cx="50"
                cy="50"
                r="45"
                stroke="currentColor"
                strokeWidth="8"
                fill="none"
                strokeDasharray={`${2 * Math.PI * 45}`}
                strokeDashoffset={`${2 * Math.PI * 45 * (1 - confidence)}`}
                className={confidence >= 0.8 ? 'text-green-500' : confidence >= 0.5 ? 'text-yellow-500' : 'text-red-500'}
                style={{ transition: 'stroke-dashoffset 0.5s ease-in-out' }}
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className={`text-xs font-bold ${confidence >= 0.8 ? 'text-green-600' : confidence >= 0.5 ? 'text-yellow-600' : 'text-red-600'}`}>
                {Math.round(confidence * 100)}%
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Recomendaciones basadas en confianza */}
      {confidence < 0.8 && (
        <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
          <div className="flex items-start gap-2">
            <svg className="w-4 h-4 text-amber-500 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <div>
              <p className="text-sm text-amber-700 font-medium">Revisa la información detectada</p>
              <p className="text-xs text-amber-600 mt-1">
                {confidence < 0.5
                  ? 'La confianza es baja. Te recomendamos verificar todos los campos manualmente.'
                  : 'Algunos campos pueden necesitar corrección. Revisa los datos antes de continuar.'
                }
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
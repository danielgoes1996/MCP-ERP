import React, { useEffect, useRef } from 'react';

interface LiveTranscriptProps {
  transcript: string;
  isRecording: boolean;
  className?: string;
}

export const LiveTranscript: React.FC<LiveTranscriptProps> = ({
  transcript,
  isRecording,
  className = ''
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll al final cuando hay nuevo contenido
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcript]);

  const formatTranscript = (text: string) => {
    if (!text.trim()) return text;

    // Dividir en oraciones para mejor legibilidad
    const sentences = text.split(/([.!?]+\s*)/).filter(s => s.trim());

    return sentences.map((sentence, index) => {
      const trimmed = sentence.trim();
      if (!trimmed) return null;

      // Resaltar números (posibles montos)
      const withNumbers = trimmed.replace(
        /(\d+(?:[.,]\d+)*)\s*(pesos?|peso|mx|mxn|\$)?/gi,
        '<span class="bg-green-100 text-green-800 px-1 rounded font-medium">$1 $2</span>'
      );

      // Resaltar fechas
      const withDates = withNumbers.replace(
        /(\d{1,2}[\s\/\-](?:de\s+)?\w+[\s\/\-]\d{4}|\d{1,2}\/\d{1,2}\/\d{4}|hoy|ayer|antier)/gi,
        '<span class="bg-blue-100 text-blue-800 px-1 rounded font-medium">$1</span>'
      );

      // Resaltar proveedores conocidos
      const withProviders = withDates.replace(
        /(pemex|oxxo|walmart|home depot|uber|taxi)/gi,
        '<span class="bg-purple-100 text-purple-800 px-1 rounded font-medium">$1</span>'
      );

      // Resaltar formas de pago
      const withPayments = withProviders.replace(
        /(tarjeta\s+empresa|tarjeta\s+empleado|efectivo|transferencia)/gi,
        '<span class="bg-orange-100 text-orange-800 px-1 rounded font-medium">$1</span>'
      );

      return (
        <span
          key={index}
          dangerouslySetInnerHTML={{ __html: withPayments }}
          className="inline"
        />
      );
    });
  };

  return (
    <div className={`bg-white rounded-lg shadow-md ${className}`}>
      <div className="px-4 py-3 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium text-gray-900 flex items-center gap-2">
            <svg className="w-5 h-5 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z" clipRule="evenodd" />
            </svg>
            Transcripción en Vivo
          </h3>

          <div className="flex items-center gap-2">
            {isRecording && (
              <div className="flex items-center gap-1 text-sm text-red-600">
                <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                Escuchando...
              </div>
            )}

            <span className="text-sm text-gray-500">
              {transcript.split(' ').filter(w => w.trim()).length} palabras
            </span>
          </div>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="p-4 h-48 overflow-y-auto bg-gray-50"
        style={{ scrollBehavior: 'smooth' }}
      >
        {transcript.trim() ? (
          <div className="space-y-2">
            <div className="text-gray-700 leading-relaxed">
              {formatTranscript(transcript)}
              {isRecording && (
                <span className="inline-block w-2 h-4 bg-blue-500 animate-pulse ml-1" />
              )}
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-gray-400">
              <svg className="w-12 h-12 mx-auto mb-2 opacity-50" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z" clipRule="evenodd" />
              </svg>
              <p className="text-sm">
                {isRecording
                  ? 'Comienza a hablar...'
                  : 'Haz clic en el micrófono para empezar'
                }
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Leyenda de colores */}
      {transcript.trim() && (
        <div className="px-4 py-2 border-t border-gray-200 bg-gray-50">
          <div className="flex flex-wrap gap-3 text-xs">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 bg-green-100 border border-green-200 rounded" />
              <span className="text-gray-600">Montos</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 bg-blue-100 border border-blue-200 rounded" />
              <span className="text-gray-600">Fechas</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 bg-purple-100 border border-purple-200 rounded" />
              <span className="text-gray-600">Proveedores</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 bg-orange-100 border border-orange-200 rounded" />
              <span className="text-gray-600">Forma de pago</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
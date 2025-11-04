import React, { useState, useEffect, useRef } from 'react';

interface VoiceBarProps {
  isRecording: boolean;
  onToggleRecording: () => void;
  onTranscriptUpdate: (transcript: string) => void;
  className?: string;
}

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
  message?: string;
}

export const VoiceBar: React.FC<VoiceBarProps> = ({
  isRecording,
  onToggleRecording,
  onTranscriptUpdate,
  className = ''
}) => {
  const [audioLevel, setAudioLevel] = useState(0);
  const [isSupported, setIsSupported] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<any>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const microphoneRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const animationRef = useRef<number>();

  useEffect(() => {
    // Verificar soporte para Web Speech API
    const SpeechRecognition =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;

    if (SpeechRecognition) {
      setIsSupported(true);

      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'es-MX';

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        let finalTranscript = '';
        let interimTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += transcript + ' ';
          } else {
            interimTranscript += transcript;
          }
        }

        onTranscriptUpdate(finalTranscript + interimTranscript);
      };

      recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
        console.error('Speech recognition error:', event.error);
        setError(`Error de reconocimiento: ${event.error}`);
        if (isRecording) {
          onToggleRecording();
        }
      };

      recognition.onend = () => {
        if (isRecording) {
          // Reiniciar automáticamente si aún estamos grabando
          recognition.start();
        }
      };

      recognitionRef.current = recognition;
    } else {
      setError('Tu navegador no soporta reconocimiento de voz');
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      stopAudioLevelMonitoring();
    };
  }, []);

  useEffect(() => {
    if (isRecording) {
      startRecording();
    } else {
      stopRecording();
    }
  }, [isRecording]);

  const startRecording = async () => {
    try {
      setError(null);

      if (recognitionRef.current) {
        recognitionRef.current.start();
      }

      // Iniciar monitoreo de nivel de audio
      await startAudioLevelMonitoring();

    } catch (err) {
      console.error('Error starting recording:', err);
      setError('Error al iniciar la grabación');
      onToggleRecording();
    }
  };

  const stopRecording = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    stopAudioLevelMonitoring();
    setAudioLevel(0);
  };

  const startAudioLevelMonitoring = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      analyserRef.current = audioContextRef.current.createAnalyser();
      microphoneRef.current = audioContextRef.current.createMediaStreamSource(stream);

      analyserRef.current.fftSize = 256;
      microphoneRef.current.connect(analyserRef.current);

      const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);

      const updateAudioLevel = () => {
        if (!analyserRef.current || !isRecording) return;

        analyserRef.current.getByteFrequencyData(dataArray);

        // Calcular nivel promedio
        const average = dataArray.reduce((sum, value) => sum + value, 0) / dataArray.length;
        const normalizedLevel = Math.min(average / 128, 1);

        setAudioLevel(normalizedLevel);

        if (isRecording) {
          animationRef.current = requestAnimationFrame(updateAudioLevel);
        }
      };

      updateAudioLevel();

    } catch (err) {
      console.error('Error accessing microphone:', err);
      setError('Error accediendo al micrófono');
    }
  };

  const stopAudioLevelMonitoring = () => {
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
    }

    if (microphoneRef.current) {
      microphoneRef.current.disconnect();
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
    }

    setAudioLevel(0);
  };

  const getStatusText = () => {
    if (!isSupported) return 'No soportado';
    if (error) return 'Error';
    if (isRecording) return 'Grabando...';
    return 'Listo para grabar';
  };

  const getStatusColor = () => {
    if (!isSupported || error) return 'text-red-500';
    if (isRecording) return 'text-green-500';
    return 'text-gray-500';
  };

  return (
    <div className={`bg-white rounded-lg shadow-md p-4 ${className}`}>
      <div className="flex items-center gap-4">

        {/* Botón de micrófono */}
        <button
          onClick={onToggleRecording}
          disabled={!isSupported || !!error}
          className={`
            relative w-12 h-12 rounded-full flex items-center justify-center
            transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2
            ${isRecording
              ? 'bg-red-500 hover:bg-red-600 focus:ring-red-500 animate-pulse'
              : 'bg-blue-500 hover:bg-blue-600 focus:ring-blue-500'
            }
            ${(!isSupported || error) ? 'opacity-50 cursor-not-allowed bg-gray-400' : ''}
          `}
          aria-label={isRecording ? 'Detener grabación' : 'Iniciar grabación'}
        >
          {isRecording ? (
            <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clipRule="evenodd" />
            </svg>
          ) : (
            <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z" clipRule="evenodd" />
            </svg>
          )}
        </button>

        {/* Indicador de nivel de audio */}
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-sm font-medium ${getStatusColor()}`}>
              {getStatusText()}
            </span>
            {isRecording && (
              <div className="flex gap-1">
                {[...Array(5)].map((_, i) => (
                  <div
                    key={i}
                    className={`w-1 h-4 rounded-full transition-all duration-150 ${
                      audioLevel * 5 > i ? 'bg-green-500' : 'bg-gray-200'
                    }`}
                    style={{
                      height: `${12 + (audioLevel * 5 > i ? audioLevel * 20 : 0)}px`
                    }}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Barra de progreso de audio */}
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all duration-150 ${
                isRecording ? 'bg-green-500' : 'bg-gray-400'
              }`}
              style={{ width: `${audioLevel * 100}%` }}
            />
          </div>
        </div>

        {/* Indicador de estado */}
        <div className="text-right">
          <div className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
            isRecording
              ? 'bg-red-100 text-red-800'
              : 'bg-gray-100 text-gray-800'
          }`}>
            <div className={`w-2 h-2 rounded-full mr-1 ${
              isRecording ? 'bg-red-500' : 'bg-gray-400'
            }`} />
            {isRecording ? 'REC' : 'STOP'}
          </div>
        </div>
      </div>

      {/* Mensaje de error */}
      {error && (
        <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            {error}
          </div>
        </div>
      )}

      {/* Instrucciones */}
      {!error && !isRecording && (
        <div className="mt-3 text-xs text-gray-500">
          💡 Haz clic en el micrófono y dicta: "Gasto de gasolina 800 pesos PEMEX 17 de septiembre tarjeta empresa"
        </div>
      )}
    </div>
  );
};
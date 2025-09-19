import React, { useState, useCallback, useRef, useEffect } from 'react';
import { VoiceBar } from './VoiceBar';
import { LiveTranscript } from './LiveTranscript';
import { DetectedSummary } from './DetectedSummary';
import { ProgressBar } from './ProgressBar';
import { CapturedFieldsPanel } from './CapturedFieldsPanel';
import { MissingFieldsPanel } from './MissingFieldsPanel';
import { FooterActions } from './FooterActions';
import { ExpenseFormFull } from './ExpenseFormFull';
import { parseGasto } from '../utils/expenseParser';

interface ExpenseRegistrationProps {
  className?: string;
}

export const ExpenseRegistration: React.FC<ExpenseRegistrationProps> = ({
  className = ''
}) => {
  // Estados principales
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [transcript, setTranscript] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [currentSummary, setCurrentSummary] = useState('');
  const [summaryConfidence, setSummaryConfidence] = useState(0);
  const [isVoiceMode, setIsVoiceMode] = useState(true);
  const [audioLevel, setAudioLevel] = useState(0);

  // Estados de operaciones
  const [isSaving, setIsSaving] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [lastSaveTime, setLastSaveTime] = useState<Date | null>(null);

  // Referencias para Web Speech API
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const microphoneRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Inicializar Web Speech API
  useEffect(() => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();

      const recognition = recognitionRef.current;
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'es-MX';

      recognition.onresult = (event) => {
        let finalTranscript = '';
        let interimTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += transcript;
          } else {
            interimTranscript += transcript;
          }
        }

        const fullTranscript = transcript + finalTranscript + interimTranscript;
        setTranscript(fullTranscript);

        // Procesar solo si hay contenido final nuevo
        if (finalTranscript.trim()) {
          processTranscript(fullTranscript);
        }
      };

      recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setIsRecording(false);
      };

      recognition.onend = () => {
        setIsRecording(false);
      };
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      stopAudioMonitoring();
    };
  }, []);

  // Procesar transcripción y extraer datos
  const processTranscript = useCallback((fullTranscript: string) => {
    if (!fullTranscript.trim()) return;

    try {
      const parseResult = parseGasto(fullTranscript);

      if (parseResult.fields && Object.keys(parseResult.fields).length > 0) {
        setFormData(prevData => {
          const newData = { ...prevData };

          // Actualizar solo campos que no han sido editados manualmente
          Object.entries(parseResult.fields).forEach(([key, value]) => {
            if (!newData._manualEdits?.[key] && value !== undefined && value !== null && value !== '') {
              newData[key] = value;
            }
          });

          // Actualizar confianzas
          newData._confidence = {
            ...newData._confidence,
            ...parseResult.confidence
          };

          return newData;
        });

        setCurrentSummary(parseResult.summary || '');
        setSummaryConfidence(parseResult.overallConfidence || 0);
      }
    } catch (error) {
      console.error('Error processing transcript:', error);
    }
  }, []);

  // Iniciar monitoreo de audio
  const startAudioMonitoring = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioContextRef.current = new AudioContext();
      analyserRef.current = audioContextRef.current.createAnalyser();
      microphoneRef.current = audioContextRef.current.createMediaStreamSource(stream);

      microphoneRef.current.connect(analyserRef.current);
      analyserRef.current.fftSize = 256;

      const bufferLength = analyserRef.current.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      const updateAudioLevel = () => {
        if (analyserRef.current) {
          analyserRef.current.getByteFrequencyData(dataArray);
          const average = dataArray.reduce((a, b) => a + b) / bufferLength;
          setAudioLevel(average / 255);
          animationFrameRef.current = requestAnimationFrame(updateAudioLevel);
        }
      };

      updateAudioLevel();
    } catch (error) {
      console.error('Error accessing microphone:', error);
    }
  };

  // Detener monitoreo de audio
  const stopAudioMonitoring = () => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
    if (microphoneRef.current) {
      microphoneRef.current.disconnect();
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
    }
  };

  // Manejar grabación
  const handleToggleRecording = useCallback(() => {
    if (!recognitionRef.current) {
      alert('Tu navegador no soporta reconocimiento de voz. Usa Chrome o Edge.');
      return;
    }

    if (isRecording) {
      recognitionRef.current.stop();
      stopAudioMonitoring();
      setIsRecording(false);
    } else {
      recognitionRef.current.start();
      startAudioMonitoring();
      setIsRecording(true);
    }
  }, [isRecording]);

  // Manejar cambios de campo
  const handleFieldChange = useCallback((fieldKey: string, value: any) => {
    setFormData(prevData => {
      const newData = { ...prevData };

      // Establecer el valor usando la ruta de campo
      const keys = fieldKey.split('.');
      let current = newData;
      for (let i = 0; i < keys.length - 1; i++) {
        if (!current[keys[i]]) {
          current[keys[i]] = {};
        }
        current = current[keys[i]];
      }
      current[keys[keys.length - 1]] = value;

      // Marcar como editado manualmente
      if (!newData._manualEdits) {
        newData._manualEdits = {};
      }
      newData._manualEdits[fieldKey] = true;

      return newData;
    });
  }, []);

  // Guardar borrador
  const handleSaveDraft = useCallback(async () => {
    setIsSaving(true);
    try {
      // Simular guardado local o envío al servidor
      await new Promise(resolve => setTimeout(resolve, 1000));
      setLastSaveTime(new Date());
      console.log('Borrador guardado:', formData);
    } catch (error) {
      console.error('Error guardando borrador:', error);
      alert('Error al guardar el borrador');
    } finally {
      setIsSaving(false);
    }
  }, [formData]);

  // Enviar a Odoo
  const handleSendToOdoo = useCallback(async () => {
    setIsSending(true);
    try {
      // Preparar datos para el endpoint MCP
      const expenseData = {
        descripcion: formData.descripcion,
        monto_total: formData.monto_total,
        fecha_gasto: formData.fecha_gasto,
        proveedor: formData.proveedor,
        empleado: formData.empleado,
        pagado_por: formData.pagado_por,
        forma_pago: formData.forma_pago,
        subtotal: formData.subtotal,
        iva: formData.iva,
        categoria: formData.categoria,
        notas: formData.notas
      };

      const response = await fetch('/mcp', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          method: 'create_complete_expense',
          params: {
            expense_data: expenseData
          }
        })
      });

      const result = await response.json();

      if (result.success) {
        alert('¡Gasto enviado a Odoo exitosamente!');
        // Limpiar formulario o redirigir
        setFormData({});
        setTranscript('');
        setCurrentSummary('');
        setSummaryConfidence(0);
      } else {
        throw new Error(result.error || 'Error desconocido');
      }
    } catch (error) {
      console.error('Error enviando a Odoo:', error);
      alert('Error al enviar el gasto a Odoo: ' + error.message);
    } finally {
      setIsSending(false);
    }
  }, [formData]);

  // Alternar modo de vista
  const handleToggleVoiceMode = () => {
    setIsVoiceMode(!isVoiceMode);
    if (isRecording) {
      handleToggleRecording();
    }
  };

  if (!isVoiceMode) {
    return (
      <div className={`max-w-4xl mx-auto p-6 space-y-6 ${className}`}>
        <ExpenseFormFull
          formData={formData}
          onFieldChange={handleFieldChange}
          onToggleVoiceMode={handleToggleVoiceMode}
        />
        <FooterActions
          formData={formData}
          onSaveDraft={handleSaveDraft}
          onSendToOdoo={handleSendToOdoo}
          isSaving={isSaving}
          isSending={isSending}
        />
      </div>
    );
  }

  return (
    <div className={`max-w-6xl mx-auto p-6 space-y-6 ${className}`}>
      {/* Header con controles principales */}
      <div className="text-center space-y-4">
        <h1 className="text-3xl font-bold text-gray-900">
          Registro de Gastos con Voz
        </h1>
        <p className="text-lg text-gray-600">
          Dicta la información de tu gasto y revisa los campos detectados
        </p>

        <button
          onClick={handleToggleVoiceMode}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-blue-700 bg-blue-100 hover:bg-blue-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
        >
          <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
          </svg>
          Cambiar a Formulario Tradicional
        </button>
      </div>

      {/* Barra de voz principal */}
      <VoiceBar
        isRecording={isRecording}
        audioLevel={audioLevel}
        onToggleRecording={handleToggleRecording}
      />

      {/* Layout principal en dos columnas */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Columna izquierda: Transcripción y resumen */}
        <div className="lg:col-span-1 space-y-6">
          <LiveTranscript
            transcript={transcript}
            isRecording={isRecording}
          />

          <DetectedSummary
            summary={currentSummary}
            confidence={summaryConfidence}
          />
        </div>

        {/* Columna derecha: Progreso y campos */}
        <div className="lg:col-span-2 space-y-6">
          <ProgressBar formData={formData} />

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <CapturedFieldsPanel
              formData={formData}
              onEditField={handleFieldChange}
            />

            <MissingFieldsPanel
              formData={formData}
              onFieldChange={handleFieldChange}
            />
          </div>
        </div>
      </div>

      {/* Footer con acciones */}
      <FooterActions
        formData={formData}
        onSaveDraft={handleSaveDraft}
        onSendToOdoo={handleSendToOdoo}
        isSaving={isSaving}
        isSending={isSending}
      />

      {/* Indicador de guardado automático */}
      {lastSaveTime && (
        <div className="fixed bottom-4 right-4 bg-green-100 border border-green-400 text-green-700 px-4 py-2 rounded-lg shadow-lg">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
            <span className="text-sm">
              Borrador guardado a las {lastSaveTime.toLocaleTimeString()}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
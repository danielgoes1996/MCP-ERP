/**
 * Expenses Create Page
 *
 * Unified UI to showcase manual, voice, and ticket/photo expense creation.
 * Currently focused on demonstrating capabilities; backend wiring and future
 * WhatsApp intake will hook into these sections.
 */

'use client';

import { ChangeEvent, useMemo, useState } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { AppLayout } from '@/components/layout/AppLayout';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { cn } from '@/lib/utils/cn';
import {
  CheckCircle2,
  FileText,
  Mic,
  Image as ImageIcon,
  MessageCircle,
  Sparkles,
  Radio,
  Upload,
  Wand2,
  PhoneCall,
} from 'lucide-react';

type ManualStatus = 'draft' | 'validated' | 'sent';
type VoiceStage = 'idle' | 'recording' | 'processing' | 'ready';
type TicketStage = 'idle' | 'uploading' | 'extracted' | 'ready';
type EntryMode = 'manual' | 'voice' | 'ticket';

type FormField =
  | 'description'
  | 'amount'
  | 'date'
  | 'provider'
  | 'category';

const categoryOptions = [
  { value: 'alimentacion', label: 'Alimentación / Representación' },
  { value: 'viaticos', label: 'Viáticos y viajes' },
  { value: 'combustibles', label: 'Combustibles' },
  { value: 'servicios', label: 'Servicios Profesionales' },
  { value: 'otros', label: 'Otros gastos operativos' },
];

const whatsappSteps = [
  {
    title: 'Texto',
    description: 'Mensajes con comandos rápidos (“gasto comida 450 MXN hoy”)',
    status: 'Operacional (API /expenses)',
  },
  {
    title: 'Voz',
    description: 'Notas de voz → `/voice_mcp_enhanced` → `/complete_expense`',
    status: 'UI lista, pendiente webhook WhatsApp',
  },
  {
    title: 'Foto/Ticket',
    description: 'Imagen → OCR interno → `/invoicing/tickets/{id}/create-expense`',
    status: 'UI lista, OCR operativo',
  },
  {
    title: 'Confirmación',
    description: 'Respuesta automática con estatus y enlace al gasto',
    status: 'Por activar con template oficial de WhatsApp',
  },
];

const badgeStyles = {
  neutral: 'bg-gray-100 text-gray-700',
  warning: 'bg-amber-100 text-amber-700',
  success: 'bg-emerald-100 text-emerald-700',
  info: 'bg-sky-100 text-sky-700',
} as const;

type BadgeTone = keyof typeof badgeStyles;

const entryModeConfig: Record<
  EntryMode,
  {
    title: string;
    description: string;
    endpoint: string;
    icon: React.ComponentType<{ className?: string }>;
  }
> = {
  manual: {
    title: 'Captura manual',
    description: 'Formulario completo con validaciones y metadata SAT',
    endpoint: 'POST /expenses',
    icon: FileText,
  },
  voice: {
    title: 'Nota de voz asistida',
    description: 'Transcribe, enriquece y completa desde /voice_mcp_enhanced',
    endpoint: '/voice_mcp_enhanced → /complete_expense',
    icon: Mic,
  },
  ticket: {
    title: 'Foto / ticket',
    description: 'Sube imagen, procesa OCR y crea gasto automáticamente',
    endpoint: '/invoicing/tickets/{id}/create-expense',
    icon: ImageIcon,
  },
};

type FieldProgressStatus = 'complete' | 'auto' | 'pending';

interface FieldProgress {
  label: string;
  value?: string;
  detail: string;
  status: FieldProgressStatus;
}

const requiredFields = [
  {
    key: 'description',
    label: 'Descripción (descripcion)',
    helper: 'Texto del gasto que verá contabilidad',
  },
  {
    key: 'amount',
    label: 'Monto total (monto_total)',
    helper: 'Debe ser mayor a 0 MXN',
  },
  {
    key: 'date',
    label: 'Fecha del gasto (fecha_gasto)',
    helper: 'Formato ISO YYYY-MM-DD',
  },
] as const;

const fieldStatusStyles: Record<FieldProgressStatus, string> = {
  complete: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  auto: 'bg-sky-50 text-sky-700 border-sky-200',
  pending: 'bg-amber-50 text-amber-700 border-amber-200',
};

const fieldStatusLabel: Record<FieldProgressStatus, string> = {
  complete: 'Listo',
  auto: 'Detectado automáticamente',
  pending: 'Pendiente por llenar',
};

export default function CreateExpensePage() {
  const [manualStatus, setManualStatus] = useState<ManualStatus>('draft');
  const [voiceStage, setVoiceStage] = useState<VoiceStage>('idle');
  const [ticketStage, setTicketStage] = useState<TicketStage>('idle');
  const [entryMode, setEntryMode] = useState<EntryMode>('manual');
  const [formData, setFormData] = useState({
    description: 'Comida con cliente importante',
    amount: '1450.00',
    date: new Date().toISOString().split('T')[0],
    provider: 'Restaurante La Hacienda',
    category: 'alimentacion',
    notes: 'Cliente ACME Corp - seguimiento contrato Q2.',
  });
  const [transcript, setTranscript] = useState(
    'Gasté unos 1,450 pesos en la comida con el cliente ACME en La Hacienda hoy al medio día, pagué con tarjeta de la empresa.'
  );
  const [ticketNotes, setTicketNotes] = useState(
    'Ticket CAFE VERDE #90342 - Total 289.50 MXN\nIVA 46.32 MXN · 08/02/2025 09:12'
  );

  const handleFieldChange =
    (field: FormField) =>
    (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setFormData((prev) => ({
        ...prev,
        [field]: event.target.value,
      }));
      setManualStatus('draft');
    };

  const handleNotesChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setFormData((prev) => ({
      ...prev,
      notes: event.target.value,
    }));
    setManualStatus('draft');
  };

  const manualStatusLabel: Record<ManualStatus, string> = {
    draft: 'En borrador',
    validated: 'Validado',
    sent: 'Enviado a /expenses',
  };

  const manualStatusTone: Record<ManualStatus, BadgeTone> = {
    draft: 'neutral',
    validated: 'warning',
    sent: 'success',
  };

  const manualChecks = [
    {
      label: 'Monto y fecha validados por Pydantic',
      satisfied: manualStatus !== 'draft',
    },
    {
      label: 'Categoría → cuenta contable asignada',
      satisfied: manualStatus !== 'draft',
    },
    {
      label: 'Información lista para `/expenses`',
      satisfied: manualStatus === 'sent',
    },
  ];

  const handleManualValidate = () => {
    setManualStatus('validated');
  };

  const handleManualSubmit = () => {
    setManualStatus('sent');
  };

  const handleVoiceRecording = () => {
    if (voiceStage === 'idle' || voiceStage === 'ready') {
      setVoiceStage('recording');
      return;
    }
    if (voiceStage === 'recording') {
      setVoiceStage('processing');
      return;
    }
    if (voiceStage === 'processing') {
      setVoiceStage('ready');
    }
  };

  const handleVoiceComplete = () => {
    setVoiceStage('ready');
  };

  const handleTicketUpload = () => {
    if (ticketStage === 'idle') {
      setTicketStage('uploading');
      return;
    }
    if (ticketStage === 'uploading') {
      setTicketStage('extracted');
      return;
    }
    setTicketStage('ready');
  };

  const omnichannelHighlights = useMemo(
    () => [
      {
        title: 'Captura manual',
        description: 'Formulario completo con validaciones y metadata SAT',
        status: manualStatusLabel[manualStatus],
        tone: badgeStyles[manualStatusTone[manualStatus]],
        icon: FileText,
      },
      {
        title: 'Voz asistida',
        description: 'Transcripción + LLM + formulario corto',
        status:
          voiceStage === 'ready'
            ? 'Listo para `/complete_expense`'
            : voiceStage === 'processing'
            ? 'Procesando transcripción'
            : voiceStage === 'recording'
            ? 'Grabando'
            : 'Esperando nota de voz',
        tone:
          voiceStage === 'ready'
            ? badgeStyles.success
            : voiceStage === 'recording'
            ? badgeStyles.warning
            : badgeStyles.neutral,
        icon: Mic,
      },
      {
        title: 'Foto / ticket',
        description: 'OCR + ticket virtual → gasto automático',
        status:
          ticketStage === 'ready'
            ? 'Listo para crear gasto'
            : ticketStage === 'extracted'
            ? 'Datos extraídos'
            : ticketStage === 'uploading'
            ? 'Cargando imagen'
            : 'Esperando captura',
        tone:
          ticketStage === 'ready'
            ? badgeStyles.success
            : ticketStage === 'extracted'
            ? badgeStyles.info
            : badgeStyles.neutral,
        icon: ImageIcon,
      },
    ],
    [manualStatus, voiceStage, ticketStage]
  );

  const voiceSteps = [
    {
      label: 'Captura de voz',
      description: 'Nota directa o WhatsApp',
      active: voiceStage !== 'idle',
    },
    {
      label: 'Transcripción + IA',
      description: 'Whisper + enriquecimiento LLM',
      active: ['processing', 'ready'].includes(voiceStage),
    },
    {
      label: 'Completar campos',
      description: 'Formulario corto → `/complete_expense`',
      active: voiceStage === 'ready',
    },
  ];

  const ticketSteps = [
    {
      label: 'Carga del ticket',
      description: 'Foto, PDF, captura WhatsApp',
      active: ticketStage !== 'idle',
    },
    {
      label: 'OCR y parsing',
      description: 'Motor interno + matching proveedor',
      active: ['extracted', 'ready'].includes(ticketStage),
    },
    {
      label: 'Crear gasto',
      description: 'Webhook `/invoicing/tickets/{id}/create-expense`',
      active: ticketStage === 'ready',
    },
  ];

  const manualFieldProgress = useMemo<FieldProgress[]>(() => {
    return requiredFields.map((field) => {
      const value =
        field.key === 'description'
          ? formData.description
          : field.key === 'amount'
          ? formData.amount
          : formData.date;
      const filled = Boolean(value && value.trim().length > 0);
      return {
        label: field.label,
        value,
        detail: filled
          ? 'Ingresado manualmente por el usuario'
          : 'Completar en el formulario para pasar las validaciones',
        status: filled ? 'complete' : 'pending',
      };
    });
  }, [formData]);

  const voiceAmountMatch = useMemo(() => {
    const match = transcript.match(/(\d+(?:[\.,]\d+)?)/);
    return match ? match[1].replace(',', '') : '';
  }, [transcript]);

  const voiceFieldProgress = useMemo<FieldProgress[]>(() => {
    const hasTranscript = transcript.trim().length > 0;
    const inferredDate =
      voiceStage === 'ready'
        ? new Date().toISOString().split('T')[0]
        : voiceStage === 'processing'
        ? 'Detectando...'
        : '';

    return requiredFields.map((field) => {
      let status: FieldProgressStatus = 'pending';
      let value = '';
      let detail = 'Falta confirmarlo antes de crear el gasto';

      if (field.key === 'description') {
        value = hasTranscript ? transcript.slice(0, 80) : '';
        if (hasTranscript) {
          status = 'auto';
          detail = 'El ASR + LLM ya propusieron esta descripción';
        }
      } else if (field.key === 'amount') {
        value = voiceAmountMatch;
        if (voiceAmountMatch) {
          status = 'auto';
          detail = 'Detectado en la transcripción (se puede ajustar)';
        }
      } else if (field.key === 'date') {
        value = inferredDate;
        if (voiceStage === 'ready') {
          status = 'complete';
          detail = 'Confirmado en `/complete_expense`';
        } else if (voiceStage === 'processing') {
          status = 'auto';
          detail = 'IA determinando fecha probable';
        }
      }

      return {
        label: field.label,
        value,
        detail,
        status,
      };
    });
  }, [transcript, voiceAmountMatch, voiceStage]);

  const ticketAmountMatch = useMemo(() => {
    const match = ticketNotes.match(/(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))/);
    return match ? match[1].replace(',', '') : '';
  }, [ticketNotes]);

  const ticketDateMatch = useMemo(() => {
    const match = ticketNotes.match(
      /(\d{2}[\/\-]\d{2}[\/\-]\d{2,4})|(\d{4}-\d{2}-\d{2})/
    );
    return match ? match[0] : '';
  }, [ticketNotes]);

  const ticketFieldProgress = useMemo<FieldProgress[]>(() => {
    return requiredFields.map((field) => {
      let status: FieldProgressStatus = 'pending';
      let value = '';
      let detail = 'Esperando validación humana en la UI';

      if (field.key === 'description') {
        value =
          ticketStage === 'ready'
            ? 'Ticket Café Verde · Consumo interno'
            : '';
        if (value) {
          status = 'complete';
          detail = 'Confirmado tras el OCR + clasificación';
        } else if (ticketStage === 'extracted') {
          status = 'auto';
          detail = 'OCR propondrá la descripción';
        }
      } else if (field.key === 'amount') {
        value = ticketAmountMatch;
        if (ticketAmountMatch) {
          status = 'auto';
          detail = 'Detectado del ticket (Total)';
        }
        if (ticketStage === 'ready' && ticketAmountMatch) {
          status = 'complete';
          detail = 'Validado contra reglas fiscales';
        }
      } else if (field.key === 'date') {
        value = ticketDateMatch;
        if (ticketDateMatch) {
          status = 'auto';
          detail = 'Leído del encabezado del ticket';
        }
        if (ticketStage === 'ready' && ticketDateMatch) {
          status = 'complete';
          detail = 'Normalizado al formato ISO';
        }
      }

      return {
        label: field.label,
        value,
        detail,
        status,
      };
    });
  }, [ticketAmountMatch, ticketDateMatch, ticketStage]);

  const renderFieldProgress = (fields: FieldProgress[]) => (
    <div className="mt-6 rounded-xl border border-gray-200 p-4 bg-gray-50">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <p className="text-sm font-semibold text-gray-700">Campos clave</p>
          <p className="text-xs text-gray-500">
            Basados en ExpenseCreate → expense_records
          </p>
        </div>
        <p className="text-xs text-gray-400">
          Requeridos: descripcion, monto_total, fecha_gasto
        </p>
      </div>
      <div className="mt-4 space-y-3">
        {fields.map((field) => (
          <div
            key={field.label}
            className="flex items-start justify-between gap-3 rounded-2xl border bg-white p-3"
          >
            <div>
              <p className="font-semibold text-gray-900">{field.label}</p>
              <p className="text-sm text-gray-600">
                {field.value ? field.value : '—'}
              </p>
              <p className="text-xs text-gray-500 mt-1">{field.detail}</p>
            </div>
            <span
              className={cn(
                'px-3 py-1 rounded-full text-xs font-semibold border',
                fieldStatusStyles[field.status]
              )}
            >
              {fieldStatusLabel[field.status]}
            </span>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <ProtectedRoute>
      <AppLayout>
        <div className="space-y-6">
          <Card noPadding className="bg-gradient-to-r from-[#11446e] via-[#0d3454] to-[#09263a] text-white">
            <div className="p-6 space-y-6">
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                <div>
                  <p className="text-sm uppercase tracking-widest text-white/70">
                    Flujo omnicanal
                  </p>
                  <h1 className="text-3xl font-bold mt-1">
                    Crear gastos manual, por voz y por ticket en un solo lugar
                  </h1>
                  <p className="text-white/80 mt-2 max-w-2xl">
                    Esta vista es la demostración central: hoy podemos capturar
                    gastos desde la web y desde pipelines de voz/foto; el
                    siguiente paso es enlazar el intake de WhatsApp (texto, voz e
                    imágenes) a los mismos componentes.
                  </p>
                </div>
                <div className="bg-white/10 border border-white/20 rounded-2xl p-4 w-full max-w-sm">
                  <div className="flex items-center gap-3">
                    <MessageCircle className="w-10 h-10 text-[#60b97b]" />
                    <div>
                      <p className="text-sm uppercase text-white/70">
                        Próxima integración
                      </p>
                      <p className="font-semibold">
                        WhatsApp ↔️ MCP Server
                      </p>
                    </div>
                  </div>
                  <p className="text-sm text-white/80 mt-3">
                    El 100% del flujo visual ya respeta los endpoints finales.
                    Solo faltan los webhooks oficiales de WhatsApp para disparar
                    estos mismos caminos desde cualquier chat.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {omnichannelHighlights.map((highlight) => (
                  <div
                    key={highlight.title}
                    className="bg-white/10 border border-white/20 rounded-2xl p-4"
                  >
                    <div className="flex items-center gap-3">
                      <div className="bg-white/20 rounded-xl p-2">
                        <highlight.icon className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <p className="font-semibold">{highlight.title}</p>
                        <p className="text-sm text-white/70">
                          {highlight.description}
                        </p>
                      </div>
                    </div>
                    <span
                      className={cn(
                        'inline-flex mt-4 px-3 py-1 rounded-full text-xs font-semibold',
                        highlight.tone
                      )}
                    >
                      {highlight.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          <Card
            title="Selecciona el tipo de captura"
            subtitle="Cada modalidad usa el mismo backend; aquí solo elegimos cuál demostrar."
          >
            <div className="grid gap-4 md:grid-cols-3">
              {(Object.keys(entryModeConfig) as EntryMode[]).map((mode) => {
                const modeInfo = entryModeConfig[mode];
                const Icon = modeInfo.icon;
                const isActive = entryMode === mode;
                return (
                  <button
                    key={mode}
                    onClick={() => setEntryMode(mode)}
                    className={cn(
                      'text-left rounded-2xl border p-4 transition-all duration-200',
                      isActive
                        ? 'border-[#11446e] bg-[#11446e]/5 shadow-md'
                        : 'border-gray-200 bg-white hover:border-[#11446e]/40'
                    )}
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={cn(
                          'rounded-xl p-3',
                          isActive ? 'bg-[#11446e]' : 'bg-gray-100'
                        )}
                      >
                        <Icon
                          className={cn(
                            'w-6 h-6',
                            isActive ? 'text-white' : 'text-gray-500'
                          )}
                        />
                      </div>
                      <div>
                        <p
                          className={cn(
                            'font-semibold',
                            isActive ? 'text-[#11446e]' : 'text-gray-900'
                          )}
                        >
                          {modeInfo.title}
                        </p>
                        <p className="text-sm text-gray-500">
                          {modeInfo.endpoint}
                        </p>
                      </div>
                    </div>
                    <p className="text-sm text-gray-600 mt-3">
                      {modeInfo.description}
                    </p>
                  </button>
                );
              })}
            </div>
          </Card>

          {entryMode === 'manual' && (
            <Card
              title="Captura manual controlada"
              subtitle="Valida en vivo con Pydantic y manda directo a POST /expenses"
            >
              <div className="grid gap-4 md:grid-cols-2">
                <Input
                  label="Descripción"
                  placeholder="Ej. Comida con cliente"
                  value={formData.description}
                  onChange={handleFieldChange('description')}
                />
                <Input
                  label="Monto (MXN)"
                  type="number"
                  step="0.01"
                  value={formData.amount}
                  onChange={handleFieldChange('amount')}
                />
                <Input
                  label="Fecha del gasto"
                  type="date"
                  value={formData.date}
                  onChange={handleFieldChange('date')}
                />
                <Input
                  label="Proveedor / Comercio"
                  placeholder="Nombre del comercio"
                  value={formData.provider}
                  onChange={handleFieldChange('provider')}
                />
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Categoría SAT sugerida
                  </label>
                  <select
                    value={formData.category}
                    onChange={handleFieldChange('category')}
                    className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  >
                    {categoryOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    RFC del proveedor (opcional)
                  </label>
                  <Input placeholder="PEM840212XY1" />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Notas / contexto para el aprobador
                  </label>
                  <textarea
                    value={formData.notes}
                    onChange={handleNotesChange}
                    rows={3}
                    className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>

              <div className="flex flex-wrap gap-3 mt-6">
                <Button onClick={handleManualValidate}>Validar datos</Button>
                <Button
                  variant="secondary"
                  disabled={manualStatus !== 'validated'}
                  onClick={handleManualSubmit}
                >
                  Crear gasto vía /expenses
                </Button>
                <Button variant="ghost">Guardar como borrador</Button>
              </div>

              <div className="mt-6 rounded-xl border border-dashed border-gray-200 p-4 bg-gray-50">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div>
                    <p className="text-sm font-semibold text-gray-700">
                      Estado del flujo manual
                    </p>
                    <p className="text-sm text-gray-500">
                      Validaciones Pydantic + mapeo de categoría → cuenta contable
                    </p>
                  </div>
                  <span
                    className={cn(
                      'inline-flex px-3 py-1 rounded-full text-xs font-semibold',
                      badgeStyles[manualStatusTone[manualStatus]]
                    )}
                  >
                    {manualStatusLabel[manualStatus]}
                  </span>
                </div>
                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  {manualChecks.map((check) => (
                    <div
                      key={check.label}
                      className="flex items-start gap-2 text-sm text-gray-600"
                    >
                      <CheckCircle2
                        className={cn(
                          'w-4 h-4 mt-0.5',
                          check.satisfied ? 'text-emerald-500' : 'text-gray-300'
                        )}
                      />
                      <span>{check.label}</span>
                    </div>
                  ))}
                </div>
              </div>

              {renderFieldProgress(manualFieldProgress)}
            </Card>
          )}

          {entryMode === 'voice' && (
            <Card
              title="Captura por voz"
              subtitle="Simulación del endpoint `/voice_mcp_enhanced`"
            >
              <div className="space-y-4">
                <div className="rounded-2xl border border-gray-200 p-4 bg-gray-50">
                  <div className="flex items-center gap-3">
                    <div className="bg-white border border-gray-200 rounded-xl p-3">
                      <Mic className="w-6 h-6 text-[#11446e]" />
                    </div>
                    <div>
                      <p className="font-semibold text-gray-900">Estado actual</p>
                      <p className="text-sm text-gray-500">
                        {voiceStage === 'ready'
                          ? 'Listo para completar campos faltantes'
                          : voiceStage === 'processing'
                          ? 'Procesando audio y detectando campos'
                          : voiceStage === 'recording'
                          ? 'Grabando nota de voz...'
                          : 'Esperando nota de voz'}
                      </p>
                    </div>
                  </div>
                  <div className="mt-4">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Transcripción sugerida
                    </label>
                    <textarea
                      rows={4}
                      className="w-full border border-gray-200 rounded-xl px-4 py-3 bg-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                      value={transcript}
                      onChange={(event) => setTranscript(event.target.value)}
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      El LLM detecta descripción, monto, fecha y forma de pago
                      automáticamente.
                    </p>
                  </div>
                </div>

                <div className="grid gap-3">
                  {voiceSteps.map((step) => (
                    <div
                      key={step.label}
                      className={cn(
                        'rounded-xl border px-4 py-3 flex items-start gap-3',
                        step.active
                          ? 'border-emerald-200 bg-emerald-50'
                          : 'border-gray-200 bg-white'
                      )}
                    >
                      <Sparkles
                        className={cn(
                          'w-5 h-5 mt-0.5',
                          step.active ? 'text-emerald-600' : 'text-gray-400'
                        )}
                      />
                      <div>
                        <p className="font-medium text-gray-900">{step.label}</p>
                        <p className="text-sm text-gray-500">
                          {step.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex flex-wrap gap-3">
                  <Button onClick={handleVoiceRecording}>
                    {voiceStage === 'recording'
                      ? 'Detener y transcribir'
                      : 'Iniciar grabación demo'}
                  </Button>
                  <Button variant="secondary" onClick={handleVoiceComplete}>
                    Generar gasto con `/complete_expense`
                  </Button>
                </div>

                {renderFieldProgress(voiceFieldProgress)}
              </div>
            </Card>
          )}

          {entryMode === 'ticket' && (
            <Card
              title="Foto / Ticket"
              subtitle="Simula `/invoicing/tickets/{id}/create-expense`"
            >
              <div className="space-y-4">
                <div className="border-2 border-dashed border-gray-200 rounded-2xl p-6 text-center bg-gray-50">
                  <ImageIcon className="w-10 h-10 text-gray-400 mx-auto" />
                  <p className="mt-3 font-medium text-gray-900">
                    Arrastra una foto o ticket
                  </p>
                  <p className="text-sm text-gray-500">
                    JPG, PNG o PDF hasta 10MB. También recibiremos fotos desde
                    WhatsApp.
                  </p>
                  <Button
                    className="mt-4"
                    variant="outline"
                    onClick={handleTicketUpload}
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    Simular subida
                  </Button>
                </div>

                <div className="rounded-xl border border-gray-200 p-4 bg-white">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Datos OCR detectados
                  </label>
                  <textarea
                    rows={4}
                    className="w-full border border-gray-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary-500"
                    value={ticketNotes}
                    onChange={(event) => setTicketNotes(event.target.value)}
                  />
                </div>

                <div className="grid gap-3">
                  {ticketSteps.map((step) => (
                    <div
                      key={step.label}
                      className={cn(
                        'rounded-xl border px-4 py-3 flex items-start gap-3',
                        step.active
                          ? 'border-sky-200 bg-sky-50'
                          : 'border-gray-200 bg-white'
                      )}
                    >
                      <Radio
                        className={cn(
                          'w-5 h-5 mt-0.5',
                          step.active ? 'text-sky-600' : 'text-gray-400'
                        )}
                      />
                      <div>
                        <p className="font-medium text-gray-900">{step.label}</p>
                        <p className="text-sm text-gray-500">
                          {step.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>

                <Button
                  variant="secondary"
                  fullWidth
                  disabled={ticketStage !== 'ready'}
                >
                  Crear gasto desde ticket
                </Button>

                {renderFieldProgress(ticketFieldProgress)}
              </div>
            </Card>
          )}

          <Card
            title="Cómo se conecta con WhatsApp"
            subtitle="El flujo completo vive aquí; WhatsApp será una puerta adicional a los mismos endpoints."
          >
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {whatsappSteps.map((step) => (
                <div
                  key={step.title}
                  className="rounded-2xl border border-gray-200 p-4 bg-gray-50"
                >
                  <div className="flex items-center gap-3">
                    <div className="bg-white rounded-xl p-2 border border-gray-200">
                      {step.title === 'Texto' && (
                        <MessageCircle className="w-5 h-5 text-[#11446e]" />
                      )}
                      {step.title === 'Voz' && (
                        <Mic className="w-5 h-5 text-[#11446e]" />
                      )}
                      {step.title === 'Foto/Ticket' && (
                        <ImageIcon className="w-5 h-5 text-[#11446e]" />
                      )}
                      {step.title === 'Confirmación' && (
                        <PhoneCall className="w-5 h-5 text-[#11446e]" />
                      )}
                    </div>
                    <div>
                      <p className="font-semibold text-gray-900">
                        {step.title}
                      </p>
                      <p className="text-xs text-gray-500">{step.status}</p>
                    </div>
                  </div>
                  <p className="text-sm text-gray-600 mt-3">{step.description}</p>
                </div>
              ))}
            </div>

            <div className="mt-6 rounded-xl border border-dashed border-[#60b97b] bg-[#60b97b]/10 p-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-3">
                <Wand2 className="w-6 h-6 text-[#11446e]" />
                <div>
                  <p className="font-semibold text-[#11446e]">
                    Demo lista para mostrar
                  </p>
                  <p className="text-sm text-[#11446e]/80">
                    Desde aquí se puede continuar capturando gastos; cuando
                    llegue el webhook de WhatsApp, solo haremos forward de los
                    payloads a estas mismas acciones.
                  </p>
                </div>
              </div>
              <Button variant="outline">
                Ver documentación de endpoints
              </Button>
            </div>
          </Card>
        </div>
      </AppLayout>
    </ProtectedRoute>
  );
}

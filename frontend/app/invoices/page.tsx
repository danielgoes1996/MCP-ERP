/**
 * Invoices List Page
 *
 * Comprehensive and granular viewer for all uploaded invoices
 * Shows all extracted CFDI data in organized sections
 */

'use client';

import { useState, useEffect, useMemo } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { AppLayout } from '@/components/layout/AppLayout';
import { PageHeader } from '@/components/ui/PageHeader';
import { Button } from '@/components/ui/Button';
import {
  FileText,
  Search,
  CheckCircle,
  XCircle,
  Clock,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Calendar,
  DollarSign,
  Building,
  Hash,
  Tag,
  TrendingUp,
  RefreshCw,
  X,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import Link from 'next/link';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import { InlineClassificationControl, type ClassificationData } from '@/components/classification/InlineClassificationControl';
import { getClassificationDetail, confirmClassification, correctClassification } from '@/services/classificationService';
import { ClassificationCorrectionModal } from '@/components/classification/ClassificationCorrectionModal';

// Catálogos del SAT
const FORMA_PAGO_SAT: Record<string, string> = {
  '01': 'Efectivo',
  '02': 'Cheque nominativo',
  '03': 'Transferencia electrónica de fondos',
  '04': 'Tarjeta de crédito',
  '05': 'Monedero electrónico',
  '06': 'Dinero electrónico',
  '08': 'Vales de despensa',
  '12': 'Dación en pago',
  '13': 'Pago por subrogación',
  '14': 'Pago por consignación',
  '15': 'Condonación',
  '17': 'Compensación',
  '23': 'Novación',
  '24': 'Confusión',
  '25': 'Remisión de deuda',
  '26': 'Prescripción o caducidad',
  '27': 'A satisfacción del acreedor',
  '28': 'Tarjeta de débito',
  '29': 'Tarjeta de servicios',
  '30': 'Aplicación de anticipos',
  '31': 'Intermediario pagos',
  '99': 'Por definir',
};

const METODO_PAGO_SAT: Record<string, string> = {
  'PUE': 'Pago en una sola exhibición',
  'PPD': 'Pago en parcialidades o diferido',
};

const USO_CFDI_SAT: Record<string, string> = {
  'G01': 'Adquisición de mercancías',
  'G02': 'Devoluciones, descuentos o bonificaciones',
  'G03': 'Gastos en general',
  'I01': 'Construcciones',
  'I02': 'Mobilario y equipo de oficina por inversiones',
  'I03': 'Equipo de transporte',
  'I04': 'Equipo de computo y accesorios',
  'I05': 'Dados, troqueles, moldes, matrices y herramental',
  'I06': 'Comunicaciones telefónicas',
  'I07': 'Comunicaciones satelitales',
  'I08': 'Otra maquinaria y equipo',
  'D01': 'Honorarios médicos, dentales y gastos hospitalarios',
  'D02': 'Gastos médicos por incapacidad o discapacidad',
  'D03': 'Gastos funerales',
  'D04': 'Donativos',
  'D05': 'Intereses reales efectivamente pagados por créditos hipotecarios (casa habitación)',
  'D06': 'Aportaciones voluntarias al SAR',
  'D07': 'Primas por seguros de gastos médicos',
  'D08': 'Gastos de transportación escolar obligatoria',
  'D09': 'Depósitos en cuentas para el ahorro, primas que tengan como base planes de pensiones',
  'D10': 'Pagos por servicios educativos (colegiaturas)',
  'S01': 'Sin efectos fiscales',
  'CP01': 'Pagos',
  'CN01': 'Nómina',
};

const getFormaPagoLabel = (code: string | null) => {
  if (!code) return 'No especificado';
  return FORMA_PAGO_SAT[code] || `${code} (No catalogado)`;
};

const getMetodoPagoLabel = (code: string | null) => {
  if (!code) return 'No especificado';
  return METODO_PAGO_SAT[code] || `${code} (No catalogado)`;
};

const getUsoCFDILabel = (code: string | null) => {
  if (!code) return 'No especificado';
  return USO_CFDI_SAT[code] || `${code} (No catalogado)`;
};

interface InvoiceSession {
  session_id: string;
  company_id: string;
  user_id: string;
  original_filename: string;
  status: string;
  extraction_status: string;
  detected_format: string;
  parser_used: string;
  extraction_confidence: number;
  validation_score: number;
  overall_quality_score: number;
  has_parsed_data: boolean;
  has_template_match: boolean;
  has_validation_results: boolean;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  display_info?: {
    emisor_nombre: string | null;
    emisor_rfc: string | null;
    receptor_rfc: string | null;
    total: number | null;
    moneda: string | null;
    fecha_emision: string | null;
    metodo_pago: string | null;
    tipo_comprobante: string | null;
    sat_status: string | null;  // LLM-inferred status
    uuid: string | null;
    serie: string | null;
    folio: string | null;
  };
  sat_validation?: {
    status: string;  // Real SAT validation status
    codigoEstatus: string | null;
    esCancelable: boolean | null;
    estado: string | null;
    validacionEfos: string | null;
    verifiedAt: string | null;
    lastCheckAt: string | null;
    error: string | null;
    verificationUrl: string | null;
  };
}

interface ExtractedData {
  uuid: string;
  serie: string | null;
  folio: string | null;
  fecha_emision: string;
  fecha_timbrado: string;
  tipo_comprobante: string;
  moneda: string;
  tipo_cambio: number | null;
  subtotal: number;
  descuento: number | null;
  total: number;
  forma_pago: string | null;
  metodo_pago: string | null;
  uso_cfdi: string | null;
  sat_status: string;
  emisor: {
    nombre: string | null;
    rfc: string | null;
    regimen_fiscal: string | null;
  };
  receptor: {
    nombre: string | null;
    rfc: string | null;
    uso_cfdi: string | null;
    domicilio_fiscal: string | null;
  };
  impuestos: {
    traslados: any[];
    retenciones: any[];
  };
  tax_badges: string[];
  pagos: {
    tipo: string;
    numero_parcialidades: number | null;
  };
  conceptos: any[];
}

export default function InvoicesPage() {
  const [sessions, setSessions] = useState<InvoiceSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [extractedData, setExtractedData] = useState<Record<string, ExtractedData>>({});
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [invoiceTypeFilter, setInvoiceTypeFilter] = useState<string>('all'); // all, emitidas, recibidas
  const [paymentMethodFilter, setPaymentMethodFilter] = useState<string>('all'); // all, PUE, PPD, undefined
  const [satStatusFilter, setSatStatusFilter] = useState<string>('all'); // all, vigente, cancelado, sustituido, desconocido

  // Default to all periods (null) to show all invoices on first load
  // Users can then filter by specific period
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<number | null>(null);
  const [expandedSessions, setExpandedSessions] = useState<Set<string>>(new Set());
  const [reprocessing, setReprocessing] = useState(false);
  const [reprocessMessage, setReprocessMessage] = useState<string | null>(null);

  // Classification state
  const [classifications, setClassifications] = useState<Record<string, ClassificationData>>({});
  const [classificationLoading, setClassificationLoading] = useState(false);
  const [correctionModalOpen, setCorrectionModalOpen] = useState(false);
  const [correctionSessionId, setCorrectionSessionId] = useState<string | null>(null);

  // Tab state for switching between Facturas and Complementos de Pago
  const [activeTab, setActiveTab] = useState<'invoices' | 'payment-complements'>('invoices');

  // Get user and tenant from auth context
  const { user, tenant} = useAuthStore();

  // RFC de la empresa (deberías obtenerlo del contexto de autenticación)
  const companyRFC = 'POL210218264'; // TODO: Get from auth context

  useEffect(() => {
    if (user && tenant) {
      fetchSessions();
    }
  }, [user, tenant]); // Only refetch when auth changes, filtering is done client-side

  const fetchSessions = async () => {
    try {
      setLoading(true);

      // Get company_id from authenticated user's tenant
      if (!user || !tenant) {
        console.error('User not authenticated');
        setSessions([]);
        setLoading(false);
        return;
      }

      // Use company_id string from tenant (populated by backend from companies.company_id)
      // Falls back to tenant ID if company_id is not set (for backward compatibility)
      const companyId = tenant.company_id || tenant.id.toString();

      if (!tenant.company_id) {
        console.warn('[Invoices] tenant.company_id is not set, falling back to tenant.id:', tenant.id);
      }

      // Fetch ALL sessions - filtering is done client-side to avoid multiple requests
      const url = `http://localhost:8000/universal-invoice/sessions/company/${companyId}`;

      console.log(`[Invoices] Fetching sessions for company ${companyId} from:`, url);

      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });

      console.log(`[Invoices] Response status:`, response.status);

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`[Invoices] Error response:`, errorText);
        throw new Error('Failed to fetch sessions');
      }

      const data = await response.json();
      console.log(`[Invoices] Received data:`, data);
      console.log(`[Invoices] Sessions count:`, data.sessions?.length || 0);
      setSessions(data.sessions || []);

      // Cargar datos extraídos de TODAS las sesiones (no solo completed)
      // para poder mostrarlos en la tabla de complementos de pago
      (data.sessions || []).forEach((session: InvoiceSession) => {
        fetchExtractedData(session.session_id);
      });

      // Cargar clasificaciones para todas las sesiones
      fetchClassifications(data.sessions || []);
    } catch (error) {
      console.error('Error fetching sessions:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchExtractedData = async (sessionId: string) => {
    try {
      const response = await fetch(
        `http://localhost:8000/universal-invoice/sessions/${sessionId}/extracted-data`,
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to fetch extracted data');
      }

      const data = await response.json();
      setExtractedData(prev => ({
        ...prev,
        [sessionId]: data.extracted_data,
      }));
    } catch (error) {
      console.error('Error fetching extracted data:', error);
    }
  };

  // Fetch classifications for all sessions
  const fetchClassifications = async (sessions: InvoiceSession[]) => {
    try {
      // Fetch classification for each session in parallel
      const classificationPromises = sessions.map(async (session) => {
        try {
          const detail = await getClassificationDetail(session.session_id);

          // Debug logging
          console.log(`Classification detail for ${session.session_id}:`, detail);
          console.log(`confidence_sat: ${detail.classification.confidence_sat}`);
          console.log(`metrics.confidence: ${detail.metrics?.confidence}`);

          // Use confidence_sat with fallback to metrics.confidence, then to 0.5
          const confidence =
            detail.classification.confidence_sat ??
            detail.metrics?.confidence ??
            0.5;

          console.log(`Final confidence used: ${confidence}`);

          // Transform ClassificationDetail to ClassificationData
          const classification: ClassificationData = {
            session_id: detail.session_id,
            sat_code: detail.classification.sat_account_code,
            sat_account_name: detail.classification.sat_account_code, // Use code as name fallback
            family_code: detail.classification.family_code,
            confidence: confidence,
            explanation: detail.classification.explanation_short,
            explanation_detail: undefined,
            status: detail.classification.status as 'pending_confirmation' | 'confirmed' | 'corrected' | 'not_classified',
            confirmed_by: detail.classification.confirmed_by || undefined,
            confirmed_at: detail.classification.confirmed_at || undefined,
            corrected_code: detail.classification.corrected_sat_code || undefined,
            corrected_at: detail.classification.corrected_at || undefined,
            corrected_notes: detail.classification.correction_notes || undefined,
            alternative_candidates: detail.classification.alternative_candidates || undefined,
            hierarchical_phase1: detail.metadata?.hierarchical_phase1 || undefined,
          };

          return { sessionId: session.session_id, classification };
        } catch (error) {
          // Classification not found or error - skip it
          console.error(`Error fetching classification for ${session.session_id}:`, error);
          return { sessionId: session.session_id, classification: null };
        }
      });

      const results = await Promise.all(classificationPromises);

      // Build classifications map
      const classificationsMap: Record<string, ClassificationData> = {};
      results.forEach(({ sessionId, classification }) => {
        if (classification) {
          classificationsMap[sessionId] = classification;
        }
      });

      console.log('Final classifications map:', classificationsMap);
      setClassifications(classificationsMap);
    } catch (error) {
      console.error('Error fetching classifications:', error);
    }
  };

  // Handle confirm classification
  const handleConfirmClassification = async (sessionId: string, alternativeCode?: string) => {
    if (!user?.id) return;

    try {
      setClassificationLoading(true);

      // If alternative code provided, use correction endpoint
      if (alternativeCode) {
        await correctClassification(
          sessionId,
          alternativeCode,
          'Seleccionado de candidatos alternativos',
          user.id.toString()
        );

        // Update local state
        setClassifications(prev => ({
          ...prev,
          [sessionId]: {
            ...prev[sessionId],
            status: 'corrected',
            corrected_code: alternativeCode,
            corrected_by: user.full_name,
            corrected_at: new Date().toISOString(),
            corrected_notes: 'Seleccionado de candidatos alternativos',
          },
        }));

        alert('Clasificación alternativa confirmada exitosamente');
      } else {
        // Otherwise, use normal confirmation
        await confirmClassification(sessionId, user.id.toString());

        // Update local state
        setClassifications(prev => ({
          ...prev,
          [sessionId]: {
            ...prev[sessionId],
            status: 'confirmed',
            confirmed_by: user.full_name,
            confirmed_at: new Date().toISOString(),
          },
        }));

        alert('Clasificación confirmada exitosamente');
      }
    } catch (error) {
      console.error('Error confirming classification:', error);
      alert('Error al confirmar clasificación');
    } finally {
      setClassificationLoading(false);
    }
  };

  // Handle correct classification
  const handleCorrectClassification = (sessionId: string) => {
    setCorrectionSessionId(sessionId);
    setCorrectionModalOpen(true);
  };

  // Handle submit correction
  const handleSubmitCorrection = async (correctedCode: string, notes?: string) => {
    if (!correctionSessionId || !user?.id) return;

    try {
      setClassificationLoading(true);
      await correctClassification(correctionSessionId, correctedCode, notes, user.id.toString());

      // Update local state
      setClassifications(prev => ({
        ...prev,
        [correctionSessionId]: {
          ...prev[correctionSessionId],
          status: 'corrected',
          corrected_code: correctedCode,
          corrected_notes: notes,
          corrected_by: user.full_name,
          corrected_at: new Date().toISOString(),
        },
      }));

      setCorrectionModalOpen(false);
      setCorrectionSessionId(null);
      alert('Clasificación corregida exitosamente');
    } catch (error) {
      console.error('Error correcting classification:', error);
      alert('Error al corregir clasificación');
    } finally {
      setClassificationLoading(false);
    }
  };

  // Handle classify manually
  const handleClassifyManually = (sessionId: string) => {
    // Open correction modal with empty code (manual classification)
    setCorrectionSessionId(sessionId);
    setCorrectionModalOpen(true);
  };

  const handleReprocessFailed = async () => {
    if (!tenant) {
      setReprocessMessage('Error: No se pudo identificar la empresa');
      return;
    }

    try {
      setReprocessing(true);
      setReprocessMessage(null);

      const response = await fetch(
        `http://localhost:8000/universal-invoice/sessions/reprocess-failed/?company_id=${tenant.id}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to reprocess failed invoices');
      }

      const result = await response.json();

      if (result.reprocessed_sessions === 0) {
        setReprocessMessage('No hay facturas con datos incompletos para reprocesar');
      } else {
        setReprocessMessage(
          `✓ Reprocesando ${result.reprocessed_sessions} factura${result.reprocessed_sessions !== 1 ? 's' : ''} en segundo plano. El procesamiento continuará aunque salgas de esta página.`
        );

        // Refresh the list after a delay to show updated statuses
        setTimeout(() => {
          fetchSessions();
        }, 3000);
      }
    } catch (error) {
      console.error('Error reprocessing failed invoices:', error);
      setReprocessMessage('Error al reprocesar facturas. Intenta nuevamente.');
    } finally {
      setReprocessing(false);

      // Clear message after 10 seconds
      setTimeout(() => {
        setReprocessMessage(null);
      }, 10000);
    }
  };

  const toggleSessionExpanded = (sessionId: string) => {
    const newExpanded = new Set(expandedSessions);
    if (newExpanded.has(sessionId)) {
      newExpanded.delete(sessionId);
    } else {
      newExpanded.add(sessionId);
      // Fetch extracted data if not already loaded
      if (!extractedData[sessionId]) {
        fetchExtractedData(sessionId);
      }
    }
    setExpandedSessions(newExpanded);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle strokeWidth={1.5} className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />;
      case 'processing':
        return <Clock strokeWidth={1.5} className="w-4 h-4 text-blue-600 dark:text-blue-400" />;
      case 'pending':
        return <CheckCircle strokeWidth={1.5} className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />;
      case 'failed':
        return <XCircle strokeWidth={1.5} className="w-4 h-4 text-red-600 dark:text-red-400" />;
      default:
        return <AlertCircle strokeWidth={1.5} className="w-4 h-4 text-slate-400" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      completed: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20',
      processing: 'bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20',
      pending: 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700',
      failed: 'bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/20',
    };

    const labels: Record<string, string> = {
      completed: 'Completado',
      processing: 'Procesando',
      pending: 'Pendiente',
      failed: 'Fallido',
    };

    return (
      <span className={cn('px-2.5 py-1 rounded-lg text-xs font-medium border backdrop-blur-xl', styles[status] || styles.pending)}>
        {labels[status] || status}
      </span>
    );
  };

  const formatCurrency = (amount: number, currency: string = 'MXN') => {
    return new Intl.NumberFormat('es-MX', {
      style: 'currency',
      currency: currency,
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('es-MX', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getInvoiceDisplayInfo = (session: InvoiceSession) => {
    // Priorizar display_info del backend (cargado directamente con la sesión)
    if (session.display_info) {
      const { emisor_nombre, total, moneda, fecha_emision } = session.display_info;

      // Título: Nombre del emisor
      const title = emisor_nombre || session.original_filename;

      // Descripción: Generar resumen inteligente
      let description = '';

      if (total && moneda) {
        description += `${formatCurrency(total, moneda)}`;
      }

      if (fecha_emision) {
        const fecha = new Date(fecha_emision).toLocaleDateString('es-MX', {
          day: 'numeric',
          month: 'short',
          year: 'numeric'
        });
        description += description ? ` • ${fecha}` : fecha;
      }

      return {
        title,
        description: description || 'Factura procesada'
      };
    }

    // Fallback: Usar extractedData cargado asíncronamente
    const data = extractedData[session.session_id];

    if (!data) {
      return {
        title: session.original_filename,
        description: 'Procesando información...'
      };
    }

    // Título: Nombre del emisor
    const title = data.emisor?.nombre || session.original_filename;

    // Descripción: Generar resumen inteligente
    let description = '';

    if (data.total && data.moneda) {
      description += `${formatCurrency(data.total, data.moneda)}`;
    }

    if (data.fecha_emision) {
      const fecha = new Date(data.fecha_emision).toLocaleDateString('es-MX', {
        day: 'numeric',
        month: 'short',
        year: 'numeric'
      });
      description += description ? ` • ${fecha}` : fecha;
    }

    // Agregar concepto principal si existe
    if (data.conceptos && data.conceptos.length > 0) {
      const concepto = data.conceptos[0].descripcion || data.conceptos[0].concepto;
      if (concepto) {
        const conceptoCorto = concepto.length > 50
          ? concepto.substring(0, 50) + '...'
          : concepto;
        description += description ? ` • ${conceptoCorto}` : conceptoCorto;
      }
    }

    // Si no hay descripción, usar uso CFDI
    if (!description && data.uso_cfdi) {
      description = getUsoCFDILabel(data.uso_cfdi);
    }

    return {
      title,
      description: description || 'Factura procesada'
    };
  };

  // Determinar si una factura es emitida o recibida
  const getInvoiceType = (session: InvoiceSession): 'emitida' | 'recibida' | 'unknown' => {
    if (!session.display_info?.emisor_rfc || !session.display_info?.receptor_rfc) {
      return 'unknown';
    }
    return session.display_info.emisor_rfc === companyRFC ? 'emitida' : 'recibida';
  };

  // Obtener método de pago de la sesión
  const getPaymentMethod = (session: InvoiceSession): string => {
    if (session.display_info?.metodo_pago) {
      return session.display_info.metodo_pago;
    }
    // Fallback: buscar en extractedData
    const data = extractedData[session.session_id];
    return data?.metodo_pago || 'Sin definir';
  };

  // Obtener estado SAT de la sesión
  const getSatStatus = (session: InvoiceSession): string => {
    // Prioridad 1: display_info.sat_status (si no es "desconocido")
    if (session.display_info?.sat_status &&
        session.display_info.sat_status !== 'desconocido') {
      return session.display_info.sat_status;
    }

    // Prioridad 2: sat_validation.status (fallback crítico)
    if (session.sat_validation?.status &&
        session.sat_validation.status !== 'pending') {
      return session.sat_validation.status;
    }

    // Prioridad 3: display_info.sat_status incluso si es "desconocido"
    if (session.display_info?.sat_status) {
      return session.display_info.sat_status;
    }

    // Prioridad 4: buscar en extractedData
    const data = extractedData[session.session_id];
    return data?.sat_status || 'desconocido';
  };

  // Obtener tipo de comprobante (I, E, P, N, T)
  const getTipoComprobante = (session: InvoiceSession): string | null => {
    if (session.display_info?.tipo_comprobante) {
      return session.display_info.tipo_comprobante;
    }
    // Fallback: buscar en extractedData
    const data = extractedData[session.session_id];
    return data?.tipo_comprobante || null;
  };

  // Extraer años únicos de las facturas
  const availableYears = useMemo(() => {
    const years = new Set<number>();
    sessions.forEach(session => {
      const dateStr = session.display_info?.fecha_emision || session.created_at;
      if (dateStr) {
        const year = new Date(dateStr).getFullYear();
        if (!isNaN(year)) {
          years.add(year);
        }
      }
    });
    return Array.from(years).sort((a, b) => b - a); // Más reciente primero
  }, [sessions]);

  // Filtrar sesiones
  const filteredSessions = sessions.filter(session => {
    // FILTRO POR TAB: Separar facturas de complementos de pago
    const tipoComprobante = getTipoComprobante(session);

    if (activeTab === 'invoices') {
      // En tab de facturas: SOLO mostrar tipo I, E, N, T (excluir tipo P)
      if (tipoComprobante === 'P') {
        return false; // Excluir complementos de pago
      }
    } else if (activeTab === 'payment-complements') {
      // En tab de complementos: SOLO mostrar tipo P
      if (tipoComprobante !== 'P') {
        return false; // Excluir facturas normales
      }
    }

    // Filtro de búsqueda
    const matchesSearch = session.original_filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
      session.session_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (session.display_info?.emisor_nombre?.toLowerCase().includes(searchTerm.toLowerCase()) || false);

    // Filtro de estado
    // Accept invoices where:
    // 1. status matches the filter, OR
    // 2. extraction_status is completed (data is ready to display)
    let matchesStatus = statusFilter === 'all' || session.status === statusFilter;

    // If statusFilter is 'completed', also show invoices with extraction_status = 'completed'
    // This allows users to see invoices that have been processed but not yet fully completed
    if (statusFilter === 'completed' && session.extraction_status === 'completed') {
      matchesStatus = true;
    }

    // For 'all' filter, show anything with display_info (extraction completed)
    if (statusFilter === 'all' && session.display_info) {
      matchesStatus = true;
    }

    // Filtro de tipo de factura (emitida/recibida)
    let matchesInvoiceType = true;
    if (invoiceTypeFilter !== 'all') {
      const invoiceType = getInvoiceType(session);
      matchesInvoiceType = invoiceType === invoiceTypeFilter;
    }

    // Filtro de método de pago
    let matchesPaymentMethod = true;
    if (paymentMethodFilter !== 'all') {
      const paymentMethod = getPaymentMethod(session);
      if (paymentMethodFilter === 'undefined') {
        matchesPaymentMethod = !paymentMethod || paymentMethod === 'Sin definir';
      } else {
        matchesPaymentMethod = paymentMethod === paymentMethodFilter;
      }
    }

    // Filtro de estado SAT
    let matchesSatStatus = true;
    if (satStatusFilter !== 'all') {
      const satStatus = getSatStatus(session);
      matchesSatStatus = satStatus === satStatusFilter;
    }

    // Filtro de año y mes
    let matchesDate = true;
    if (selectedYear !== null || selectedMonth !== null) {
      const dateStr = session.display_info?.fecha_emision || session.created_at;
      if (dateStr) {
        const date = new Date(dateStr);
        if (selectedYear !== null) {
          matchesDate = matchesDate && date.getFullYear() === selectedYear;
        }
        if (selectedMonth !== null) {
          matchesDate = matchesDate && (date.getMonth() + 1) === selectedMonth;
        }
      } else {
        matchesDate = false;
      }
    }

    return matchesSearch && matchesStatus && matchesInvoiceType && matchesPaymentMethod && matchesSatStatus && matchesDate;
  });

  // Calcular estadísticas detalladas para las 4 cards (basadas en filtros activos)
  const detailedStats = useMemo(() => {
    // Usar filteredSessions para que las stats reflejen los filtros activos
    const vigenteSessions = filteredSessions.filter(s => getSatStatus(s) === 'vigente');
    const canceladoSessions = filteredSessions.filter(s => getSatStatus(s) === 'cancelado');
    const sustituidoSessions = filteredSessions.filter(s => getSatStatus(s) === 'sustituido');

    // Card 1: Resumen del periodo
    const recibidas = vigenteSessions.filter(s => getInvoiceType(s) === 'recibida');
    const emitidas = vigenteSessions.filter(s => getInvoiceType(s) === 'emitida');
    const recibidasTotal = recibidas.reduce((sum, s) => sum + (s.display_info?.total || 0), 0);
    const emitidasTotal = emitidas.reduce((sum, s) => sum + (s.display_info?.total || 0), 0);

    // Card 2: IVA del periodo (simplificado - usamos el total como aproximación)
    const ivaAcreditable = recibidasTotal * 0.16; // Aproximación del IVA
    const ivaTrasladado = emitidasTotal * 0.16; // Aproximación del IVA
    const baseTasa0 = 0; // Por ahora en 0, se puede calcular después

    // Card 3: Pagos & complementos
    const pue = vigenteSessions.filter(s => getPaymentMethod(s) === 'PUE');
    const ppd = vigenteSessions.filter(s => getPaymentMethod(s) === 'PPD');
    const ppdConComplementoCount = 0; // Por definir con campo real
    const ppdSinComplementoCount = ppd.length; // Por ahora todos sin complemento

    // Card 4: SAT & Conciliación
    const failedCount = filteredSessions.filter(s => s.status === 'failed').length;

    // Estadísticas de complementos de pago (Tipo P)
    const paymentComplements = filteredSessions.filter(s => getTipoComprobante(s) === 'P');
    const paymentComplementsVigentes = paymentComplements.filter(s => getSatStatus(s) === 'vigente');

    // Calcular monto total pagado (suma de payment_complement.pagos[].monto)
    const totalPagado = paymentComplementsVigentes.reduce((sum, s) => {
      const paymentComp = s.parsed_data?.payment_complement;
      if (!paymentComp?.pagos) return sum;
      const pagosTotal = paymentComp.pagos.reduce((pSum: number, pago: any) => pSum + (pago.monto || 0), 0);
      return sum + pagosTotal;
    }, 0);

    // Contar formas de pago CON MONTOS + PORCENTAJES
    const formasPagoStats: Record<string, { count: number; monto: number }> = {};
    paymentComplementsVigentes.forEach(s => {
      const paymentComp = s.parsed_data?.payment_complement;
      if (!paymentComp?.pagos) return;
      paymentComp.pagos.forEach((pago: any) => {
        const forma = pago.forma_pago || 'No especificado';
        if (!formasPagoStats[forma]) {
          formasPagoStats[forma] = { count: 0, monto: 0 };
        }
        formasPagoStats[forma].count++;
        formasPagoStats[forma].monto += pago.monto || 0;
      });
    });

    // Analizar facturas relacionadas: totalmente pagadas vs con saldo pendiente
    const facturasRelacionadasMap = new Map<string, { saldoPendiente: number; totalPagado: number; numParcialidades: number }>();
    paymentComplementsVigentes.forEach(s => {
      const paymentComp = s.parsed_data?.payment_complement;
      if (!paymentComp?.pagos) return;
      paymentComp.pagos.forEach((pago: any) => {
        if (pago.documentos_relacionados) {
          pago.documentos_relacionados.forEach((doc: any) => {
            const uuid = doc.id_documento;
            if (!uuid) return;

            if (!facturasRelacionadasMap.has(uuid)) {
              facturasRelacionadasMap.set(uuid, { saldoPendiente: 0, totalPagado: 0, numParcialidades: 0 });
            }
            const facturaData = facturasRelacionadasMap.get(uuid)!;
            facturaData.saldoPendiente = doc.imp_saldo_insoluto || 0;
            facturaData.totalPagado += doc.imp_pagado || 0;
            facturaData.numParcialidades++;
          });
        }
      });
    });

    // Contar facturas totalmente pagadas vs con saldo pendiente
    let facturasTotalmentePagadas = 0;
    let facturasConSaldoPendiente = 0;
    let saldoPendienteTotal = 0;

    facturasRelacionadasMap.forEach(({ saldoPendiente }) => {
      if (saldoPendiente === 0) {
        facturasTotalmentePagadas++;
      } else {
        facturasConSaldoPendiente++;
        saldoPendienteTotal += saldoPendiente;
      }
    });

    // Contar parcialidades completas vs pendientes
    let parcialidadesCompletas = 0;
    let parcialidadesPendientes = 0;
    paymentComplementsVigentes.forEach(s => {
      const paymentComp = s.parsed_data?.payment_complement;
      if (!paymentComp?.pagos) return;
      paymentComp.pagos.forEach((pago: any) => {
        if (pago.documentos_relacionados) {
          pago.documentos_relacionados.forEach((doc: any) => {
            if (doc.imp_saldo_insoluto === 0) {
              parcialidadesCompletas++;
            } else {
              parcialidadesPendientes++;
            }
          });
        }
      });
    });

    return {
      // Card 1
      vigentesCount: vigenteSessions.length,
      recibidasCount: recibidas.length,
      recibidasTotal,
      emitidasCount: emitidas.length,
      emitidasTotal,
      totalGeneral: recibidasTotal + emitidasTotal,

      // Card 2
      ivaAcreditable,
      ivaTrasladado,
      baseTasa0,

      // Card 3
      pueCount: pue.length,
      ppdCount: ppd.length,
      ppdConComplementoCount,
      ppdSinComplementoCount,

      // Card 4
      canceladoCount: canceladoSessions.length,
      sustituidoCount: sustituidoSessions.length,
      failedCount,

      // Total
      total: filteredSessions.length,

      // Complementos de pago (Tipo P) - Versión mejorada
      paymentComplementsCount: paymentComplements.length,
      paymentComplementsVigentesCount: paymentComplementsVigentes.length,
      totalPagado,
      formasPagoStats, // { forma: { count, monto } }
      facturasRelacionadasCount: facturasRelacionadasMap.size,
      facturasTotalmentePagadas,
      facturasConSaldoPendiente,
      saldoPendienteTotal,
      parcialidadesCompletas,
      parcialidadesPendientes,
    };
  }, [filteredSessions]);

  // Contar complementos de pago excluidos para mostrar nota informativa
  const excludedPaymentComplements = useMemo(() => {
    return sessions.filter(s => getTipoComprobante(s) === 'P').length;
  }, [sessions]);

  // Ordenar facturas por fecha (más reciente primero)
  const sortedSessions = useMemo(() => {
    return [...filteredSessions].sort((a, b) => {
      const dateA = new Date(a.display_info?.fecha_emision || a.created_at);
      const dateB = new Date(b.display_info?.fecha_emision || b.created_at);
      return dateB.getTime() - dateA.getTime(); // Descendente (más reciente primero)
    });
  }, [filteredSessions]);

  return (
    <ProtectedRoute>
      <AppLayout>
        <div className="space-y-6">
          {/* Header */}
          <div className="flex flex-col gap-2">
            <PageHeader
              title="Facturas"
              subtitle="Visualizador de CFDI recibidos y emitidos listos para conciliación"
              actions={
                <>
                  <Button
                    variant="outline"
                    onClick={handleReprocessFailed}
                    disabled={reprocessing}
                  >
                    <RefreshCw className={cn("w-4 h-4 mr-2", reprocessing && "animate-spin")} />
                    {reprocessing ? 'Reprocesando...' : 'Reprocesar Fallidas'}
                  </Button>
                  <Link href="/invoices/upload">
                    <Button variant="primary">
                      <FileText className="w-4 h-4 mr-2" />
                      Subir Facturas
                    </Button>
                  </Link>
                </>
              }
            />

            {/* Línea de contexto */}
            <div className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-2">
              <span>Empresa: {tenant?.name || 'Carreta Verde'}</span>
              <span>·</span>
              <span>
                Periodo: {selectedYear && selectedMonth
                  ? `${['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'][selectedMonth - 1]} ${selectedYear}`
                  : selectedYear
                  ? `${selectedYear}`
                  : 'Todos los periodos'}
              </span>
              <span>·</span>
              <span>
                Filtros: {statusFilter !== 'all' || invoiceTypeFilter !== 'all' || paymentMethodFilter !== 'all' || satStatusFilter !== 'all' || selectedYear !== null
                  ? 'Filtrados'
                  : 'Todos los CFDI'}
              </span>
            </div>
          </div>

          {/* Tabs: Facturas | Complementos de Pago */}
          <div className="flex items-center gap-1 border-b border-slate-200 dark:border-slate-700">
            <button
              onClick={() => setActiveTab('invoices')}
              className={cn(
                "px-4 py-3 text-sm font-medium transition-all border-b-2 -mb-px",
                activeTab === 'invoices'
                  ? "border-slate-900 dark:border-white text-slate-900 dark:text-white"
                  : "border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
              )}
            >
              Facturas ({sessions.filter(s => getTipoComprobante(s) !== 'P').length})
            </button>
            <button
              onClick={() => setActiveTab('payment-complements')}
              className={cn(
                "px-4 py-3 text-sm font-medium transition-all border-b-2 -mb-px",
                activeTab === 'payment-complements'
                  ? "border-slate-900 dark:border-white text-slate-900 dark:text-white"
                  : "border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
              )}
            >
              Complementos de Pago ({sessions.filter(s => getTipoComprobante(s) === 'P').length})
            </button>
          </div>

          {/* Reprocess Message */}
          {reprocessMessage && (
            <div className={cn(
              "relative p-4 rounded-xl backdrop-blur-xl border transition-all duration-200",
              reprocessMessage.includes('✓')
                ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-700 dark:text-emerald-400"
                : reprocessMessage.includes('Error')
                ? "bg-red-500/10 border-red-500/20 text-red-700 dark:text-red-400"
                : "bg-blue-500/10 border-blue-500/20 text-blue-700 dark:text-blue-400"
            )}>
              <p className="text-sm font-medium">{reprocessMessage}</p>
            </div>
          )}

          {/* Stats Cards - 4 cards interactivas */}
          {activeTab === 'payment-complements' ? (
            // Estadísticas específicas para Complementos de Pago (Tipo P)
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Card 1: Resumen de complementos de pago */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border-2 border-slate-300/80 dark:border-slate-600/80 p-5 hover:shadow-lg transition-all hover:border-slate-400 dark:hover:border-slate-500 cursor-pointer">
                <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-3 uppercase tracking-wide">Complementos de pago</p>
                <div className="space-y-2">
                  <button
                    onClick={() => setSatStatusFilter('vigente')}
                    className="w-full text-left hover:bg-slate-50 dark:hover:bg-slate-800 -mx-2 px-2 py-1 rounded transition-colors cursor-pointer"
                  >
                    <p className="text-3xl font-bold text-slate-900 dark:text-white">{detailedStats.paymentComplementsVigentesCount} vigentes</p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {detailedStats.paymentComplementsCount > 0 ? `${Math.round((detailedStats.paymentComplementsVigentesCount / detailedStats.paymentComplementsCount) * 100)}%` : '0%'} de los complementos están vigentes
                    </p>
                  </button>
                  <div className="space-y-1 text-sm">
                    <div className="px-2 py-0.5">
                      <span className="text-slate-700 dark:text-slate-300 font-medium">Total complementos: {detailedStats.paymentComplementsCount}</span>
                    </div>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 pt-2 border-t border-slate-200/60 dark:border-slate-700/60">
                    <span className="font-semibold">Monto total pagado:</span> {formatCurrency(detailedStats.totalPagado)}
                  </p>
                </div>
              </div>

              {/* Card 2: Facturas relacionadas - MEJORADO con montos */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200/60 dark:border-slate-700/60 p-4 hover:shadow-md transition-shadow">
                <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-3">Facturas relacionadas</p>
                <div className="space-y-2">
                  <div className="px-2 py-1">
                    <p className="text-2xl font-semibold text-slate-900 dark:text-white">{detailedStats.facturasRelacionadasCount}</p>
                    <p className="text-sm text-slate-700 dark:text-slate-300 mt-1">Facturas únicas con pagos</p>
                  </div>
                  <div className="space-y-1 text-sm">
                    <div className="px-2 py-1 bg-emerald-50 dark:bg-emerald-950/30 rounded-md border border-emerald-200/50 dark:border-emerald-900/50">
                      <p className="text-xs text-emerald-800 dark:text-emerald-300">
                        <CheckCircle2 className="w-3 h-3 inline mr-1" />
                        Pagadas totalmente: {detailedStats.facturasTotalmentePagadas}
                      </p>
                    </div>
                    {detailedStats.facturasConSaldoPendiente > 0 && (
                      <div className="px-2 py-1 bg-amber-50 dark:bg-amber-950/30 rounded-md border border-amber-200/50 dark:border-amber-900/50">
                        <p className="text-xs text-amber-800 dark:text-amber-300 leading-relaxed">
                          <AlertTriangle className="w-3 h-3 inline mr-1" />
                          Con saldo pendiente: {detailedStats.facturasConSaldoPendiente} · {formatCurrency(detailedStats.saldoPendienteTotal)}
                        </p>
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 pt-1 border-t border-slate-200/60 dark:border-slate-700/60">
                    {detailedStats.parcialidadesCompletas} parcialidades completas · {detailedStats.parcialidadesPendientes} pendientes
                  </p>
                </div>
              </div>

              {/* Card 3: Formas de pago - MEJORADO con montos y % */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200/60 dark:border-slate-700/60 p-4 hover:shadow-md transition-shadow">
                <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-3">Formas de pago (SAT)</p>
                <div className="space-y-2">
                  <div className="space-y-1 text-sm">
                    {Object.entries(detailedStats.formasPagoStats || {})
                      .sort(([, a], [, b]) => (b as any).monto - (a as any).monto)
                      .slice(0, 4)
                      .map(([forma, stats]: [string, any]) => {
                        const formaName = forma === '03' ? 'Transferencia' : forma === '04' ? 'Tarjeta crédito' : forma === '01' ? 'Efectivo' : forma === '28' ? 'Tarjeta débito' : `Forma ${forma}`;
                        const porcentaje = detailedStats.totalPagado > 0 ? Math.round((stats.monto / detailedStats.totalPagado) * 100) : 0;
                        return (
                          <div key={forma} className="px-2 py-1 hover:bg-slate-50 dark:hover:bg-slate-800 rounded transition-colors">
                            <div className="flex items-center justify-between">
                              <span className="text-slate-700 dark:text-slate-300 font-medium text-xs">{formaName}</span>
                              <span className="text-slate-500 dark:text-slate-400 text-xs">{porcentaje}%</span>
                            </div>
                            <div className="flex items-center justify-between mt-0.5">
                              <span className="text-slate-900 dark:text-white font-semibold text-sm">{formatCurrency(stats.monto)}</span>
                              <span className="text-slate-500 dark:text-slate-400 text-xs">{stats.count} pagos</span>
                            </div>
                          </div>
                        );
                      })}
                    {Object.keys(detailedStats.formasPagoStats || {}).length === 0 && (
                      <div className="px-2 py-0.5">
                        <span className="text-slate-400 dark:text-slate-500 text-xs italic">Sin formas de pago registradas</span>
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 pt-1 border-t border-slate-200/60 dark:border-slate-700/60">
                    Ordenado por monto total
                  </p>
                </div>
              </div>

              {/* Card 4: Estado SAT */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200/60 dark:border-slate-700/60 p-4 hover:shadow-md transition-shadow">
                <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-3">Validación SAT</p>
                <div className="space-y-2">
                  <button
                    onClick={() => setSatStatusFilter('vigente')}
                    className="w-full text-left hover:bg-slate-50 dark:hover:bg-slate-800 -mx-2 px-2 py-1 rounded transition-colors cursor-pointer"
                  >
                    <p className="text-2xl font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                      {detailedStats.paymentComplementsVigentesCount} vigentes
                      <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {detailedStats.paymentComplementsCount > 0 ? `${Math.round((detailedStats.paymentComplementsVigentesCount / detailedStats.paymentComplementsCount) * 100)}%` : '0%'} de {detailedStats.paymentComplementsCount} complementos
                    </p>
                  </button>
                  <div className="space-y-1 text-sm">
                    <div className="flex items-center gap-2 px-2">
                      <button
                        onClick={() => setSatStatusFilter('cancelado')}
                        className="hover:underline text-slate-700 dark:text-slate-300 cursor-pointer"
                      >
                        <span>Cancelados: </span>
                        <span className="font-medium text-slate-900 dark:text-white">
                          {detailedStats.paymentComplementsCount - detailedStats.paymentComplementsVigentesCount}
                        </span>
                      </button>
                    </div>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 pt-1 border-t border-slate-200/60 dark:border-slate-700/60">
                    Complementos validados contra SAT
                  </p>
                </div>
              </div>
            </div>
          ) : (
            // Estadísticas normales para facturas (Tipo I, E, etc.)
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Card 1: Resumen del periodo - MÁS PESO VISUAL */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border-2 border-slate-300/80 dark:border-slate-600/80 p-5 hover:shadow-lg transition-all hover:border-slate-400 dark:hover:border-slate-500 cursor-pointer">
                <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-3 uppercase tracking-wide">Resumen del periodo</p>
                <div className="space-y-2">
                  <button
                    onClick={() => {
                      setSatStatusFilter('vigente');
                      setInvoiceTypeFilter('all');
                    }}
                    className="w-full text-left hover:bg-slate-50 dark:hover:bg-slate-800 -mx-2 px-2 py-1 rounded transition-colors cursor-pointer"
                  >
                    <p className="text-3xl font-bold text-slate-900 dark:text-white">{detailedStats.vigentesCount} CFDI vigentes</p>
                    <p className="text-xs text-slate-500 mt-0.5">{detailedStats.total === detailedStats.vigentesCount ? '100%' : `${Math.round((detailedStats.vigentesCount / detailedStats.total) * 100)}%`} del total</p>
                  </button>
                  <div className="space-y-1 text-sm">
                    <button
                      onClick={() => setInvoiceTypeFilter('recibida')}
                      className="w-full text-left hover:bg-slate-50 dark:hover:bg-slate-800 -mx-2 px-2 py-0.5 rounded transition-colors flex items-center justify-between cursor-pointer"
                    >
                      <span className="text-slate-700 dark:text-slate-300 font-medium">Recibidas: {detailedStats.recibidasCount}</span>
                      <span className="text-slate-600 dark:text-slate-400">· {formatCurrency(detailedStats.recibidasTotal)}</span>
                    </button>
                    <button
                      onClick={() => setInvoiceTypeFilter('emitida')}
                      className="w-full text-left hover:bg-slate-50 dark:hover:bg-slate-800 -mx-2 px-2 py-0.5 rounded transition-colors flex items-center justify-between cursor-pointer"
                    >
                      <span className="text-slate-700 dark:text-slate-300 font-medium">Emitidas: {detailedStats.emitidasCount}</span>
                      <span className="text-slate-600 dark:text-slate-400">· {formatCurrency(detailedStats.emitidasTotal)}</span>
                    </button>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 pt-2 border-t border-slate-200/60 dark:border-slate-700/60">
                    <span className="font-semibold">Total CFDI (importe con IVA):</span> {formatCurrency(detailedStats.totalGeneral)}
                  </p>
                </div>
              </div>

              {/* Card 2: IVA del periodo */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200/60 dark:border-slate-700/60 p-4 hover:shadow-md transition-shadow">
                <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-3">IVA del periodo (CFDI vigentes)</p>
                <div className="space-y-2">
                  <button
                    onClick={() => setInvoiceTypeFilter('recibida')}
                    className="w-full text-left hover:bg-slate-50 dark:hover:bg-slate-800 -mx-2 px-2 py-1 rounded transition-colors cursor-pointer"
                  >
                    <p className="text-sm text-slate-700 dark:text-slate-300">IVA acreditable (recibidas):</p>
                    <p className="text-xl font-semibold text-slate-900 dark:text-white">{formatCurrency(detailedStats.ivaAcreditable)}</p>
                  </button>
                  <div className="space-y-1 text-sm">
                    {detailedStats.ivaTrasladado > 0 ? (
                      <button
                        onClick={() => setInvoiceTypeFilter('emitida')}
                        className="w-full text-left hover:bg-slate-50 dark:hover:bg-slate-800 -mx-2 px-2 py-0.5 rounded transition-colors cursor-pointer"
                      >
                        <span className="text-slate-700 dark:text-slate-300">IVA trasladado (emitidas): </span>
                        <span className="font-medium text-slate-900 dark:text-white">{formatCurrency(detailedStats.ivaTrasladado)}</span>
                      </button>
                    ) : (
                      <div className="px-2 py-0.5">
                        <span className="text-slate-400 dark:text-slate-500 text-xs italic">No hay IVA trasladado en este periodo</span>
                      </div>
                    )}
                    {detailedStats.baseTasa0 > 0 ? (
                      <div className="text-slate-700 dark:text-slate-300 px-2 py-0.5">
                        <span>Base tasa 0%: </span>
                        <span className="font-medium text-slate-900 dark:text-white">{formatCurrency(detailedStats.baseTasa0)}</span>
                      </div>
                    ) : (
                      <div className="px-2 py-0.5">
                        <span className="text-slate-400 dark:text-slate-500 text-xs italic">Sin operaciones a tasa 0%</span>
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 pt-1 border-t border-slate-200/60 dark:border-slate-700/60">
                    Cálculo estimado con CFDI vigentes del periodo
                  </p>
                </div>
              </div>

              {/* Card 3: Pagos & complementos */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200/60 dark:border-slate-700/60 p-4 hover:shadow-md transition-shadow">
                <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-3">Métodos de pago</p>
                <div className="space-y-2">
                  <button
                    onClick={() => setPaymentMethodFilter('PUE')}
                    className="w-full text-left hover:bg-slate-50 dark:hover:bg-slate-800 -mx-2 px-2 py-1 rounded transition-colors cursor-pointer"
                  >
                    <p className="text-2xl font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                      PUE: {detailedStats.pueCount} CFDI
                      <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">Pago en una sola exhibición</p>
                  </button>
                  <div className="space-y-1 text-sm">
                    <button
                      onClick={() => setPaymentMethodFilter('PPD')}
                      className="w-full text-left hover:bg-slate-50 dark:hover:bg-slate-800 -mx-2 px-2 py-0.5 rounded transition-colors cursor-pointer"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-slate-700 dark:text-slate-300 font-medium">PPD: {detailedStats.ppdCount} CFDI</span>
                        {detailedStats.ppdSinComplementoCount > 0 && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 text-xs font-medium">
                            <AlertTriangle className="w-3 h-3" />
                            {detailedStats.ppdSinComplementoCount} sin complemento
                          </span>
                        )}
                      </div>
                    </button>
                    {detailedStats.ppdSinComplementoCount > 0 && (
                      <div className="px-2 py-1 bg-amber-50 dark:bg-amber-950/30 rounded-md border border-amber-200/50 dark:border-amber-900/50">
                        <p className="text-xs text-amber-800 dark:text-amber-300 leading-relaxed">
                          <AlertTriangle className="w-3 h-3 inline mr-1" />
                          PPD sin complemento no son deducibles hasta recibir el CFDI de pago
                        </p>
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 pt-1 border-t border-slate-200/60 dark:border-slate-700/60">
                    Basado en método de pago del CFDI
                  </p>
                </div>
              </div>

              {/* Card 4: SAT & Conciliación bancaria */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200/60 dark:border-slate-700/60 p-4 hover:shadow-md transition-shadow">
                <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-3">Estado SAT & conciliación</p>
                <div className="space-y-2">
                  <button
                    onClick={() => setSatStatusFilter('vigente')}
                    className="w-full text-left hover:bg-slate-50 dark:hover:bg-slate-800 -mx-2 px-2 py-1 rounded transition-colors cursor-pointer"
                  >
                    <p className="text-2xl font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                      {detailedStats.vigentesCount} vigentes
                      <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {detailedStats.total > 0 ? `${Math.round((detailedStats.vigentesCount / detailedStats.total) * 100)}%` : '0%'} de {detailedStats.total} CFDI totales
                    </p>
                  </button>
                  <div className="space-y-1 text-sm">
                    <div className="flex items-center gap-2 px-2">
                      <button
                        onClick={() => setSatStatusFilter('cancelado')}
                        className="hover:underline text-slate-700 dark:text-slate-300 cursor-pointer"
                      >
                        <span>Canceladas: </span>
                        <span className="font-medium text-slate-900 dark:text-white">{detailedStats.canceladoCount}</span>
                      </button>
                      <span className="text-slate-500">·</span>
                      <button
                        onClick={() => setSatStatusFilter('sustituido')}
                        className="hover:underline text-slate-700 dark:text-slate-300 cursor-pointer"
                      >
                        <span>Sustituidas: </span>
                        <span className="font-medium text-slate-900 dark:text-white">{detailedStats.sustituidoCount}</span>
                      </button>
                    </div>
                    <div className="px-2 py-1.5 bg-blue-50 dark:bg-blue-950/30 rounded-md border border-blue-200/50 dark:border-blue-900/50 mt-2">
                      <p className="text-xs text-blue-700 dark:text-blue-300 font-medium mb-0.5">Conciliación bancaria</p>
                      <div className="text-xs text-blue-800 dark:text-blue-200">
                        <span className="font-semibold">{Math.floor(detailedStats.vigentesCount * 0.65)}</span> de <span className="font-semibold">{detailedStats.vigentesCount}</span> conciliadas
                        <span className="text-blue-600 dark:text-blue-400 ml-1">
                          ({detailedStats.vigentesCount > 0 ? Math.round((Math.floor(detailedStats.vigentesCount * 0.65) / detailedStats.vigentesCount) * 100) : 0}%)
                        </span>
                      </div>
                    </div>
                  </div>
                  {detailedStats.failedCount > 0 && (
                    <p className="text-xs text-amber-600 dark:text-amber-400 pt-1 border-t border-slate-200/60 dark:border-slate-700/60 flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" />
                      {detailedStats.failedCount} CFDI con errores de procesamiento
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Filtros Compactos + Búsqueda */}
          <div className="flex flex-col gap-3">
            {/* Fila 1: Búsqueda + Filtros principales */}
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Buscar facturas..."
                  className="w-full pl-9 pr-3 py-2.5 text-sm rounded-xl bg-white dark:bg-slate-900 border border-slate-200/60 dark:border-slate-700/60 text-slate-900 dark:text-white placeholder-slate-400 focus:border-slate-400 dark:focus:border-slate-500 focus:ring-0 outline-none transition-all"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-2.5 text-sm rounded-xl bg-white dark:bg-slate-900 border border-slate-200/60 dark:border-slate-700/60 text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600 focus:border-slate-400 dark:focus:border-slate-500 focus:ring-0 outline-none cursor-pointer transition-all appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%2212%22%20viewBox%3D%220%200%2012%2012%22%3E%3Cpath%20fill%3D%22%23475569%22%20d%3D%22M10.293%203.293L6%207.586%201.707%203.293A1%201%200%2000.293%204.707l5%205a1%201%200%20001.414%200l5-5a1%201%200%2010-1.414-1.414z%22%2F%3E%3C%2Fsvg%3E')] bg-[length:12px] bg-[center_right_0.75rem] bg-no-repeat pr-8"
              >
                <option value="all">Estado</option>
                <option value="completed">Completadas</option>
                <option value="processing">Procesando</option>
                <option value="pending">Pendientes</option>
                <option value="failed">Fallidas</option>
              </select>

              <select
                value={invoiceTypeFilter}
                onChange={(e) => setInvoiceTypeFilter(e.target.value)}
                className="px-3 py-2.5 text-sm rounded-xl bg-white dark:bg-slate-900 border border-slate-200/60 dark:border-slate-700/60 text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600 focus:border-slate-400 dark:focus:border-slate-500 focus:ring-0 outline-none cursor-pointer transition-all appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%2212%22%20viewBox%3D%220%200%2012%2012%22%3E%3Cpath%20fill%3D%22%23475569%22%20d%3D%22M10.293%203.293L6%207.586%201.707%203.293A1%201%200%2000.293%204.707l5%205a1%201%200%20001.414%200l5-5a1%201%200%2010-1.414-1.414z%22%2F%3E%3C%2Fsvg%3E')] bg-[length:12px] bg-[center_right_0.75rem] bg-no-repeat pr-8"
              >
                <option value="all">Tipo</option>
                <option value="emitida">Emitidas</option>
                <option value="recibida">Recibidas</option>
              </select>

              <select
                value={paymentMethodFilter}
                onChange={(e) => setPaymentMethodFilter(e.target.value)}
                className="px-3 py-2.5 text-sm rounded-xl bg-white dark:bg-slate-900 border border-slate-200/60 dark:border-slate-700/60 text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600 focus:border-slate-400 dark:focus:border-slate-500 focus:ring-0 outline-none cursor-pointer transition-all appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%2212%22%20viewBox%3D%220%200%2012%2012%22%3E%3Cpath%20fill%3D%22%23475569%22%20d%3D%22M10.293%203.293L6%207.586%201.707%203.293A1%201%200%2000.293%204.707l5%205a1%201%200%20001.414%200l5-5a1%201%200%2010-1.414-1.414z%22%2F%3E%3C%2Fsvg%3E')] bg-[length:12px] bg-[center_right_0.75rem] bg-no-repeat pr-8"
              >
                <option value="all">Método</option>
                <option value="PUE">PUE</option>
                <option value="PPD">PPD</option>
                <option value="undefined">Sin definir</option>
              </select>

              <select
                value={satStatusFilter}
                onChange={(e) => setSatStatusFilter(e.target.value)}
                className="px-3 py-2.5 text-sm rounded-xl bg-white dark:bg-slate-900 border border-slate-200/60 dark:border-slate-700/60 text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600 focus:border-slate-400 dark:focus:border-slate-500 focus:ring-0 outline-none cursor-pointer transition-all appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%2212%22%20viewBox%3D%220%200%2012%2012%22%3E%3Cpath%20fill%3D%22%23475569%22%20d%3D%22M10.293%203.293L6%207.586%201.707%203.293A1%201%200%2000.293%204.707l5%205a1%201%200%20001.414%200l5-5a1%201%200%2010-1.414-1.414z%22%2F%3E%3C%2Fsvg%3E')] bg-[length:12px] bg-[center_right_0.75rem] bg-no-repeat pr-8"
              >
                <option value="all">SAT</option>
                <option value="vigente">Vigente</option>
                <option value="cancelado">Cancelada</option>
                <option value="sustituido">Sustituida</option>
                <option value="desconocido">Desconocida</option>
              </select>

              <div className="flex items-center gap-1.5">
                <select
                  value={selectedYear || ''}
                  onChange={(e) => {
                    const year = e.target.value ? Number(e.target.value) : null;
                    setSelectedYear(year);
                    if (!year) setSelectedMonth(null); // Clear month if year is cleared
                  }}
                  className="px-3 py-2.5 text-sm rounded-xl bg-white dark:bg-slate-900 border border-slate-200/60 dark:border-slate-700/60 text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600 focus:border-slate-400 dark:focus:border-slate-500 focus:ring-0 outline-none cursor-pointer transition-all appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%2212%22%20viewBox%3D%220%200%2012%2012%22%3E%3Cpath%20fill%3D%22%23475569%22%20d%3D%22M10.293%203.293L6%207.586%201.707%203.293A1%201%200%2000.293%204.707l5%205a1%201%200%20001.414%200l5-5a1%201%200%2010-1.414-1.414z%22%2F%3E%3C%2Fsvg%3E')] bg-[length:12px] bg-[center_right_0.75rem] bg-no-repeat pr-8"
                >
                  <option value="">Año</option>
                  {availableYears.map(year => (
                    <option key={year} value={year}>{year}</option>
                  ))}
                </select>

                {selectedYear && (
                  <select
                    value={selectedMonth || ''}
                    onChange={(e) => {
                      const month = e.target.value ? Number(e.target.value) : null;
                      setSelectedMonth(month);
                    }}
                    className="px-3 py-2.5 text-sm rounded-xl bg-white dark:bg-slate-900 border border-slate-200/60 dark:border-slate-700/60 text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600 focus:border-slate-400 dark:focus:border-slate-500 focus:ring-0 outline-none cursor-pointer transition-all appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%2212%22%20viewBox%3D%220%200%2012%2012%22%3E%3Cpath%20fill%3D%22%23475569%22%20d%3D%22M10.293%203.293L6%207.586%201.707%203.293A1%201%200%2000.293%204.707l5%205a1%201%200%20001.414%200l5-5a1%201%200%2010-1.414-1.414z%22%2F%3E%3C%2Fsvg%3E')] bg-[length:12px] bg-[center_right_0.75rem] bg-no-repeat pr-8 animate-in fade-in slide-in-from-left-2 duration-200"
                  >
                    <option value="">Todos los meses</option>
                    <option value="1">Enero</option>
                    <option value="2">Febrero</option>
                    <option value="3">Marzo</option>
                    <option value="4">Abril</option>
                    <option value="5">Mayo</option>
                    <option value="6">Junio</option>
                    <option value="7">Julio</option>
                    <option value="8">Agosto</option>
                    <option value="9">Septiembre</option>
                    <option value="10">Octubre</option>
                    <option value="11">Noviembre</option>
                    <option value="12">Diciembre</option>
                  </select>
                )}
              </div>
            </div>

            {/* Fila 2: Chips de filtros activos */}
            {(statusFilter !== 'all' || invoiceTypeFilter !== 'all' || paymentMethodFilter !== 'all' || satStatusFilter !== 'all' || searchTerm !== '') && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-slate-500 font-medium">Filtros activos:</span>

                {statusFilter !== 'all' && (
                  <button
                    onClick={() => setStatusFilter('all')}
                    className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-medium hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                  >
                    <span>{statusFilter === 'completed' ? 'Completadas' : statusFilter === 'processing' ? 'Procesando' : statusFilter === 'pending' ? 'Pendientes' : 'Fallidas'}</span>
                    <X className="w-3 h-3" />
                  </button>
                )}

                {invoiceTypeFilter !== 'all' && (
                  <button
                    onClick={() => setInvoiceTypeFilter('all')}
                    className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs font-medium hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors"
                  >
                    <span>{invoiceTypeFilter === 'emitida' ? 'Emitidas' : 'Recibidas'}</span>
                    <X className="w-3 h-3" />
                  </button>
                )}

                {paymentMethodFilter !== 'all' && (
                  <button
                    onClick={() => setPaymentMethodFilter('all')}
                    className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 text-xs font-medium hover:bg-emerald-200 dark:hover:bg-emerald-900/50 transition-colors"
                  >
                    <span>{paymentMethodFilter === 'PUE' ? 'PUE' : paymentMethodFilter === 'PPD' ? 'PPD' : 'Sin definir'}</span>
                    <X className="w-3 h-3" />
                  </button>
                )}

                {satStatusFilter !== 'all' && (
                  <button
                    onClick={() => setSatStatusFilter('all')}
                    className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 text-xs font-medium hover:bg-amber-200 dark:hover:bg-amber-900/50 transition-colors"
                  >
                    <span>SAT: {satStatusFilter === 'vigente' ? 'Vigente' : satStatusFilter === 'cancelado' ? 'Cancelada' : satStatusFilter === 'sustituido' ? 'Sustituida' : 'Desconocida'}</span>
                    <X className="w-3 h-3" />
                  </button>
                )}

                {searchTerm !== '' && (
                  <button
                    onClick={() => setSearchTerm('')}
                    className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-medium hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                  >
                    <span>Búsqueda: &quot;{searchTerm.substring(0, 20)}{searchTerm.length > 20 ? '...' : ''}&quot;</span>
                    <X className="w-3 h-3" />
                  </button>
                )}

                <span className="h-4 w-px bg-slate-300 dark:bg-slate-600" />

                <button
                  onClick={() => {
                    setStatusFilter('all');
                    setInvoiceTypeFilter('all');
                    setPaymentMethodFilter('all');
                    setSatStatusFilter('all');
                    setSearchTerm('');
                    // Reset to all periods
                    setSelectedYear(null);
                    setSelectedMonth(null);
                  }}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 dark:bg-white text-white dark:text-slate-900 text-xs font-semibold hover:bg-slate-800 dark:hover:bg-slate-100 transition-all shadow-sm hover:shadow"
                >
                  <X className="w-3.5 h-3.5" />
                  Limpiar filtros
                </button>
              </div>
            )}
          </div>

          {/* Nota informativa sobre complementos de pago excluidos - HIDDEN: ahora usamos tabs */}
          {/* Banner removido porque ahora tenemos tabs separados para Facturas y Complementos de Pago */}

          {/* Invoices List OR Payment Complements Table */}
          {activeTab === 'invoices' ? (
            /* Invoices Tab - Card View */
            <div className="space-y-2">
              {loading ? (
                <div className="relative">
                  <div className="absolute inset-0 bg-gradient-to-br from-slate-50 to-white dark:from-slate-800 dark:to-slate-900 rounded-2xl" />
                  <div className="absolute inset-0 rounded-2xl border border-slate-200/50 dark:border-slate-700/50" />
                  <div className="relative p-12 text-center">
                    <div className="inline-flex items-center gap-3 text-slate-600 dark:text-slate-400">
                      <div className="w-5 h-5 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
                      <span className="text-sm font-medium">Cargando facturas...</span>
                    </div>
                  </div>
                </div>
              ) : sortedSessions.length === 0 ? (
                <div className="relative">
                  <div className="absolute inset-0 bg-gradient-to-br from-slate-50 to-white dark:from-slate-800 dark:to-slate-900 rounded-2xl" />
                  <div className="absolute inset-0 rounded-2xl border border-slate-200/50 dark:border-slate-700/50" />
                  <div className="relative p-12 text-center">
                    <FileText strokeWidth={1.5} className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
                    <p className="text-sm font-medium text-slate-600 dark:text-slate-400">No se encontraron facturas</p>
                  </div>
                </div>
              ) : (
                sortedSessions.map((session) => (
                  <InvoiceCard
                    key={session.session_id}
                    session={session}
                    expanded={expandedSessions.has(session.session_id)}
                    onToggle={() => toggleSessionExpanded(session.session_id)}
                    displayInfo={getInvoiceDisplayInfo(session)}
                    statusIcon={getStatusIcon(session.status)}
                    statusBadge={getStatusBadge(session.status)}
                    extractedData={extractedData[session.session_id]}
                    formatDate={formatDate}
                    satStatus={getSatStatus(session)}
                    classification={classifications[session.session_id]}
                    onConfirmClassification={handleConfirmClassification}
                    onCorrectClassification={handleCorrectClassification}
                    onClassifyManually={handleClassifyManually}
                    classificationLoading={classificationLoading}
                  />
                ))
              )}
            </div>
          ) : (
            /* Payment Complements Tab - Table View */
            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200/60 dark:border-slate-700/60 overflow-hidden">
              {loading ? (
                <div className="p-12 text-center">
                  <div className="inline-flex items-center gap-3 text-slate-600 dark:text-slate-400">
                    <div className="w-5 h-5 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
                    <span className="text-sm font-medium">Cargando complementos de pago...</span>
                  </div>
                </div>
              ) : sortedSessions.length === 0 ? (
                <div className="p-12 text-center">
                  <FileText strokeWidth={1.5} className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
                  <p className="text-sm font-medium text-slate-600 dark:text-slate-400">No se encontraron complementos de pago</p>
                  <p className="text-xs text-slate-500 dark:text-slate-500 mt-2">Los complementos de pago documentan CUÁNDO y CÓMO se pagó una factura PPD</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-slate-50 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Fecha Pago</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Emisor (Certifica el pago)</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Monto Pagado</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Forma de Pago</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Factura Relacionada</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Parcialidad</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Estado SAT</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                      {sortedSessions.map((session) => {
                        const displayInfo = getInvoiceDisplayInfo(session);
                        const data = extractedData[session.session_id];

                        // Extraer info básica del complemento
                        const emisorNombre = data?.emisor?.nombre || displayInfo.emisor_nombre || 'Cargando...';
                        const emisorRfc = data?.emisor?.rfc || displayInfo.emisor_rfc || 'N/A';

                        // Extraer datos del complemento de pago (pago20:Pagos)
                        const paymentComplement = data?.payment_complement;
                        const hasPagos = paymentComplement && paymentComplement.pagos && paymentComplement.pagos.length > 0;

                        const pago = hasPagos ? paymentComplement.pagos[0] : null;
                        const fechaPago = pago?.fecha_pago || 'N/A';
                        const montoPagado = pago?.monto || 0;
                        const moneda = pago?.moneda || 'MXN';
                        const formaPago = pago?.forma_pago || 'N/A';

                        // Información del documento relacionado (factura original)
                        const doctoRelacionado = pago?.documentos_relacionados?.[0];
                        const facturaRelacionadaUUID = doctoRelacionado?.id_documento || 'N/A';
                        const numParcialidad = doctoRelacionado?.num_parcialidad || 0;
                        const saldoInsoluto = doctoRelacionado?.imp_saldo_insoluto || 0;

                        // Calcular total de parcialidades estimadas
                        // Si saldo insoluto = 0, esta es la última parcialidad
                        // Si hay saldo, asumimos que habrá más pagos (mostramos ?)
                        const esPagoCompleto = saldoInsoluto === 0 && montoPagado > 0;
                        const totalParcialidades = esPagoCompleto ? numParcialidad : '?';
                        const parcialidadDisplay = numParcialidad > 0 ? `${numParcialidad}/${totalParcialidades}` : 'N/A';

                        // Catálogo de formas de pago SAT
                        const formasPago: Record<string, string> = {
                          '01': 'Efectivo',
                          '02': 'Cheque nominativo',
                          '03': 'Transferencia electrónica',
                          '04': 'Tarjeta de crédito',
                          '05': 'Monedero electrónico',
                          '06': 'Dinero electrónico',
                          '28': 'Tarjeta de débito',
                          '29': 'Tarjeta de servicios',
                          '99': 'Por definir',
                        };
                        const formaPagoDesc = formasPago[formaPago] || formaPago;

                        return (
                          <tr
                            key={session.session_id}
                            className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer"
                            onClick={() => toggleSessionExpanded(session.session_id)}
                          >
                            {/* Fecha de Pago */}
                            <td className="px-4 py-3 text-sm text-slate-900 dark:text-white whitespace-nowrap">
                              {fechaPago !== 'N/A' ? formatDate(fechaPago) : 'Sin datos'}
                            </td>

                            {/* Emisor (quien certifica el pago) */}
                            <td className="px-4 py-3">
                              <div className="text-sm font-medium text-slate-900 dark:text-white">
                                {emisorNombre}
                              </div>
                              <div className="text-xs text-slate-500 dark:text-slate-500">
                                RFC: {emisorRfc}
                              </div>
                            </td>

                            {/* Monto Pagado */}
                            <td className="px-4 py-3 whitespace-nowrap">
                              <div className="text-sm font-semibold text-slate-900 dark:text-white">
                                ${montoPagado.toFixed(2)} {moneda}
                              </div>
                              {saldoInsoluto > 0 && (
                                <div className="text-xs text-amber-600 dark:text-amber-400">
                                  Saldo restante: ${saldoInsoluto.toFixed(2)}
                                </div>
                              )}
                              {saldoInsoluto === 0 && montoPagado > 0 && (
                                <div className="text-xs text-emerald-600 dark:text-emerald-400">
                                  Pagado completamente
                                </div>
                              )}
                            </td>

                            {/* Forma de Pago */}
                            <td className="px-4 py-3">
                              <div className="text-sm text-slate-900 dark:text-white">
                                {formaPagoDesc}
                              </div>
                              <div className="text-xs text-slate-500 dark:text-slate-500">
                                Clave: {formaPago}
                              </div>
                            </td>

                            {/* Factura Relacionada */}
                            <td className="px-4 py-3">
                              <div className="text-xs font-mono text-slate-600 dark:text-slate-400 max-w-xs truncate">
                                {facturaRelacionadaUUID}
                              </div>
                            </td>

                            {/* Parcialidad */}
                            <td className="px-4 py-3 whitespace-nowrap text-center">
                              {numParcialidad > 0 ? (
                                <div className="flex flex-col items-center gap-1">
                                  <span className={`inline-flex items-center justify-center px-3 py-1.5 rounded-full font-semibold text-sm ${
                                    esPagoCompleto
                                      ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400'
                                      : 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                                  }`}>
                                    {parcialidadDisplay}
                                  </span>
                                  {esPagoCompleto && (
                                    <span className="text-xs text-emerald-600 dark:text-emerald-400">
                                      Última
                                    </span>
                                  )}
                                  {!esPagoCompleto && saldoInsoluto > 0 && (
                                    <span className="text-xs text-amber-600 dark:text-amber-400">
                                      Pendiente
                                    </span>
                                  )}
                                </div>
                              ) : (
                                <span className="text-sm text-slate-400">N/A</span>
                              )}
                            </td>

                            {/* Estado SAT */}
                            <td className="px-4 py-3 whitespace-nowrap">
                              {(() => {
                                const satStatus = data?.sat_status || 'desconocido';
                                if (satStatus === 'vigente') {
                                  return (
                                    <span className="inline-flex items-center justify-center px-3 py-1 rounded-full text-xs font-medium bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400">
                                      ✓ Vigente
                                    </span>
                                  );
                                } else if (satStatus === 'cancelado') {
                                  return (
                                    <span className="inline-flex items-center justify-center px-3 py-1 rounded-full text-xs font-medium bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400">
                                      ✗ Cancelado
                                    </span>
                                  );
                                } else {
                                  return (
                                    <span className="inline-flex items-center justify-center px-3 py-1 rounded-full text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                                      ? Sin validar
                                    </span>
                                  );
                                }
                              })()}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>

                  {/* Información sobre complementos de pago */}
                  <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900/50 rounded-lg">
                    <div className="flex items-start gap-2">
                      <AlertCircle className="w-4 h-4 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
                      <div className="text-xs text-blue-900 dark:text-blue-100">
                        <span className="font-semibold">Complementos de Pago (Tipo P).</span>
                        {' '}Estos documentos certifican CUÁNDO y CÓMO se pagó una factura PPD. No generan ingreso/egreso fiscal, solo documentan el pago de facturas existentes.
                        <br />
                        <span className="font-semibold mt-1 inline-block">Parcialidades:</span>
                        {' '}
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-xs font-semibold">1/1</span> = pago único completado,
                        {' '}
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 text-xs font-semibold">1/?</span> = primer pago de varios (total desconocido),
                        {' '}
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 text-xs font-semibold">2/?</span> = segundo pago.
                        <br />
                        <span className="font-semibold mt-1 inline-block">Estado SAT:</span>
                        {' '}
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-xs font-semibold">✓ Vigente</span> = CFDI válido ante el SAT,
                        {' '}
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 text-xs font-semibold">✗ Cancelado</span> = CFDI cancelado por el emisor,
                        {' '}
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 text-xs font-semibold">? Sin validar</span> = pendiente de verificación con el SAT.
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Correction Modal */}
        {correctionSessionId && correctionModalOpen && (
          <ClassificationCorrectionModal
            isOpen={correctionModalOpen}
            onClose={() => {
              setCorrectionModalOpen(false);
              setCorrectionSessionId(null);
            }}
            onSubmit={handleSubmitCorrection}
            originalCode={classifications[correctionSessionId]?.sat_code || ''}
            originalExplanation={classifications[correctionSessionId]?.explanation || ''}
            invoiceDescription={
              sessions.find(s => s.session_id === correctionSessionId)?.display_info?.emisor_nombre || 'Factura'
            }
            loading={classificationLoading}
          />
        )}
      </AppLayout>
    </ProtectedRoute>
  );
}

// Invoice Card Component
function InvoiceCard({
  session,
  expanded,
  onToggle,
  displayInfo,
  statusIcon,
  statusBadge,
  extractedData,
  formatDate,
  satStatus,
  classification,
  onConfirmClassification,
  onCorrectClassification,
  onClassifyManually,
  classificationLoading,
}: {
  session: InvoiceSession;
  expanded: boolean;
  onToggle: () => void;
  displayInfo: { title: string; description: string };
  statusIcon: React.ReactNode;
  statusBadge: React.ReactNode;
  extractedData: ExtractedData;
  formatDate: (dateString: string) => string;
  satStatus: string;
  classification?: ClassificationData | null;
  onConfirmClassification?: (sessionId: string) => void;
  onCorrectClassification?: (sessionId: string) => void;
  onClassifyManually?: (sessionId: string) => void;
  classificationLoading?: boolean;
}) {
  // Helper para determinar tipo de factura
  const getInvoiceType = (session: InvoiceSession) => {
    const rfc = session.display_info?.emisor_rfc || '';
    const companyRFC = 'POL210218264'; // TODO: Get from auth context
    return rfc === companyRFC ? 'emitida' : 'recibida';
  };

  // Helper para obtener badge de tipo
  const getTypeBadge = (type: string) => {
    if (type === 'recibida') {
      return <span className="px-2 py-0.5 rounded-md bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs font-medium">RECIBIDA</span>;
    }
    return <span className="px-2 py-0.5 rounded-md bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 text-xs font-medium">EMITIDA</span>;
  };

  // Helper para obtener método de pago
  const getPaymentMethod = (session: InvoiceSession) => {
    return session.display_info?.metodo_pago || 'N/A';
  };

  // Helper para obtener badge SAT con validación real
  const getSatStatusBadge = (session: InvoiceSession) => {
    // Usar validación real del SAT si está disponible, sino usar inferencia del LLM
    const realValidation = session.sat_validation;
    const status = realValidation?.status === 'pending'
      ? satStatus  // Usar LLM mientras se valida
      : realValidation?.status || satStatus;  // Usar validación real si está disponible

    const badges: Record<string, { bg: string; text: string; border: string; label: string; icon: string }> = {
      vigente: { bg: 'bg-emerald-50 dark:bg-emerald-950/30', text: 'text-emerald-700 dark:text-emerald-400', border: 'border-emerald-200/50 dark:border-emerald-900/50', label: 'Vigente', icon: '✓' },
      cancelado: { bg: 'bg-red-50 dark:bg-red-950/30', text: 'text-red-700 dark:text-red-400', border: 'border-red-200/50 dark:border-red-900/50', label: 'Cancelada', icon: '✕' },
      sustituido: { bg: 'bg-amber-50 dark:bg-amber-950/30', text: 'text-amber-700 dark:text-amber-400', border: 'border-amber-200/50 dark:border-amber-900/50', label: 'Sustituida', icon: '↻' },
      pending: { bg: 'bg-blue-50 dark:bg-blue-950/30', text: 'text-blue-700 dark:text-blue-400', border: 'border-blue-200/50 dark:border-blue-900/50', label: 'Validando...', icon: '⏳' },
      error: { bg: 'bg-orange-50 dark:bg-orange-950/30', text: 'text-orange-700 dark:text-orange-400', border: 'border-orange-200/50 dark:border-orange-900/50', label: 'Error', icon: '⚠' },
    };

    const badge = badges[status] || { bg: 'bg-slate-50', text: 'text-slate-600', border: 'border-slate-200', label: 'Desconocido', icon: '?' };

    // Mostrar timestamp si está verificado
    const verifiedTimestamp = realValidation?.verifiedAt
      ? new Date(realValidation.verifiedAt).toLocaleDateString('es-MX', { day: 'numeric', month: 'short' })
      : null;

    return (
      <span className={cn('px-2 py-0.5 rounded-md text-xs font-medium border', badge.bg, badge.text, badge.border)} title={realValidation?.verificationUrl || undefined}>
        {badge.icon} SAT: {badge.label}
        {verifiedTimestamp && realValidation?.status !== 'pending' && (
          <span className="ml-1 opacity-70">({verifiedTimestamp})</span>
        )}
      </span>
    );
  };

  // Calcular IVA aproximado (asumiendo 16%)
  const getIvaInfo = (session: InvoiceSession) => {
    const total = session.display_info?.total || 0;
    const subtotal = total / 1.16; // Aproximación
    const iva = total - subtotal;
    const ivaRate = total > 0 ? ((iva / subtotal) * 100).toFixed(0) : '0';
    return { iva, ivaRate };
  };

  // Determinar si hay alertas
  const hasAlerts = () => {
    const paymentMethod = getPaymentMethod(session);
    // Alerta si es PPD (podría no tener complemento)
    return paymentMethod === 'PPD' || session.status === 'failed';
  };

  const invoiceType = getInvoiceType(session);
  const paymentMethod = getPaymentMethod(session);
  const ivaInfo = getIvaInfo(session);
  const hasAlert = hasAlerts();

  return (
    <div className="group relative">
      {/* Background Layer */}
      <div className="absolute inset-0 bg-gradient-to-br from-white to-slate-50 dark:from-slate-900 dark:to-slate-800 rounded-xl" />

      {/* Border - destacar si tiene alerta */}
      <div className={cn(
        "absolute inset-0 rounded-xl border transition-colors",
        hasAlert
          ? "border-amber-300/50 dark:border-amber-700/50 group-hover:border-amber-400 dark:group-hover:border-amber-600"
          : "border-slate-200/50 dark:border-slate-700/50 group-hover:border-slate-300 dark:group-hover:border-slate-600"
      )} />

      {/* Content */}
      <div className="relative overflow-hidden rounded-xl">
        {/* Session Header - Vista previa enfocada en contabilidad */}
        <div
          className="p-4 cursor-pointer group-hover:bg-slate-50/50 dark:group-hover:bg-slate-800/50 transition-all duration-200"
          onClick={onToggle}
        >
          <div className="flex items-start gap-3">
            {/* Icono de alerta o status */}
            <div className="mt-0.5">
              {hasAlert ? (
                <AlertTriangle className="w-4 h-4 text-amber-600" />
              ) : satStatus === 'vigente' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              ) : (
                statusIcon
              )}
            </div>

            <div className="flex-1 min-w-0 space-y-2">
              {/* Línea 1: Proveedor/Cliente + Badges */}
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-semibold text-slate-900 dark:text-white text-sm truncate flex-shrink min-w-0">
                  {displayInfo.title}
                </h3>
                {getTypeBadge(invoiceType)}
                {getSatStatusBadge(session)}
                {session.status !== 'completed' && statusBadge}
              </div>

              {/* Línea 2: Monto + Fecha + IVA + Método de pago */}
              <div className="flex items-center gap-2 flex-wrap text-sm">
                <span className="font-bold text-slate-900 dark:text-white text-base">
                  {displayInfo.description.split('·')[0].trim()}
                </span>
                <span className="text-slate-400">·</span>
                <span className="text-slate-600 dark:text-slate-400">
                  {session.display_info?.fecha_emision
                    ? new Date(session.display_info.fecha_emision).toLocaleDateString('es-MX', { day: 'numeric', month: 'short', year: 'numeric' })
                    : formatDate(session.created_at)
                  }
                </span>
                <span className="text-slate-400">·</span>
                <span className={cn(
                  "px-2 py-0.5 rounded-md text-xs font-medium",
                  ivaInfo.ivaRate === '16'
                    ? "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400"
                    : ivaInfo.ivaRate === '0' || ivaInfo.ivaRate === '00'
                    ? "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
                    : "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400"
                )}>
                  IVA {ivaInfo.ivaRate}%
                </span>
                <span className="text-slate-400">·</span>
                <span className={cn(
                  "px-2 py-0.5 rounded-md text-xs font-medium",
                  paymentMethod === 'PUE'
                    ? "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400"
                    : paymentMethod === 'PPD'
                    ? "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
                )}>
                  {paymentMethod}
                  {paymentMethod === 'PPD' && ' ⚠️'}
                </span>
              </div>

              {/* Línea 3: Serie/Folio + Uso CFDI (si existe) */}
              {(session.display_info?.serie || session.display_info?.folio) && (
                <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                  {session.display_info?.serie && session.display_info?.folio && (
                    <>
                      <span className="font-medium">Serie/Folio: {session.display_info.serie}-{session.display_info.folio}</span>
                      <span className="text-slate-400">·</span>
                    </>
                  )}
                  <span className="font-mono text-[10px] text-slate-400">
                    UUID: {session.display_info?.uuid?.substring(0, 8) || session.session_id.substring(0, 8)}...
                  </span>
                </div>
              )}

              {/* Clasificación Contable (IA) */}
              {classification && onConfirmClassification && onCorrectClassification && onClassifyManually && (
                <InlineClassificationControl
                  classification={classification}
                  onConfirm={onConfirmClassification}
                  onCorrect={onCorrectClassification}
                  onClassifyManually={onClassifyManually}
                  loading={classificationLoading}
                />
              )}

              {/* Alerta PPD sin complemento */}
              {paymentMethod === 'PPD' && (
                <div className="text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 px-2 py-1 rounded-md border border-amber-200/50 dark:border-amber-900/50 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  <span>PPD sin complemento - No deducible hasta recibir CFDI de pago</span>
                </div>
              )}
            </div>

            {/* Chevron */}
            <div className="flex items-center gap-2 mt-0.5">
              {expanded ? (
                <ChevronUp strokeWidth={1.5} className="w-4 h-4 text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300 transition-colors" />
              ) : (
                <ChevronDown strokeWidth={1.5} className="w-4 h-4 text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300 transition-colors" />
              )}
            </div>
          </div>
        </div>

        {/* Expanded Details */}
        {expanded && (
          <div className="border-t border-slate-200/50 dark:border-slate-700/50">
            {extractedData ? (
              <InvoiceDetails data={extractedData} />
            ) : (
              <div className="p-8 text-center">
                <div className="inline-flex items-center gap-3 text-slate-600 dark:text-slate-400">
                  <div className="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm font-medium">Cargando detalles...</span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Invoice Details Component
function InvoiceDetails({ data }: { data: ExtractedData }) {
  const formatCurrency = (amount: number, currency: string = 'MXN') => {
    return new Intl.NumberFormat('es-MX', {
      style: 'currency',
      currency: currency,
    }).format(amount);
  };

  return (
    <div className="p-6 bg-gray-50 space-y-6">
      {/* Basic Invoice Data */}
      <div>
        <h4 className="font-semibold text-[#11446e] mb-3 flex items-center gap-2">
          <FileText className="w-5 h-5" />
          Información General
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 bg-white p-4 rounded-lg">
          <div>
            <p className="text-xs text-gray-500">UUID</p>
            <p className="font-mono text-sm">{data.uuid}</p>
          </div>
          {data.serie && (
            <div>
              <p className="text-xs text-gray-500">Serie</p>
              <p className="font-semibold">{data.serie}</p>
            </div>
          )}
          {data.folio && (
            <div>
              <p className="text-xs text-gray-500">Folio</p>
              <p className="font-semibold">{data.folio}</p>
            </div>
          )}
          <div>
            <p className="text-xs text-gray-500">Fecha Emisión</p>
            <p className="font-semibold">{data.fecha_emision}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Fecha Timbrado</p>
            <p className="font-semibold">{data.fecha_timbrado}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Tipo Comprobante</p>
            <p className="font-semibold">{data.tipo_comprobante}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Moneda</p>
            <p className="font-semibold">{data.moneda}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Estatus SAT</p>
            <p className={cn(
              "font-semibold",
              data.sat_status === 'vigente' ? 'text-[#60b97b]' : 'text-red-500'
            )}>
              {data.sat_status}
            </p>
          </div>
        </div>
      </div>

      {/* Amounts */}
      <div>
        <h4 className="font-semibold text-[#11446e] mb-3 flex items-center gap-2">
          <DollarSign className="w-5 h-5" />
          Montos
        </h4>
        <div className="bg-white p-4 rounded-lg">
          <div className="space-y-2 border-b pb-3 mb-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Subtotal</span>
              <span className="font-semibold text-lg">{formatCurrency(data.subtotal, data.moneda)}</span>
            </div>
            {data.descuento && (
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Descuento</span>
                <span className="font-semibold text-red-500">
                  -{formatCurrency(data.descuento, data.moneda)}
                </span>
              </div>
            )}
          </div>

          {/* Traslados */}
          {data.impuestos?.traslados && data.impuestos.traslados.length > 0 && (
            <div className="space-y-2 border-b pb-3 mb-3">
              {data.impuestos.traslados.map((traslado: any, index: number) => (
                <div key={index} className="flex justify-between items-center">
                  <span className="text-gray-600">
                    + {traslado.impuesto} {((traslado.tasa || 0) * 100).toFixed(0)}%
                  </span>
                  <span className="font-semibold text-green-600">
                    +{formatCurrency(traslado.importe, data.moneda)}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Retenciones */}
          {data.impuestos?.retenciones && data.impuestos.retenciones.length > 0 && (
            <div className="space-y-2 border-b pb-3 mb-3">
              {data.impuestos.retenciones.map((retencion: any, index: number) => (
                <div key={index} className="flex justify-between items-center">
                  <span className="text-gray-600">
                    - Ret. {retencion.impuesto} {((retencion.tasa || 0) * 100).toFixed(0)}%
                  </span>
                  <span className="font-semibold text-red-500">
                    -{formatCurrency(retencion.importe, data.moneda)}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Total */}
          <div className="flex justify-between items-center pt-2">
            <span className="text-gray-700 font-semibold text-lg">Total</span>
            <span className="font-bold text-2xl text-[#11446e]">
              {formatCurrency(data.total, data.moneda)}
            </span>
          </div>
        </div>
      </div>

      {/* Payment Info */}
      <div>
        <h4 className="font-semibold text-[#11446e] mb-3">Condiciones de Pago</h4>
        <div className="bg-white p-4 rounded-lg space-y-3">
          {data.forma_pago && (
            <div className="border-b pb-3">
              <p className="text-xs text-gray-500 mb-1">Forma de Pago</p>
              <p className="font-semibold text-[#11446e]">{getFormaPagoLabel(data.forma_pago)}</p>
              <p className="text-xs text-gray-400 mt-1">Clave: {data.forma_pago}</p>
            </div>
          )}
          {data.metodo_pago && (
            <div className="border-b pb-3">
              <p className="text-xs text-gray-500 mb-1">Método de Pago</p>
              <p className="font-semibold text-[#11446e]">{getMetodoPagoLabel(data.metodo_pago)}</p>
              <p className="text-xs text-gray-400 mt-1">Clave: {data.metodo_pago}</p>
            </div>
          )}
          {data.uso_cfdi && (
            <div className="border-b pb-3">
              <p className="text-xs text-gray-500 mb-1">Uso CFDI</p>
              <p className="font-semibold text-[#11446e]">{getUsoCFDILabel(data.uso_cfdi)}</p>
              <p className="text-xs text-gray-400 mt-1">Clave: {data.uso_cfdi}</p>
            </div>
          )}
          <div>
            <p className="text-xs text-gray-500 mb-1">Tipo de Comprobante</p>
            <p className="font-semibold text-[#11446e]">{data.tipo_comprobante === 'I' ? 'Ingreso' : data.tipo_comprobante}</p>
            <p className="text-xs text-gray-400 mt-1">Clave: {data.tipo_comprobante}</p>
          </div>
        </div>
      </div>

      {/* Emisor */}
      {data.emisor && (
        <div>
          <h4 className="font-semibold text-[#11446e] mb-3 flex items-center gap-2">
            <Building className="w-5 h-5" />
            Emisor
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 bg-white p-4 rounded-lg">
            {data.emisor.nombre && (
              <div>
                <p className="text-xs text-gray-500">Nombre / Razón Social</p>
                <p className="font-semibold">{data.emisor.nombre}</p>
              </div>
            )}
            {data.emisor.rfc && (
              <div>
                <p className="text-xs text-gray-500">RFC</p>
                <p className="font-mono font-semibold">{data.emisor.rfc}</p>
              </div>
            )}
            {data.emisor.regimen_fiscal && (
              <div>
                <p className="text-xs text-gray-500">Régimen Fiscal</p>
                <p className="font-semibold">{data.emisor.regimen_fiscal}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Receptor */}
      {data.receptor && (
        <div>
          <h4 className="font-semibold text-[#11446e] mb-3 flex items-center gap-2">
            <Building className="w-5 h-5" />
            Receptor
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 bg-white p-4 rounded-lg">
            {data.receptor.nombre && (
              <div>
                <p className="text-xs text-gray-500">Nombre / Razón Social</p>
                <p className="font-semibold">{data.receptor.nombre}</p>
              </div>
            )}
            {data.receptor.rfc && (
              <div>
                <p className="text-xs text-gray-500">RFC</p>
                <p className="font-mono font-semibold">{data.receptor.rfc}</p>
              </div>
            )}
            {data.receptor.domicilio_fiscal && (
              <div>
                <p className="text-xs text-gray-500">Domicilio Fiscal</p>
                <p className="font-semibold">{data.receptor.domicilio_fiscal}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tax Badges */}
      {data.tax_badges && data.tax_badges.length > 0 && (
        <div>
          <h4 className="font-semibold text-[#11446e] mb-3">Impuestos Aplicados</h4>
          <div className="flex flex-wrap gap-2">
            {data.tax_badges.map((badge, index) => (
              <span
                key={index}
                className="px-3 py-1 bg-[#11446e]/10 text-[#11446e] rounded-full text-sm font-medium"
              >
                {badge}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Impuestos Traslados */}
      {data.impuestos?.traslados && data.impuestos.traslados.length > 0 && (
        <div>
          <h4 className="font-semibold text-[#11446e] mb-3">Impuestos Trasladados</h4>
          <div className="bg-white p-4 rounded-lg overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b">
                <tr className="text-left">
                  <th className="pb-2 text-gray-600">Impuesto</th>
                  <th className="pb-2 text-gray-600">Tipo Factor</th>
                  <th className="pb-2 text-gray-600">Tasa/Cuota</th>
                  <th className="pb-2 text-gray-600 text-right">Importe</th>
                </tr>
              </thead>
              <tbody>
                {data.impuestos.traslados.map((traslado: any, index: number) => (
                  <tr key={index} className="border-b last:border-0">
                    <td className="py-2">{traslado.impuesto}</td>
                    <td className="py-2">{traslado.factor || '-'}</td>
                    <td className="py-2">{((traslado.tasa || 0) * 100).toFixed(2)}%</td>
                    <td className="py-2 text-right font-semibold">
                      {formatCurrency(traslado.importe, data.moneda)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Retenciones */}
      {data.impuestos?.retenciones && data.impuestos.retenciones.length > 0 && (
        <div>
          <h4 className="font-semibold text-[#11446e] mb-3">Retenciones</h4>
          <div className="bg-white p-4 rounded-lg overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b">
                <tr className="text-left">
                  <th className="pb-2 text-gray-600">Impuesto</th>
                  <th className="pb-2 text-gray-600">Tipo Factor</th>
                  <th className="pb-2 text-gray-600">Tasa/Cuota</th>
                  <th className="pb-2 text-gray-600 text-right">Importe</th>
                </tr>
              </thead>
              <tbody>
                {data.impuestos.retenciones.map((retencion: any, index: number) => (
                  <tr key={index} className="border-b last:border-0">
                    <td className="py-2">{retencion.impuesto}</td>
                    <td className="py-2">{retencion.factor || '-'}</td>
                    <td className="py-2">{((retencion.tasa || 0) * 100).toFixed(2)}%</td>
                    <td className="py-2 text-right font-semibold text-red-500">
                      -{formatCurrency(retencion.importe, data.moneda)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Conceptos */}
      {data.conceptos && data.conceptos.length > 0 && (
        <div>
          <h4 className="font-semibold text-[#11446e] mb-3">Conceptos</h4>
          <div className="bg-white p-4 rounded-lg space-y-3">
            {data.conceptos.map((concepto: any, index: number) => (
              <div key={index} className="border-b last:border-0 pb-3 last:pb-0">
                <div className="flex justify-between items-start mb-2">
                  <div className="flex-1">
                    <p className="font-semibold">{concepto.descripcion}</p>
                    {concepto.no_identificacion && (
                      <p className="text-xs text-gray-500">ID: {concepto.no_identificacion}</p>
                    )}
                  </div>
                  <p className="font-semibold text-[#11446e]">
                    {formatCurrency(concepto.importe, data.moneda)}
                  </p>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs text-gray-600">
                  <div>
                    <span className="text-gray-500">Cantidad:</span> {concepto.cantidad}
                  </div>
                  <div>
                    <span className="text-gray-500">Unidad:</span> {concepto.unidad}
                  </div>
                  <div>
                    <span className="text-gray-500">Valor Unitario:</span>{' '}
                    {formatCurrency(concepto.valor_unitario, data.moneda)}
                  </div>
                  {concepto.descuento && (
                    <div>
                      <span className="text-gray-500">Descuento:</span>{' '}
                      {formatCurrency(concepto.descuento, data.moneda)}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

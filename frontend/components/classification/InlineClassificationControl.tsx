/**
 * Inline Classification Control
 *
 * Shows classification status and actions directly in the invoice card
 */

'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils/cn';
import { Brain, CheckCircle, Edit3, AlertCircle } from 'lucide-react';

export interface AlternativeCandidate {
  code: string;
  name: string;
  family_code: string;
  score: number;
  description?: string;
}

export interface HierarchicalPhase1 {
  family_code: string;
  family_name: string;
  confidence: number;
  override_uso_cfdi: boolean;
  override_reason: string | null;
  uso_cfdi_declared: string | null;
  requires_human_review: boolean;
}

export interface ClassificationData {
  session_id: string;
  sat_code: string;
  sat_account_name?: string; // Official name from SAT catalog (e.g., "Depreciación de edificios")
  family_code: string;
  confidence: number;
  explanation: string; // AI's contextual explanation (may differ from official name)
  explanation_detail?: string; // Razonamiento completo de la IA
  status: 'pending_confirmation' | 'confirmed' | 'corrected' | 'not_classified';
  confirmed_by?: string;
  confirmed_at?: string;
  corrected_code?: string;
  corrected_by?: string;
  corrected_at?: string;
  corrected_notes?: string;
  alternative_candidates?: AlternativeCandidate[];
  hierarchical_phase1?: HierarchicalPhase1;
}

interface InlineClassificationControlProps {
  classification: ClassificationData | null;
  onConfirm: (sessionId: string, alternativeCode?: string) => void;
  onCorrect: (sessionId: string) => void;
  onClassifyManually: (sessionId: string) => void;
  loading?: boolean;
}

export function InlineClassificationControl({
  classification,
  onConfirm,
  onCorrect,
  onClassifyManually,
  loading = false,
}: InlineClassificationControlProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showAlternatives, setShowAlternatives] = useState(false);
  const [showDetailedExplanation, setShowDetailedExplanation] = useState(false);
  const [selectedAlternative, setSelectedAlternative] = useState<string | null>(null);

  // Sin clasificación
  if (!classification || classification.status === 'not_classified') {
    return (
      <div className="pt-2 mt-2 border-t border-slate-200/50 dark:border-slate-700/50">
        <div className="flex items-center gap-2 text-sm">
          <Brain className="w-4 h-4 text-slate-400" />
          <span className="text-slate-600 dark:text-slate-400 text-xs">
            Clasificación contable:
          </span>
          <span className="text-slate-500 dark:text-slate-500 text-xs">
            Sin sugerencia disponible
          </span>
          <button
            onClick={() => onClassifyManually(classification?.session_id || '')}
            disabled={loading}
            className="ml-auto px-3 py-1 text-xs font-medium text-blue-700 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/30 rounded-md transition-colors disabled:opacity-50"
          >
            Clasificar manualmente
          </button>
        </div>
      </div>
    );
  }

  // Confirmada
  if (classification.status === 'confirmed') {
    return (
      <div className="pt-2 mt-2 border-t border-slate-200/50 dark:border-slate-700/50">
        <div className="flex items-center gap-2 text-sm">
          <CheckCircle className="w-4 h-4 text-emerald-600" />
          <span className="font-medium text-emerald-700 dark:text-emerald-400 text-xs">
            {classification.sat_code}
          </span>
          <span className="text-slate-600 dark:text-slate-400 text-xs">
            – {classification.sat_account_name || classification.explanation}
          </span>
        </div>
        {classification.confirmed_by && classification.confirmed_at && (
          <div className="ml-6 mt-1 text-xs text-slate-500 dark:text-slate-500">
            Confirmado por {classification.confirmed_by} ·{' '}
            {new Date(classification.confirmed_at).toLocaleDateString('es-MX', {
              day: 'numeric',
              month: 'short',
            })}
          </div>
        )}
      </div>
    );
  }

  // Corregida
  if (classification.status === 'corrected' && classification.corrected_code) {
    return (
      <div className="pt-2 mt-2 border-t border-slate-200/50 dark:border-slate-700/50">
        <div className="flex items-center gap-2 text-sm">
          <Edit3 className="w-4 h-4 text-blue-600" />
          <span className="font-medium text-blue-700 dark:text-blue-400 text-xs">
            {classification.corrected_code}
          </span>
          <span className="text-slate-600 dark:text-slate-400 text-xs">
            – {classification.corrected_notes || classification.explanation}
          </span>
        </div>
        <div className="ml-6 mt-1 flex items-center gap-2">
          {classification.corrected_by && classification.corrected_at && (
            <span className="text-xs text-slate-500 dark:text-slate-500">
              Corregido por {classification.corrected_by} ·{' '}
              {new Date(classification.corrected_at).toLocaleDateString('es-MX', {
                day: 'numeric',
                month: 'short',
              })}
            </span>
          )}
          <span className="text-xs text-slate-400 line-through">
            Original: {classification.sat_code}
          </span>
        </div>
      </div>
    );
  }

  // Pendiente de confirmación (con sugerencia de IA)
  const confidencePercent = Math.round(classification.confidence * 100);
  const confidenceColor =
    confidencePercent >= 90
      ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400'
      : confidencePercent >= 70
      ? 'bg-blue-100 text-blue-700 dark:bg-blue-950/30 dark:text-blue-400'
      : 'bg-amber-100 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400';

  return (
    <div className="pt-2 mt-2 border-t border-slate-200/50 dark:border-slate-700/50">
      {/* Línea principal */}
      <div className="flex items-start gap-2">
        <Brain className="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-slate-600 dark:text-slate-400 text-xs">
              Clasificación contable:
            </span>
            <span className="font-semibold text-slate-900 dark:text-white text-sm">
              {classification.sat_code}
            </span>
            <span className={cn('px-2 py-0.5 rounded-md text-xs font-medium', confidenceColor)}>
              🤖 {confidencePercent}%
            </span>
          </div>

          {/* Official SAT account name from catalog */}
          <div className="mt-1 text-xs text-slate-600 dark:text-slate-400">
            {classification.sat_account_name || classification.explanation}
          </div>

          {/* UsoCFDI Override Warning */}
          {classification.hierarchical_phase1?.override_uso_cfdi && (
            <div className="mt-2 flex items-start gap-2 text-xs bg-amber-50 dark:bg-amber-950/30 border border-amber-200/50 dark:border-amber-900/50 rounded-md p-2">
              <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <div className="font-semibold text-amber-900 dark:text-amber-100 mb-0.5">
                  UsoCFDI del proveedor corregido
                </div>
                <div className="text-amber-800 dark:text-amber-200">
                  <span className="font-medium">Proveedor declaró:</span>{' '}
                  <code className="px-1 py-0.5 bg-amber-100 dark:bg-amber-900/50 rounded text-xs">
                    {classification.hierarchical_phase1.uso_cfdi_declared}
                  </code>
                  <span className="mx-1.5">→</span>
                  <span className="font-medium">Familia real:</span>{' '}
                  <code className="px-1 py-0.5 bg-amber-100 dark:bg-amber-900/50 rounded text-xs">
                    {classification.hierarchical_phase1.family_code} ({classification.hierarchical_phase1.family_name})
                  </code>
                </div>
                {classification.hierarchical_phase1.override_reason && (
                  <div className="mt-1 text-amber-700 dark:text-amber-300 italic">
                    {classification.hierarchical_phase1.override_reason}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Botón para ver razonamiento detallado (si existe) */}
          {classification.explanation_detail && (
            <div className="mt-2">
              <button
                onClick={() => setShowDetailedExplanation(!showDetailedExplanation)}
                className="flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 transition-colors font-medium"
              >
                <Brain className="w-3.5 h-3.5" />
                <span>{showDetailedExplanation ? 'Ocultar' : 'Ver'} razonamiento de la IA</span>
                <svg
                  className={cn('w-3 h-3 transition-transform', showDetailedExplanation && 'rotate-180')}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {showDetailedExplanation && (
                <div className="mt-2 p-3 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg">
                  <div className="flex items-start gap-2 mb-2">
                    <Brain className="w-4 h-4 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
                    <span className="text-xs font-semibold text-slate-900 dark:text-white">
                      Razonamiento completo:
                    </span>
                  </div>
                  <div className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap pl-6">
                    {classification.explanation_detail}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Alternativas (si existen) */}
          {classification.alternative_candidates && classification.alternative_candidates.length > 0 && (
            <div className="mt-2">
              <button
                onClick={() => setShowAlternatives(!showAlternatives)}
                className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
              >
                <span>Ver alternativas ({classification.alternative_candidates.length})</span>
                <svg
                  className={cn('w-3 h-3 transition-transform', showAlternatives && 'rotate-180')}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {showAlternatives && (
                <div className="mt-2 space-y-1.5 pl-2 border-l-2 border-slate-200 dark:border-slate-700">
                  {classification.alternative_candidates.map((alt) => (
                    <div
                      key={alt.code}
                      className={cn(
                        'flex items-center justify-between gap-2 p-1.5 rounded text-xs',
                        selectedAlternative === alt.code
                          ? 'bg-blue-50 dark:bg-blue-950/30'
                          : 'hover:bg-slate-50 dark:hover:bg-slate-800/50'
                      )}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="font-medium text-slate-900 dark:text-white">
                            {alt.code}
                          </span>
                          <span className="text-slate-500 dark:text-slate-500">
                            ({Math.round(alt.score * 100)}%)
                          </span>
                        </div>
                        <div className="text-slate-600 dark:text-slate-400 truncate">
                          {alt.name}
                        </div>
                      </div>
                      <button
                        onClick={() => setSelectedAlternative(selectedAlternative === alt.code ? null : alt.code)}
                        className={cn(
                          'px-2 py-1 text-xs rounded transition-colors flex-shrink-0',
                          selectedAlternative === alt.code
                            ? 'bg-blue-600 text-white'
                            : 'bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-300 dark:hover:bg-slate-600'
                        )}
                      >
                        {selectedAlternative === alt.code ? 'Seleccionada' : 'Elegir'}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Indicador de alternativa seleccionada */}
          {selectedAlternative && (
            <div className="mt-2 p-1.5 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900 rounded text-xs text-blue-900 dark:text-blue-100">
              Confirmarás con: <span className="font-semibold">{selectedAlternative}</span>
            </div>
          )}

          {/* Botones de acción */}
          <div className="mt-2 flex items-center gap-2">
            <button
              onClick={() => onConfirm(classification.session_id, selectedAlternative || undefined)}
              disabled={loading}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-lg transition-all',
                'bg-emerald-600 hover:bg-emerald-700 text-white',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                'flex items-center gap-1.5'
              )}
            >
              <CheckCircle className="w-3.5 h-3.5" />
              {selectedAlternative ? 'Confirmar Alternativa' : 'Confirmar'}
            </button>
            <button
              onClick={() => onCorrect(classification.session_id)}
              disabled={loading}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-lg transition-all',
                'border border-slate-300 dark:border-slate-600',
                'text-slate-700 dark:text-slate-300',
                'hover:bg-slate-50 dark:hover:bg-slate-800',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                'flex items-center gap-1.5'
              )}
            >
              <Edit3 className="w-3.5 h-3.5" />
              Corregir
            </button>
          </div>

          {/* Advertencia de baja confianza */}
          {confidencePercent < 70 && (
            <div className="mt-2 flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 px-2 py-1.5 rounded-md border border-amber-200/50 dark:border-amber-900/50">
              <AlertCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
              <span>
                Confianza baja – Revisa cuidadosamente antes de confirmar
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

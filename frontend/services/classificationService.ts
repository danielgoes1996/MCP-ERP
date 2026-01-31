/**
 * Invoice Classification Service
 *
 * API client for invoice accounting classification endpoints
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface AlternativeCandidate {
  code: string;
  name: string;
  family_code: string;
  score: number;
  description: string;
}

export interface PendingInvoice {
  session_id: string;
  filename: string;
  created_at: string;
  source: 'manual' | 'sat_auto_sync';  // Origin of invoice
  sat_code: string;
  family_code: string;
  confidence: number;
  explanation: string;
  invoice_total: number;
  provider: {
    rfc: string;
    nombre: string;
  };
  description: string;
  alternative_candidates?: AlternativeCandidate[];
}

export interface PendingClassificationsResponse {
  company_id: string;
  total: number;
  limit: number;
  offset: number;
  invoices: PendingInvoice[];
}

export interface ClassificationStats {
  company_id: string;
  period_days: number;
  total_invoices: number;
  classified: number;
  pending_confirmation: number;
  confirmed: number;
  corrected: number;
  not_classified: number;
  classification_rate: number;
  confirmation_rate: number;
  correction_rate: number;
  avg_confidence: number | null;
  avg_duration_seconds: number | null;
}

export interface ConfirmResponse {
  session_id: string;
  status: string;
  sat_account_code: string;
  confirmed_at: string;
  confirmed_by: string;
}

export interface CorrectResponse {
  session_id: string;
  status: string;
  original_sat_code: string;
  corrected_sat_code: string;
  corrected_at: string;
  corrected_by: string;
  correction_notes: string | null;
}

export interface ClassificationDetail {
  session_id: string;
  company_id: string;
  filename: string;
  created_at: string;
  classification: {
    sat_account_code: string;
    sat_account_name?: string;  // Optional: nombre oficial del catálogo SAT
    family_code: string;
    confidence_sat: number;
    confidence_family: number;
    status: string;
    classified_at: string;
    confirmed_at: string | null;
    confirmed_by: string | null;
    corrected_at: string | null;
    corrected_sat_code: string | null;
    correction_notes: string | null;
    explanation_short: string;
    explanation_detail?: string;  // Optional: explicación detallada
    alternative_candidates?: Array<{
      code: string;
      name: string;
      confidence: number;
    }>;  // Optional: alternativas sugeridas
  };
  invoice_data: {
    tipo_comprobante: string;
    total: number;
    fecha_emision: string;
    emisor: {
      rfc: string;
      nombre: string;
    };
    receptor: {
      rfc: string;
      nombre: string;
    };
    conceptos: Array<{
      descripcion: string;
      cantidad: number;
      valor_unitario: number;
      importe: number;
    }>;
  };
  metrics: {
    classification_duration_ms: number;
    num_candidates: number;
    used_llm: boolean;
    confidence: number;
  };
}

/**
 * Get pending classifications for a company
 */
export async function getPendingClassifications(
  companyId: string,
  limit: number = 50,
  offset: number = 0,
  source?: 'manual' | 'sat_auto_sync'  // Filter by source
): Promise<PendingClassificationsResponse> {
  let url = `${API_BASE_URL}/invoice-classification/pending?company_id=${companyId}&limit=${limit}&offset=${offset}`;

  if (source) {
    url += `&source=${source}`;
  }

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to fetch pending classifications: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get count of pending SAT auto-sync invoices
 */
export async function getSATSyncPendingCount(companyId: number): Promise<{ company_id: number; pending_count: number }> {
  const response = await fetch(`${API_BASE_URL}/sat/sync-config/pending-count/${companyId}`);

  if (!response.ok) {
    throw new Error(`Failed to fetch SAT pending count: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get classification statistics
 */
export async function getClassificationStats(
  companyId: string,
  days: number = 30
): Promise<ClassificationStats> {
  const response = await fetch(
    `${API_BASE_URL}/invoice-classification/stats/${companyId}?days=${days}`
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch classification stats: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get classification detail
 */
export async function getClassificationDetail(
  sessionId: string
): Promise<ClassificationDetail> {
  const response = await fetch(
    `${API_BASE_URL}/invoice-classification/detail/${sessionId}`
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch classification detail: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Confirm a classification as correct
 */
export async function confirmClassification(
  sessionId: string,
  userId?: string
): Promise<ConfirmResponse> {
  const url = userId
    ? `${API_BASE_URL}/invoice-classification/confirm/${sessionId}?user_id=${userId}`
    : `${API_BASE_URL}/invoice-classification/confirm/${sessionId}`;

  const response = await fetch(url, {
    method: 'POST',
  });

  if (!response.ok) {
    // Try to get error details from response body
    let errorMessage = `Failed to confirm classification: ${response.statusText}`;
    try {
      const errorData = await response.json();
      if (errorData.detail) {
        errorMessage = `Error al confirmar: ${errorData.detail}`;
      } else if (errorData.message) {
        errorMessage = `Error al confirmar: ${errorData.message}`;
      }
    } catch (e) {
      // If can't parse JSON, use text
      try {
        const errorText = await response.text();
        if (errorText) {
          errorMessage = `Error al confirmar: ${errorText}`;
        }
      } catch (e2) {
        // Use default error message
      }
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

/**
 * Correct a classification
 */
export async function correctClassification(
  sessionId: string,
  correctedSatCode: string,
  correctionNotes?: string,
  userId?: string
): Promise<CorrectResponse> {
  const params = new URLSearchParams({
    corrected_sat_code: correctedSatCode,
  });

  if (correctionNotes) {
    params.append('correction_notes', correctionNotes);
  }

  if (userId) {
    params.append('user_id', userId);
  }

  const response = await fetch(
    `${API_BASE_URL}/invoice-classification/correct/${sessionId}?${params.toString()}`,
    {
      method: 'POST',
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to correct classification: ${response.statusText}`);
  }

  return response.json();
}

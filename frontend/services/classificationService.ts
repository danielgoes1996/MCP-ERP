/**
 * Invoice Classification Service
 *
 * API client for invoice accounting classification endpoints
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

export interface PendingInvoice {
  session_id: string;
  filename: string;
  created_at: string;
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
  offset: number = 0
): Promise<PendingClassificationsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/invoice-classification/pending?company_id=${companyId}&limit=${limit}&offset=${offset}`
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch pending classifications: ${response.statusText}`);
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
    throw new Error(`Failed to confirm classification: ${response.statusText}`);
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

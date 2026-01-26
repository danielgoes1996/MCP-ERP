/**
 * Purchase Orders Service
 *
 * API client for Purchase Orders management
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export type POStatus =
  | 'draft'
  | 'pending_approval'
  | 'approved'
  | 'rejected'
  | 'sent_to_vendor'
  | 'received'
  | 'invoiced'
  | 'cancelled';

export interface PurchaseOrder {
  id: number;
  tenant_id: number;
  po_number: string;
  project_id?: number;
  department_id?: number;
  requester_user_id: number;
  approver_user_id?: number;
  vendor_name: string;
  vendor_rfc?: string;
  vendor_email?: string;
  vendor_phone?: string;
  description: string;
  total_amount: number;
  currency: string;
  status: POStatus;
  sat_invoice_id?: string;
  pdf_url?: string;
  attachment_urls?: string[];
  notes?: string;
  rejection_reason?: string;
  created_at: string;
  updated_at: string;
  approved_at?: string;
  rejected_at?: string;
  sent_at?: string;
  received_at?: string;
  is_approved: boolean;
  is_cancelled: boolean;
  // Joined fields
  project_name?: string;
  department_name?: string;
  requester_name?: string;
  approver_name?: string;
  // Line items
  lines?: Array<{
    line_number: number;
    description: string;
    sku?: string;
    quantity: number;
    unit_price: number;
    total: number;
  }>;
}

export interface PurchaseOrderCreate {
  project_id?: number;
  department_id?: number;
  vendor_name: string;
  vendor_rfc?: string;
  vendor_email?: string;
  vendor_phone?: string;
  description: string;
  total_amount: number;
  currency?: string;
  notes?: string;
}

export interface PurchaseOrderUpdate {
  project_id?: number;
  department_id?: number;
  vendor_name?: string;
  vendor_rfc?: string;
  vendor_email?: string;
  vendor_phone?: string;
  description?: string;
  total_amount?: number;
  currency?: string;
  notes?: string;
}

export interface PurchaseOrderApprove {
  notes?: string;
}

export interface PurchaseOrderReject {
  rejection_reason: string;
}

export interface PurchaseOrderLinkInvoice {
  sat_invoice_id: string;
}

export interface BudgetSummary {
  project_id: number;
  project_name: string;
  budget_total: number;
  committed_mxn: number;
  spent_manual_mxn: number;
  spent_pos_mxn: number;
  spent_total_mxn: number;
  remaining_mxn: number;
  budget_used_percentage: number;
  pos_pending_count: number;
  pos_invoiced_count: number;
}

/**
 * Get auth token from localStorage
 */
function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('auth_token');
}

/**
 * Get auth headers
 */
function getAuthHeaders(): HeadersInit {
  const token = getAuthToken();
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
  };
}

/**
 * Get all purchase orders
 */
export async function getPurchaseOrders(params?: {
  status_filter?: POStatus;
  project_id?: number;
  limit?: number;
  offset?: number;
}): Promise<PurchaseOrder[]> {
  const queryParams = new URLSearchParams();
  if (params?.status_filter) queryParams.append('status_filter', params.status_filter);
  if (params?.project_id) queryParams.append('project_id', params.project_id.toString());
  if (params?.limit) queryParams.append('limit', params.limit.toString());
  if (params?.offset) queryParams.append('offset', params.offset.toString());

  const response = await fetch(
    `${API_BASE_URL}/api/purchase-orders/?${queryParams}`,
    { headers: getAuthHeaders() }
  );

  if (!response.ok) {
    throw new Error('Error al cargar órdenes de compra');
  }

  return response.json();
}

/**
 * Get a single purchase order by ID
 */
export async function getPurchaseOrder(id: number): Promise<PurchaseOrder> {
  const response = await fetch(
    `${API_BASE_URL}/api/purchase-orders/${id}`,
    { headers: getAuthHeaders() }
  );

  if (!response.ok) {
    throw new Error('Error al cargar orden de compra');
  }

  return response.json();
}

/**
 * Create a new purchase order
 */
export async function createPurchaseOrder(
  data: PurchaseOrderCreate
): Promise<PurchaseOrder> {
  const response = await fetch(`${API_BASE_URL}/api/purchase-orders/`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error al crear orden de compra');
  }

  return response.json();
}

/**
 * Update a purchase order (only draft status)
 */
export async function updatePurchaseOrder(
  id: number,
  data: PurchaseOrderUpdate
): Promise<PurchaseOrder> {
  const response = await fetch(`${API_BASE_URL}/api/purchase-orders/${id}`, {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error al actualizar orden de compra');
  }

  return response.json();
}

/**
 * Submit purchase order for approval
 */
export async function submitPurchaseOrder(id: number): Promise<PurchaseOrder> {
  const response = await fetch(
    `${API_BASE_URL}/api/purchase-orders/${id}/submit`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error al enviar orden para aprobación');
  }

  return response.json();
}

/**
 * Approve purchase order
 */
export async function approvePurchaseOrder(
  id: number,
  data: PurchaseOrderApprove
): Promise<PurchaseOrder> {
  const response = await fetch(
    `${API_BASE_URL}/api/purchase-orders/${id}/approve`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error al aprobar orden de compra');
  }

  return response.json();
}

/**
 * Reject purchase order
 */
export async function rejectPurchaseOrder(
  id: number,
  data: PurchaseOrderReject
): Promise<PurchaseOrder> {
  const response = await fetch(
    `${API_BASE_URL}/api/purchase-orders/${id}/reject`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error al rechazar orden de compra');
  }

  return response.json();
}

/**
 * Link SAT invoice to purchase order
 */
export async function linkInvoiceToPurchaseOrder(
  id: number,
  data: PurchaseOrderLinkInvoice
): Promise<PurchaseOrder> {
  const response = await fetch(
    `${API_BASE_URL}/api/purchase-orders/${id}/link-invoice`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error al vincular factura');
  }

  return response.json();
}

/**
 * Cancel purchase order
 */
export async function cancelPurchaseOrder(id: number): Promise<PurchaseOrder> {
  const response = await fetch(
    `${API_BASE_URL}/api/purchase-orders/${id}/cancel`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error al cancelar orden de compra');
  }

  return response.json();
}

/**
 * Get project budget summary
 */
export async function getProjectBudgetSummary(
  projectId: number
): Promise<BudgetSummary> {
  const response = await fetch(
    `${API_BASE_URL}/api/purchase-orders/projects/${projectId}/budget-summary`,
    { headers: getAuthHeaders() }
  );

  if (!response.ok) {
    throw new Error('Error al cargar resumen de presupuesto');
  }

  return response.json();
}

// ========================================================================
// Multi-Invoice Linking (New B2B Pattern)
// ========================================================================

export type InvoiceType = 'anticipo' | 'parcial' | 'finiquito' | 'total';

export interface POInvoice {
  id: number;
  po_id: number;
  sat_invoice_id: string;
  tenant_id: number;
  invoice_type: InvoiceType;
  invoice_amount: number;
  covered_lines?: Record<string, any>;
  notes?: string;
  linked_by: number;
  linked_at: string;
}

export interface POInvoiceLinkRequest {
  sat_invoice_id: string;
  invoice_type: InvoiceType;
  invoice_amount: number;
  covered_lines?: Record<string, any>;
  notes?: string;
}

export interface SATInvoice {
  id: string;
  emisor_nombre: string;
  emisor_rfc: string;
  receptor_nombre: string;
  receptor_rfc: string;
  total: number;
  fecha: string;
  folio?: string;
  serie?: string;
  tipo_comprobante: string;
  uso_cfdi?: string;
  metodo_pago?: string;
  forma_pago?: string;
}

export interface UnlinkedInvoicesResponse {
  vendor_rfc: string;
  count: number;
  invoices: SATInvoice[];
}

/**
 * Link a SAT invoice to a PO (Multi-invoice pattern)
 * Supports anticipo, parcial, finiquito, total
 */
export async function linkInvoiceToPO(
  poId: number,
  data: POInvoiceLinkRequest
): Promise<PurchaseOrder> {
  const response = await fetch(
    `${API_BASE_URL}/api/purchase-orders/${poId}/invoices`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error al vincular factura');
  }

  return response.json();
}

/**
 * Unlink a SAT invoice from a PO
 */
export async function unlinkInvoiceFromPO(
  poId: number,
  invoiceLinkId: number
): Promise<PurchaseOrder> {
  const response = await fetch(
    `${API_BASE_URL}/api/purchase-orders/${poId}/invoices/${invoiceLinkId}`,
    {
      method: 'DELETE',
      headers: getAuthHeaders(),
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error al desvincular factura');
  }

  return response.json();
}

/**
 * Get unlinked SAT invoices for a specific vendor
 * Used to suggest invoices for linking
 */
export async function getUnlinkedInvoices(
  vendorRFC: string
): Promise<UnlinkedInvoicesResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/purchase-orders/invoices/unlinked?vendor_rfc=${vendorRFC}`,
    { headers: getAuthHeaders() }
  );

  if (!response.ok) {
    throw new Error('Error al cargar facturas no vinculadas');
  }

  return response.json();
}

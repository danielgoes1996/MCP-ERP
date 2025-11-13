/**
 * Bank Statement Upload Page
 *
 * Allows uploading PDF, Excel, or CSV bank statements for reconciliation
 */

'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { AppLayout } from '@/components/layout/AppLayout';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import {
  Upload,
  FileText,
  CheckCircle,
  XCircle,
  AlertCircle,
  Building2,
  Calendar,
  DollarSign,
  ArrowLeft,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import Link from 'next/link';

interface UploadResponse {
  statement_id: number;
  filename: string;
  bank_name?: string;
  account_number?: string;
  transaction_count?: number;
  date_range?: {
    start_date: string;
    end_date: string;
  };
  total_credits?: number;
  total_debits?: number;
  parsing_status: 'pending' | 'processing' | 'completed' | 'failed';
  message?: string;
}

export default function ReconciliationUploadPage() {
  const router = useRouter();
  const token = useAuthStore((state) => state.token);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  // TODO: Get from payment accounts list or let user select
  // For now using a default account ID
  const accountId = 1;

  const authHeaders = useMemo(() => {
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, [token]);

  const handleFileSelect = (file: File) => {
    const validExtensions = ['.pdf', '.xlsx', '.xls', '.csv'];
    const fileExtension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));

    if (!validExtensions.includes(fileExtension)) {
      setError(`Tipo de archivo no válido. Solo se permiten: ${validExtensions.join(', ')}`);
      return;
    }

    if (file.size > 50 * 1024 * 1024) { // 50MB limit
      setError('El archivo es demasiado grande. Tamaño máximo: 50MB');
      return;
    }

    setSelectedFile(file);
    setError(null);
    setUploadResult(null);
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelect(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Por favor selecciona un archivo');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await fetch(`http://localhost:8001/bank-statements/accounts/${accountId}/upload`, {
        method: 'POST',
        body: formData,
        headers: authHeaders,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Error desconocido' }));
        throw new Error(errorData.detail || `Error ${response.status}`);
      }

      const result: UploadResponse = await response.json();
      setUploadResult(result);

      // If processing completed successfully, redirect after a delay
      if (result.parsing_status === 'completed') {
        setTimeout(() => {
          router.push('/reconciliation');
        }, 3000);
      }
    } catch (err) {
      console.error('Upload error:', err);
      setError(err instanceof Error ? err.message : 'Error al subir el archivo');
    } finally {
      setUploading(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('es-MX', {
      style: 'currency',
      currency: 'MXN',
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('es-MX', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  return (
    <ProtectedRoute>
      <AppLayout>
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Header */}
          <div className="flex items-center gap-4">
            <Link href="/reconciliation">
              <Button variant="outline" size="sm">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Regresar
              </Button>
            </Link>
            <div>
              <h1 className="text-3xl font-bold text-[#11446e]">Subir Estado de Cuenta</h1>
              <p className="text-gray-600 mt-1">
                Sube archivos PDF, Excel o CSV de tu banco para generar sugerencias de conciliación
              </p>
            </div>
          </div>

          {/* Upload Area */}
          <Card className="p-8">
            <div
              className={cn(
                'border-2 border-dashed rounded-lg p-12 text-center transition-colors',
                dragActive
                  ? 'border-[#11446e] bg-[#11446e]/5'
                  : 'border-gray-300 hover:border-[#11446e]/50',
                selectedFile && 'border-[#60b97b] bg-[#60b97b]/5'
              )}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <input
                type="file"
                id="file-upload"
                className="hidden"
                accept=".pdf,.xlsx,.xls,.csv"
                onChange={handleFileInput}
                disabled={uploading}
              />

              {selectedFile ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-center gap-3">
                    <FileText className="w-12 h-12 text-[#60b97b]" />
                    <div className="text-left">
                      <p className="font-semibold text-[#11446e]">{selectedFile.name}</p>
                      <p className="text-sm text-gray-500">
                        {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                  </div>
                  {!uploading && !uploadResult && (
                    <div className="flex gap-3 justify-center">
                      <label htmlFor="file-upload" className="cursor-pointer">
                        <Button variant="outline" size="sm" type="button" onClick={(e) => e.preventDefault()}>
                          Cambiar Archivo
                        </Button>
                      </label>
                      <Button
                        className="bg-[#11446e] hover:bg-[#11446e]/90"
                        onClick={handleUpload}
                        type="button"
                      >
                        <Upload className="w-4 h-4 mr-2" />
                        Subir y Procesar
                      </Button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-4">
                  <Upload className="w-16 h-16 text-gray-400 mx-auto" />
                  <div>
                    <p className="text-lg font-medium text-gray-700 mb-2">
                      Arrastra tu estado de cuenta aquí
                    </p>
                    <p className="text-sm text-gray-500 mb-4">
                      o haz clic para seleccionar un archivo
                    </p>
                    <label htmlFor="file-upload" className="cursor-pointer">
                      <Button variant="outline" type="button" onClick={(e) => e.preventDefault()}>
                        Seleccionar Archivo
                      </Button>
                    </label>
                  </div>
                  <p className="text-xs text-gray-400">
                    Formatos soportados: PDF, Excel (.xlsx, .xls), CSV
                  </p>
                </div>
              )}
            </div>

            {/* Upload Progress */}
            {uploading && (
              <div className="mt-6">
                <div className="flex items-center justify-center gap-3 text-[#11446e]">
                  <Loader2 className="w-6 h-6 animate-spin" />
                  <p className="font-medium">Procesando estado de cuenta...</p>
                </div>
                <div className="mt-4 bg-gray-200 rounded-full h-2 overflow-hidden">
                  <div className="bg-[#11446e] h-2 rounded-full animate-pulse w-2/3"></div>
                </div>
              </div>
            )}

            {/* Error Message */}
            {error && (
              <div className="mt-6 p-4 bg-red-50 border-2 border-red-200 rounded-lg flex items-start gap-3">
                <XCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-red-700">Error</p>
                  <p className="text-sm text-red-600">{error}</p>
                </div>
              </div>
            )}

            {/* Success Result */}
            {uploadResult && uploadResult.parsing_status === 'completed' && (
              <div className="mt-6 space-y-4">
                <div className="p-4 bg-[#60b97b]/10 border-2 border-[#60b97b]/30 rounded-lg flex items-start gap-3">
                  <CheckCircle className="w-5 h-5 text-[#60b97b] flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="font-semibold text-[#60b97b]">Estado de cuenta procesado exitosamente</p>
                    <p className="text-sm text-gray-600 mt-1">
                      Las sugerencias de conciliación están siendo generadas...
                    </p>
                  </div>
                </div>

                {/* Statement Details */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {uploadResult.bank_name && (
                    <div className="p-4 bg-white border border-gray-200 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <Building2 className="w-4 h-4 text-[#11446e]" />
                        <p className="text-sm text-gray-600">Banco</p>
                      </div>
                      <p className="font-semibold text-[#11446e]">{uploadResult.bank_name}</p>
                      {uploadResult.account_number && (
                        <p className="text-xs text-gray-500 mt-1">
                          Cuenta: •••• {uploadResult.account_number.slice(-4)}
                        </p>
                      )}
                    </div>
                  )}

                  {uploadResult.transaction_count !== undefined && (
                    <div className="p-4 bg-white border border-gray-200 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <FileText className="w-4 h-4 text-[#11446e]" />
                        <p className="text-sm text-gray-600">Transacciones</p>
                      </div>
                      <p className="font-semibold text-[#11446e] text-2xl">
                        {uploadResult.transaction_count}
                      </p>
                    </div>
                  )}

                  {uploadResult.date_range && (
                    <div className="p-4 bg-white border border-gray-200 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <Calendar className="w-4 h-4 text-[#11446e]" />
                        <p className="text-sm text-gray-600">Período</p>
                      </div>
                      <p className="text-sm font-medium text-[#11446e]">
                        {formatDate(uploadResult.date_range.start_date)}
                      </p>
                      <p className="text-sm font-medium text-[#11446e]">
                        {formatDate(uploadResult.date_range.end_date)}
                      </p>
                    </div>
                  )}

                  {(uploadResult.total_credits !== undefined || uploadResult.total_debits !== undefined) && (
                    <div className="p-4 bg-white border border-gray-200 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <DollarSign className="w-4 h-4 text-[#11446e]" />
                        <p className="text-sm text-gray-600">Movimientos</p>
                      </div>
                      {uploadResult.total_credits !== undefined && (
                        <p className="text-sm">
                          <span className="text-gray-600">Créditos:</span>{' '}
                          <span className="font-semibold text-[#60b97b]">
                            {formatCurrency(uploadResult.total_credits)}
                          </span>
                        </p>
                      )}
                      {uploadResult.total_debits !== undefined && (
                        <p className="text-sm">
                          <span className="text-gray-600">Débitos:</span>{' '}
                          <span className="font-semibold text-red-600">
                            {formatCurrency(Math.abs(uploadResult.total_debits))}
                          </span>
                        </p>
                      )}
                    </div>
                  )}
                </div>

                <div className="text-center pt-4">
                  <p className="text-sm text-gray-600 mb-3">
                    Redirigiendo al panel de conciliación...
                  </p>
                  <Link href="/reconciliation">
                    <Button className="bg-[#11446e]">
                      Ir a Conciliación
                    </Button>
                  </Link>
                </div>
              </div>
            )}

            {/* Processing or Pending */}
            {uploadResult && (uploadResult.parsing_status === 'pending' || uploadResult.parsing_status === 'processing') && (
              <div className="mt-6 p-4 bg-blue-50 border-2 border-blue-200 rounded-lg flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-blue-700">Procesamiento en segundo plano</p>
                  <p className="text-sm text-blue-600">
                    El estado de cuenta se está procesando. Puedes ver el progreso en el panel de conciliación.
                  </p>
                  <Link href="/reconciliation">
                    <Button variant="outline" size="sm" className="mt-3">
                      Ir a Conciliación
                    </Button>
                  </Link>
                </div>
              </div>
            )}

            {/* Failed */}
            {uploadResult && uploadResult.parsing_status === 'failed' && (
              <div className="mt-6 p-4 bg-red-50 border-2 border-red-200 rounded-lg flex items-start gap-3">
                <XCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-red-700">Error al procesar</p>
                  <p className="text-sm text-red-600">
                    {uploadResult.message || 'No se pudo procesar el estado de cuenta'}
                  </p>
                </div>
              </div>
            )}
          </Card>

          {/* Help Section */}
          <Card className="p-6 bg-gradient-to-br from-[#11446e]/5 to-white">
            <h3 className="font-bold text-[#11446e] mb-3">¿Cómo funciona?</h3>
            <div className="space-y-3 text-sm text-gray-600">
              <div className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 bg-[#11446e] text-white rounded-full flex items-center justify-center font-semibold text-xs">
                  1
                </span>
                <p>
                  <span className="font-semibold">Sube tu estado de cuenta</span> en formato PDF, Excel o CSV
                </p>
              </div>
              <div className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 bg-[#11446e] text-white rounded-full flex items-center justify-center font-semibold text-xs">
                  2
                </span>
                <p>
                  <span className="font-semibold">El sistema detecta automáticamente</span> el banco y extrae las transacciones
                </p>
              </div>
              <div className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 bg-[#11446e] text-white rounded-full flex items-center justify-center font-semibold text-xs">
                  3
                </span>
                <p>
                  <span className="font-semibold">La IA genera sugerencias</span> de conciliación basadas en montos, fechas y descripciones
                </p>
              </div>
              <div className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 bg-[#11446e] text-white rounded-full flex items-center justify-center font-semibold text-xs">
                  4
                </span>
                <p>
                  <span className="font-semibold">Revisa y aprueba</span> las sugerencias de conciliación en el panel
                </p>
              </div>
            </div>
          </Card>
        </div>
      </AppLayout>
    </ProtectedRoute>
  );
}

/**
 * Invoice Upload Page
 *
 * Upload individual invoices or batch process folders
 */

'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { AppLayout } from '@/components/layout/AppLayout';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Progress } from '@/components/ui/Progress';
import {
  Upload,
  File,
  FolderOpen,
  X,
  CheckCircle,
  AlertCircle,
  FileText,
  Image as ImageIcon,
  Loader2,
  ArrowLeft,
  FileCheck,
  ExternalLink,
} from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import { useRouter } from 'next/navigation';

interface UploadedFile {
  file: File;
  id: string;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error';
  progress: number;
  result?: any;
  error?: string;
  invoiceType?: 'Ingreso' | 'Egreso' | 'Complemento' | 'Desconocido';
}

type UploadMode = 'single' | 'batch';

export default function InvoiceUploadPage() {
  const router = useRouter();
  const [uploadMode, setUploadMode] = useState<UploadMode>('single');
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [overallProgress, setOverallProgress] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  // Get user and tenant from auth context
  const { user, tenant } = useAuthStore();

  // Calculate overall progress
  useEffect(() => {
    if (uploadedFiles.length === 0) {
      setOverallProgress(0);
      return;
    }
    const totalProgress = uploadedFiles.reduce((sum, file) => sum + file.progress, 0);
    const avgProgress = totalProgress / uploadedFiles.length;
    setOverallProgress(avgProgress);
  }, [uploadedFiles]);

  // Handle drag and drop
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    handleFiles(files);
  }, []);

  // Handle file selection
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      handleFiles(files);
    }
  };

  // Process selected files
  const handleFiles = async (files: File[]) => {
    // Filter valid invoice files
    const validExtensions = ['.pdf', '.xml', '.jpg', '.jpeg', '.png', '.csv'];
    const validFiles = files.filter((file) => {
      const extension = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
      return validExtensions.includes(extension);
    });

    if (validFiles.length === 0) {
      alert('Por favor selecciona archivos válidos (PDF, XML, JPG, PNG, CSV)');
      return;
    }

    // Create upload file objects
    const newFiles: UploadedFile[] = validFiles.map((file) => ({
      file,
      id: `${Date.now()}-${Math.random()}`,
      status: 'pending',
      progress: 0,
    }));

    setUploadedFiles((prev) => [...prev, ...newFiles]);

    // Auto-process files immediately
    setTimeout(() => {
      processFiles(newFiles);
    }, 100);
  };

  // Remove file from list
  const removeFile = (id: string) => {
    setUploadedFiles((prev) => prev.filter((f) => f.id !== id));
  };

  // Clear all files
  const clearAllFiles = () => {
    setUploadedFiles([]);
  };

  // Process files (upload and process) using BATCH UPLOAD
  const processFiles = async (filesToProcess?: UploadedFile[]) => {
    const files = filesToProcess || uploadedFiles.filter(f => f.status === 'pending');
    if (files.length === 0) return;

    setIsProcessing(true);

    try {
      // Check authentication
      if (!user || !tenant) {
        throw new Error('Usuario no autenticado');
      }

      const companyId = tenant.name.toLowerCase().replace(/\s+/g, '_');
      const userId = user.id;

      // NUEVO: Usar batch-upload para subir TODOS los archivos de una vez
      console.log(`[Batch Upload] Subiendo ${files.length} archivos...`);

      // Crear FormData con TODOS los archivos
      const formData = new FormData();
      files.forEach(uploadFile => {
        formData.append('files', uploadFile.file);
      });

      // Marcar todos como "uploading"
      setUploadedFiles((prev) =>
        prev.map((f) =>
          files.find(file => file.id === f.id)
            ? { ...f, status: 'uploading', progress: 10 }
            : f
        )
      );

      // Upload TODOS los archivos con batch-upload
      const batchResponse = await fetch(
        `http://localhost:8001/universal-invoice/sessions/batch-upload/?company_id=${companyId}&user_id=${userId}`,
        {
          method: 'POST',
          body: formData,
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          },
        }
      );

      if (!batchResponse.ok) {
        const errorText = await batchResponse.text();
        console.error(`[Batch Upload] Error:`, errorText);
        throw new Error(`Error al subir archivos: ${batchResponse.status}`);
      }

      const batchResult = await batchResponse.json();
      console.log(`[Batch Upload] Resultado:`, batchResult);
      console.log(`✅ ${batchResult.created_sessions} archivos subidos y procesándose en background`);
      console.log(`📦 Batch ID: ${batchResult.batch_id}`);

      // Guardar batch_id en localStorage para poder consultar más tarde
      localStorage.setItem('last_batch_id', batchResult.batch_id);
      localStorage.setItem('last_batch_company_id', companyId);

      // Marcar todos como "processing" porque ya están en el backend
      setUploadedFiles((prev) =>
        prev.map((f) =>
          files.find(file => file.id === f.id)
            ? { ...f, status: 'processing', progress: 30 }
            : f
        )
      );

      // NUEVO: Polling para verificar el estado del batch
      const pollBatchStatus = async () => {
        try {
          const statusResponse = await fetch(
            `http://localhost:8001/universal-invoice/sessions/batch-status/${batchResult.batch_id}?company_id=${companyId}`
          );

          if (!statusResponse.ok) {
            console.error(`[Batch Status] Error: ${statusResponse.status}`);
            return;
          }

          const statusData = await statusResponse.json();
          console.log(`[Batch Status] Progreso: ${statusData.completed}/${statusData.total_sessions} (${statusData.progress_percentage.toFixed(1)}%)`);
          console.log(`[Batch Status] Sesiones:`, statusData.sessions);

          // Usar las sesiones del batch directamente en lugar de consultar tenant
          let completedSessions = new Set<string>();
          if (statusData.sessions && Array.isArray(statusData.sessions)) {
            console.log(`[Batch Sessions] Total sessions from batch: ${statusData.sessions.length}`);
            console.log(`[Batch Sessions] Sample session:`, statusData.sessions[0]);

            // Filtrar solo las sesiones que están completadas
            const completedSessionsList = statusData.sessions.filter((s: any) => s.extraction_status === 'completed');
            console.log(`[Batch Sessions] Completed sessions: ${completedSessionsList.length}`);
            console.log(`[Batch Sessions] Completed filenames:`, completedSessionsList.map((s: any) => s.original_filename));

            completedSessions = new Set(
              completedSessionsList.map((s: any) => s.original_filename)
            );
          }

          // Actualizar estado de archivos individuales
          setUploadedFiles((prev) =>
            prev.map((f) => {
              if (!files.find(file => file.id === f.id)) return f;

              // Si ya está completado o tiene error, no cambiar
              if (f.status === 'completed' || f.status === 'error') return f;

              // Verificar si este archivo específico ya está completado
              const isFileCompleted = completedSessions.has(f.file.name);

              console.log(`[File Matching Debug]`, {
                uploadedFileName: f.file.name,
                completedSessionsCount: completedSessions.size,
                isMatch: isFileCompleted,
                currentStatus: f.status,
                currentProgress: f.progress
              });

              if (isFileCompleted) {
                return {
                  ...f,
                  status: 'completed',
                  progress: 100,
                  invoiceType: 'Ingreso'
                };
              }

              // Si no está completado, actualizar progreso basado en el batch
              const batchProgress = statusData.progress_percentage || 0;
              const newProgress = 30 + (batchProgress * 0.7);

              return {
                ...f,
                progress: Math.round(newProgress)
              };
            })
          );

          // Si el batch está completo, detener polling
          if (statusData.is_complete) {
            console.log(`[Batch Status] ✅ Batch completo!`);
            clearInterval(pollingInterval);
            setIsProcessing(false);
          }
        } catch (error) {
          console.error(`[Batch Status] Error:`, error);
        }
      };

      // Iniciar polling cada 3 segundos
      const pollingInterval = setInterval(pollBatchStatus, 3000);

      // Primera verificación inmediata
      await pollBatchStatus();

      // Timeout después de 5 minutos (por si acaso)
      setTimeout(() => {
        clearInterval(pollingInterval);
        setIsProcessing(false);
        console.log('[Batch Upload] Timeout - deteniendo polling');
      }, 300000);

    } catch (error: any) {
      console.error('[Batch Upload] Error:', error);

      // Marcar todos los archivos pendientes como error
      setUploadedFiles((prev) =>
        prev.map((f) =>
          f.status === 'uploading' || f.status === 'processing'
            ? {
                ...f,
                status: 'error',
                error: error.message,
                progress: 0,
              }
            : f
        )
      );

      setIsProcessing(false);
    }
  };

  // Get file icon
  const getFileIcon = (fileName: string) => {
    const ext = fileName.toLowerCase().slice(fileName.lastIndexOf('.'));
    if (ext === '.pdf') return FileText;
    if (ext === '.xml') return File;
    if (['.jpg', '.jpeg', '.png'].includes(ext)) return ImageIcon;
    return File;
  };

  // Get status color
  const getStatusColor = (status: UploadedFile['status']) => {
    switch (status) {
      case 'completed':
        return 'text-[#60b97b]';
      case 'error':
        return 'text-red-500';
      case 'uploading':
      case 'processing':
        return 'text-[#11446e]';
      default:
        return 'text-gray-500';
    }
  };

  // Get status icon
  const getStatusIcon = (status: UploadedFile['status']) => {
    switch (status) {
      case 'completed':
        return CheckCircle;
      case 'error':
        return AlertCircle;
      case 'uploading':
      case 'processing':
        return Loader2;
      default:
        return File;
    }
  };

  // Get status text
  const getStatusText = (status: UploadedFile['status']) => {
    switch (status) {
      case 'completed':
        return 'Completado';
      case 'error':
        return 'Error';
      case 'uploading':
        return 'Subiendo...';
      case 'processing':
        return 'Procesando...';
      default:
        return 'Pendiente';
    }
  };

  const pendingCount = uploadedFiles.filter((f) => f.status === 'pending').length;
  const completedCount = uploadedFiles.filter(
    (f) => f.status === 'completed'
  ).length;
  const errorCount = uploadedFiles.filter((f) => f.status === 'error').length;
  const processingCount = uploadedFiles.filter(
    (f) => f.status === 'uploading' || f.status === 'processing'
  ).length;

  // Invoice type statistics
  const ingresoCount = uploadedFiles.filter(
    (f) => f.status === 'completed' && f.invoiceType === 'Ingreso'
  ).length;
  const egresoCount = uploadedFiles.filter(
    (f) => f.status === 'completed' && f.invoiceType === 'Egreso'
  ).length;
  const complementoCount = uploadedFiles.filter(
    (f) => f.status === 'completed' && f.invoiceType === 'Complemento'
  ).length;

  return (
    <ProtectedRoute>
      <AppLayout>
        <div className="space-y-6">
          {/* Page Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-[#11446e]">
                Subir Facturas
              </h1>
              <p className="text-gray-600 mt-2">
                Sube facturas individuales o procesa lotes completos
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() => window.history.back()}
              className="flex items-center space-x-2"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Volver</span>
            </Button>
          </div>

          {/* Upload Mode Selection */}
          <Card title="Modo de Carga">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <button
                onClick={() => setUploadMode('single')}
                className={cn(
                  'p-6 border-2 rounded-xl transition-all duration-200',
                  uploadMode === 'single'
                    ? 'border-[#11446e] bg-[#11446e]/5'
                    : 'border-gray-200 hover:border-gray-300'
                )}
              >
                <div className="flex items-start space-x-4">
                  <div
                    className={cn(
                      'p-3 rounded-xl',
                      uploadMode === 'single'
                        ? 'bg-[#11446e] text-white'
                        : 'bg-gray-100 text-gray-600'
                    )}
                  >
                    <FileCheck className="w-6 h-6" />
                  </div>
                  <div className="text-left flex-1">
                    <h3 className="font-semibold text-gray-900 mb-1">
                      Facturas Individuales
                    </h3>
                    <p className="text-sm text-gray-600">
                      Procesa cada factura individualmente con seguimiento
                      detallado
                    </p>
                  </div>
                </div>
              </button>

              <button
                onClick={() => setUploadMode('batch')}
                className={cn(
                  'p-6 border-2 rounded-xl transition-all duration-200',
                  uploadMode === 'batch'
                    ? 'border-[#11446e] bg-[#11446e]/5'
                    : 'border-gray-200 hover:border-gray-300'
                )}
              >
                <div className="flex items-start space-x-4">
                  <div
                    className={cn(
                      'p-3 rounded-xl',
                      uploadMode === 'batch'
                        ? 'bg-[#11446e] text-white'
                        : 'bg-gray-100 text-gray-600'
                    )}
                  >
                    <FolderOpen className="w-6 h-6" />
                  </div>
                  <div className="text-left flex-1">
                    <h3 className="font-semibold text-gray-900 mb-1">
                      Procesamiento por Lotes
                    </h3>
                    <p className="text-sm text-gray-600">
                      Sube carpetas completas y procesa múltiples facturas
                      simultáneamente
                    </p>
                  </div>
                </div>
              </button>
            </div>
          </Card>

          {/* Upload Area */}
          <Card>
            <div
              className={cn(
                'border-2 border-dashed rounded-xl p-12 text-center transition-all duration-200',
                isDragging
                  ? 'border-[#11446e] bg-[#11446e]/5'
                  : 'border-gray-300 hover:border-gray-400'
              )}
              onDragEnter={handleDragEnter}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <div className="flex flex-col items-center space-y-4">
                <div className="p-4 bg-[#11446e]/5 rounded-full">
                  <Upload className="w-12 h-12 text-[#11446e]" />
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">
                    Arrastra archivos aquí
                  </h3>
                  <p className="text-gray-600 mb-4">
                    o haz clic para seleccionar archivos
                  </p>
                  <p className="text-sm text-gray-500">
                    Formatos soportados: PDF, XML, JPG, PNG, CSV
                  </p>
                </div>
                <div className="flex items-center space-x-4">
                  <Button
                    variant="primary"
                    onClick={() => fileInputRef.current?.click()}
                    className="flex items-center space-x-2"
                  >
                    <File className="w-4 h-4" />
                    <span>Seleccionar Archivos</span>
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => folderInputRef.current?.click()}
                    className="flex items-center space-x-2"
                  >
                    <FolderOpen className="w-4 h-4" />
                    <span>Seleccionar Carpeta</span>
                  </Button>
                </div>
              </div>
            </div>

            {/* Hidden file inputs */}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.xml,.jpg,.jpeg,.png,.csv"
              onChange={handleFileSelect}
              className="hidden"
            />
            <input
              ref={folderInputRef}
              type="file"
              multiple
              {...({ webkitdirectory: '', directory: '' } as any)}
              onChange={handleFileSelect}
              className="hidden"
            />
          </Card>

          {/* Files List with Progress */}
          {uploadedFiles.length > 0 && (
            <Card>
              {/* Header with actions */}
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-bold text-gray-900">
                  Archivos Subidos
                </h3>
                <div className="flex items-center space-x-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={clearAllFiles}
                    disabled={isProcessing}
                  >
                    Limpiar Todo
                  </Button>
                  {completedCount > 0 && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => router.push('/invoices')}
                      className="flex items-center space-x-2"
                    >
                      <ExternalLink className="w-4 h-4" />
                      <span>Ver Facturas</span>
                    </Button>
                  )}
                </div>
              </div>

              {/* Progress Bar */}
              {isProcessing && (
                <div className="mb-6 space-y-3">
                  <div className="p-4 bg-gradient-to-r from-[#11446e]/5 to-[#60b97b]/5 rounded-xl">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-700">
                        Procesando archivos...
                      </span>
                      <span className="text-sm font-bold text-[#11446e]">
                        {Math.round((overallProgress / 100) * uploadedFiles.length)} de {uploadedFiles.length}
                      </span>
                    </div>
                    <Progress value={overallProgress} max={100} />
                    <p className="text-xs text-gray-600 mt-2">
                      {Math.round(overallProgress)}% completado
                    </p>
                  </div>
                  {/* Info message about background processing */}
                  <div className="flex items-start gap-2 p-3 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 rounded-lg">
                    <AlertCircle className="w-4 h-4 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
                    <p className="text-xs text-blue-700 dark:text-blue-300">
                      <strong>El procesamiento continúa en segundo plano.</strong> Puedes salir de esta página y las facturas seguirán procesándose. Revisa la lista de facturas en unos minutos para ver los resultados.
                    </p>
                  </div>
                </div>
              )}

              {/* Summary Statistics - Only show when processing is complete */}
              {!isProcessing && completedCount > 0 && (
                <div className="mb-6">
                  <h4 className="text-sm font-semibold text-gray-700 mb-3">
                    Resumen por Tipo de Comprobante
                  </h4>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-4 bg-blue-50 rounded-xl border border-blue-100">
                      <p className="text-xs text-gray-600 mb-1">Ingreso</p>
                      <p className="text-2xl font-bold text-blue-600">
                        {ingresoCount}
                      </p>
                    </div>
                    <div className="p-4 bg-orange-50 rounded-xl border border-orange-100">
                      <p className="text-xs text-gray-600 mb-1">Egreso</p>
                      <p className="text-2xl font-bold text-orange-600">
                        {egresoCount}
                      </p>
                    </div>
                    <div className="p-4 bg-purple-50 rounded-xl border border-purple-100">
                      <p className="text-xs text-gray-600 mb-1">Complemento</p>
                      <p className="text-2xl font-bold text-purple-600">
                        {complementoCount}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Status Summary */}
              <div className="grid grid-cols-4 gap-4 mb-6">
                <div className="p-4 bg-gray-50 rounded-xl">
                  <p className="text-sm text-gray-600">Pendientes</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {pendingCount}
                  </p>
                </div>
                <div className="p-4 bg-blue-50 rounded-xl">
                  <p className="text-sm text-gray-600">Procesando</p>
                  <p className="text-2xl font-bold text-[#11446e]">
                    {processingCount}
                  </p>
                </div>
                <div className="p-4 bg-[#60b97b]/10 rounded-xl">
                  <p className="text-sm text-gray-600">Completados</p>
                  <p className="text-2xl font-bold text-[#60b97b]">
                    {completedCount}
                  </p>
                </div>
                <div className="p-4 bg-red-50 rounded-xl">
                  <p className="text-sm text-gray-600">Errores</p>
                  <p className="text-2xl font-bold text-red-500">
                    {errorCount}
                  </p>
                </div>
              </div>

              {/* Files List */}
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {uploadedFiles.map((uploadFile) => {
                  const FileIcon = getFileIcon(uploadFile.file.name);
                  const StatusIcon = getStatusIcon(uploadFile.status);

                  return (
                    <div
                      key={uploadFile.id}
                      className="flex items-center justify-between p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors"
                    >
                      <div className="flex items-center space-x-4 flex-1">
                        <div className="p-2 bg-white rounded-xl border border-gray-100">
                          <FileIcon className="w-5 h-5 text-[#11446e]" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-gray-900 truncate">
                            {uploadFile.file.name}
                          </p>
                          <div className="flex items-center space-x-2 text-sm text-gray-500">
                            <span>{(uploadFile.file.size / 1024).toFixed(1)} KB</span>
                            {uploadFile.invoiceType && uploadFile.status === 'completed' && (
                              <>
                                <span>•</span>
                                <span className="font-medium text-[#11446e]">
                                  {uploadFile.invoiceType}
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-4">
                        <div className="flex items-center space-x-2">
                          <StatusIcon
                            className={cn(
                              'w-5 h-5',
                              getStatusColor(uploadFile.status),
                              (uploadFile.status === 'uploading' ||
                                uploadFile.status === 'processing') &&
                                'animate-spin'
                            )}
                          />
                          <span
                            className={cn(
                              'text-sm font-medium',
                              getStatusColor(uploadFile.status)
                            )}
                          >
                            {getStatusText(uploadFile.status)}
                          </span>
                        </div>
                        {uploadFile.status === 'pending' && (
                          <button
                            onClick={() => removeFile(uploadFile.id)}
                            className="p-2 rounded-lg hover:bg-red-50 transition-colors"
                            disabled={isProcessing}
                          >
                            <X className="w-4 h-4 text-red-500" />
                          </button>
                        )}
                      </div>
                      {uploadFile.error && (
                        <div className="mt-2 text-sm text-red-600">
                          {uploadFile.error}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </Card>
          )}

          {/* Help Card */}
          <Card title="Ayuda">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h4 className="font-semibold text-gray-900 mb-2">
                  Formatos Soportados
                </h4>
                <ul className="space-y-2 text-sm text-gray-600">
                  <li className="flex items-center space-x-2">
                    <div className="w-1.5 h-1.5 bg-[#60b97b] rounded-full" />
                    <span>
                      <strong>PDF:</strong> Facturas en formato PDF estándar
                    </span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <div className="w-1.5 h-1.5 bg-[#60b97b] rounded-full" />
                    <span>
                      <strong>XML:</strong> Archivos CFDI del SAT
                    </span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <div className="w-1.5 h-1.5 bg-[#60b97b] rounded-full" />
                    <span>
                      <strong>Imágenes:</strong> JPG, PNG para tickets
                    </span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <div className="w-1.5 h-1.5 bg-[#60b97b] rounded-full" />
                    <span>
                      <strong>CSV:</strong> Importación masiva
                    </span>
                  </li>
                </ul>
              </div>
              <div>
                <h4 className="font-semibold text-gray-900 mb-2">
                  Consejos
                </h4>
                <ul className="space-y-2 text-sm text-gray-600">
                  <li className="flex items-center space-x-2">
                    <div className="w-1.5 h-1.5 bg-[#11446e] rounded-full" />
                    <span>Asegúrate de que los archivos estén completos</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <div className="w-1.5 h-1.5 bg-[#11446e] rounded-full" />
                    <span>Los archivos XML deben ser CFDI válidos</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <div className="w-1.5 h-1.5 bg-[#11446e] rounded-full" />
                    <span>
                      Usa procesamiento por lotes para carpetas grandes
                    </span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <div className="w-1.5 h-1.5 bg-[#11446e] rounded-full" />
                    <span>El sistema detecta automáticamente el formato</span>
                  </li>
                </ul>
              </div>
            </div>
          </Card>
        </div>
      </AppLayout>
    </ProtectedRoute>
  );
}

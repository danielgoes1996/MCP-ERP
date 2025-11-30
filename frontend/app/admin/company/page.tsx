'use client';

import { useState, useEffect, useRef } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { AppLayout } from '@/components/layout/AppLayout';
import { PageHeader } from '@/components/ui/PageHeader';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import {
  Building2,
  Upload,
  FileText,
  Image,
  Save,
  CheckCircle,
  AlertCircle,
  Loader2,
} from 'lucide-react';

interface CompanyInfo {
  id: number;
  name: string;
  company_id: string | null;
  status: string | null;
  rfc: string | null;
  logo_url: string | null;
  fiscal_document_url: string | null;
  settings: {
    industry?: string;
    business_model?: string;
    typical_expenses?: string[];
    provider_treatments?: { [key: string]: string };
    preferences?: any;
  } | null;
  created_at: string;
}

export default function CompanyPage() {
  const { user, token } = useAuthStore();
  const [company, setCompany] = useState<CompanyInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [uploadingDocument, setUploadingDocument] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Editable fields
  const [companyName, setCompanyName] = useState('');
  const [aiContext, setAiContext] = useState('');

  const logoInputRef = useRef<HTMLInputElement>(null);
  const documentInputRef = useRef<HTMLInputElement>(null);

  const isAdmin = user?.roles?.includes('admin') || user?.role === 'admin';

  useEffect(() => {
    fetchCompanyInfo();
  }, []);

  const fetchCompanyInfo = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch('http://localhost:8000/api/admin/company', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Error al cargar información de la empresa');
      }

      const data = await response.json();
      setCompany(data);
      setCompanyName(data.name || '');
      setAiContext(JSON.stringify(data.settings || {}, null, 2));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateName = async () => {
    if (!isAdmin) {
      setError('Solo administradores pueden cambiar el nombre');
      return;
    }

    try {
      setSaving(true);
      setError(null);
      setSuccess(null);

      const response = await fetch('http://localhost:8000/api/admin/company/name', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ name: companyName }),
      });

      if (!response.ok) {
        throw new Error('Error al actualizar nombre');
      }

      setSuccess('Nombre actualizado correctamente');
      await fetchCompanyInfo();

      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateSettings = async () => {
    if (!isAdmin) {
      setError('Solo administradores pueden cambiar el contexto');
      return;
    }

    try {
      setSaving(true);
      setError(null);
      setSuccess(null);

      // Parse and validate JSON
      const parsedSettings = JSON.parse(aiContext);

      const response = await fetch('http://localhost:8000/api/admin/company/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(parsedSettings),
      });

      if (!response.ok) {
        throw new Error('Error al actualizar configuración');
      }

      setSuccess('Configuración actualizada correctamente');
      await fetchCompanyInfo();

      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      if (err instanceof SyntaxError) {
        setError('JSON inválido. Por favor, revisa la sintaxis.');
      } else {
        setError(err.message);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploadingLogo(true);
      setError(null);
      setSuccess(null);

      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('http://localhost:8000/api/admin/company/logo', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Error al subir logo');
      }

      setSuccess('Logo subido correctamente');
      await fetchCompanyInfo();

      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUploadingLogo(false);
      if (logoInputRef.current) {
        logoInputRef.current.value = '';
      }
    }
  };

  const handleDocumentUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploadingDocument(true);
      setError(null);
      setSuccess(null);

      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('http://localhost:8000/api/admin/company/fiscal-document', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Error al subir documento fiscal');
      }

      setSuccess('Documento fiscal subido correctamente');
      await fetchCompanyInfo();

      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUploadingDocument(false);
      if (documentInputRef.current) {
        documentInputRef.current.value = '';
      }
    }
  };

  if (loading) {
    return (
      <ProtectedRoute>
        <AppLayout>
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 text-[#11446e] animate-spin" />
          </div>
        </AppLayout>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <AppLayout>
        <div className="space-y-6">
          {/* Header */}
          <PageHeader
            title="Configuración de Empresa"
            subtitle="Gestiona la información de tu empresa y contexto para IA"
          />

          {/* Success/Error Messages */}
          {success && (
            <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-xl">
              <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
              <p className="text-sm text-green-800">{success}</p>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-xl">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          {/* Company Info Card */}
          <Card className="p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-[#11446e]/10 flex items-center justify-center">
                <Building2 className="w-5 h-5 text-[#11446e]" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-900">Información de la Empresa</h2>
                <p className="text-sm text-gray-600">Datos básicos de la compañía</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input
                  label="Nombre de la Empresa"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  disabled={!isAdmin}
                  placeholder="Ej: ContaFlow S.A. de C.V."
                />

                <Input
                  label="RFC"
                  value={company?.rfc || ''}
                  disabled
                  placeholder="No configurado"
                />
              </div>

              {isAdmin && (
                <div className="flex justify-end pt-2">
                  <Button
                    onClick={handleUpdateName}
                    disabled={saving || companyName === company?.name}
                    variant="primary"
                    size="sm"
                  >
                    {saving ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Guardando...
                      </>
                    ) : (
                      <>
                        <Save className="w-4 h-4 mr-2" />
                        Guardar Cambios
                      </>
                    )}
                  </Button>
                </div>
              )}
            </div>
          </Card>

          {/* Logo Upload Card */}
          <Card className="p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-purple-100 flex items-center justify-center">
                <Image className="w-5 h-5 text-purple-600" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-900">Logo de la Empresa</h2>
                <p className="text-sm text-gray-600">Formatos permitidos: PNG, JPG, JPEG, SVG</p>
              </div>
            </div>

            <div className="space-y-4">
              {company?.logo_url && (
                <div className="flex items-center justify-center p-8 bg-gray-50 rounded-xl border border-gray-200">
                  <img
                    src={`http://localhost:8000${company.logo_url}`}
                    alt="Company Logo"
                    className="max-h-32 max-w-full object-contain"
                  />
                </div>
              )}

              {isAdmin && (
                <div>
                  <input
                    ref={logoInputRef}
                    type="file"
                    accept="image/png,image/jpeg,image/jpg,image/svg+xml"
                    onChange={handleLogoUpload}
                    className="hidden"
                  />
                  <Button
                    onClick={() => logoInputRef.current?.click()}
                    disabled={uploadingLogo}
                    variant="secondary"
                    size="sm"
                  >
                    {uploadingLogo ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Subiendo...
                      </>
                    ) : (
                      <>
                        <Upload className="w-4 h-4 mr-2" />
                        {company?.logo_url ? 'Cambiar Logo' : 'Subir Logo'}
                      </>
                    )}
                  </Button>
                </div>
              )}
            </div>
          </Card>

          {/* Fiscal Document Card */}
          <Card className="p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
                <FileText className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-900">Constancia de Situación Fiscal</h2>
                <p className="text-sm text-gray-600">Formato permitido: PDF</p>
              </div>
            </div>

            <div className="space-y-4">
              {company?.fiscal_document_url ? (
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-200">
                  <div className="flex items-center gap-3">
                    <FileText className="w-5 h-5 text-gray-600" />
                    <div>
                      <p className="text-sm font-medium text-gray-900">Documento fiscal subido</p>
                      <a
                        href={`http://localhost:8000${company.fiscal_document_url}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-[#11446e] hover:underline"
                      >
                        Ver documento
                      </a>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-center p-8 bg-gray-50 rounded-xl border border-gray-200 border-dashed">
                  <p className="text-sm text-gray-500">No hay documento fiscal subido</p>
                </div>
              )}

              {isAdmin && (
                <div>
                  <input
                    ref={documentInputRef}
                    type="file"
                    accept="application/pdf"
                    onChange={handleDocumentUpload}
                    className="hidden"
                  />
                  <Button
                    onClick={() => documentInputRef.current?.click()}
                    disabled={uploadingDocument}
                    variant="secondary"
                    size="sm"
                  >
                    {uploadingDocument ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Subiendo...
                      </>
                    ) : (
                      <>
                        <Upload className="w-4 h-4 mr-2" />
                        {company?.fiscal_document_url ? 'Cambiar Documento' : 'Subir Documento'}
                      </>
                    )}
                  </Button>
                </div>
              )}
            </div>
          </Card>

          {/* AI Context Card */}
          <Card className="p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-green-100 flex items-center justify-center">
                <FileText className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-900">Contexto de IA</h2>
                <p className="text-sm text-gray-600">
                  Configuración utilizada para clasificación inteligente
                </p>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-gray-900 mb-2">
                  Configuración JSON
                </label>
                <textarea
                  value={aiContext}
                  onChange={(e) => setAiContext(e.target.value)}
                  disabled={!isAdmin}
                  rows={15}
                  className="w-full px-4 py-3 bg-white border border-gray-300 rounded-xl text-sm text-gray-900 font-mono focus:outline-none focus:border-[#11446e] focus:ring-2 focus:ring-[#11446e]/10 transition-all disabled:bg-gray-50 disabled:text-gray-600"
                  placeholder='{\n  "industry": "...",\n  "business_model": "...",\n  "typical_expenses": [...]\n}'
                />
                <p className="mt-2 text-sm text-gray-500">
                  Formato JSON válido. Incluye: industry, business_model, typical_expenses,
                  provider_treatments, preferences
                </p>
              </div>

              {isAdmin && (
                <div className="flex justify-end pt-2">
                  <Button
                    onClick={handleUpdateSettings}
                    disabled={saving}
                    variant="primary"
                    size="sm"
                  >
                    {saving ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Guardando...
                      </>
                    ) : (
                      <>
                        <Save className="w-4 h-4 mr-2" />
                        Guardar Contexto
                      </>
                    )}
                  </Button>
                </div>
              )}
            </div>
          </Card>
        </div>
      </AppLayout>
    </ProtectedRoute>
  );
}

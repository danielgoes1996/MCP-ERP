/**
 * SAT Credentials Page
 *
 * Upload and manage SAT FIEL credentials for automatic invoice downloads
 */

'use client';

import { useState, useEffect } from 'react';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import { useRouter } from 'next/navigation';
import {
  getSATCredentials,
  uploadSATCredentials,
  deleteSATCredentials,
  type SATCredentials,
} from '@/services/satCredentialsService';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Upload, FileKey, FileCheck, Trash2, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react';

export default function SATCredentialsPage() {
  const router = useRouter();
  const { user, tenant, isAuthenticated } = useAuthStore();

  // State
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [credentials, setCredentials] = useState<SATCredentials | null>(null);
  const [showUpdateForm, setShowUpdateForm] = useState(false);

  // Form state
  const [rfc, setRfc] = useState('');
  const [satPassword, setSatPassword] = useState('');
  const [fielPassword, setFielPassword] = useState('');
  const [cerFile, setCerFile] = useState<File | null>(null);
  const [keyFile, setKeyFile] = useState<File | null>(null);

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  // Load existing credentials
  useEffect(() => {
    async function loadCredentials() {
      const companyId = tenant?.company_id;

      if (!companyId || isNaN(Number(companyId))) {
        console.log('No valid company_id found');
        setError('No se encontró ID de empresa. Por favor, vuelve a iniciar sesión.');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        const data = await getSATCredentials(Number(companyId));
        setCredentials(data);
      } catch (err: any) {
        console.error('Error loading SAT credentials:', err);
        setError('Error al cargar credenciales');
      } finally {
        setLoading(false);
      }
    }

    loadCredentials();
  }, [tenant?.company_id]);

  // Handle form submit
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validation
    if (!rfc || !satPassword || !fielPassword || !cerFile || !keyFile) {
      setError('Por favor completa todos los campos');
      return;
    }

    if (rfc.length < 12 || rfc.length > 13) {
      setError('RFC debe tener 12 o 13 caracteres');
      return;
    }

    if (!cerFile.name.endsWith('.cer')) {
      setError('El certificado debe ser un archivo .cer');
      return;
    }

    if (!keyFile.name.endsWith('.key')) {
      setError('La clave privada debe ser un archivo .key');
      return;
    }

    try {
      setUploading(true);
      setError(null);
      setSuccessMessage(null);

      const uploadedCredentials = await uploadSATCredentials({
        rfc,
        sat_password: satPassword,
        fiel_password: fielPassword,
        cer_file: cerFile,
        key_file: keyFile,
      });

      setCredentials(uploadedCredentials);
      setSuccessMessage('Credenciales guardadas exitosamente');

      // Clear form
      setRfc('');
      setSatPassword('');
      setFielPassword('');
      setCerFile(null);
      setKeyFile(null);

      // Clear file inputs
      const cerInput = document.getElementById('cer_file') as HTMLInputElement;
      const keyInput = document.getElementById('key_file') as HTMLInputElement;
      if (cerInput) cerInput.value = '';
      if (keyInput) keyInput.value = '';

      // Clear success message after 3 seconds
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      console.error('Error uploading credentials:', err);
      setError(err.message || 'Error al guardar credenciales');
    } finally {
      setUploading(false);
    }
  };

  // Handle delete
  const handleDelete = async () => {
    if (!tenant?.company_id) return;
    if (!confirm('¿Estás seguro de eliminar estas credenciales?')) return;

    try {
      setDeleting(true);
      setError(null);
      setSuccessMessage(null);

      await deleteSATCredentials(Number(tenant.company_id));
      setCredentials(null);
      setSuccessMessage('Credenciales eliminadas exitosamente');

      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      console.error('Error deleting credentials:', err);
      setError(err.message || 'Error al eliminar credenciales');
    } finally {
      setDeleting(false);
    }
  };

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-neutral-900 mb-2">
            Credenciales SAT (e.firma)
          </h1>
          <p className="text-neutral-600">
            Configura tus credenciales de e.firma (FIEL) para descargar facturas automáticamente del portal del SAT
          </p>
        </div>

        {/* Success Message */}
        {successMessage && (
          <div className="mb-6 p-4 bg-success-50 border-l-4 border-success-600 rounded">
            <p className="text-success-900 font-semibold">{successMessage}</p>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-error-50 border-l-4 border-error-600 rounded">
            <p className="text-error-900 font-semibold">{error}</p>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <Card className="p-6 animate-pulse">
            <div className="h-6 bg-neutral-300 rounded w-1/3 mb-4"></div>
            <div className="h-4 bg-neutral-200 rounded w-2/3 mb-2"></div>
            <div className="h-4 bg-neutral-200 rounded w-1/2"></div>
          </Card>
        )}

        {/* Existing Credentials Card */}
        {!loading && credentials && (
          <Card className="p-6 mb-6 bg-success-50 border border-success-200">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-3">
                  <FileCheck className="w-6 h-6 text-success-600" />
                  <h3 className="text-lg font-semibold text-success-900">
                    Credenciales Activas
                  </h3>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex">
                    <span className="text-neutral-600 font-medium w-48">RFC:</span>
                    <span className="text-neutral-900">{credentials.rfc}</span>
                  </div>
                  {credentials.certificate_serial_number && (
                    <div className="flex">
                      <span className="text-neutral-600 font-medium w-48">Número de Serie:</span>
                      <span className="text-neutral-900 font-mono text-xs">{credentials.certificate_serial_number}</span>
                    </div>
                  )}
                  {credentials.certificate_valid_until && (
                    <div className="flex">
                      <span className="text-neutral-600 font-medium w-48">Válido hasta:</span>
                      <span className="text-neutral-900">
                        {new Date(credentials.certificate_valid_until).toLocaleDateString('es-MX', {
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric'
                        })}
                      </span>
                    </div>
                  )}
                  <div className="flex">
                    <span className="text-neutral-600 font-medium w-48">Creado:</span>
                    <span className="text-neutral-900">
                      {new Date(credentials.created_at).toLocaleDateString('es-MX')}
                    </span>
                  </div>
                </div>
              </div>
              <Button
                variant="outline"
                onClick={handleDelete}
                disabled={deleting}
                className="flex items-center gap-2 text-error-600 border-error-300 hover:bg-error-50"
              >
                <Trash2 className="w-4 h-4" />
                {deleting ? 'Eliminando...' : 'Eliminar'}
              </Button>
            </div>
          </Card>
        )}

        {/* Info Card - Only show if no credentials exist */}
        {!loading && !credentials && (
          <Card className="p-6 mb-6 bg-blue-50 border border-blue-200">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5" />
              <div className="text-sm text-blue-900">
                <p className="font-semibold mb-1">¿Qué necesitas?</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>RFC de tu empresa (12-13 caracteres)</li>
                  <li>Contraseña del portal del SAT</li>
                  <li>Archivos de e.firma (FIEL): .cer y .key</li>
                  <li>Contraseña de la e.firma (FIEL)</li>
                </ul>
              </div>
            </div>
          </Card>
        )}

        {/* Show expand button if credentials exist */}
        {!loading && credentials && !showUpdateForm && (
          <Button
            type="button"
            onClick={() => setShowUpdateForm(true)}
            variant="outline"
            className="w-full flex items-center justify-center gap-2 border-neutral-300 hover:bg-neutral-50"
          >
            <ChevronDown className="w-5 h-5" />
            <span>Actualizar Credenciales</span>
          </Button>
        )}

        {/* Upload Form - Always visible if no credentials, collapsible if credentials exist */}
        {!loading && (!credentials || showUpdateForm) && (
          <form onSubmit={handleSubmit} className="space-y-6">
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-neutral-900">
                  {credentials ? 'Actualizar Credenciales' : 'Subir Credenciales'}
                </h3>
                {credentials && (
                  <button
                    type="button"
                    onClick={() => setShowUpdateForm(false)}
                    className="text-neutral-500 hover:text-neutral-700 transition-colors"
                  >
                    <ChevronUp className="w-5 h-5" />
                  </button>
                )}
              </div>

              <div className="space-y-4">
                {/* RFC */}
                <div>
                  <label htmlFor="rfc" className="block text-sm font-medium text-neutral-700 mb-2">
                    RFC de la Empresa
                  </label>
                  <input
                    id="rfc"
                    type="text"
                    value={rfc}
                    onChange={(e) => setRfc(e.target.value.toUpperCase())}
                    placeholder="XAXX010101000"
                    maxLength={13}
                    className="w-full px-4 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 uppercase"
                  />
                </div>

                {/* SAT Password */}
                <div>
                  <label htmlFor="sat_password" className="block text-sm font-medium text-neutral-700 mb-2">
                    Contraseña del Portal SAT
                  </label>
                  <input
                    id="sat_password"
                    type="password"
                    value={satPassword}
                    onChange={(e) => setSatPassword(e.target.value)}
                    placeholder="Tu contraseña del portal SAT"
                    className="w-full px-4 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  />
                </div>

                {/* Certificate File */}
                <div>
                  <label htmlFor="cer_file" className="block text-sm font-medium text-neutral-700 mb-2">
                    Certificado (.cer)
                  </label>
                  <div className="relative">
                    <input
                      id="cer_file"
                      type="file"
                      accept=".cer"
                      onChange={(e) => setCerFile(e.target.files?.[0] || null)}
                      className="w-full px-4 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    />
                    {cerFile && (
                      <div className="mt-2 flex items-center gap-2 text-sm text-success-600">
                        <FileCheck className="w-4 h-4" />
                        {cerFile.name}
                      </div>
                    )}
                  </div>
                </div>

                {/* Key File */}
                <div>
                  <label htmlFor="key_file" className="block text-sm font-medium text-neutral-700 mb-2">
                    Clave Privada (.key)
                  </label>
                  <div className="relative">
                    <input
                      id="key_file"
                      type="file"
                      accept=".key"
                      onChange={(e) => setKeyFile(e.target.files?.[0] || null)}
                      className="w-full px-4 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    />
                    {keyFile && (
                      <div className="mt-2 flex items-center gap-2 text-sm text-success-600">
                        <FileKey className="w-4 h-4" />
                        {keyFile.name}
                      </div>
                    )}
                  </div>
                </div>

                {/* FIEL Password */}
                <div>
                  <label htmlFor="fiel_password" className="block text-sm font-medium text-neutral-700 mb-2">
                    Contraseña de la e.firma (FIEL)
                  </label>
                  <input
                    id="fiel_password"
                    type="password"
                    value={fielPassword}
                    onChange={(e) => setFielPassword(e.target.value)}
                    placeholder="Contraseña de tu e.firma"
                    className="w-full px-4 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  />
                </div>
              </div>
            </Card>

            {/* Submit Button */}
            <Button
              type="submit"
              disabled={uploading}
              className="w-full bg-primary-600 hover:bg-primary-700 text-white flex items-center justify-center gap-2"
            >
              <Upload className="w-5 h-5" />
              {uploading ? 'Subiendo...' : credentials ? 'Actualizar Credenciales' : 'Guardar Credenciales'}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}

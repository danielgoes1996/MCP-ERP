/**
 * VerifyEmailForm Component
 *
 * Componente para verificar email automáticamente con token desde URL
 */

'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { Button } from '@/components/shared/Button';

export function VerifyEmailForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [isVerifying, setIsVerifying] = useState(true);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError('Token de verificación no encontrado');
      setIsVerifying(false);
      return;
    }

    verifyEmail(token);
  }, [token]);

  const verifyEmail = async (verificationToken: string) => {
    setIsVerifying(true);
    setError(null);

    try {
      const response = await apiClient.post('/auth/verify-email', {
        token: verificationToken,
      });

      if (response.data.success) {
        setSuccess(true);

        // Redirect to login after 3 seconds
        setTimeout(() => {
          router.push('/auth/login');
        }, 3000);
      }
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Error al verificar el email';
      setError(errorMessage);
    } finally {
      setIsVerifying(false);
    }
  };

  const handleResendVerification = async () => {
    // Esta función podría implementarse para reenviar el correo
    // Por ahora redirige a login
    router.push('/auth/login');
  };

  // Loading state
  if (isVerifying) {
    return (
      <div className="text-center py-8">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary-100 mb-4">
          <Loader2 className="h-8 w-8 text-primary-600 animate-spin" />
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Verificando tu email
        </h3>
        <p className="text-gray-600 text-sm">
          Esto solo tomará un momento...
        </p>
      </div>
    );
  }

  // Success state
  if (success) {
    return (
      <div className="text-center py-8">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 mb-4">
          <CheckCircle className="h-8 w-8 text-green-600" />
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          ¡Email verificado!
        </h3>
        <p className="text-gray-600 text-sm mb-6">
          Tu cuenta ha sido verificada exitosamente. Ya puedes iniciar sesión.
        </p>
        <Button
          variant="primary"
          size="lg"
          fullWidth
          onClick={() => router.push('/auth/login')}
        >
          Ir al inicio de sesión
        </Button>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="text-center py-8">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-100 mb-4">
          <XCircle className="h-8 w-8 text-red-600" />
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Error de verificación
        </h3>
        <p className="text-gray-600 text-sm mb-6">
          {error}
        </p>
        <div className="space-y-3">
          <Button
            variant="primary"
            size="lg"
            fullWidth
            onClick={handleResendVerification}
          >
            Volver al inicio de sesión
          </Button>
          <p className="text-xs text-gray-500">
            Si el problema persiste, contacta a soporte
          </p>
        </div>
      </div>
    );
  }

  return null;
}

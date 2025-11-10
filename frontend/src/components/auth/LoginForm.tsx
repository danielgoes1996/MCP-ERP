/**
 * LoginForm Component
 *
 * Formulario de login con validación de Zod y React Hook Form
 * Incluye manejo de email no verificado
 */

'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import Link from 'next/link';
import { AlertCircle } from 'lucide-react';
import { loginSchema, type LoginFormData } from '@/lib/validators/auth';
import { useAuth } from '@/hooks/useAuth';
import { apiClient } from '@/lib/api/client';
import { Button } from '@/components/shared/Button';
import { Input } from '@/components/shared/Input';

export function LoginForm() {
  const { login, isLoggingIn } = useAuth();
  const [showEmailNotVerified, setShowEmailNotVerified] = useState(false);
  const [emailForResend, setEmailForResend] = useState('');
  const [isResending, setIsResending] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  const onSubmit = async (data: LoginFormData) => {
    setShowEmailNotVerified(false);
    setEmailForResend('');
    login(data);
  };

  const handleResendVerification = async () => {
    setIsResending(true);
    try {
      await apiClient.post('/auth/resend-verification', {
        email: emailForResend,
      });
      alert('Correo de verificación reenviado. Revisa tu bandeja de entrada.');
      setShowEmailNotVerified(false);
    } catch (error) {
      alert('Error al reenviar el correo de verificación');
    } finally {
      setIsResending(false);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      {/* Email Not Verified Warning */}
      {showEmailNotVerified && (
        <div className="rounded-lg bg-amber-50 border border-amber-200 p-4">
          <div className="flex">
            <AlertCircle className="h-5 w-5 text-amber-600 mr-3 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-800 mb-1">
                Email no verificado
              </p>
              <p className="text-sm text-amber-700 mb-2">
                Debes verificar tu email antes de iniciar sesión.
              </p>
              <button
                type="button"
                onClick={handleResendVerification}
                disabled={isResending}
                className="text-sm font-medium text-amber-800 underline hover:text-amber-900 disabled:opacity-50"
              >
                {isResending ? 'Reenviando...' : 'Reenviar correo de verificación'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Email */}
      <div>
        <Input
          {...register('email')}
          type="email"
          label="Email"
          placeholder="tu@email.com"
          error={errors.email?.message}
          fullWidth
          required
          autoComplete="email"
          disabled={isLoggingIn}
        />
      </div>

      {/* Password */}
      <div>
        <Input
          {...register('password')}
          type="password"
          label="Contraseña"
          placeholder="••••••••"
          error={errors.password?.message}
          fullWidth
          required
          autoComplete="current-password"
          disabled={isLoggingIn}
        />
      </div>

      {/* Forgot Password Link */}
      <div className="flex justify-end">
        <Link
          href="/auth/forgot-password"
          className="text-sm text-primary-500 hover:text-primary-600 font-medium"
        >
          ¿Olvidaste tu contraseña?
        </Link>
      </div>

      {/* Submit Button */}
      <Button
        type="submit"
        variant="primary"
        size="lg"
        fullWidth
        isLoading={isLoggingIn}
        disabled={isLoggingIn}
      >
        {isLoggingIn ? 'Iniciando sesión...' : 'Iniciar Sesión'}
      </Button>

      {/* Register Link */}
      <div className="text-center text-sm text-gray-600">
        ¿No tienes cuenta?{' '}
        <Link
          href="/auth/register"
          className="text-primary-500 hover:text-primary-600 font-medium"
        >
          Regístrate aquí
        </Link>
      </div>
    </form>
  );
}

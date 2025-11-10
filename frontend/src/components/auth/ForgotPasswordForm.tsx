/**
 * ForgotPasswordForm Component
 *
 * Formulario para solicitar restablecimiento de contraseña
 */

'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { CheckCircle } from 'lucide-react';
import { authService } from '@/services/auth/authService';
import { Button } from '@/components/shared/Button';
import { Input } from '@/components/shared/Input';

const forgotPasswordSchema = z.object({
  email: z.string().email('Email inválido'),
});

type ForgotPasswordFormData = z.infer<typeof forgotPasswordSchema>;

export function ForgotPasswordForm() {
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordFormData>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: {
      email: '',
    },
  });

  const onSubmit = async (data: ForgotPasswordFormData) => {
    setIsLoading(true);
    setError(null);

    try {
      await authService.requestPasswordReset(data.email);
      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al enviar el correo');
    } finally {
      setIsLoading(false);
    }
  };

  if (success) {
    return (
      <div className="text-center py-8">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 mb-4">
          <CheckCircle className="h-8 w-8 text-green-600" />
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          ¡Correo enviado!
        </h3>
        <p className="text-gray-600 text-sm">
          Si tu email existe en nuestro sistema, recibirás un enlace para restablecer tu contraseña.
        </p>
        <p className="text-gray-500 text-xs mt-4">
          Revisa tu bandeja de entrada y spam
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      {/* Error Message */}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4">
          <p className="text-sm text-red-600">{error}</p>
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
          disabled={isLoading}
        />
      </div>

      {/* Submit Button */}
      <Button
        type="submit"
        variant="primary"
        size="lg"
        fullWidth
        isLoading={isLoading}
        disabled={isLoading}
      >
        {isLoading ? 'Enviando...' : 'Enviar enlace de recuperación'}
      </Button>
    </form>
  );
}

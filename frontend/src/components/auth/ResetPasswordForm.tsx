/**
 * ResetPasswordForm Component
 *
 * Formulario para restablecer contraseña con token
 */

'use client';

import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useRouter, useSearchParams } from 'next/navigation';
import { CheckCircle } from 'lucide-react';
import { authService } from '@/services/auth/authService';
import { Button } from '@/components/shared/Button';
import { Input } from '@/components/shared/Input';

const resetPasswordSchema = z.object({
  password: z
    .string()
    .min(8, 'La contraseña debe tener al menos 8 caracteres')
    .regex(/[A-Z]/, 'Debe contener al menos una mayúscula')
    .regex(/[a-z]/, 'Debe contener al menos una minúscula')
    .regex(/[0-9]/, 'Debe contener al menos un número'),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: 'Las contraseñas no coinciden',
  path: ['confirmPassword'],
});

type ResetPasswordFormData = z.infer<typeof resetPasswordSchema>;

export function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetPasswordFormData>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: {
      password: '',
      confirmPassword: '',
    },
  });

  useEffect(() => {
    if (!token) {
      setError('Token de verificación no válido');
    }
  }, [token]);

  const onSubmit = async (data: ResetPasswordFormData) => {
    if (!token) {
      setError('Token no encontrado');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await authService.resetPassword(token, data.password);
      setSuccess(true);

      // Redirect to login after 3 seconds
      setTimeout(() => {
        router.push('/auth/login');
      }, 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al restablecer la contraseña');
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
          ¡Contraseña restablecida!
        </h3>
        <p className="text-gray-600 text-sm">
          Tu contraseña ha sido actualizada correctamente.
        </p>
        <p className="text-gray-500 text-xs mt-4">
          Redirigiendo al inicio de sesión...
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

      {/* New Password */}
      <div>
        <Input
          {...register('password')}
          type="password"
          label="Nueva Contraseña"
          placeholder="••••••••"
          error={errors.password?.message}
          fullWidth
          required
          autoComplete="new-password"
          disabled={isLoading || !token}
        />
        <p className="text-xs text-gray-500 mt-1">
          Mínimo 8 caracteres, una mayúscula, una minúscula y un número
        </p>
      </div>

      {/* Confirm Password */}
      <div>
        <Input
          {...register('confirmPassword')}
          type="password"
          label="Confirmar Contraseña"
          placeholder="••••••••"
          error={errors.confirmPassword?.message}
          fullWidth
          required
          autoComplete="new-password"
          disabled={isLoading || !token}
        />
      </div>

      {/* Submit Button */}
      <Button
        type="submit"
        variant="primary"
        size="lg"
        fullWidth
        isLoading={isLoading}
        disabled={isLoading || !token}
      >
        {isLoading ? 'Restableciendo...' : 'Restablecer contraseña'}
      </Button>
    </form>
  );
}

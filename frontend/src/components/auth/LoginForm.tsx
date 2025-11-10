/**
 * LoginForm Component
 *
 * Formulario de login con validación de Zod y React Hook Form
 */

'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import Link from 'next/link';
import { Mail, Lock } from 'lucide-react';
import { loginSchema, type LoginFormData } from '@/lib/validators/auth';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/shared/Button';
import { Input } from '@/components/shared/Input';

export function LoginForm() {
  const { login, isLoggingIn } = useAuth();

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

  const onSubmit = (data: LoginFormData) => {
    login(data);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
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

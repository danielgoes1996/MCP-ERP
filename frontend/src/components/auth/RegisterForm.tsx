/**
 * RegisterForm Component
 *
 * Formulario de registro con validación de Zod y React Hook Form
 */

'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import Link from 'next/link';
import { User, Mail, Lock, Building } from 'lucide-react';
import { registerSchema, type RegisterFormData } from '@/lib/validators/auth';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/shared/Button';
import { Input } from '@/components/shared/Input';

export function RegisterForm() {
  const { register: registerUser, isRegistering } = useAuth();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      name: '',
      email: '',
      password: '',
      confirmPassword: '',
      company_name: '',
      acceptTerms: false,
    },
  });

  const onSubmit = (data: RegisterFormData) => {
    // Remover confirmPassword antes de enviar
    const { confirmPassword, acceptTerms, ...registerData } = data;
    registerUser(registerData);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
      {/* Name */}
      <div>
        <Input
          {...register('name')}
          type="text"
          label="Nombre completo"
          placeholder="Juan Pérez"
          error={errors.name?.message}
          fullWidth
          required
          autoComplete="name"
          disabled={isRegistering}
        />
      </div>

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
          disabled={isRegistering}
        />
      </div>

      {/* Company Name (Optional) */}
      <div>
        <Input
          {...register('company_name')}
          type="text"
          label="Nombre de la empresa"
          placeholder="Mi Empresa S.A."
          error={errors.company_name?.message}
          fullWidth
          helperText="Opcional - puedes configurarlo después"
          disabled={isRegistering}
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
          autoComplete="new-password"
          helperText="Mínimo 8 caracteres, una mayúscula, una minúscula y un número"
          disabled={isRegistering}
        />
      </div>

      {/* Confirm Password */}
      <div>
        <Input
          {...register('confirmPassword')}
          type="password"
          label="Confirmar contraseña"
          placeholder="••••••••"
          error={errors.confirmPassword?.message}
          fullWidth
          required
          autoComplete="new-password"
          disabled={isRegistering}
        />
      </div>

      {/* Terms and Conditions */}
      <div className="flex items-start gap-2">
        <input
          {...register('acceptTerms')}
          type="checkbox"
          id="acceptTerms"
          className="mt-1 w-4 h-4 text-primary-500 border-gray-300 rounded focus:ring-primary-500"
          disabled={isRegistering}
        />
        <label htmlFor="acceptTerms" className="text-sm text-gray-600">
          Acepto los{' '}
          <Link href="/terms" className="text-primary-500 hover:text-primary-600">
            términos y condiciones
          </Link>{' '}
          y la{' '}
          <Link href="/privacy" className="text-primary-500 hover:text-primary-600">
            política de privacidad
          </Link>
        </label>
      </div>
      {errors.acceptTerms && (
        <p className="text-sm text-error-500">{errors.acceptTerms.message}</p>
      )}

      {/* Submit Button */}
      <Button
        type="submit"
        variant="primary"
        size="lg"
        fullWidth
        isLoading={isRegistering}
        disabled={isRegistering}
      >
        {isRegistering ? 'Creando cuenta...' : 'Crear Cuenta'}
      </Button>

      {/* Login Link */}
      <div className="text-center text-sm text-gray-600">
        ¿Ya tienes cuenta?{' '}
        <Link
          href="/auth/login"
          className="text-primary-500 hover:text-primary-600 font-medium"
        >
          Inicia sesión aquí
        </Link>
      </div>
    </form>
  );
}

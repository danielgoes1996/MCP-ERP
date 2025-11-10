/**
 * Reset Password Page
 *
 * Página para restablecer contraseña con token
 */

import { Metadata } from 'next';
import Link from 'next/link';
import { Card } from '@/components/shared/Card';
import { Logo } from '@/components/shared/Logo';
import { ResetPasswordForm } from '@/components/auth/ResetPasswordForm';

export const metadata: Metadata = {
  title: 'Restablecer Contraseña - ContaFlow',
  description: 'Crea una nueva contraseña para tu cuenta',
};

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 via-white to-accent-50 px-4 py-8">
      <div className="w-full max-w-md animate-fadeIn">
        {/* Logo / Header */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <Logo size="lg" />
          </div>
          <p className="text-gray-600">
            Gestión contable inteligente impulsada por IA
          </p>
        </div>

        {/* Reset Password Card */}
        <Card className="shadow-xl">
          <div className="px-6 py-8">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-gray-900">
                Restablecer contraseña
              </h2>
              <p className="text-sm text-gray-600 mt-1">
                Ingresa tu nueva contraseña
              </p>
            </div>

            <ResetPasswordForm />
          </div>
        </Card>

        {/* Back to Login */}
        <div className="mt-6 text-center text-sm text-gray-600">
          <Link
            href="/auth/login"
            className="text-primary-500 hover:text-primary-600 font-medium"
          >
            ← Volver al inicio de sesión
          </Link>
        </div>
      </div>
    </div>
  );
}

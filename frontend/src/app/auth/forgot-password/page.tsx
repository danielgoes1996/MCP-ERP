/**
 * Forgot Password Page
 *
 * Página para solicitar restablecimiento de contraseña
 */

import { Metadata } from 'next';
import Link from 'next/link';
import { Card } from '@/components/shared/Card';
import { Logo } from '@/components/shared/Logo';
import { ForgotPasswordForm } from '@/components/auth/ForgotPasswordForm';

export const metadata: Metadata = {
  title: 'Recuperar Contraseña - ContaFlow',
  description: 'Solicita un enlace para restablecer tu contraseña',
};

export default function ForgotPasswordPage() {
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

        {/* Forgot Password Card */}
        <Card className="shadow-xl">
          <div className="px-6 py-8">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-gray-900">
                ¿Olvidaste tu contraseña?
              </h2>
              <p className="text-sm text-gray-600 mt-1">
                Ingresa tu email y te enviaremos un enlace para restablecerla
              </p>
            </div>

            <ForgotPasswordForm />
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

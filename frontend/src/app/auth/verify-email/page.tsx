/**
 * Verify Email Page
 *
 * Página para verificar email con token
 */

import { Metadata } from 'next';
import Link from 'next/link';
import { Card } from '@/components/shared/Card';
import { Logo } from '@/components/shared/Logo';
import { VerifyEmailForm } from '@/components/auth/VerifyEmailForm';

export const metadata: Metadata = {
  title: 'Verificar Email - ContaFlow',
  description: 'Verifica tu dirección de correo electrónico',
};

export default function VerifyEmailPage() {
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

        {/* Verify Email Card */}
        <Card className="shadow-xl">
          <div className="px-6 py-8">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-gray-900">
                Verificación de Email
              </h2>
              <p className="text-sm text-gray-600 mt-1">
                Estamos verificando tu correo electrónico
              </p>
            </div>

            <VerifyEmailForm />
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

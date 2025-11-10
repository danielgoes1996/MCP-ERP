/**
 * Login Page
 *
 * Página de inicio de sesión con LoginForm
 */

import { Metadata } from 'next';
import Link from 'next/link';
import { Card } from '@/components/shared/Card';
import { Logo } from '@/components/shared/Logo';
import { LoginForm } from '@/components/auth/LoginForm';

export const metadata: Metadata = {
  title: 'Iniciar Sesión - ContaFlow',
  description: 'Inicia sesión en tu cuenta de ContaFlow',
};

export default function LoginPage() {
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

        {/* Login Card */}
        <Card className="shadow-xl">
          <div className="px-6 py-8">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-gray-900">
                Bienvenido de vuelta
              </h2>
              <p className="text-sm text-gray-600 mt-1">
                Ingresa tus credenciales para acceder a tu cuenta
              </p>
            </div>

            <LoginForm />
          </div>
        </Card>

        {/* Additional Links */}
        <div className="mt-6 text-center text-sm text-gray-600">
          <p>
            ¿Necesitas ayuda?{' '}
            <Link
              href="/support"
              className="text-primary-500 hover:text-primary-600 font-medium"
            >
              Contacta soporte
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

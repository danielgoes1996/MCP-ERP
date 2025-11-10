/**
 * Register Page
 *
 * Página de registro con RegisterForm
 */

import { Metadata } from 'next';
import Link from 'next/link';
import { Card } from '@/components/shared/Card';
import { Logo } from '@/components/shared/Logo';
import { RegisterForm } from '@/components/auth/RegisterForm';

export const metadata: Metadata = {
  title: 'Crear Cuenta - ContaFlow',
  description: 'Crea tu cuenta de ContaFlow y comienza a gestionar tu contabilidad',
};

export default function RegisterPage() {
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

        {/* Register Card */}
        <Card className="shadow-xl">
          <div className="px-6 py-8">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-gray-900">
                Crea tu cuenta
              </h2>
              <p className="text-sm text-gray-600 mt-1">
                Comienza a gestionar tu contabilidad de forma inteligente
              </p>
            </div>

            <RegisterForm />
          </div>
        </Card>

        {/* Additional Info */}
        <div className="mt-6 text-center">
          <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-100">
            <p className="text-xs text-gray-600">
              Al crear una cuenta, obtienes acceso a:
            </p>
            <ul className="mt-2 text-xs text-gray-700 space-y-1">
              <li>✓ Conciliación bancaria automatizada</li>
              <li>✓ Detección inteligente de gastos</li>
              <li>✓ Sugerencias de IA para clasificación</li>
              <li>✓ Reportes financieros en tiempo real</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

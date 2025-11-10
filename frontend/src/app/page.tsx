/**
 * Home Page
 *
 * Landing page que redirige a login o dashboard según autenticación
 */

'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import Link from 'next/link';
import { Button } from '@/components/shared/Button';
import { Logo } from '@/components/shared/Logo';
import { ArrowRight, Sparkles, TrendingUp, Shield, Zap } from 'lucide-react';

export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuthStore();

  useEffect(() => {
    // Si está autenticado, redirigir a módulo de gastos
    if (isAuthenticated && !isLoading) {
      router.push('/expenses');
    }
  }, [isAuthenticated, isLoading, router]);

  // Mientras verifica autenticación
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-primary-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Cargando...</p>
        </div>
      </div>
    );
  }

  // Landing page para usuarios no autenticados
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-accent-50">
      {/* Header */}
      <header className="container mx-auto px-4 py-6">
        <nav className="flex items-center justify-between">
          <Link href="/">
            <Logo size="md" />
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/auth/login">
              <Button variant="ghost">Iniciar Sesión</Button>
            </Link>
            <Link href="/auth/register">
              <Button variant="primary">
                Comenzar Gratis <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
          </div>
        </nav>
      </header>

      {/* Hero Section */}
      <main className="container mx-auto px-4 py-20">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-primary-100 text-primary-700 px-4 py-2 rounded-full text-sm font-medium mb-6 animate-slideIn">
            <Sparkles className="w-4 h-4" />
            Impulsado por Inteligencia Artificial
          </div>

          <h2 className="text-5xl md:text-6xl font-bold text-gray-900 mb-6 animate-fadeIn">
            Gestión Contable
            <span className="text-primary-600 block mt-2">
              Inteligente y Automatizada
            </span>
          </h2>

          <p className="text-xl text-gray-600 mb-10 max-w-2xl mx-auto animate-fadeIn animation-delay-200">
            ContaFlow utiliza IA para automatizar tu contabilidad, detectar gastos,
            conciliar cuentas bancarias y generar reportes financieros en tiempo real.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16 animate-fadeIn animation-delay-300">
            <Link href="/auth/register">
              <Button variant="primary" size="lg">
                Crear Cuenta Gratis
                <ArrowRight className="w-5 h-5 ml-2" />
              </Button>
            </Link>
            <Link href="/demo">
              <Button variant="outline" size="lg">
                Ver Demo
              </Button>
            </Link>
          </div>

          {/* Features Grid */}
          <div className="grid md:grid-cols-3 gap-8 mt-20">
            <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100 animate-slideIn animation-delay-400">
              <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mb-4">
                <Sparkles className="w-6 h-6 text-primary-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                IA Inteligente
              </h3>
              <p className="text-gray-600 text-sm">
                Clasificación automática de gastos y sugerencias inteligentes
                basadas en tu historial.
              </p>
            </div>

            <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100 animate-slideIn animation-delay-500">
              <div className="w-12 h-12 bg-accent-100 rounded-lg flex items-center justify-center mb-4">
                <Zap className="w-6 h-6 text-accent-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Automatización Total
              </h3>
              <p className="text-gray-600 text-sm">
                Conciliación bancaria automática y detección de duplicados en
                segundos.
              </p>
            </div>

            <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100 animate-slideIn animation-delay-600">
              <div className="w-12 h-12 bg-success-100 rounded-lg flex items-center justify-center mb-4">
                <TrendingUp className="w-6 h-6 text-success-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Reportes en Tiempo Real
              </h3>
              <p className="text-gray-600 text-sm">
                Dashboard con métricas financieras actualizadas y análisis
                predictivo.
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="container mx-auto px-4 py-8 mt-20 border-t border-gray-200">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-gray-600 text-sm">
            © 2025 ContaFlow. Todos los derechos reservados.
          </p>
          <div className="flex gap-6 text-sm text-gray-600">
            <Link href="/terms" className="hover:text-primary-600">
              Términos
            </Link>
            <Link href="/privacy" className="hover:text-primary-600">
              Privacidad
            </Link>
            <Link href="/support" className="hover:text-primary-600">
              Soporte
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

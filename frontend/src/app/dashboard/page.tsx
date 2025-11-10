/**
 * Dashboard Page
 *
 * Página principal del dashboard protegida por autenticación
 */

'use client';

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { Header } from '@/components/layout/Header';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import { Button } from '@/components/shared/Button';
import { Card } from '@/components/shared/Card';
import {
  LayoutDashboard,
  TrendingUp,
  DollarSign,
  FileText,
  Sparkles,
} from 'lucide-react';

function DashboardContent() {
  const { user } = useAuthStore();

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        {/* Welcome Section */}
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-gray-900 mb-2">
            Bienvenido, {user?.full_name?.split(' ')[0] || user?.username}
          </h2>
          <p className="text-gray-600">
            Aquí está el resumen de tu actividad financiera
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <Card className="hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Ingresos del mes</p>
                <p className="text-2xl font-bold text-gray-900">$0.00</p>
                <p className="text-xs text-success-600 mt-1">+0% vs mes anterior</p>
              </div>
              <div className="w-12 h-12 bg-success-100 rounded-lg flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-success-600" />
              </div>
            </div>
          </Card>

          <Card className="hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Gastos del mes</p>
                <p className="text-2xl font-bold text-gray-900">$0.00</p>
                <p className="text-xs text-error-600 mt-1">+0% vs mes anterior</p>
              </div>
              <div className="w-12 h-12 bg-error-100 rounded-lg flex items-center justify-center">
                <DollarSign className="w-6 h-6 text-error-600" />
              </div>
            </div>
          </Card>

          <Card className="hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Facturas pendientes</p>
                <p className="text-2xl font-bold text-gray-900">0</p>
                <p className="text-xs text-gray-500 mt-1">0 vencidas</p>
              </div>
              <div className="w-12 h-12 bg-warning-100 rounded-lg flex items-center justify-center">
                <FileText className="w-6 h-6 text-warning-600" />
              </div>
            </div>
          </Card>

          <Card className="hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Balance actual</p>
                <p className="text-2xl font-bold text-gray-900">$0.00</p>
                <p className="text-xs text-primary-600 mt-1">Actualizado hoy</p>
              </div>
              <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center">
                <LayoutDashboard className="w-6 h-6 text-primary-600" />
              </div>
            </div>
          </Card>
        </div>

        {/* Quick Actions */}
        <div className="grid md:grid-cols-2 gap-6 mb-8">
          <Card
            title="Acciones rápidas"
            subtitle="Tareas comunes para gestionar tu contabilidad"
          >
            <div className="space-y-3">
              <Button variant="outline" fullWidth className="justify-start">
                <FileText className="w-5 h-5 mr-3" />
                Registrar nuevo gasto
              </Button>
              <Button variant="outline" fullWidth className="justify-start">
                <TrendingUp className="w-5 h-5 mr-3" />
                Ver reportes financieros
              </Button>
              <Button variant="outline" fullWidth className="justify-start">
                <DollarSign className="w-5 h-5 mr-3" />
                Conciliar cuentas bancarias
              </Button>
            </div>
          </Card>

          <Card
            title="Sugerencias de IA"
            subtitle="Recomendaciones personalizadas para ti"
          >
            <div className="space-y-3">
              <div className="flex items-start gap-3 p-3 bg-primary-50 rounded-lg">
                <Sparkles className="w-5 h-5 text-primary-600 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    Configura tu primera cuenta bancaria
                  </p>
                  <p className="text-xs text-gray-600 mt-1">
                    Conecta tu banco para comenzar la conciliación automática
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3 p-3 bg-accent-50 rounded-lg">
                <Sparkles className="w-5 h-5 text-accent-600 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    Completa tu perfil de empresa
                  </p>
                  <p className="text-xs text-gray-600 mt-1">
                    Agrega información de tu empresa para reportes personalizados
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3 p-3 bg-success-50 rounded-lg">
                <Sparkles className="w-5 h-5 text-success-600 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    Invita a tu equipo
                  </p>
                  <p className="text-xs text-gray-600 mt-1">
                    Colabora con tu equipo contable en tiempo real
                  </p>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Recent Activity */}
        <Card title="Actividad reciente" subtitle="Últimas transacciones y eventos">
          <div className="text-center py-12">
            <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-600 mb-2">No hay actividad reciente</p>
            <p className="text-sm text-gray-500 mb-4">
              Comienza registrando tu primera transacción
            </p>
            <Button variant="primary">
              Registrar transacción
            </Button>
          </div>
        </Card>
      </main>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}

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
  Loader2,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react';
import { useDashboardMetrics, useQuickStats } from '@/hooks/useDashboard';
import Link from 'next/link';

function DashboardContent() {
  const { user } = useAuthStore();
  const { data: metrics, isLoading: metricsLoading } = useDashboardMetrics();
  const { data: stats, isLoading: statsLoading } = useQuickStats();

  // Helper function to format currency
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('es-MX', {
      style: 'currency',
      currency: 'MXN',
    }).format(amount);
  };

  // Helper function to format percentage
  const formatPercent = (percent: number) => {
    const sign = percent >= 0 ? '+' : '';
    return `${sign}${percent.toFixed(1)}%`;
  };

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
          {/* Ingresos del mes */}
          <Card className="hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Ingresos del mes</p>
                {metricsLoading ? (
                  <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                ) : (
                  <>
                    <p className="text-2xl font-bold text-gray-900">
                      {formatCurrency(metrics?.monthly_income || 0)}
                    </p>
                    <div className="flex items-center gap-1 mt-1">
                      {(metrics?.income_change_percent || 0) >= 0 ? (
                        <ArrowUpRight className="w-3 h-3 text-success-600" />
                      ) : (
                        <ArrowDownRight className="w-3 h-3 text-error-600" />
                      )}
                      <p
                        className={`text-xs ${
                          (metrics?.income_change_percent || 0) >= 0
                            ? 'text-success-600'
                            : 'text-error-600'
                        }`}
                      >
                        {formatPercent(metrics?.income_change_percent || 0)} vs mes anterior
                      </p>
                    </div>
                  </>
                )}
              </div>
              <div className="w-12 h-12 bg-success-100 rounded-lg flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-success-600" />
              </div>
            </div>
          </Card>

          {/* Gastos del mes */}
          <Card className="hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Gastos del mes</p>
                {metricsLoading ? (
                  <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                ) : (
                  <>
                    <p className="text-2xl font-bold text-gray-900">
                      {formatCurrency(metrics?.monthly_expenses || 0)}
                    </p>
                    <div className="flex items-center gap-1 mt-1">
                      {(metrics?.expenses_change_percent || 0) >= 0 ? (
                        <ArrowUpRight className="w-3 h-3 text-error-600" />
                      ) : (
                        <ArrowDownRight className="w-3 h-3 text-success-600" />
                      )}
                      <p
                        className={`text-xs ${
                          (metrics?.expenses_change_percent || 0) >= 0
                            ? 'text-error-600'
                            : 'text-success-600'
                        }`}
                      >
                        {formatPercent(metrics?.expenses_change_percent || 0)} vs mes anterior
                      </p>
                    </div>
                  </>
                )}
              </div>
              <div className="w-12 h-12 bg-error-100 rounded-lg flex items-center justify-center">
                <DollarSign className="w-6 h-6 text-error-600" />
              </div>
            </div>
          </Card>

          {/* Facturas pendientes */}
          <Card className="hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Facturas pendientes</p>
                {metricsLoading ? (
                  <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                ) : (
                  <>
                    <p className="text-2xl font-bold text-gray-900">
                      {metrics?.pending_invoices || 0}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {metrics?.overdue_invoices || 0} vencidas
                    </p>
                  </>
                )}
              </div>
              <div className="w-12 h-12 bg-warning-100 rounded-lg flex items-center justify-center">
                <FileText className="w-6 h-6 text-warning-600" />
              </div>
            </div>
          </Card>

          {/* Balance actual */}
          <Card className="hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Balance actual</p>
                {metricsLoading ? (
                  <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                ) : (
                  <>
                    <p className="text-2xl font-bold text-gray-900">
                      {formatCurrency(metrics?.current_balance || 0)}
                    </p>
                    <p className="text-xs text-primary-600 mt-1">Actualizado hoy</p>
                  </>
                )}
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
              <Link href="/expenses" className="block">
                <Button variant="outline" fullWidth className="justify-start">
                  <FileText className="w-5 h-5 mr-3" />
                  Registrar nuevo gasto
                </Button>
              </Link>
              <Link href="/reports" className="block">
                <Button variant="outline" fullWidth className="justify-start">
                  <TrendingUp className="w-5 h-5 mr-3" />
                  Ver reportes financieros
                </Button>
              </Link>
              <Link href="/reconciliation" className="block">
                <Button variant="outline" fullWidth className="justify-start">
                  <DollarSign className="w-5 h-5 mr-3" />
                  Conciliar cuentas bancarias
                </Button>
              </Link>
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

        {/* Recent Activity - No data yet message for quick stats */}
        {!statsLoading && stats && (
          <div className="mb-8 grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card className="bg-gradient-to-br from-primary-50 to-primary-100 border-primary-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-primary-700 font-medium mb-1">
                    Promedio por gasto
                  </p>
                  <p className="text-2xl font-bold text-primary-900">
                    {formatCurrency(stats.average_expense)}
                  </p>
                </div>
                <TrendingUp className="w-8 h-8 text-primary-600" />
              </div>
            </Card>

            <Card className="bg-gradient-to-br from-accent-50 to-accent-100 border-accent-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-accent-700 font-medium mb-1">
                    Categoría más frecuente
                  </p>
                  <p className="text-lg font-bold text-accent-900">
                    {stats.most_frequent_category || '-'}
                  </p>
                </div>
                <FileText className="w-8 h-8 text-accent-600" />
              </div>
            </Card>

            <Card className="bg-gradient-to-br from-success-50 to-success-100 border-success-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-success-700 font-medium mb-1">
                    Ahorro vs presupuesto
                  </p>
                  <p className="text-2xl font-bold text-success-900">
                    {stats.budget_savings_percent.toFixed(1)}%
                  </p>
                </div>
                <DollarSign className="w-8 h-8 text-success-600" />
              </div>
            </Card>
          </div>
        )}

        {/* Recent Activity */}
        <Card title="Actividad reciente" subtitle="Últimas transacciones y eventos">
          <div className="text-center py-12">
            <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-600 mb-2">No hay actividad reciente</p>
            <p className="text-sm text-gray-500 mb-4">
              Comienza registrando tu primera transacción
            </p>
            <Link href="/expenses">
              <Button variant="primary">Registrar transacción</Button>
            </Link>
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

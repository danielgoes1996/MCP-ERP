/**
 * Dashboard Page - ContaFlow Enterprise Design System
 *
 * Main dashboard with overview statistics and quick actions
 */

'use client';

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { AppLayout } from '@/components/layout/AppLayout';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { StatCard } from '@/components/ui/StatCard';
import { PageHeader } from '@/components/ui/PageHeader';
import {
  FileText,
  Receipt,
  CreditCard,
  TrendingUp,
  AlertCircle,
  CheckCircle,
  Clock,
  DollarSign,
  Brain,
  Zap,
} from 'lucide-react';
import { cn } from '@/lib/utils/cn';

export default function DashboardPage() {
  // TODO: Replace with real data from API
  const stats = [
    {
      name: 'Gastos Pendientes',
      value: '24',
      change: '+12%',
      trend: 'up' as const,
      icon: FileText,
      color: 'text-[#11446e]',
      bgColor: 'bg-[#11446e]/5',
    },
    {
      name: 'Facturas Este Mes',
      value: '156',
      change: '+8%',
      trend: 'up' as const,
      icon: Receipt,
      color: 'text-[#60b97b]',
      bgColor: 'bg-[#60b97b]/10',
    },
    {
      name: 'Conciliaciones',
      value: '89%',
      change: '+5%',
      trend: 'up' as const,
      icon: CreditCard,
      color: 'text-[#11446e]',
      bgColor: 'bg-[#11446e]/5',
    },
    {
      name: 'Total Gastos',
      value: '$847,392',
      change: '-3%',
      trend: 'down' as const,
      icon: DollarSign,
      color: 'text-[#60b97b]',
      bgColor: 'bg-[#60b97b]/10',
    },
  ];

  const recentExpenses = [
    {
      id: 1,
      description: 'Compra de papelería',
      amount: '$1,250',
      status: 'pending',
      date: '2025-01-08',
    },
    {
      id: 2,
      description: 'Servicios de internet',
      amount: '$890',
      status: 'approved',
      date: '2025-01-07',
    },
    {
      id: 3,
      description: 'Mantenimiento vehículo',
      amount: '$3,500',
      status: 'rejected',
      date: '2025-01-06',
    },
  ];

  const aiInsights = [
    {
      type: 'classification',
      message: '12 gastos clasificados automáticamente hoy',
      icon: Brain,
      color: 'text-[#11446e]',
    },
    {
      type: 'automation',
      message: '3 portales sincronizados exitosamente',
      icon: Zap,
      color: 'text-[#60b97b]',
    },
    {
      type: 'reconciliation',
      message: '45 transacciones conciliadas con IA',
      icon: CheckCircle,
      color: 'text-[#60b97b]',
    },
  ];

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'approved':
        return 'bg-[#60b97b]/10 text-[#60b97b]';
      case 'rejected':
        return 'bg-red-50 text-red-600';
      case 'pending':
        return 'bg-amber-50 text-amber-600';
      default:
        return 'bg-gray-100 text-gray-700';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'approved':
        return 'Aprobado';
      case 'rejected':
        return 'Rechazado';
      case 'pending':
        return 'Pendiente';
      default:
        return status;
    }
  };

  return (
    <ProtectedRoute>
      <AppLayout>
        <div className="space-y-6">
          {/* Page Header */}
          <PageHeader
            title="Dashboard"
            subtitle="Bienvenido al sistema de gestión financiera"
          />

          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {stats.map((stat, index) => (
              <StatCard
                key={stat.name}
                name={stat.name}
                value={stat.value}
                change={stat.change}
                trend={stat.trend}
                icon={stat.icon}
                iconColor={stat.color}
                iconBgColor={stat.bgColor}
                delay={index * 0.1}
              />
            ))}
          </div>

          {/* Main Content Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Recent Expenses */}
            <Card title="Gastos Recientes" className="lg:col-span-2">
              <div className="space-y-4">
                {recentExpenses.map((expense) => (
                  <div
                    key={expense.id}
                    className="flex items-center justify-between p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex items-center space-x-4">
                      <div className="p-2 bg-white rounded-xl border border-gray-100">
                        <FileText className="w-5 h-5 text-[#11446e]" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">
                          {expense.description}
                        </p>
                        <p className="text-sm text-gray-500">{expense.date}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-bold text-gray-900">{expense.amount}</p>
                      <span
                        className={cn(
                          'text-xs font-medium px-2 py-1 rounded-full',
                          getStatusColor(expense.status)
                        )}
                      >
                        {getStatusText(expense.status)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4">
                <Button variant="outline" fullWidth>
                  Ver Todos los Gastos
                </Button>
              </div>
            </Card>

            {/* AI Insights */}
            <Card title="Insights IA">
              <div className="space-y-4">
                {aiInsights.map((insight, index) => (
                  <div
                    key={index}
                    className="flex items-start space-x-3 p-3 bg-gray-50 rounded-xl"
                  >
                    <div className="p-2 bg-white rounded-xl border border-gray-100">
                      <insight.icon className={cn('w-5 h-5', insight.color)} />
                    </div>
                    <p className="text-sm text-gray-700 mt-1">
                      {insight.message}
                    </p>
                  </div>
                ))}
              </div>
              <div className="mt-4">
                <Button variant="secondary" fullWidth>
                  Ver Dashboard IA
                </Button>
              </div>
            </Card>
          </div>

          {/* Quick Actions */}
          <Card title="Acciones Rápidas">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <Button variant="primary" className="justify-center">
                <FileText className="w-5 h-5 mr-2" />
                Nuevo Gasto
              </Button>
              <Button variant="secondary" className="justify-center">
                <Receipt className="w-5 h-5 mr-2" />
                Subir Factura
              </Button>
              <Button variant="outline" className="justify-center">
                <CreditCard className="w-5 h-5 mr-2" />
                Conciliación
              </Button>
              <Button variant="outline" className="justify-center">
                <TrendingUp className="w-5 h-5 mr-2" />
                Ver Reportes
              </Button>
            </div>
          </Card>
        </div>
      </AppLayout>
    </ProtectedRoute>
  );
}

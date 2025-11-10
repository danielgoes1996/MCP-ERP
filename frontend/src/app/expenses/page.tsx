/**
 * Expenses Module Page
 *
 * Módulo principal de gestión de gastos
 */

'use client';

import { useState } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { Header } from '@/components/layout/Header';
import { Card } from '@/components/shared/Card';
import { Button } from '@/components/shared/Button';
import {
  Plus,
  Search,
  Filter,
  Download,
  Upload,
  Calendar,
  DollarSign,
  FileText,
  TrendingUp,
  TrendingDown,
  Clock,
  CheckCircle2,
  AlertCircle,
  ChevronRight,
  Eye,
  Edit,
  Trash2,
} from 'lucide-react';

function ExpensesContent() {
  const [searchQuery, setSearchQuery] = useState('');

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-primary-50/10">
      <Header />

      <main className="container mx-auto px-4 py-8">
        {/* Header Section */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">
                Gestión de Gastos
              </h1>
              <p className="text-gray-600">
                Administra y controla todos tus gastos empresariales
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="outline" className="gap-2">
                <Upload className="w-4 h-4" />
                Importar
              </Button>
              <Button variant="outline" className="gap-2">
                <Download className="w-4 h-4" />
                Exportar
              </Button>
              <Button variant="primary" className="gap-2">
                <Plus className="w-5 h-5" />
                Nuevo Gasto
              </Button>
            </div>
          </div>
        </div>

        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <Card className="border-l-4 border-l-primary-500 hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Total del mes</p>
                <p className="text-2xl font-bold text-gray-900">$0.00</p>
                <div className="flex items-center gap-1 mt-1">
                  <TrendingUp className="w-3 h-3 text-success-600" />
                  <p className="text-xs text-success-600">+0% vs mes anterior</p>
                </div>
              </div>
              <div className="w-12 h-12 bg-primary-100 rounded-xl flex items-center justify-center">
                <DollarSign className="w-6 h-6 text-primary-600" />
              </div>
            </div>
          </Card>

          <Card className="border-l-4 border-l-warning-500 hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Pendientes</p>
                <p className="text-2xl font-bold text-gray-900">0</p>
                <p className="text-xs text-gray-500 mt-1">Por revisar</p>
              </div>
              <div className="w-12 h-12 bg-warning-100 rounded-xl flex items-center justify-center">
                <Clock className="w-6 h-6 text-warning-600" />
              </div>
            </div>
          </Card>

          <Card className="border-l-4 border-l-success-500 hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Aprobados</p>
                <p className="text-2xl font-bold text-gray-900">0</p>
                <p className="text-xs text-gray-500 mt-1">Este mes</p>
              </div>
              <div className="w-12 h-12 bg-success-100 rounded-xl flex items-center justify-center">
                <CheckCircle2 className="w-6 h-6 text-success-600" />
              </div>
            </div>
          </Card>

          <Card className="border-l-4 border-l-error-500 hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Rechazados</p>
                <p className="text-2xl font-bold text-gray-900">0</p>
                <p className="text-xs text-gray-500 mt-1">Requieren corrección</p>
              </div>
              <div className="w-12 h-12 bg-error-100 rounded-xl flex items-center justify-center">
                <AlertCircle className="w-6 h-6 text-error-600" />
              </div>
            </div>
          </Card>
        </div>

        {/* Filters and Search */}
        <Card className="mb-6">
          <div className="flex flex-col lg:flex-row gap-4">
            {/* Search */}
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Buscar por proveedor, concepto, monto..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
              />
            </div>

            {/* Filters */}
            <div className="flex gap-3">
              <Button variant="outline" className="gap-2">
                <Calendar className="w-4 h-4" />
                Fecha
              </Button>
              <Button variant="outline" className="gap-2">
                <Filter className="w-4 h-4" />
                Filtros
              </Button>
            </div>
          </div>
        </Card>

        {/* Expenses Table */}
        <Card className="p-0 overflow-hidden">
          {/* Table Header */}
          <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
            <div className="grid grid-cols-12 gap-4 text-sm font-semibold text-gray-700">
              <div className="col-span-1">Estado</div>
              <div className="col-span-2">Fecha</div>
              <div className="col-span-3">Proveedor / Concepto</div>
              <div className="col-span-2">Categoría</div>
              <div className="col-span-2 text-right">Monto</div>
              <div className="col-span-2 text-right">Acciones</div>
            </div>
          </div>

          {/* Table Body - Empty State */}
          <div className="p-12 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-gray-100 rounded-full mb-4">
              <FileText className="w-8 h-8 text-gray-400" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              No hay gastos registrados
            </h3>
            <p className="text-gray-600 mb-6">
              Comienza registrando tu primer gasto o importa desde un archivo
            </p>
            <div className="flex items-center justify-center gap-3">
              <Button variant="outline" className="gap-2">
                <Upload className="w-4 h-4" />
                Importar gastos
              </Button>
              <Button variant="primary" className="gap-2">
                <Plus className="w-5 h-5" />
                Registrar primer gasto
              </Button>
            </div>
          </div>

          {/* Example of how rows would look (commented for now) */}
          {/* <div className="divide-y divide-gray-200">
            <div className="px-6 py-4 hover:bg-gray-50 transition-colors">
              <div className="grid grid-cols-12 gap-4 items-center">
                <div className="col-span-1">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-warning-100 text-warning-800">
                    Pendiente
                  </span>
                </div>
                <div className="col-span-2 text-sm text-gray-900">
                  05 Nov 2025
                </div>
                <div className="col-span-3">
                  <p className="text-sm font-medium text-gray-900">Amazon Web Services</p>
                  <p className="text-xs text-gray-500">Servicios de hosting</p>
                </div>
                <div className="col-span-2 text-sm text-gray-600">
                  Tecnología
                </div>
                <div className="col-span-2 text-sm font-semibold text-gray-900 text-right">
                  $1,234.56
                </div>
                <div className="col-span-2 flex items-center justify-end gap-2">
                  <button className="p-2 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors">
                    <Eye className="w-4 h-4" />
                  </button>
                  <button className="p-2 text-gray-400 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors">
                    <Edit className="w-4 h-4" />
                  </button>
                  <button className="p-2 text-gray-400 hover:text-error-600 hover:bg-error-50 rounded-lg transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          </div> */}
        </Card>

        {/* Quick Stats Footer */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="bg-gradient-to-br from-primary-50 to-primary-100 border-primary-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-primary-700 font-medium mb-1">
                  Promedio por gasto
                </p>
                <p className="text-2xl font-bold text-primary-900">$0.00</p>
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
                <p className="text-lg font-bold text-accent-900">-</p>
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
                <p className="text-2xl font-bold text-success-900">0%</p>
              </div>
              <TrendingDown className="w-8 h-8 text-success-600" />
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}

export default function ExpensesPage() {
  return (
    <ProtectedRoute>
      <ExpensesContent />
    </ProtectedRoute>
  );
}

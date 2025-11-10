/**
 * Invoice Classifier Page
 *
 * Página principal del clasificador de facturas con IA
 */

'use client';

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { Header } from '@/components/layout/Header';
import { Card } from '@/components/shared/Card';
import { Button } from '@/components/shared/Button';
import {
  Upload,
  FileText,
  Sparkles,
  CheckCircle2,
  Clock,
  AlertCircle,
  TrendingUp,
  Zap,
  Brain,
  FileCheck,
} from 'lucide-react';

function InvoiceClassifierContent() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-primary-50/20">
      <Header />

      <main className="container mx-auto px-4 py-8">
        {/* Hero Section */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-3 bg-gradient-to-br from-primary-500 to-accent-500 rounded-xl">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                Clasificador de Facturas
              </h1>
              <p className="text-gray-600 mt-1">
                Clasifica automáticamente tus facturas con inteligencia artificial
              </p>
            </div>
          </div>

          {/* Beta Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-accent-100 text-accent-700 rounded-lg">
            <Zap className="w-4 h-4" />
            <span className="text-sm font-semibold">Versión Beta</span>
            <span className="text-xs">Powered by IA</span>
          </div>
        </div>

        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <Card className="border-l-4 border-l-success-500">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Clasificadas</p>
                <p className="text-2xl font-bold text-gray-900">0</p>
              </div>
              <div className="w-12 h-12 bg-success-100 rounded-lg flex items-center justify-center">
                <CheckCircle2 className="w-6 h-6 text-success-600" />
              </div>
            </div>
          </Card>

          <Card className="border-l-4 border-l-warning-500">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Pendientes</p>
                <p className="text-2xl font-bold text-gray-900">0</p>
              </div>
              <div className="w-12 h-12 bg-warning-100 rounded-lg flex items-center justify-center">
                <Clock className="w-6 h-6 text-warning-600" />
              </div>
            </div>
          </Card>

          <Card className="border-l-4 border-l-error-500">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Requieren revisión</p>
                <p className="text-2xl font-bold text-gray-900">0</p>
              </div>
              <div className="w-12 h-12 bg-error-100 rounded-lg flex items-center justify-center">
                <AlertCircle className="w-6 h-6 text-error-600" />
              </div>
            </div>
          </Card>

          <Card className="border-l-4 border-l-primary-500">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Precisión IA</p>
                <p className="text-2xl font-bold text-gray-900">98.5%</p>
              </div>
              <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-primary-600" />
              </div>
            </div>
          </Card>
        </div>

        <div className="grid lg:grid-cols-3 gap-8">
          {/* Main Upload Area */}
          <div className="lg:col-span-2">
            <Card className="p-0 overflow-hidden">
              {/* Upload Zone */}
              <div className="p-8 bg-gradient-to-br from-primary-50 to-accent-50">
                <div className="border-2 border-dashed border-primary-300 rounded-xl p-12 bg-white/50 backdrop-blur-sm hover:border-primary-500 transition-all duration-200 cursor-pointer group">
                  <div className="text-center">
                    <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-primary-500 to-accent-500 rounded-2xl mb-4 group-hover:scale-110 transition-transform">
                      <Upload className="w-8 h-8 text-white" />
                    </div>
                    <h3 className="text-xl font-semibold text-gray-900 mb-2">
                      Arrastra tus facturas aquí
                    </h3>
                    <p className="text-gray-600 mb-4">
                      o haz clic para seleccionar archivos
                    </p>
                    <p className="text-sm text-gray-500 mb-6">
                      Soportamos PDF, XML, JPG, PNG hasta 10MB
                    </p>
                    <Button variant="primary" size="lg" className="gap-2">
                      <Upload className="w-5 h-5" />
                      Seleccionar archivos
                    </Button>
                  </div>
                </div>
              </div>

              {/* How it works */}
              <div className="p-8 border-t border-gray-100">
                <h4 className="text-lg font-semibold text-gray-900 mb-6 flex items-center gap-2">
                  <Brain className="w-5 h-5 text-primary-600" />
                  ¿Cómo funciona la clasificación automática?
                </h4>
                <div className="grid md:grid-cols-3 gap-6">
                  <div className="text-center">
                    <div className="w-12 h-12 bg-primary-100 text-primary-600 rounded-full flex items-center justify-center mx-auto mb-3 font-bold">
                      1
                    </div>
                    <h5 className="font-medium text-gray-900 mb-2">Sube tu factura</h5>
                    <p className="text-sm text-gray-600">
                      Arrastra o selecciona tu archivo PDF o XML
                    </p>
                  </div>
                  <div className="text-center">
                    <div className="w-12 h-12 bg-accent-100 text-accent-600 rounded-full flex items-center justify-center mx-auto mb-3 font-bold">
                      2
                    </div>
                    <h5 className="font-medium text-gray-900 mb-2">IA analiza</h5>
                    <p className="text-sm text-gray-600">
                      Nuestra IA extrae y clasifica automáticamente
                    </p>
                  </div>
                  <div className="text-center">
                    <div className="w-12 h-12 bg-success-100 text-success-600 rounded-full flex items-center justify-center mx-auto mb-3 font-bold">
                      3
                    </div>
                    <h5 className="font-medium text-gray-900 mb-2">Revisa y confirma</h5>
                    <p className="text-sm text-gray-600">
                      Verifica la clasificación y guarda en tu sistema
                    </p>
                  </div>
                </div>
              </div>
            </Card>

            {/* Recent Invoices */}
            <Card title="Facturas recientes" subtitle="Últimas facturas procesadas" className="mt-6">
              <div className="text-center py-12">
                <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-600 mb-2">No hay facturas procesadas aún</p>
                <p className="text-sm text-gray-500">
                  Sube tu primera factura para comenzar
                </p>
              </div>
            </Card>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* AI Features */}
            <Card
              title="Características IA"
              subtitle="Potenciado por inteligencia artificial"
            >
              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-primary-100 rounded-lg mt-0.5">
                    <Sparkles className="w-4 h-4 text-primary-600" />
                  </div>
                  <div>
                    <h5 className="font-medium text-gray-900 text-sm mb-1">
                      Clasificación inteligente
                    </h5>
                    <p className="text-xs text-gray-600">
                      Detecta automáticamente el tipo de gasto y categoría
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <div className="p-2 bg-accent-100 rounded-lg mt-0.5">
                    <FileCheck className="w-4 h-4 text-accent-600" />
                  </div>
                  <div>
                    <h5 className="font-medium text-gray-900 text-sm mb-1">
                      Extracción de datos
                    </h5>
                    <p className="text-xs text-gray-600">
                      Extrae fecha, monto, proveedor y más automáticamente
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <div className="p-2 bg-success-100 rounded-lg mt-0.5">
                    <Brain className="w-4 h-4 text-success-600" />
                  </div>
                  <div>
                    <h5 className="font-medium text-gray-900 text-sm mb-1">
                      Aprendizaje continuo
                    </h5>
                    <p className="text-xs text-gray-600">
                      Mejora con cada factura que procesas
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <div className="p-2 bg-warning-100 rounded-lg mt-0.5">
                    <Zap className="w-4 h-4 text-warning-600" />
                  </div>
                  <div>
                    <h5 className="font-medium text-gray-900 text-sm mb-1">
                      Procesamiento rápido
                    </h5>
                    <p className="text-xs text-gray-600">
                      Clasifica en segundos lo que tomaría horas
                    </p>
                  </div>
                </div>
              </div>
            </Card>

            {/* Quick Stats */}
            <Card title="Estadísticas del mes">
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm text-gray-600">Facturas procesadas</span>
                    <span className="text-sm font-semibold text-gray-900">0 / 100</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div className="bg-primary-500 h-2 rounded-full" style={{ width: '0%' }} />
                  </div>
                </div>

                <div className="pt-4 border-t border-gray-100">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-xs text-gray-600">Tiempo ahorrado</span>
                    <span className="text-xs font-semibold text-success-600">0 horas</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-600">Precisión promedio</span>
                    <span className="text-xs font-semibold text-primary-600">98.5%</span>
                  </div>
                </div>
              </div>
            </Card>

            {/* Help Card */}
            <Card className="bg-gradient-to-br from-primary-50 to-accent-50 border-primary-200">
              <div className="text-center">
                <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center mx-auto mb-3">
                  <Sparkles className="w-6 h-6 text-primary-600" />
                </div>
                <h4 className="font-semibold text-gray-900 mb-2">¿Necesitas ayuda?</h4>
                <p className="text-sm text-gray-600 mb-4">
                  Consulta nuestra guía o contacta a soporte
                </p>
                <Button variant="outline" size="sm" fullWidth>
                  Ver guía rápida
                </Button>
              </div>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}

export default function InvoiceClassifierPage() {
  return (
    <ProtectedRoute>
      <InvoiceClassifierContent />
    </ProtectedRoute>
  );
}

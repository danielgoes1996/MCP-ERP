/**
 * Bank Reconciliation Dashboard
 *
 * Shows reconciliation status, suggestions, and allows managing bank statements
 */

'use client';

import { useState, useEffect } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { AppLayout } from '@/components/layout/AppLayout';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import {
  Upload,
  FileText,
  CheckCircle,
  XCircle,
  AlertCircle,
  TrendingUp,
  DollarSign,
  Link as LinkIcon,
  Calendar,
  Building,
} from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import Link from 'next/link';

interface ReconciliationStats {
  totalInvoices: number;
  reconciledInvoices: number;
  pendingInvoices: number;
  totalAmount: number;
  reconciledAmount: number;
  pendingAmount: number;
  reconciliationRate: number;
}

interface ReconciliationSuggestion {
  id: string;
  invoiceId: number;
  bankTransactionId: number;
  invoiceData: {
    uuid: string;
    emisor: string;
    total: number;
    fecha: string;
  };
  bankData: {
    description: string;
    amount: number;
    date: string;
  };
  confidenceScore: number;
  matchMethod: string;
}

export default function ReconciliationPage() {
  const [stats, setStats] = useState<ReconciliationStats | null>(null);
  const [suggestions, setSuggestions] = useState<ReconciliationSuggestion[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchReconciliationData();
  }, []);

  const fetchReconciliationData = async () => {
    try {
      setLoading(true);

      // Fetch stats
      const statsResponse = await fetch('http://localhost:8001/ai-reconciliation/stats', {
        headers: { 'Content-Type': 'application/json' },
      });

      if (statsResponse.ok) {
        const statsData = await statsResponse.json();
        setStats(statsData);
      }

      // Fetch suggestions
      const suggestionsResponse = await fetch('http://localhost:8001/ai-reconciliation/suggestions', {
        headers: { 'Content-Type': 'application/json' },
      });

      if (suggestionsResponse.ok) {
        const suggestionsData = await suggestionsResponse.json();
        setSuggestions(suggestionsData.suggestions || []);
      }
    } catch (error) {
      console.error('Error fetching reconciliation data:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('es-MX', {
      style: 'currency',
      currency: 'MXN',
    }).format(amount);
  };

  const getConfidenceBadge = (confidence: number) => {
    if (confidence >= 85) {
      return <span className="px-2 py-1 bg-[#60b97b]/10 text-[#60b97b] text-xs font-semibold rounded-full">Alta {confidence}%</span>;
    } else if (confidence >= 60) {
      return <span className="px-2 py-1 bg-yellow-100 text-yellow-700 text-xs font-semibold rounded-full">Media {confidence}%</span>;
    } else {
      return <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs font-semibold rounded-full">Baja {confidence}%</span>;
    }
  };

  return (
    <ProtectedRoute>
      <AppLayout>
        <div className="space-y-6">
          {/* Header */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-3xl font-bold text-[#11446e]">Conciliación Bancaria</h1>
              <p className="text-gray-600 mt-1">
                Gestiona estados de cuenta y concilia facturas con transacciones bancarias
              </p>
            </div>
            <div className="flex gap-3">
              <Link href="/invoices/upload">
                <Button variant="outline">
                  <FileText className="w-4 h-4 mr-2" />
                  Subir Facturas
                </Button>
              </Link>
              <Link href="/reconciliation/upload">
                <Button className="bg-[#11446e] hover:bg-[#11446e]/90">
                  <Upload className="w-4 h-4 mr-2" />
                  Subir Estado de Cuenta
                </Button>
              </Link>
            </div>
          </div>

          {/* Stats Cards */}
          {stats && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card className="p-6 bg-gradient-to-br from-[#60b97b]/10 to-white border-2 border-[#60b97b]/20">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-gray-600">Facturas Conciliadas</h3>
                  <CheckCircle className="w-5 h-5 text-[#60b97b]" />
                </div>
                <div className="space-y-2">
                  <p className="text-3xl font-bold text-[#60b97b]">{stats.reconciledInvoices}</p>
                  <p className="text-sm text-gray-600">{formatCurrency(stats.reconciledAmount)}</p>
                  <div className="flex items-center gap-2 text-sm">
                    <TrendingUp className="w-4 h-4 text-[#60b97b]" />
                    <span className="text-[#60b97b] font-semibold">{stats.reconciliationRate.toFixed(1)}% conciliado</span>
                  </div>
                </div>
              </Card>

              <Card className="p-6 bg-gradient-to-br from-yellow-50 to-white border-2 border-yellow-200">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-gray-600">Pendientes de Conciliar</h3>
                  <AlertCircle className="w-5 h-5 text-yellow-600" />
                </div>
                <div className="space-y-2">
                  <p className="text-3xl font-bold text-yellow-700">{stats.pendingInvoices}</p>
                  <p className="text-sm text-gray-600">{formatCurrency(stats.pendingAmount)}</p>
                  <div className="flex items-center gap-2 text-sm">
                    <AlertCircle className="w-4 h-4 text-yellow-600" />
                    <span className="text-yellow-700 font-semibold">{((stats.pendingInvoices / stats.totalInvoices) * 100).toFixed(1)}% pendiente</span>
                  </div>
                </div>
              </Card>

              <Card className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-gray-600">Total de Facturas</h3>
                  <DollarSign className="w-5 h-5 text-[#11446e]" />
                </div>
                <div className="space-y-2">
                  <p className="text-3xl font-bold text-[#11446e]">{stats.totalInvoices}</p>
                  <p className="text-sm text-gray-600">{formatCurrency(stats.totalAmount)}</p>
                  <div className="w-full bg-gray-200 rounded-full h-2 mt-3">
                    <div
                      className="bg-[#60b97b] h-2 rounded-full transition-all"
                      style={{ width: `${stats.reconciliationRate}%` }}
                    ></div>
                  </div>
                </div>
              </Card>
            </div>
          )}

          {/* AI Suggestions */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-xl font-bold text-[#11446e]">Sugerencias de Conciliación (IA)</h2>
                <p className="text-sm text-gray-600 mt-1">
                  Sugerencias automáticas basadas en montos, fechas y descripciones
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={fetchReconciliationData}
              >
                Actualizar
              </Button>
            </div>

            {loading ? (
              <div className="text-center py-12 text-gray-500">
                Cargando sugerencias...
              </div>
            ) : suggestions.length === 0 ? (
              <div className="text-center py-12">
                <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                <p className="text-gray-600 font-medium">No hay sugerencias disponibles</p>
                <p className="text-sm text-gray-500 mt-1">
                  Sube un estado de cuenta para generar sugerencias automáticas
                </p>
                <Link href="/reconciliation/upload">
                  <Button className="mt-4 bg-[#11446e]">
                    <Upload className="w-4 h-4 mr-2" />
                    Subir Estado de Cuenta
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="space-y-3">
                {suggestions.map((suggestion) => (
                  <Card key={suggestion.id} className="p-4 hover:shadow-md transition-shadow border-l-4 border-l-[#60b97b]">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 grid grid-cols-2 gap-6">
                        {/* Invoice Side */}
                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <FileText className="w-4 h-4 text-[#11446e]" />
                            <h4 className="font-semibold text-[#11446e]">Factura</h4>
                          </div>
                          <div className="space-y-1 text-sm">
                            <p><span className="text-gray-500">Emisor:</span> <span className="font-medium">{suggestion.invoiceData.emisor}</span></p>
                            <p><span className="text-gray-500">UUID:</span> <span className="font-mono text-xs">{suggestion.invoiceData.uuid.substring(0, 16)}...</span></p>
                            <p><span className="text-gray-500">Monto:</span> <span className="font-semibold text-[#60b97b]">{formatCurrency(suggestion.invoiceData.total)}</span></p>
                            <p><span className="text-gray-500">Fecha:</span> {suggestion.invoiceData.fecha}</p>
                          </div>
                        </div>

                        {/* Bank Side */}
                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <Building className="w-4 h-4 text-[#11446e]" />
                            <h4 className="font-semibold text-[#11446e]">Transacción Bancaria</h4>
                          </div>
                          <div className="space-y-1 text-sm">
                            <p><span className="text-gray-500">Descripción:</span> <span className="font-medium">{suggestion.bankData.description}</span></p>
                            <p><span className="text-gray-500">Monto:</span> <span className="font-semibold text-red-600">{formatCurrency(Math.abs(suggestion.bankData.amount))}</span></p>
                            <p><span className="text-gray-500">Fecha:</span> {suggestion.bankData.date}</p>
                          </div>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="ml-6 flex flex-col items-end gap-3">
                        {getConfidenceBadge(suggestion.confidenceScore)}
                        <Button size="sm" className="bg-[#60b97b]">
                          <LinkIcon className="w-4 h-4 mr-2" />
                          Conciliar
                        </Button>
                      </div>
                    </div>
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <p className="text-xs text-gray-500">
                        <span className="font-medium">Método:</span> {suggestion.matchMethod}
                      </p>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </Card>

          {/* Quick Actions */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link href="/invoices">
              <Card className="p-6 hover:shadow-lg transition-shadow cursor-pointer h-full">
                <FileText className="w-10 h-10 text-[#11446e] mb-3" />
                <h3 className="font-bold text-[#11446e] mb-2">Ver Facturas</h3>
                <p className="text-sm text-gray-600">
                  Revisa todas las facturas procesadas y su estado SAT
                </p>
              </Card>
            </Link>

            <Link href="/reconciliation/upload">
              <Card className="p-6 hover:shadow-lg transition-shadow cursor-pointer h-full bg-gradient-to-br from-[#11446e]/5 to-white">
                <Upload className="w-10 h-10 text-[#11446e] mb-3" />
                <h3 className="font-bold text-[#11446e] mb-2">Subir Estado de Cuenta</h3>
                <p className="text-sm text-gray-600">
                  Sube archivos PDF, Excel o CSV de tu banco
                </p>
              </Card>
            </Link>

            <Link href="/reconciliation/history">
              <Card className="p-6 hover:shadow-lg transition-shadow cursor-pointer h-full">
                <Calendar className="w-10 h-10 text-[#11446e] mb-3" />
                <h3 className="font-bold text-[#11446e] mb-2">Historial de Conciliación</h3>
                <p className="text-sm text-gray-600">
                  Revisa todas las conciliaciones realizadas
                </p>
              </Card>
            </Link>
          </div>
        </div>
      </AppLayout>
    </ProtectedRoute>
  );
}

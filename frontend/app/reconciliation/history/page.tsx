/**
 * Reconciliation History Page
 *
 * Shows past reconciliations with matched invoice-bank transaction pairs
 */

'use client';

import { useState, useEffect } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { AppLayout } from '@/components/layout/AppLayout';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import {
  ArrowLeft,
  CheckCircle,
  FileText,
  Building,
  Calendar,
  Link as LinkIcon,
  Filter,
  Search,
} from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import Link from 'next/link';

interface ReconciliationRecord {
  id: number;
  invoice: {
    id: number;
    uuid: string;
    emisor: string;
    total: number;
    fecha: string;
  };
  bankTransaction: {
    id: number;
    description: string;
    amount: number;
    date: string;
  };
  matchConfidence: number;
  matchMethod: string;
  reconciledAt: string;
  reconciledBy: 'auto' | 'manual';
}

export default function ReconciliationHistoryPage() {
  const [records, setRecords] = useState<ReconciliationRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState<'all' | 'auto' | 'manual'>('all');
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchReconciliationHistory();
  }, []);

  const fetchReconciliationHistory = async () => {
    try {
      setLoading(true);
      // TODO: Implement actual API endpoint
      // const response = await fetch('http://localhost:8001/ai-reconciliation/history');
      // const data = await response.json();
      // setRecords(data.records || []);

      // Mock data for now
      setRecords([]);
    } catch (error) {
      console.error('Error fetching reconciliation history:', error);
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

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('es-MX', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
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

  const filteredRecords = records.filter(record => {
    const matchesFilter = filterType === 'all' || record.reconciledBy === filterType;
    const matchesSearch = !searchTerm ||
      record.invoice.emisor.toLowerCase().includes(searchTerm.toLowerCase()) ||
      record.bankTransaction.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      record.invoice.uuid.toLowerCase().includes(searchTerm.toLowerCase());

    return matchesFilter && matchesSearch;
  });

  return (
    <ProtectedRoute>
      <AppLayout>
        <div className="space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/reconciliation">
                <Button variant="outline" size="sm">
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Regresar
                </Button>
              </Link>
              <div>
                <h1 className="text-3xl font-bold text-[#11446e]">Historial de Conciliación</h1>
                <p className="text-gray-600 mt-1">
                  Revisa todas las conciliaciones realizadas entre facturas y transacciones bancarias
                </p>
              </div>
            </div>
          </div>

          {/* Filters and Search */}
          <Card className="p-4">
            <div className="flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
              <div className="flex gap-3">
                <Button
                  variant={filterType === 'all' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setFilterType('all')}
                  className={filterType === 'all' ? 'bg-[#11446e]' : ''}
                >
                  Todas
                </Button>
                <Button
                  variant={filterType === 'auto' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setFilterType('auto')}
                  className={filterType === 'auto' ? 'bg-[#60b97b]' : ''}
                >
                  Automáticas
                </Button>
                <Button
                  variant={filterType === 'manual' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setFilterType('manual')}
                  className={filterType === 'manual' ? 'bg-[#11446e]' : ''}
                >
                  Manuales
                </Button>
              </div>

              <div className="relative w-full md:w-64">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Buscar por emisor, UUID..."
                  className="w-full pl-10 pr-4 py-2 border-2 border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#60b97b]/20 focus:border-[#60b97b]"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </div>
          </Card>

          {/* Summary Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="p-6 bg-gradient-to-br from-[#60b97b]/10 to-white border-2 border-[#60b97b]/20">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-gray-600">Total Conciliadas</h3>
                <CheckCircle className="w-5 h-5 text-[#60b97b]" />
              </div>
              <p className="text-3xl font-bold text-[#60b97b]">{records.length}</p>
            </Card>

            <Card className="p-6 bg-gradient-to-br from-[#11446e]/10 to-white border-2 border-[#11446e]/20">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-gray-600">Automáticas</h3>
                <LinkIcon className="w-5 h-5 text-[#11446e]" />
              </div>
              <p className="text-3xl font-bold text-[#11446e]">
                {records.filter(r => r.reconciledBy === 'auto').length}
              </p>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-gray-600">Manuales</h3>
                <LinkIcon className="w-5 h-5 text-gray-600" />
              </div>
              <p className="text-3xl font-bold text-gray-700">
                {records.filter(r => r.reconciledBy === 'manual').length}
              </p>
            </Card>
          </div>

          {/* Records List */}
          <Card className="p-6">
            {loading ? (
              <div className="text-center py-12 text-gray-500">
                Cargando historial...
              </div>
            ) : filteredRecords.length === 0 ? (
              <div className="text-center py-12">
                <CheckCircle className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                <p className="text-gray-600 font-medium">No hay conciliaciones registradas</p>
                <p className="text-sm text-gray-500 mt-1">
                  Las conciliaciones automáticas y manuales aparecerán aquí
                </p>
                <Link href="/reconciliation">
                  <Button className="mt-4 bg-[#11446e]">
                    Ir a Conciliación
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredRecords.map((record) => (
                  <Card key={record.id} className="p-4 hover:shadow-md transition-shadow border-l-4 border-l-[#60b97b]">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <CheckCircle className="w-5 h-5 text-[#60b97b]" />
                        <span className="text-sm text-gray-500">
                          Conciliado {formatDate(record.reconciledAt)}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {getConfidenceBadge(record.matchConfidence)}
                        <span className={cn(
                          'px-3 py-1 rounded-full text-xs font-semibold',
                          record.reconciledBy === 'auto'
                            ? 'bg-[#60b97b]/10 text-[#60b97b]'
                            : 'bg-[#11446e]/10 text-[#11446e]'
                        )}>
                          {record.reconciledBy === 'auto' ? 'Automática' : 'Manual'}
                        </span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-6">
                      {/* Invoice Side */}
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <FileText className="w-4 h-4 text-[#11446e]" />
                          <h4 className="font-semibold text-[#11446e]">Factura</h4>
                        </div>
                        <div className="space-y-1 text-sm">
                          <p><span className="text-gray-500">Emisor:</span> <span className="font-medium">{record.invoice.emisor}</span></p>
                          <p><span className="text-gray-500">UUID:</span> <span className="font-mono text-xs">{record.invoice.uuid.substring(0, 16)}...</span></p>
                          <p><span className="text-gray-500">Monto:</span> <span className="font-semibold text-[#60b97b]">{formatCurrency(record.invoice.total)}</span></p>
                          <p><span className="text-gray-500">Fecha:</span> {formatDate(record.invoice.fecha)}</p>
                        </div>
                      </div>

                      {/* Bank Side */}
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <Building className="w-4 h-4 text-[#11446e]" />
                          <h4 className="font-semibold text-[#11446e]">Transacción Bancaria</h4>
                        </div>
                        <div className="space-y-1 text-sm">
                          <p><span className="text-gray-500">Descripción:</span> <span className="font-medium">{record.bankTransaction.description}</span></p>
                          <p><span className="text-gray-500">Monto:</span> <span className="font-semibold text-red-600">{formatCurrency(Math.abs(record.bankTransaction.amount))}</span></p>
                          <p><span className="text-gray-500">Fecha:</span> {formatDate(record.bankTransaction.date)}</p>
                        </div>
                      </div>
                    </div>

                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <p className="text-xs text-gray-500">
                        <span className="font-medium">Método:</span> {record.matchMethod}
                      </p>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </Card>
        </div>
      </AppLayout>
    </ProtectedRoute>
  );
}

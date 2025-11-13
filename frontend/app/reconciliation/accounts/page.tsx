/**
 * Reconciliation Accounts Page
 *
 * Modern UI to manage cash, bank, credit card and terminal accounts
 * connected to the reconciliation module.
 */

'use client';

import {
  useState,
  useEffect,
  useMemo,
  useCallback,
  type ComponentType,
} from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { AppLayout } from '@/components/layout/AppLayout';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Alert } from '@/components/ui/Alert';
import { cn } from '@/lib/utils/cn';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import {
  Banknote,
  CreditCard,
  Wallet,
  Search,
  RefreshCw,
  Filter,
  AlertTriangle,
  ShieldCheck,
  PiggyBank,
  ArrowUpRight,
  ArrowDownRight,
  Terminal,
  Loader2,
  Plus,
  Circle,
} from 'lucide-react';

const UI_PAYMENT_ACCOUNTS_ENDPOINT = '/api/payment-accounts';
const UI_BANKING_INSTITUTIONS_ENDPOINT = `${UI_PAYMENT_ACCOUNTS_ENDPOINT}/banking-institutions`;

type TipoCuenta = 'bancaria' | 'efectivo' | 'terminal';
type SubtipoCuenta = 'debito' | 'credito' | null;

interface UserPaymentAccount {
  id: number;
  nombre: string;
  tipo: TipoCuenta;
  subtipo: SubtipoCuenta;
  moneda: string;
  saldo_inicial: number;
  saldo_actual: number;
  propietario_id: number;
  tenant_id: number;
  limite_credito?: number | null;
  fecha_corte?: number | null;
  fecha_pago?: number | null;
  credito_disponible?: number | null;
  proveedor_terminal?: string | null;
  banco_nombre?: string | null;
  numero_tarjeta?: string | null;
  numero_cuenta?: string | null;
  numero_cuenta_enmascarado?: string | null;
  clabe?: string | null;
  numero_identificacion?: string | null;
  activo: boolean;
  created_at?: string;
  updated_at?: string;
}

interface BankingInstitution {
  id: number;
  name: string;
  short_name?: string | null;
  type: string;
}

interface AccountPayload {
  nombre: string;
  tipo: TipoCuenta;
  subtipo?: SubtipoCuenta | null;
  moneda: string;
  saldo_inicial: number;
  limite_credito?: number | null;
  fecha_corte?: number | null;
  fecha_pago?: number | null;
  proveedor_terminal?: string | null;
  banco_nombre?: string | null;
  numero_tarjeta?: string | null;
  numero_cuenta?: string | null;
  numero_cuenta_enmascarado?: string | null;
  clabe?: string | null;
  numero_identificacion?: string | null;
  activo?: boolean;
}

const currencyFormatter = new Intl.NumberFormat('es-MX', {
  style: 'currency',
  currency: 'MXN',
  maximumFractionDigits: 2,
});

const typeSegments = [
  {
    id: 'all',
    label: 'Todas',
    description: 'Resumen completo',
    icon: PiggyBank,
  },
  {
    id: 'efectivo',
    label: 'Efectivo',
    description: 'Cajas y bóvedas',
    icon: Wallet,
  },
  {
    id: 'bancaria_debito',
    label: 'Bancos Débito',
    description: 'Cuentas operativas',
    icon: Banknote,
  },
  {
    id: 'bancaria_credito',
    label: 'Tarjetas Crédito',
    description: 'Líneas disponibles',
    icon: CreditCard,
  },
  {
    id: 'terminal',
    label: 'Terminales',
    description: 'Cobros POS',
    icon: Terminal,
  },
] as const;

const saldoBadgeStyles: Record<string, string> = {
  positivo: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  cero: 'bg-slate-50 text-slate-600 border-slate-100',
  negativo: 'bg-red-50 text-red-700 border-red-100',
  disponible: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  medio: 'bg-amber-50 text-amber-700 border-amber-100',
  bajo: 'bg-orange-50 text-orange-700 border-orange-100',
  sin_credito: 'bg-rose-50 text-rose-700 border-rose-100',
};

const defaultFormState = {
  nombre: '',
  tipo: 'bancaria' as TipoCuenta,
  subtipo: 'debito' as SubtipoCuenta,
  moneda: 'MXN',
  saldo_inicial: 0,
  limite_credito: null as number | null,
  fecha_corte: null as number | null,
  fecha_pago: null as number | null,
  proveedor_terminal: '',
  banco_nombre: '',
  numero_tarjeta: '',
  numero_cuenta: '',
  numero_cuenta_enmascarado: '',
  clabe: '',
  numero_identificacion: '',
  activo: true,
};

type AccountFormState = typeof defaultFormState;

export default function ReconciliationAccountsPage() {
  const [accounts, setAccounts] = useState<UserPaymentAccount[]>([]);
  const [filteredType, setFilteredType] =
    useState<(typeof typeSegments)[number]['id']>('all');
  const [search, setSearch] = useState('');
  const [activeOnly, setActiveOnly] = useState(true);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editingAccount, setEditingAccount] =
    useState<UserPaymentAccount | null>(null);
  const [bankingInstitutions, setBankingInstitutions] = useState<
    BankingInstitution[]
  >([]);
  const token = useAuthStore((state) => state.token);

  const authHeaders = useMemo(() => {
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, [token]);

  const fetchAccounts = useCallback(async () => {
    if (!token) {
      setError('Tu sesión no es válida, vuelve a iniciar sesión.');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams({
        active_only: String(activeOnly),
      });

      const response = await fetch(
        `${UI_PAYMENT_ACCOUNTS_ENDPOINT}?${params.toString()}`,
        {
          credentials: 'include',
          headers: {
            ...authHeaders,
          },
        }
      );

      if (!response.ok) {
        throw new Error('No se pudieron cargar las cuentas');
      }

      const data = await response.json();
      setAccounts(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
      setError(
        err instanceof Error
          ? err.message
          : 'Ocurrió un error al cargar las cuentas'
      );
    } finally {
      setLoading(false);
    }
  }, [activeOnly, authHeaders, token]);

  const fetchInstitutions = useCallback(async () => {
    if (!token) return;

    try {
      const response = await fetch(
        UI_BANKING_INSTITUTIONS_ENDPOINT,
        {
          credentials: 'include',
          headers: {
            ...authHeaders,
          },
        }
      );
      if (!response.ok) {
        throw new Error('No se pudieron cargar los bancos');
      }
      const data = await response.json();
      setBankingInstitutions(Array.isArray(data) ? data : []);
    } catch (err) {
      console.warn('Banking institutions not available', err);
    }
  }, [authHeaders, token]);

  useEffect(() => {
    fetchAccounts();
  }, [fetchAccounts]);

  useEffect(() => {
    fetchInstitutions();
  }, [fetchInstitutions]);

  const filteredAccounts = useMemo(() => {
    const filtered = accounts.filter((account) => {
      if (filteredType === 'efectivo') {
        if (account.tipo !== 'efectivo') return false;
      } else if (filteredType === 'terminal') {
        if (account.tipo !== 'terminal') return false;
      } else if (filteredType === 'bancaria_debito') {
        if (!(account.tipo === 'bancaria' && account.subtipo === 'debito')) {
          return false;
        }
      } else if (filteredType === 'bancaria_credito') {
        if (!(account.tipo === 'bancaria' && account.subtipo === 'credito')) {
          return false;
        }
      }

      if (!search.trim()) return true;
      const term = search.toLowerCase();
      return (
        account.nombre.toLowerCase().includes(term) ||
        (account.banco_nombre?.toLowerCase().includes(term) ?? false) ||
        (account.clabe?.includes(term) ?? false) ||
        (account.numero_cuenta?.includes(term) ?? false) ||
        (account.numero_tarjeta?.includes(term) ?? false)
      );
    });

    return filtered;
  }, [accounts, filteredType, search]);

  const summary = useMemo(() => {
    const totalBalance = accounts.reduce(
      (sum, account) => sum + (account.saldo_actual ?? 0),
      0
    );

    const availableCash = accounts
      .filter(
        (account) =>
          account.activo &&
          ((account.tipo === 'bancaria' && account.subtipo === 'debito') ||
            account.tipo === 'efectivo')
      )
      .reduce((sum, account) => sum + Math.max(account.saldo_actual ?? 0, 0), 0);

    const creditAccounts = accounts.filter(
      (account) => account.tipo === 'bancaria' && account.subtipo === 'credito'
    );

    const creditUsed = creditAccounts.reduce((sum, account) => {
      if (!account.limite_credito) return sum;
      const available =
        account.credito_disponible ??
        Math.max(account.limite_credito - Math.abs(account.saldo_actual ?? 0), 0);
      const used = Math.max(account.limite_credito - available, 0);
      return sum + used;
    }, 0);

    const creditLimit = creditAccounts.reduce(
      (sum, account) => sum + (account.limite_credito ?? 0),
      0
    );

    return {
      totalBalance,
      availableCash,
      creditUsed,
      creditLimit,
      activeAccounts: accounts.filter((account) => account.activo).length,
    };
  }, [accounts]);

  const saldoState = (account: UserPaymentAccount) => {
    if (account.tipo === 'bancaria' && account.subtipo === 'credito') {
      if (!account.limite_credito) {
        return 'sin_credito';
      }

      const available =
        account.credito_disponible ??
        Math.max(account.limite_credito - Math.abs(account.saldo_actual ?? 0), 0);

      const ratio = available / account.limite_credito;

      if (ratio > 0.8) return 'disponible';
      if (ratio > 0.5) return 'medio';
      if (ratio > 0.1) return 'bajo';
      return 'sin_credito';
    }

    if ((account.saldo_actual ?? 0) > 0) return 'positivo';
    if ((account.saldo_actual ?? 0) === 0) return 'cero';
    return 'negativo';
  };

  const openCreateDrawer = () => {
    setEditingAccount(null);
    setIsDrawerOpen(true);
  };

  const openEditDrawer = (account: UserPaymentAccount) => {
    setEditingAccount(account);
    setIsDrawerOpen(true);
  };

  const handleSaveAccount = async (payload: AccountPayload) => {
    try {
      setSubmitting(true);
      setError(null);
      setSuccessMessage(null);

      const isEdit = Boolean(editingAccount);
      const endpoint = isEdit
        ? `${UI_PAYMENT_ACCOUNTS_ENDPOINT}/${editingAccount?.id}`
        : UI_PAYMENT_ACCOUNTS_ENDPOINT;

      const response = await fetch(endpoint, {
        method: isEdit ? 'PUT' : 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders,
        },
        credentials: 'include',
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(
          detail?.detail ?? 'No se pudo guardar la cuenta. Revisa los datos.'
        );
      }

      const savedAccount = await response.json();
      if (isEdit) {
        setAccounts((prev) =>
          prev.map((account) =>
            account.id === savedAccount.id ? savedAccount : account
          )
        );
        setSuccessMessage('Cuenta actualizada correctamente');
      } else {
        setAccounts((prev) => [savedAccount, ...prev]);
        setSuccessMessage('Cuenta creada correctamente');
      }

      setIsDrawerOpen(false);
      setEditingAccount(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'No se pudo guardar la cuenta. Intenta de nuevo.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeactivate = async (account: UserPaymentAccount) => {
    if (
      !confirm(
        `¿Deseas desactivar la cuenta "${account.nombre}"? Podrás reactivarla después.`
      )
    ) {
      return;
    }

    try {
      const response = await fetch(
        `${UI_PAYMENT_ACCOUNTS_ENDPOINT}/${account.id}`,
        {
          method: 'DELETE',
          credentials: 'include',
          headers: {
            ...authHeaders,
          },
        }
      );

      if (!response.ok) {
        throw new Error('No se pudo desactivar la cuenta');
      }

      setAccounts((prev) =>
        prev.map((item) =>
          item.id === account.id ? { ...item, activo: false } : item
        )
      );
      setSuccessMessage('Cuenta desactivada');
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'No se pudo desactivar la cuenta'
      );
    }
  };

  const emptyState =
    !loading && filteredAccounts.length === 0 ? (
      <Card className="text-center py-16">
        <div className="max-w-xl mx-auto space-y-4">
          <div className="mx-auto w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center">
            <CreditCard className="w-8 h-8 text-slate-400" />
          </div>
          <h3 className="text-xl font-semibold text-gray-900">
            No encontramos cuentas para este filtro
          </h3>
          <p className="text-gray-600">
            Ajusta los filtros o crea una nueva cuenta para comenzar a conciliar
            tus transacciones.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Button onClick={openCreateDrawer} variant="primary">
              <Plus className="w-4 h-4 mr-2" />
              Nueva cuenta
            </Button>
            <Button onClick={() => setFilteredType('all')} variant="ghost">
              Limpiar filtros
            </Button>
          </div>
        </div>
      </Card>
    ) : null;

  return (
    <ProtectedRoute>
      <AppLayout>
        <div className="space-y-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-sm font-semibold text-primary-600 uppercase tracking-wide">
                Conciliación
              </p>
              <h1 className="text-3xl font-bold text-gray-900">
                Cuentas &amp; Terminales
              </h1>
              <p className="text-gray-600 mt-2 max-w-2xl">
                Controla tus cuentas bancarias, cajas de efectivo, terminales de
                cobro y tarjetas de crédito para asegurar que cada transacción
                esté lista para conciliación.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-3">
              <Button
                variant="outline"
                className="bg-white"
                onClick={fetchAccounts}
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Actualizar
              </Button>
              <Button variant="primary" onClick={openCreateDrawer}>
                <Plus className="w-4 h-4 mr-2" />
                Nueva cuenta
              </Button>
            </div>
          </div>

          {successMessage && (
            <Alert variant="success" title="Cambios guardados">
              {successMessage}
            </Alert>
          )}
          {error && (
            <Alert variant="error" title="Error">
              {error}
            </Alert>
          )}

          {/* Summary cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <SummaryCard
              title="Saldo total"
              value={currencyFormatter.format(summary.totalBalance)}
              description="Balance combinado"
              icon={PiggyBank}
            />
            <SummaryCard
              title="Disponibles operativos"
              value={currencyFormatter.format(summary.availableCash)}
              description="Bancos débito y efectivo"
              icon={Banknote}
            />
            <SummaryCard
              title="Crédito utilizado"
              value={currencyFormatter.format(summary.creditUsed)}
              description={
                summary.creditLimit > 0
                  ? `de ${currencyFormatter.format(summary.creditLimit)}`
                  : 'Sin líneas registradas'
              }
              icon={CreditCard}
              trend={
                summary.creditLimit
                  ? Math.round(
                      (summary.creditUsed / summary.creditLimit) * 100
                    )
                  : 0
              }
            />
            <SummaryCard
              title="Cuentas activas"
              value={summary.activeAccounts.toString()}
              description="Listas para conciliar"
              icon={ShieldCheck}
            />
          </div>

          {/* Filters */}
          <Card>
            <div className="flex flex-col gap-4">
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                <div className="flex items-center gap-2 text-gray-700">
                  <Filter className="w-4 h-4" />
                  <span className="text-sm font-medium uppercase tracking-wide">
                    Filtros activos
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2 text-sm text-gray-600">
                    <input
                      type="checkbox"
                      className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                      checked={activeOnly}
                      onChange={(event) =>
                        setActiveOnly(event.target.checked)
                      }
                    />
                    Solo cuentas activas
                  </label>
                  <Input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Buscar por nombre, banco, CLABE..."
                    className="w-full lg:w-80"
                    icon={<Search className="w-4 h-4 text-gray-400" />}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
                {typeSegments.map((segment) => (
                  <button
                    key={segment.id}
                    onClick={() => setFilteredType(segment.id)}
                    className={cn(
                      'flex items-start gap-3 rounded-2xl border p-4 text-left transition-all',
                      filteredType === segment.id
                        ? 'border-primary-600 bg-primary-50 shadow-sm'
                        : 'border-gray-200 bg-white hover:border-primary-200'
                    )}
                  >
                    <div
                      className={cn(
                        'p-2 rounded-xl',
                        filteredType === segment.id
                          ? 'bg-primary-600 text-white'
                          : 'bg-slate-100 text-slate-600'
                      )}
                    >
                      <segment.icon className="w-5 h-5" />
                    </div>
                    <div className="flex-1">
                      <p className="font-semibold text-gray-900">
                        {segment.label}
                      </p>
                      <p className="text-sm text-gray-500">
                        {segment.description}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </Card>

          {/* Table */}
          <Card className="overflow-hidden">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-bold text-gray-900">
                  {filteredAccounts.length} cuentas
                </h2>
                <p className="text-sm text-gray-600">
                  Resultados ordenados por tipo y nombre
                </p>
              </div>
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <Circle className="w-3 h-3 text-emerald-500" />
                Disponible
                <Circle className="w-3 h-3 text-amber-500" />
                Atención
                <Circle className="w-3 h-3 text-rose-500" />
                Sin crédito
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      Cuenta
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      Tipo / Banco
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      Saldo / Crédito
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      Identificadores
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      Estado
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      Acciones
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-100">
                  {loading && (
                    <tr>
                      <td
                        colSpan={6}
                        className="px-4 py-10 text-center text-gray-500"
                      >
                        <div className="flex flex-col items-center gap-3">
                          <Loader2 className="w-6 h-6 animate-spin text-primary-500" />
                          Cargando cuentas...
                        </div>
                      </td>
                    </tr>
                  )}
                  {!loading &&
                    filteredAccounts.map((account) => {
                      const state = saldoState(account);
                      const badgeStyle =
                        saldoBadgeStyles[state] ?? saldoBadgeStyles.positivo;
                      const isCredit =
                        account.tipo === 'bancaria' &&
                        account.subtipo === 'credito' &&
                        account.limite_credito;
                      const available =
                        account.credito_disponible ??
                        Math.max(
                          (account.limite_credito ?? 0) -
                            Math.abs(account.saldo_actual ?? 0),
                          0
                        );
                      const creditUsage = isCredit
                        ? Math.min(
                            100,
                            Math.round(
                              ((account.limite_credito! - available) /
                                account.limite_credito!) *
                                100
                            )
                          )
                        : 0;

                      return (
                        <tr
                          key={account.id}
                          className={cn(
                            'transition hover:bg-slate-50',
                            !account.activo && 'opacity-70'
                          )}
                        >
                          <td className="px-4 py-4 align-top">
                            <div className="font-semibold text-gray-900">
                              {account.nombre}
                            </div>
                            <div className="text-sm text-gray-500">
                              {account.moneda}
                            </div>
                            {!account.activo && (
                              <span className="mt-2 inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium bg-gray-50 text-gray-500 border-gray-200">
                                Inactiva
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-4 align-top">
                            <div className="flex items-center gap-2">
                              {account.tipo === 'bancaria' ? (
                                <Banknote className="w-4 h-4 text-primary-600" />
                              ) : account.tipo === 'efectivo' ? (
                                <Wallet className="w-4 h-4 text-amber-500" />
                              ) : (
                                <Terminal className="w-4 h-4 text-info-500" />
                              )}
                              <span className="font-medium text-gray-900">
                                {formatAccountType(account)}
                              </span>
                            </div>
                            <p className="text-sm text-gray-500">
                              {account.banco_nombre ??
                                account.proveedor_terminal ??
                                '—'}
                            </p>
                          </td>
                          <td className="px-4 py-4 align-top">
                            <p className="font-semibold text-gray-900">
                              {currencyFormatter.format(
                                account.saldo_actual ?? 0
                              )}
                            </p>
                            {isCredit && (
                              <div className="mt-2 space-y-1">
                                <div className="flex items-center justify-between text-xs text-gray-500">
                                  <span>Uso</span>
                                  <span>{creditUsage}%</span>
                                </div>
                                <div className="h-2 w-full rounded-full bg-gray-100 overflow-hidden">
                                  <div
                                    className={cn(
                                      'h-full rounded-full',
                                      creditUsage > 80
                                        ? 'bg-rose-500'
                                        : creditUsage > 60
                                        ? 'bg-amber-500'
                                        : 'bg-emerald-500'
                                    )}
                                    style={{ width: `${creditUsage}%` }}
                                  />
                                </div>
                                <p className="text-xs text-gray-500">
                                  Disponible:{' '}
                                  {currencyFormatter.format(available)}
                                </p>
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-4 align-top text-sm text-gray-600 space-y-1">
                            {account.clabe && (
                              <p>
                                CLABE:{' '}
                                <span className="font-mono">
                                  {account.clabe}
                                </span>
                              </p>
                            )}
                            {account.numero_cuenta_enmascarado && (
                              <p>
                                Cuenta:{' '}
                                <span className="font-mono">
                                  {account.numero_cuenta_enmascarado}
                                </span>
                              </p>
                            )}
                            {account.numero_tarjeta && (
                              <p>
                                Tarjeta:{' '}
                                <span className="font-mono">
                                  •••• {account.numero_tarjeta.slice(-4)}
                                </span>
                              </p>
                            )}
                            {account.proveedor_terminal && (
                              <p>
                                Terminal:{' '}
                                <span className="font-mono">
                                  {account.proveedor_terminal}
                                </span>
                              </p>
                            )}
                            {!account.clabe &&
                              !account.numero_cuenta_enmascarado &&
                              !account.numero_tarjeta &&
                              !account.proveedor_terminal && <p>—</p>}
                          </td>
                          <td className="px-4 py-4 align-top">
                            <span
                              className={cn(
                                'inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold',
                                badgeStyle
                              )}
                            >
                              {renderStateLabel(state)}
                            </span>
                            {account.subtipo === 'credito' &&
                              account.fecha_corte && (
                                <p className="mt-2 text-xs text-gray-500">
                                  Corte día {account.fecha_corte} · Pago día{' '}
                                  {account.fecha_pago ?? '—'}
                                </p>
                              )}
                          </td>
                          <td className="px-4 py-4 align-top text-right">
                            <div className="flex justify-end gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => openEditDrawer(account)}
                              >
                                Editar
                              </Button>
                              {account.activo && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="text-red-600 hover:text-red-700"
                                  onClick={() => handleDeactivate(account)}
                                >
                                  Desactivar
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
            {emptyState}
          </Card>
        </div>

        <AccountFormDrawer
          open={isDrawerOpen}
          onClose={() => {
            if (!submitting) {
              setIsDrawerOpen(false);
              setEditingAccount(null);
            }
          }}
          initialData={editingAccount}
          onSubmit={handleSaveAccount}
          submitting={submitting}
          institutions={bankingInstitutions}
        />
      </AppLayout>
    </ProtectedRoute>
  );
}

interface SummaryCardProps {
  title: string;
  value: string;
  description: string;
  icon: ComponentType<{ className?: string }>;
  trend?: number;
}

function SummaryCard({
  title,
  value,
  description,
  icon: Icon,
  trend,
}: SummaryCardProps) {
  const isPositive = typeof trend === 'number' ? trend < 70 : false;
  return (
    <Card className="flex flex-col gap-4 border-none shadow-md bg-gradient-to-br from-white to-slate-50">
      <div className="flex items-center justify-between">
        <div className="p-3 rounded-2xl bg-primary-50 text-primary-600">
          <Icon className="w-6 h-6" />
        </div>
        {typeof trend === 'number' && (
          <div
            className={cn(
              'flex items-center gap-1 text-sm font-semibold',
              isPositive ? 'text-emerald-600' : 'text-amber-600'
            )}
          >
            {isPositive ? (
              <ArrowDownRight className="w-4 h-4" />
            ) : (
              <ArrowUpRight className="w-4 h-4" />
            )}
            {trend}%
          </div>
        )}
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm text-gray-600">{description}</p>
      </div>
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <ShieldCheck className="w-4 h-4" />
        Monitoreado en tiempo real
      </div>
    </Card>
  );
}

interface AccountFormDrawerProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: AccountPayload) => Promise<void>;
  initialData: UserPaymentAccount | null;
  submitting: boolean;
  institutions: BankingInstitution[];
}

function AccountFormDrawer({
  open,
  onClose,
  onSubmit,
  initialData,
  submitting,
  institutions,
}: AccountFormDrawerProps) {
  const [formState, setFormState] =
    useState<AccountFormState>(defaultFormState);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (open) {
      if (initialData) {
        setFormState({
          nombre: initialData.nombre,
          tipo: initialData.tipo,
          subtipo: initialData.subtipo,
          moneda: initialData.moneda,
          saldo_inicial: initialData.saldo_inicial ?? 0,
          limite_credito: initialData.limite_credito ?? null,
          fecha_corte: initialData.fecha_corte ?? null,
          fecha_pago: initialData.fecha_pago ?? null,
          proveedor_terminal: initialData.proveedor_terminal ?? '',
          banco_nombre: initialData.banco_nombre ?? '',
          numero_tarjeta: initialData.numero_tarjeta ?? '',
          numero_cuenta: initialData.numero_cuenta ?? '',
          numero_cuenta_enmascarado:
            initialData.numero_cuenta_enmascarado ?? '',
          clabe: initialData.clabe ?? '',
          numero_identificacion: initialData.numero_identificacion ?? '',
          activo: initialData.activo,
        });
      } else {
        setFormState(defaultFormState);
      }
      setErrors({});
    }
  }, [open, initialData]);

  const handleChange = (
    field: keyof AccountFormState,
    value: string | number | boolean | null
  ) => {
    setFormState((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const validate = () => {
    const validationErrors: Record<string, string> = {};
    if (!formState.nombre.trim()) {
      validationErrors.nombre = 'Ingresa un nombre descriptivo';
    }

    if (!formState.tipo) {
      validationErrors.tipo = 'Selecciona un tipo';
    }

    if (formState.tipo === 'bancaria') {
      if (!formState.subtipo) {
        validationErrors.subtipo = 'Indica si es débito o crédito';
      }
      if (!formState.banco_nombre.trim()) {
        validationErrors.banco_nombre = 'El banco es obligatorio';
      }

      if (formState.subtipo === 'credito') {
        if (!formState.limite_credito || formState.limite_credito <= 0) {
          validationErrors.limite_credito = 'Define un límite mayor a 0';
        }
        if (!formState.fecha_corte) {
          validationErrors.fecha_corte = 'Define la fecha de corte';
        }
        if (!formState.fecha_pago) {
          validationErrors.fecha_pago = 'Define la fecha de pago';
        }
        if (
          !formState.numero_tarjeta ||
          formState.numero_tarjeta.length < 4 ||
          formState.numero_tarjeta.length > 19
        ) {
          validationErrors.numero_tarjeta =
            'Ingresa al menos los últimos 4 dígitos';
        }
      }

      if (formState.clabe && formState.clabe.length !== 18) {
        validationErrors.clabe = 'La CLABE debe tener 18 dígitos';
      }
    } else {
      if (formState.tipo === 'terminal' && !formState.proveedor_terminal) {
        validationErrors.proveedor_terminal =
          'Indica el proveedor de la terminal';
      }
    }

    return validationErrors;
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const validationErrors = validate();
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    const payload: AccountPayload = {
      nombre: formState.nombre.trim(),
      tipo: formState.tipo,
      subtipo: formState.tipo === 'bancaria' ? formState.subtipo : null,
      moneda: formState.moneda,
      saldo_inicial: Number(formState.saldo_inicial) || 0,
      limite_credito:
        formState.tipo === 'bancaria' && formState.subtipo === 'credito'
          ? Number(formState.limite_credito)
          : null,
      fecha_corte:
        formState.tipo === 'bancaria' && formState.subtipo === 'credito'
          ? Number(formState.fecha_corte)
          : null,
      fecha_pago:
        formState.tipo === 'bancaria' && formState.subtipo === 'credito'
          ? Number(formState.fecha_pago)
          : null,
      proveedor_terminal:
        formState.tipo === 'terminal' ? formState.proveedor_terminal : null,
      banco_nombre: formState.tipo === 'bancaria' ? formState.banco_nombre : null,
      numero_tarjeta:
        formState.tipo === 'bancaria' && formState.subtipo === 'credito'
          ? formState.numero_tarjeta
          : null,
      numero_cuenta:
        formState.tipo === 'bancaria' ? formState.numero_cuenta : null,
      numero_cuenta_enmascarado:
        formState.tipo === 'bancaria'
          ? formState.numero_cuenta_enmascarado
          : null,
      clabe: formState.tipo === 'bancaria' ? formState.clabe || null : null,
      numero_identificacion: formState.numero_identificacion || null,
    };

    if (initialData) {
      payload.activo = formState.activo;
    }

    await onSubmit(payload);
  };

  if (!open) {
    return null;
  }

  const typeOptions: {
    value: TipoCuenta;
    label: string;
    icon: ComponentType<{ className?: string }>;
  }[] = [
    { value: 'bancaria', label: 'Cuenta bancaria', icon: Banknote },
    { value: 'efectivo', label: 'Caja de efectivo', icon: Wallet },
    { value: 'terminal', label: 'Terminal POS', icon: Terminal },
  ];

  return (
    <div className="fixed inset-0 z-50 flex">
      <div
        className="hidden lg:block flex-1 bg-black/40"
        onClick={onClose}
      ></div>
      <div className="w-full max-w-xl bg-white shadow-2xl h-full overflow-y-auto">
        <div className="p-6 border-b border-gray-200">
          <p className="text-sm font-semibold text-primary-600 uppercase tracking-wide">
            {initialData ? 'Editar cuenta' : 'Nueva cuenta'}
          </p>
          <div className="flex items-start justify-between mt-1">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">
                {initialData ? initialData.nombre : 'Configura tu cuenta'}
              </h2>
              <p className="text-gray-600">
                Define el tipo de cuenta y los parámetros necesarios para
                conciliación automática.
              </p>
            </div>
            <Button variant="ghost" onClick={onClose}>
              Cerrar
            </Button>
          </div>
        </div>

        <form className="p-6 space-y-6" onSubmit={handleSubmit}>
          <section>
            <p className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
              Tipo de cuenta
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {typeOptions.map((option) => (
                <label
                  key={option.value}
                  className={cn(
                    'border rounded-2xl p-4 cursor-pointer flex flex-col gap-2 transition',
                    formState.tipo === option.value
                      ? 'border-primary-600 bg-primary-50'
                      : 'border-gray-200 hover:border-primary-200'
                  )}
                >
                  <input
                    type="radio"
                    name="tipo"
                    value={option.value}
                    className="hidden"
                    checked={formState.tipo === option.value}
                    onChange={() => handleChange('tipo', option.value)}
                  />
                  <div className="flex items-center gap-2">
                    <option.icon className="w-5 h-5 text-primary-600" />
                    <span className="font-semibold text-gray-900">
                      {option.label}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500">
                    {option.value === 'bancaria' && 'CLABE, débito o crédito'}
                    {option.value === 'efectivo' &&
                      'Cajas chicas, fondos fijos'}
                    {option.value === 'terminal' && 'Clip, BBVA, MercadoPago'}
                  </p>
                </label>
              ))}
            </div>
            {errors.tipo && (
              <p className="mt-2 text-sm text-red-600">{errors.tipo}</p>
            )}
          </section>

          <section className="space-y-4">
            <Input
              label="Nombre de la cuenta"
              placeholder="Ej. BBVA Nómina MXN"
              value={formState.nombre}
              onChange={(event) => handleChange('nombre', event.target.value)}
              error={errors.nombre}
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="Moneda"
                value={formState.moneda}
                onChange={(event) => handleChange('moneda', event.target.value)}
              />
              <Input
                label="Saldo inicial / saldo base"
                type="number"
                value={formState.saldo_inicial}
                onChange={(event) =>
                  handleChange('saldo_inicial', Number(event.target.value))
                }
              />
            </div>
          </section>

          {formState.tipo === 'bancaria' && (
            <section className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Subtipo
                  </label>
                  <select
                    value={formState.subtipo ?? ''}
                    onChange={(event) =>
                      handleChange(
                        'subtipo',
                        event.target.value === ''
                          ? null
                          : (event.target.value as SubtipoCuenta)
                      )
                    }
                    className={cn(
                      'w-full rounded-lg border px-3 py-2',
                      errors.subtipo
                        ? 'border-red-500'
                        : 'border-gray-300 focus:border-primary-500 focus:ring-primary-500'
                    )}
                  >
                    <option value="">Selecciona...</option>
                    <option value="debito">Débito</option>
                    <option value="credito">Crédito</option>
                  </select>
                  {errors.subtipo && (
                    <p className="mt-1 text-sm text-red-600">
                      {errors.subtipo}
                    </p>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Banco
                  </label>
                  <input
                    list="bank-options"
                    value={formState.banco_nombre}
                    onChange={(event) =>
                      handleChange('banco_nombre', event.target.value)
                    }
                    className={cn(
                      'w-full rounded-lg border px-3 py-2',
                      errors.banco_nombre ? 'border-red-500' : 'border-gray-300'
                    )}
                    placeholder="Busca o escribe el banco"
                  />
                  <datalist id="bank-options">
                    {institutions.map((institution) => (
                      <option key={institution.id} value={institution.name} />
                    ))}
                  </datalist>
                  {errors.banco_nombre && (
                    <p className="mt-1 text-sm text-red-600">
                      {errors.banco_nombre}
                    </p>
                  )}
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  label="CLABE"
                  value={formState.clabe}
                  onChange={(event) => handleChange('clabe', event.target.value)}
                  helperText="18 dígitos"
                  error={errors.clabe}
                />
                <Input
                  label="Número de cuenta"
                  value={formState.numero_cuenta}
                  onChange={(event) =>
                    handleChange('numero_cuenta', event.target.value)
                  }
                />
                <Input
                  label="Cuenta enmascarada"
                  value={formState.numero_cuenta_enmascarado}
                  onChange={(event) =>
                    handleChange('numero_cuenta_enmascarado', event.target.value)
                  }
                  helperText="Ej: •••• 1234"
                />
                <Input
                  label="Identificador interno"
                  value={formState.numero_identificacion}
                  onChange={(event) =>
                    handleChange('numero_identificacion', event.target.value)
                  }
                />
              </div>

              {formState.subtipo === 'credito' && (
                <div className="rounded-2xl border border-amber-200 bg-amber-50/40 p-4 space-y-4">
                  <p className="text-sm font-semibold text-amber-700 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" />
                    Parámetros obligatorios para tarjetas de crédito
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Input
                      label="Límite de crédito"
                      type="number"
                      value={formState.limite_credito ?? ''}
                      onChange={(event) =>
                        handleChange(
                          'limite_credito',
                          event.target.value === ''
                            ? null
                            : Number(event.target.value)
                        )
                      }
                      error={errors.limite_credito}
                    />
                    <Input
                      label="Número de tarjeta"
                      value={formState.numero_tarjeta ?? ''}
                      onChange={(event) =>
                        handleChange('numero_tarjeta', event.target.value)
                      }
                      helperText="Puedes capturar solo los últimos 4"
                      error={errors.numero_tarjeta}
                    />
                    <Input
                      label="Día de corte"
                      type="number"
                      min={1}
                      max={31}
                      value={formState.fecha_corte ?? ''}
                      onChange={(event) =>
                        handleChange(
                          'fecha_corte',
                          event.target.value === ''
                            ? null
                            : Number(event.target.value)
                        )
                      }
                      error={errors.fecha_corte}
                    />
                    <Input
                      label="Día de pago"
                      type="number"
                      min={1}
                      max={31}
                      value={formState.fecha_pago ?? ''}
                      onChange={(event) =>
                        handleChange(
                          'fecha_pago',
                          event.target.value === ''
                            ? null
                            : Number(event.target.value)
                        )
                      }
                      error={errors.fecha_pago}
                    />
                  </div>
                </div>
              )}
            </section>
          )}

          {formState.tipo === 'terminal' && (
            <section className="space-y-4">
              <Input
                label="Proveedor de la terminal"
                placeholder="Clip, BBVA SmartPay, MercadoPago..."
                value={formState.proveedor_terminal}
                onChange={(event) =>
                  handleChange('proveedor_terminal', event.target.value)
                }
                error={errors.proveedor_terminal}
              />
              <Input
                label="Identificador / Número de serie"
                value={formState.numero_identificacion}
                onChange={(event) =>
                  handleChange('numero_identificacion', event.target.value)
                }
              />
            </section>
          )}

          {formState.tipo === 'efectivo' && (
            <section className="space-y-4">
              <Input
                label="Ubicación o custodio"
                placeholder="Ej: Caja chica CDMX"
                value={formState.numero_identificacion}
                onChange={(event) =>
                  handleChange('numero_identificacion', event.target.value)
                }
              />
            </section>
          )}

          {initialData && (
            <section className="rounded-2xl border border-slate-200 p-4">
              <label className="flex items-start gap-3 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={formState.activo}
                  onChange={(event) => handleChange('activo', event.target.checked)}
                  className="mt-1 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span>
                  Mantener cuenta activa
                  <p className="text-xs text-gray-500">
                    Desmarca para ocultarla del flujo de conciliación.
                  </p>
                </span>
              </label>
            </section>
          )}

          <div className="flex items-center justify-end gap-3 border-t border-gray-200 pt-4">
            <Button variant="ghost" type="button" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              type="submit"
              isLoading={submitting}
              disabled={submitting}
            >
              {initialData ? 'Guardar cambios' : 'Crear cuenta'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function renderStateLabel(state: string) {
  switch (state) {
    case 'positivo':
      return 'Saldo positivo';
    case 'cero':
      return 'Saldo en cero';
    case 'negativo':
      return 'Saldo negativo';
    case 'disponible':
      return 'Crédito disponible';
    case 'medio':
      return 'Crédito medio';
    case 'bajo':
      return 'Crédito bajo';
    case 'sin_credito':
      return 'Sin crédito';
    default:
      return state;
  }
}

function formatAccountType(account: UserPaymentAccount) {
  if (account.tipo === 'bancaria') {
    return account.subtipo === 'credito'
      ? 'Tarjeta de crédito'
      : 'Cuenta bancaria';
  }
  if (account.tipo === 'efectivo') {
    return 'Efectivo';
  }
  return 'Terminal';
}

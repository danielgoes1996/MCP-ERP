/**
 * Main Header Component
 *
 * Header principal de la aplicación con navegación, usuario y notificaciones
 */

'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import { useAuth } from '@/hooks/useAuth';
import { Logo } from '@/components/shared/Logo';
import { Button } from '@/components/shared/Button';
import {
  FileText,
  Bell,
  Settings,
  LogOut,
  ChevronDown,
  Menu,
  X,
  Sparkles,
  LayoutDashboard,
  CreditCard,
  TrendingUp,
  Users,
  FileSpreadsheet,
  DollarSign,
} from 'lucide-react';
import { cn } from '@/lib/utils/cn';

interface NavigationItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  description?: string;
}

const navigationItems: NavigationItem[] = [
  {
    name: 'Gastos',
    href: '/expenses',
    icon: DollarSign,
    description: 'Gestión de gastos empresariales',
  },
  {
    name: 'Clasificador de Facturas',
    href: '/invoice-classifier',
    icon: FileText,
    badge: 'Beta',
    description: 'Clasifica automáticamente tus facturas con IA',
  },
  {
    name: 'Conciliación',
    href: '/reconciliation',
    icon: CreditCard,
    description: 'Concilia tus cuentas bancarias',
  },
  {
    name: 'Reportes',
    href: '/reports',
    icon: TrendingUp,
    description: 'Análisis y reportes financieros',
  },
  {
    name: 'Dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
    description: 'Vista general',
  },
];

export function Header() {
  const pathname = usePathname();
  const { user, tenant } = useAuthStore();
  const { logout } = useAuth();
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [notifications] = useState(3); // Simulado

  const isActive = (href: string) => {
    if (href === '/dashboard') {
      return pathname === '/dashboard';
    }
    return pathname.startsWith(href);
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-gray-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80">
      <div className="container mx-auto px-4">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-8">
            <Link href="/dashboard" className="flex items-center">
              <Logo size="md" variant="full" />
            </Link>

            {/* Desktop Navigation */}
            <nav className="hidden lg:flex items-center gap-1">
              {navigationItems.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.href);

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      'group relative flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200',
                      active
                        ? 'text-primary-600 bg-primary-50'
                        : 'text-gray-700 hover:text-primary-600 hover:bg-gray-50'
                    )}
                  >
                    <Icon
                      className={cn(
                        'w-4 h-4 transition-colors',
                        active ? 'text-primary-600' : 'text-gray-500 group-hover:text-primary-600'
                      )}
                    />
                    <span>{item.name}</span>
                    {item.badge && (
                      <span className="px-1.5 py-0.5 text-[10px] font-semibold text-accent-600 bg-accent-100 rounded">
                        {item.badge}
                      </span>
                    )}

                    {/* Active indicator */}
                    {active && (
                      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-1/2 h-0.5 bg-primary-600 rounded-full" />
                    )}

                    {/* Tooltip on hover */}
                    {item.description && (
                      <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2 bg-gray-900 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap">
                        {item.description}
                        <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-gray-900 rotate-45" />
                      </div>
                    )}
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Right side: Notifications, Settings, User */}
          <div className="flex items-center gap-3">
            {/* AI Assistant Button */}
            <Button
              variant="ghost"
              size="sm"
              className="hidden md:flex items-center gap-2 text-accent-600 hover:text-accent-700 hover:bg-accent-50"
            >
              <Sparkles className="w-4 h-4" />
              <span className="text-sm font-medium">Asistente IA</span>
            </Button>

            {/* Notifications */}
            <button className="relative p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors">
              <Bell className="w-5 h-5" />
              {notifications > 0 && (
                <span className="absolute top-1 right-1 flex h-4 w-4 items-center justify-center rounded-full bg-error-500 text-[10px] font-bold text-white">
                  {notifications}
                </span>
              )}
            </button>

            {/* Settings */}
            <button className="hidden md:block p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors">
              <Settings className="w-5 h-5" />
            </button>

            {/* User Menu */}
            <div className="relative">
              <button
                onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
                className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors"
              >
                {/* User Avatar */}
                <div className="flex items-center justify-center w-8 h-8 rounded-full bg-gradient-to-br from-primary-500 to-accent-500 text-white text-sm font-semibold">
                  {user?.full_name?.charAt(0).toUpperCase() || user?.username?.charAt(0).toUpperCase() || 'U'}
                </div>

                {/* User Info - Hidden on mobile */}
                <div className="hidden md:block text-left">
                  <p className="text-sm font-medium text-gray-900">{user?.full_name || user?.username || 'Usuario'}</p>
                  <p className="text-xs text-gray-500">{tenant?.name || 'Empresa'}</p>
                </div>

                <ChevronDown
                  className={cn(
                    'hidden md:block w-4 h-4 text-gray-500 transition-transform',
                    isUserMenuOpen && 'rotate-180'
                  )}
                />
              </button>

              {/* Dropdown Menu */}
              {isUserMenuOpen && (
                <>
                  {/* Backdrop */}
                  <div
                    className="fixed inset-0 z-40"
                    onClick={() => setIsUserMenuOpen(false)}
                  />

                  {/* Menu */}
                  <div className="absolute right-0 top-full mt-2 w-64 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-50">
                    {/* User Info */}
                    <div className="px-4 py-3 border-b border-gray-100">
                      <p className="text-sm font-medium text-gray-900">{user?.full_name || user?.username}</p>
                      <p className="text-xs text-gray-500">{user?.email}</p>
                      <div className="flex items-center gap-2 mt-2">
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-primary-100 text-primary-700 text-xs font-medium rounded">
                          <FileSpreadsheet className="w-3 h-3" />
                          {user?.role}
                        </span>
                        {tenant?.name && (
                          <span className="inline-flex items-center gap-1 px-2 py-1 bg-accent-100 text-accent-700 text-xs font-medium rounded">
                            {tenant.name}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Menu Items */}
                    <div className="py-2">
                      <Link
                        href="/profile"
                        className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                        onClick={() => setIsUserMenuOpen(false)}
                      >
                        <Settings className="w-4 h-4 text-gray-500" />
                        Configuración
                      </Link>
                      <Link
                        href="/help"
                        className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                        onClick={() => setIsUserMenuOpen(false)}
                      >
                        <FileText className="w-4 h-4 text-gray-500" />
                        Ayuda y soporte
                      </Link>
                    </div>

                    {/* Logout */}
                    <div className="border-t border-gray-100 pt-2">
                      <button
                        onClick={() => {
                          setIsUserMenuOpen(false);
                          logout();
                        }}
                        className="flex items-center gap-3 w-full px-4 py-2 text-sm text-error-600 hover:bg-error-50"
                      >
                        <LogOut className="w-4 h-4" />
                        Cerrar sesión
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Mobile Menu Toggle */}
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="lg:hidden p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            >
              {isMobileMenuOpen ? (
                <X className="w-6 h-6" />
              ) : (
                <Menu className="w-6 h-6" />
              )}
            </button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {isMobileMenuOpen && (
          <nav className="lg:hidden py-4 border-t border-gray-200">
            <div className="space-y-1">
              {navigationItems.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.href);

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className={cn(
                      'flex items-center gap-3 px-4 py-3 rounded-lg transition-colors',
                      active
                        ? 'text-primary-600 bg-primary-50'
                        : 'text-gray-700 hover:bg-gray-50'
                    )}
                  >
                    <Icon className={cn('w-5 h-5', active ? 'text-primary-600' : 'text-gray-500')} />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{item.name}</span>
                        {item.badge && (
                          <span className="px-1.5 py-0.5 text-[10px] font-semibold text-accent-600 bg-accent-100 rounded">
                            {item.badge}
                          </span>
                        )}
                      </div>
                      {item.description && (
                        <p className="text-xs text-gray-500 mt-0.5">{item.description}</p>
                      )}
                    </div>
                  </Link>
                );
              })}
            </div>

            {/* Mobile AI Assistant */}
            <div className="mt-4 px-4">
              <Button variant="outline" fullWidth className="justify-center gap-2 text-accent-600">
                <Sparkles className="w-4 h-4" />
                Asistente IA
              </Button>
            </div>
          </nav>
        )}
      </div>
    </header>
  );
}

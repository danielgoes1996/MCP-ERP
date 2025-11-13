/**
 * Sidebar Component
 *
 * Navigation sidebar with all backend modules
 */

'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils/cn';
import { useClassificationCount } from '@/hooks/useClassificationCount';
import {
  LayoutDashboard,
  FileText,
  Receipt,
  CreditCard,
  Brain,
  Zap,
  BarChart3,
  Settings,
  Users,
  Building2,
  ChevronDown,
  X,
  DollarSign,
  FileCheck,
} from 'lucide-react';

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  children?: NavItem[];
}

const navigation: NavItem[] = [
  {
    name: 'Dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
    color: 'text-primary-600',
  },
  {
    name: 'Gastos',
    href: '/expenses',
    icon: FileText,
    color: 'text-primary-600',
    children: [
      { name: 'Todos los Gastos', href: '/expenses', icon: FileText, color: 'text-primary-600' },
      { name: 'Crear Gasto', href: '/expenses/create', icon: FileText, color: 'text-primary-600' },
      { name: 'Aprobaciones', href: '/expenses/approvals', icon: FileCheck, color: 'text-primary-600' },
      { name: 'Adelantos', href: '/expenses/advances', icon: DollarSign, color: 'text-primary-600' },
    ],
  },
  {
    name: 'Facturas',
    href: '/invoices',
    icon: Receipt,
    color: 'text-secondary-600',
    children: [
      { name: 'Todas las Facturas', href: '/invoices', icon: Receipt, color: 'text-secondary-600' },
      { name: 'Subir Factura', href: '/invoices/upload', icon: Receipt, color: 'text-secondary-600' },
      { name: 'Clasificación Contable', href: '/invoices/classification', icon: Brain, color: 'text-secondary-600' },
    ],
  },
  {
    name: 'Conciliación',
    href: '/reconciliation',
    icon: CreditCard,
    color: 'text-accent-600',
    children: [
      { name: 'Dashboard', href: '/reconciliation', icon: LayoutDashboard, color: 'text-accent-600' },
      { name: 'Subir Estado de Cuenta', href: '/reconciliation/upload', icon: CreditCard, color: 'text-accent-600' },
      { name: 'Historial', href: '/reconciliation/history', icon: FileCheck, color: 'text-accent-600' },
    ],
  },
  {
    name: 'IA & Clasificación',
    href: '/ai',
    icon: Brain,
    color: 'text-secondary-600',
    children: [
      { name: 'Dashboard IA', href: '/ai/dashboard', icon: Brain, color: 'text-secondary-600' },
      { name: 'Clasificador', href: '/ai/classifier', icon: Brain, color: 'text-secondary-600' },
      { name: 'Aprendizaje', href: '/ai/learning', icon: Brain, color: 'text-secondary-600' },
      { name: 'Predicciones', href: '/ai/predictions', icon: Brain, color: 'text-secondary-600' },
    ],
  },
  {
    name: 'Automatización',
    href: '/automation',
    icon: Zap,
    color: 'text-warning-600',
    children: [
      { name: 'Jobs RPA', href: '/automation/jobs', icon: Zap, color: 'text-warning-600' },
      { name: 'Portales', href: '/automation/portals', icon: Zap, color: 'text-warning-600' },
      { name: 'Templates', href: '/automation/templates', icon: Zap, color: 'text-warning-600' },
      { name: 'Historial', href: '/automation/history', icon: Zap, color: 'text-warning-600' },
    ],
  },
  {
    name: 'Reportes',
    href: '/reports',
    icon: BarChart3,
    color: 'text-info-600',
    children: [
      { name: 'Dashboard', href: '/reports/dashboard', icon: BarChart3, color: 'text-info-600' },
      { name: 'Financieros', href: '/reports/financial', icon: BarChart3, color: 'text-info-600' },
      { name: 'Pólizas', href: '/reports/polizas', icon: FileText, color: 'text-info-600' },
      { name: 'Análisis de Costos', href: '/reports/cost-analysis', icon: BarChart3, color: 'text-info-600' },
    ],
  },
  {
    name: 'Administración',
    href: '/admin',
    icon: Settings,
    color: 'text-gray-600',
    children: [
      { name: 'Usuarios', href: '/admin/users', icon: Users, color: 'text-gray-600' },
      { name: 'Empresa', href: '/admin/company', icon: Building2, color: 'text-gray-600' },
      { name: 'Catálogo Contable', href: '/admin/catalog', icon: FileText, color: 'text-gray-600' },
      { name: 'Configuración', href: '/admin/settings', icon: Settings, color: 'text-gray-600' },
    ],
  },
];

export function Sidebar({ isOpen = true, onClose }: SidebarProps) {
  const pathname = usePathname();
  const [expandedItems, setExpandedItems] = useState<string[]>([]);
  const { count: pendingClassifications } = useClassificationCount();

  const toggleExpanded = (name: string) => {
    setExpandedItems((prev) =>
      prev.includes(name)
        ? prev.filter((item) => item !== name)
        : [...prev, name]
    );
  };

  const isActive = (href: string) => {
    if (href === '/dashboard') {
      return pathname === href;
    }
    return pathname.startsWith(href);
  };

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-30 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed left-0 top-0 z-40 h-screen w-72 bg-white border-r border-gray-200 transition-transform duration-300 flex flex-col',
          isOpen ? 'translate-x-0' : '-translate-x-full',
          'lg:translate-x-0'
        )}
      >
        {/* Logo Header */}
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <img
              src="/ContaFlow.png"
              alt="ContaFlow"
              className="h-10 w-auto"
            />
            <button
              onClick={onClose}
              className="lg:hidden p-2 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <X className="w-5 h-5 text-gray-600" />
            </button>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-4 space-y-1">
          {navigation.map((item) => (
            <div key={item.name}>
              {/* Parent Item */}
              {item.children ? (
                <div className="flex items-center gap-1">
                  <Link
                    href={item.href}
                    onClick={onClose}
                    className={cn(
                      'flex-1 flex items-center space-x-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors',
                      isActive(item.href)
                        ? 'bg-[#11446e]/5 text-[#11446e]'
                        : 'text-gray-700 hover:bg-gray-50'
                    )}
                  >
                    <item.icon className={cn('w-5 h-5', item.color)} />
                    <span>{item.name}</span>
                  </Link>
                  <button
                    onClick={() => toggleExpanded(item.name)}
                    className={cn(
                      'px-2 py-2.5 rounded-xl text-sm font-medium transition-colors',
                      isActive(item.href)
                        ? 'text-[#11446e]'
                        : 'text-gray-700 hover:bg-gray-50'
                    )}
                  >
                    <ChevronDown
                      className={cn(
                        'w-4 h-4 transition-transform',
                        expandedItems.includes(item.name) && 'rotate-180'
                      )}
                    />
                  </button>
                </div>
              ) : (
                <Link
                  href={item.href}
                  onClick={onClose}
                  className={cn(
                    'flex items-center space-x-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors',
                    isActive(item.href)
                      ? 'bg-[#11446e]/5 text-[#11446e]'
                      : 'text-gray-700 hover:bg-gray-50'
                  )}
                >
                  <item.icon className={cn('w-5 h-5', item.color)} />
                  <span>{item.name}</span>
                </Link>
              )}

              {/* Children Items */}
              {item.children && expandedItems.includes(item.name) && (
                <div className="ml-4 mt-1 space-y-1 border-l-2 border-gray-200 pl-4">
                  {item.children.map((child) => (
                    <Link
                      key={child.name}
                      href={child.href}
                      onClick={onClose}
                      className={cn(
                        'flex items-center space-x-3 px-3 py-2 rounded-xl text-sm transition-colors',
                        isActive(child.href)
                          ? 'bg-[#11446e]/5 text-[#11446e] font-medium'
                          : 'text-gray-600 hover:bg-gray-50'
                      )}
                    >
                      <child.icon className={cn('w-4 h-4', child.color)} />
                      <span className="flex-1">{child.name}</span>
                      {/* Badge for pending classifications */}
                      {child.href === '/invoices/classification' && pendingClassifications > 0 && (
                        <span className="px-2 py-0.5 text-xs font-semibold bg-warning-100 text-warning-700 rounded-full">
                          {pendingClassifications}
                        </span>
                      )}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200">
          <div className="px-3 py-2.5 bg-gradient-to-br from-[#11446e]/10 to-[#0d3454]/5 rounded-xl border border-[#11446e]/10">
            <p className="text-xs font-semibold text-[#11446e]">
              ContaFlow v2.0
            </p>
            <p className="text-xs text-gray-600 mt-0.5">
              Sistema Inteligente
            </p>
          </div>
        </div>
      </aside>
    </>
  );
}

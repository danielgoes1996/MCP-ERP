/**
 * Header Component
 *
 * Top navigation bar with user menu and notifications
 */

'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import { useAuth } from '@/lib/hooks/useAuth';
import {
  Bell,
  User,
  LogOut,
  Settings,
  Building2,
  ChevronDown,
  Menu,
} from 'lucide-react';
import { cn } from '@/lib/utils/cn';

interface HeaderProps {
  onMenuClick?: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  const router = useRouter();
  const { user, tenant } = useAuthStore();
  const { logout } = useAuth();
  const [showUserMenu, setShowUserMenu] = useState(false);

  const handleLogout = async () => {
    await logout();
  };

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
      <div className="flex items-center justify-between px-6 py-4">
        {/* Left side - Menu button and Logo */}
        <div className="flex items-center space-x-4">
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 rounded-lg hover:bg-gray-100 transition-colors"
            aria-label="Toggle menu"
          >
            <Menu className="w-6 h-6 text-gray-600" />
          </button>

          <div className="flex items-center space-x-3">
            {tenant && (
              <div className="flex items-center space-x-2 px-3 py-1.5 bg-[#60b97b]/10 rounded-xl">
                <Building2 className="w-4 h-4 text-[#60b97b]" />
                <span className="text-sm font-medium text-gray-900">
                  {tenant.name}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Right side - Notifications and User menu */}
        <div className="flex items-center space-x-4">
          {/* Notifications */}
          <button
            className="relative p-2 rounded-xl hover:bg-gray-50 transition-colors"
            aria-label="Notifications"
          >
            <Bell className="w-5 h-5 text-gray-600" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[#60b97b] rounded-full"></span>
          </button>

          {/* User Menu */}
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex items-center space-x-3 px-3 py-2 rounded-xl hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center space-x-2">
                <div className="w-8 h-8 bg-gradient-to-br from-[#11446e] to-[#0d3454] rounded-full flex items-center justify-center">
                  <User className="w-4 h-4 text-white" />
                </div>
                <div className="hidden md:block text-left">
                  <p className="text-sm font-medium text-gray-900">
                    {user?.full_name || user?.username}
                  </p>
                  <p className="text-xs text-gray-500 capitalize">
                    {user?.role}
                  </p>
                </div>
              </div>
              <ChevronDown
                className={cn(
                  'w-4 h-4 text-gray-400 transition-transform',
                  showUserMenu && 'rotate-180'
                )}
              />
            </button>

            {/* User Menu Dropdown */}
            {showUserMenu && (
              <>
                {/* Backdrop */}
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setShowUserMenu(false)}
                />

                {/* Dropdown Menu */}
                <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-lg border border-gray-200 py-2 z-50">
                  {/* User Info */}
                  <div className="px-4 py-3 border-b border-gray-100">
                    <p className="text-sm font-medium text-gray-900">
                      {user?.full_name}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {user?.email}
                    </p>
                  </div>

                  {/* Menu Items */}
                  <div className="py-2">
                    <button
                      onClick={() => {
                        router.push('/settings/profile');
                        setShowUserMenu(false);
                      }}
                      className="w-full flex items-center space-x-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                    >
                      <User className="w-4 h-4" />
                      <span>Mi Perfil</span>
                    </button>

                    <button
                      onClick={() => {
                        router.push('/settings');
                        setShowUserMenu(false);
                      }}
                      className="w-full flex items-center space-x-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                    >
                      <Settings className="w-4 h-4" />
                      <span>Configuración</span>
                    </button>

                    {user?.role === 'admin' && (
                      <button
                        onClick={() => {
                          router.push('/admin/company');
                          setShowUserMenu(false);
                        }}
                        className="w-full flex items-center space-x-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                      >
                        <Building2 className="w-4 h-4" />
                        <span>Gestión de Empresa</span>
                      </button>
                    )}
                  </div>

                  {/* Logout */}
                  <div className="border-t border-gray-100 pt-2">
                    <button
                      onClick={handleLogout}
                      className="w-full flex items-center space-x-3 px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                    >
                      <LogOut className="w-4 h-4" />
                      <span>Cerrar Sesión</span>
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

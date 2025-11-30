/**
 * Login Page - ContaFlow Enterprise Design System
 * Professional, minimalist, AI-driven authentication
 */

'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuthStore } from '@/stores/auth/useAuthStore';
import {
  Eye,
  EyeOff,
  Mail,
  Lock,
  ArrowRight,
  AlertCircle,
  Sparkles,
  Zap,
  TrendingUp,
  Shield
} from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface TenantOption {
  id: number;
  name: string;
  company_id?: number;
}

export default function LoginPage() {
  const router = useRouter();
  const { isAuthenticated, setUser, setTenant, setTokens, setLoading: setStoreLoading } = useAuthStore();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [availableTenants, setAvailableTenants] = useState<TenantOption[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<number | null>(null);
  const [loadingTenants, setLoadingTenants] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      router.push('/dashboard');
    }
  }, [isAuthenticated, router]);

  // Fetch tenants when email changes and contains @
  useEffect(() => {
    const fetchTenants = async () => {
      if (!email.includes('@')) {
        setAvailableTenants([]);
        setSelectedTenantId(null);
        return;
      }

      try {
        setLoadingTenants(true);
        const response = await fetch(`${API_BASE_URL}/auth/tenants?email=${encodeURIComponent(email)}`);

        if (response.ok) {
          const tenants = await response.json();
          setAvailableTenants(tenants);

          // Auto-select if only one tenant
          if (tenants.length === 1) {
            setSelectedTenantId(tenants[0].id);
          } else if (tenants.length > 1) {
            setSelectedTenantId(null); // Force user to select
          }
        } else {
          setAvailableTenants([]);
          setSelectedTenantId(null);
        }
      } catch (err) {
        console.error('Error fetching tenants:', err);
        setAvailableTenants([]);
        setSelectedTenantId(null);
      } finally {
        setLoadingTenants(false);
      }
    };

    // Debounce: wait 500ms after user stops typing
    const timeoutId = setTimeout(fetchTenants, 500);
    return () => clearTimeout(timeoutId);
  }, [email]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email || !password) {
      setError('Por favor completa todos los campos');
      return;
    }

    // If multiple tenants available, require selection
    if (availableTenants.length > 1 && !selectedTenantId) {
      setError('Por favor selecciona una empresa');
      return;
    }

    try {
      setIsLoading(true);
      setStoreLoading(true);

      // Call login API with form data
      const formData = new URLSearchParams();
      formData.append('username', email); // Backend expects 'username' field
      formData.append('password', password);

      // Send tenant_id if available (either auto-selected or user-selected)
      if (selectedTenantId) {
        formData.append('tenant_id', selectedTenantId.toString());
      }
      // Otherwise, backend will auto-determine from user's default tenant

      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString(),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Error al iniciar sesión');
      }

      const data = await response.json();

      // Update store
      setUser(data.user);
      setTenant(data.tenant);
      setTokens(data.access_token, data.refresh_token);

      // Save tokens to localStorage for API client
      localStorage.setItem('auth_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      // Redirect
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Error al iniciar sesión. Verifica tus credenciales.');
    } finally {
      setIsLoading(false);
      setStoreLoading(false);
    }
  };

  if (isAuthenticated) {
    return null;
  }

  return (
    <div className="min-h-screen flex">
      {/* Left Panel - Login Form */}
      <div className="flex-1 flex flex-col justify-center px-8 sm:px-12 lg:px-16 xl:px-24 py-12 bg-white">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md mx-auto"
        >
          {/* Logo */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="mb-12"
          >
            <Image
              src="/ContaFlow.png"
              alt="ContaFlow"
              width={240}
              height={60}
              className="h-12 w-auto"
              priority
            />
          </motion.div>

          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="mb-10"
          >
            <h1 className="text-3xl font-bold text-gray-900 mb-3">
              Iniciar sesión
            </h1>
            <p className="text-base text-gray-600">
              Accede a tu plataforma de gestión financiera inteligente
            </p>
          </motion.div>

          {/* Error Alert */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10, height: 0 }}
                animate={{ opacity: 1, y: 0, height: 'auto' }}
                exit={{ opacity: 0, y: -10, height: 0 }}
                className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3"
              >
                <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-red-800 leading-relaxed">{error}</p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Email Field */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              <label
                htmlFor="email"
                className="block text-sm font-semibold text-gray-900 mb-2"
              >
                Email
              </label>
              <div className="relative">
                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  id="email"
                  type="text"
                  placeholder="tu@empresa.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full pl-12 pr-4 py-3.5 bg-white border border-gray-300 rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:border-[#11446e] focus:ring-2 focus:ring-[#11446e]/10 transition-all"
                />
              </div>
            </motion.div>

            {/* Password Field */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.35 }}
            >
              <label
                htmlFor="password"
                className="block text-sm font-semibold text-gray-900 mb-2"
              >
                Contraseña
              </label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full pl-12 pr-14 py-3.5 bg-white border border-gray-300 rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:border-[#11446e] focus:ring-2 focus:ring-[#11446e]/10 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </motion.div>

            {/* Tenant Selection - Only show if multiple tenants found */}
            <AnimatePresence>
              {availableTenants.length > 1 && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ delay: 0.4 }}
                >
                  <label
                    htmlFor="tenant"
                    className="block text-sm font-semibold text-gray-900 mb-2"
                  >
                    Empresa
                  </label>
                  <div className="relative">
                    <select
                      id="tenant"
                      value={selectedTenantId || ''}
                      onChange={(e) => setSelectedTenantId(Number(e.target.value))}
                      className="w-full px-4 py-3.5 bg-white border border-gray-300 rounded-xl text-gray-900 focus:outline-none focus:border-[#11446e] focus:ring-2 focus:ring-[#11446e]/10 transition-all appearance-none cursor-pointer"
                    >
                      <option value="">Selecciona una empresa...</option>
                      {availableTenants.map((tenant) => (
                        <option key={tenant.id} value={tenant.id}>
                          {tenant.name}
                        </option>
                      ))}
                    </select>
                    <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none">
                      <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </div>
                  <p className="mt-2 text-xs text-gray-500">
                    Tienes acceso a {availableTenants.length} empresas
                  </p>
                </motion.div>
              )}

              {/* Show single tenant auto-detected */}
              {availableTenants.length === 1 && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ delay: 0.4 }}
                  className="p-3 bg-green-50 border border-green-200 rounded-xl"
                >
                  <p className="text-sm text-green-800 flex items-center gap-2">
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    <span className="font-medium">{availableTenants[0].name}</span>
                  </p>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Forgot Password Link */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.4 }}
              className="flex justify-end"
            >
              <a
                href="/forgot-password"
                className="text-sm text-[#11446e] hover:text-[#0d3454] font-medium transition-colors"
              >
                ¿Olvidaste tu contraseña?
              </a>
            </motion.div>

            {/* Submit Button */}
            <motion.button
              type="submit"
              disabled={isLoading || !email || !password}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.45 }}
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
              className="w-full py-3.5 bg-gradient-to-r from-[#11446e] to-[#0d3454] text-white font-semibold rounded-xl shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2 group"
            >
              {isLoading ? (
                <>
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                    className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full"
                  />
                  <span>Iniciando sesión...</span>
                </>
              ) : (
                <>
                  <span>Continuar</span>
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-0.5 transition-transform" />
                </>
              )}
            </motion.button>
          </form>

          {/* Register Link */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="mt-6 text-center"
          >
            <p className="text-sm text-gray-600">
              ¿No tienes cuenta?{' '}
              <a
                href="/register"
                className="text-[#11446e] hover:text-[#0d3454] font-semibold transition-colors"
              >
                Regístrate aquí
              </a>
            </p>
          </motion.div>

          {/* Footer */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
            className="mt-12 pt-6 border-t border-gray-200 text-center"
          >
            <p className="text-sm text-gray-500">
              <span className="text-[#11446e] font-semibold">
                ContaFlow
              </span>
              {' '}· Plataforma de gestión empresarial
            </p>
          </motion.div>
        </motion.div>

        {/* Bottom Badge */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="mt-auto pt-8 text-center"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-[#11446e]/5 to-[#60b97b]/5 rounded-full border border-[#11446e]/10">
            <Sparkles className="w-4 h-4 text-[#60b97b]" />
            <span className="text-sm font-medium text-gray-700">
              Powered by AI
            </span>
          </div>
        </motion.div>
      </div>

      {/* Right Panel - Feature Showcase */}
      <div className="hidden lg:flex flex-1 bg-gradient-to-br from-[#11446e] via-[#0d3454] to-[#0a2740] relative overflow-hidden">
        {/* Subtle Grid Pattern */}
        <div className="absolute inset-0 opacity-[0.03]">
          <div
            className="absolute inset-0"
            style={{
              backgroundImage: `
                linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)
              `,
              backgroundSize: '100px 100px',
            }}
          />
        </div>

        {/* Gradient Orbs */}
        <motion.div
          animate={{
            scale: [1, 1.2, 1],
            opacity: [0.15, 0.25, 0.15],
          }}
          transition={{
            duration: 8,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          className="absolute top-20 right-20 w-96 h-96 bg-[#60b97b] rounded-full blur-[120px]"
        />
        <motion.div
          animate={{
            scale: [1, 1.3, 1],
            opacity: [0.1, 0.2, 0.1],
          }}
          transition={{
            duration: 10,
            repeat: Infinity,
            ease: 'easeInOut',
            delay: 2,
          }}
          className="absolute bottom-20 left-20 w-[30rem] h-[30rem] bg-[#11446e] rounded-full blur-[120px]"
        />

        {/* Content */}
        <div className="relative z-10 flex flex-col justify-center px-16 xl:px-24 text-white">
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
          >
            {/* Badge */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="inline-flex items-center gap-2 px-4 py-2 bg-white/10 backdrop-blur-xl rounded-full border border-white/20 mb-8"
            >
              <Shield className="w-4 h-4" />
              <span className="text-sm font-semibold">
                Sistema Empresarial Seguro
              </span>
            </motion.div>

            {/* Main Heading */}
            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="text-5xl font-bold mb-6 leading-tight"
            >
              Gestión financiera
              <span className="block text-[#60b97b]">potenciada por IA</span>
            </motion.h2>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.7 }}
              className="text-xl text-white/80 mb-12 leading-relaxed max-w-lg"
            >
              Automatiza clasificación, conciliación y reportes con inteligencia artificial de última generación.
            </motion.p>

            {/* Features List */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.8 }}
              className="space-y-5"
            >
              {[
                {
                  icon: Sparkles,
                  title: 'Clasificación automática',
                  description: '98% de precisión con machine learning',
                },
                {
                  icon: Zap,
                  title: 'Automatización RPA',
                  description: 'Descarga de facturas sin intervención',
                },
                {
                  icon: TrendingUp,
                  title: 'Análisis predictivo',
                  description: 'Insights financieros en tiempo real',
                },
              ].map((feature, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.9 + index * 0.1 }}
                  className="flex items-start gap-4"
                >
                  <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-white/10 backdrop-blur-sm flex items-center justify-center">
                    <feature.icon className="w-5 h-5 text-[#60b97b]" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-lg mb-1">
                      {feature.title}
                    </h3>
                    <p className="text-white/70 text-sm leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                </motion.div>
              ))}
            </motion.div>

            {/* Stats */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.2 }}
              className="mt-16 grid grid-cols-3 gap-8"
            >
              {[
                { value: '98%', label: 'Precisión' },
                { value: '10x', label: 'Velocidad' },
                { value: '24/7', label: 'Disponible' },
              ].map((stat, index) => (
                <div key={index} className="text-center">
                  <div className="text-4xl font-bold text-[#60b97b] mb-2">
                    {stat.value}
                  </div>
                  <div className="text-sm text-white/60 font-medium">
                    {stat.label}
                  </div>
                </div>
              ))}
            </motion.div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}

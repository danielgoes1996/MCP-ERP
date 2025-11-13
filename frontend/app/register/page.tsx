/**
 * Register Page - ContaFlow Enterprise Design System
 * Professional, minimalist registration flow
 */

'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '@/lib/hooks/useAuth';
import {
  Eye,
  EyeOff,
  Building2,
  Mail,
  Lock,
  User,
  ArrowRight,
  AlertCircle,
  Sparkles,
  CheckCircle,
  Shield,
  Zap,
} from 'lucide-react';

export default function RegisterPage() {
  const router = useRouter();
  const { register, error, isLoading, isAuthenticated } = useAuth();

  // User fields
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Company fields
  const [companyName, setCompanyName] = useState('');
  const [companyDescription, setCompanyDescription] = useState('');

  // Validation
  const [passwordError, setPasswordError] = useState('');

  useEffect(() => {
    if (isAuthenticated) {
      router.push('/dashboard');
    }
  }, [isAuthenticated, router]);

  const validatePassword = (pass: string, confirm: string) => {
    if (pass !== confirm) {
      setPasswordError('Las contraseñas no coinciden');
      return false;
    }
    if (pass.length < 8) {
      setPasswordError('La contraseña debe tener al menos 8 caracteres');
      return false;
    }
    setPasswordError('');
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validatePassword(password, confirmPassword)) {
      return;
    }

    register({
      username,
      email,
      password,
      full_name: fullName,
      company_name: companyName,
      company_description: companyDescription,
    });
  };

  return (
    <div className="min-h-screen flex">
      {/* Left Panel - Registration Form */}
      <div className="flex-1 flex flex-col justify-center px-8 sm:px-12 lg:px-16 xl:px-24 py-12 bg-white overflow-y-auto">
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
              Crear cuenta
            </h1>
            <p className="text-base text-gray-600">
              Comienza tu transformación financiera con IA
            </p>
          </motion.div>

          {/* Error Alert */}
          <AnimatePresence>
            {(error || passwordError) && (
              <motion.div
                initial={{ opacity: 0, y: -10, height: 0 }}
                animate={{ opacity: 1, y: 0, height: 'auto' }}
                exit={{ opacity: 0, y: -10, height: 0 }}
                className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3"
              >
                <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-red-800 leading-relaxed">
                  {error || passwordError}
                </p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Personal Information Section */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="space-y-6"
            >
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 mb-4">
                <User className="w-4 h-4 text-[#11446e]" />
                <span>Información Personal</span>
              </div>

              {/* Full Name */}
              <div>
                <label
                  htmlFor="fullName"
                  className="block text-sm font-semibold text-gray-900 mb-2"
                >
                  Nombre Completo
                </label>
                <div className="relative">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    id="fullName"
                    type="text"
                    placeholder="Juan Pérez González"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    required
                    className="w-full pl-12 pr-4 py-3.5 bg-white border border-gray-300 rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:border-[#11446e] focus:ring-2 focus:ring-[#11446e]/10 transition-all"
                  />
                </div>
              </div>

              {/* Email and Username */}
              <div className="grid grid-cols-1 gap-6">
                <div>
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
                      type="email"
                      placeholder="tu@empresa.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      className="w-full pl-12 pr-4 py-3.5 bg-white border border-gray-300 rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:border-[#11446e] focus:ring-2 focus:ring-[#11446e]/10 transition-all"
                    />
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="username"
                    className="block text-sm font-semibold text-gray-900 mb-2"
                  >
                    Usuario
                  </label>
                  <div className="relative">
                    <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      id="username"
                      type="text"
                      placeholder="juanperez"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      required
                      className="w-full pl-12 pr-4 py-3.5 bg-white border border-gray-300 rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:border-[#11446e] focus:ring-2 focus:ring-[#11446e]/10 transition-all"
                    />
                  </div>
                </div>
              </div>

              {/* Password Fields */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
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
                </div>

                <div>
                  <label
                    htmlFor="confirmPassword"
                    className="block text-sm font-semibold text-gray-900 mb-2"
                  >
                    Confirmar
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      id="confirmPassword"
                      type={showPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      required
                      className="w-full pl-12 pr-4 py-3.5 bg-white border border-gray-300 rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:border-[#11446e] focus:ring-2 focus:ring-[#11446e]/10 transition-all"
                    />
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Company Information Section */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="pt-6 border-t border-gray-200 space-y-6"
            >
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 mb-4">
                <Building2 className="w-4 h-4 text-[#11446e]" />
                <span>Información de la Empresa</span>
              </div>

              {/* Company Name */}
              <div>
                <label
                  htmlFor="companyName"
                  className="block text-sm font-semibold text-gray-900 mb-2"
                >
                  Nombre de la Empresa
                </label>
                <div className="relative">
                  <Building2 className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    id="companyName"
                    type="text"
                    placeholder="Mi Empresa S.A. de C.V."
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    required
                    className="w-full pl-12 pr-4 py-3.5 bg-white border border-gray-300 rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:border-[#11446e] focus:ring-2 focus:ring-[#11446e]/10 transition-all"
                  />
                </div>
              </div>

              {/* Company Description */}
              <div>
                <label
                  htmlFor="companyDescription"
                  className="block text-sm font-semibold text-gray-900 mb-2"
                >
                  Descripción <span className="text-gray-400 font-normal">(opcional)</span>
                </label>
                <textarea
                  id="companyDescription"
                  placeholder="Describe brevemente tu empresa..."
                  value={companyDescription}
                  onChange={(e) => setCompanyDescription(e.target.value)}
                  rows={3}
                  className="w-full px-4 py-3.5 bg-white border border-gray-300 rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:border-[#11446e] focus:ring-2 focus:ring-[#11446e]/10 transition-all resize-none"
                />
              </div>
            </motion.div>

            {/* Submit Button */}
            <motion.button
              type="submit"
              disabled={isLoading || !username || !email || !password || !confirmPassword || !fullName || !companyName}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
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
                  <span>Creando cuenta...</span>
                </>
              ) : (
                <>
                  <span>Crear Cuenta</span>
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-0.5 transition-transform" />
                </>
              )}
            </motion.button>
          </form>

          {/* Footer */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
            className="mt-8 text-center"
          >
            <p className="text-sm text-gray-500">
              ¿Ya tienes cuenta?{' '}
              <a
                href="/login"
                className="text-[#11446e] font-semibold hover:text-[#0d3454] transition-colors"
              >
                Iniciar sesión
              </a>
            </p>
          </motion.div>
        </motion.div>

        {/* Bottom Badge */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7 }}
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
                Plataforma Segura y Confiable
              </span>
            </motion.div>

            {/* Main Heading */}
            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="text-5xl font-bold mb-6 leading-tight"
            >
              Únete a la revolución
              <span className="block text-[#60b97b]">financiera con IA</span>
            </motion.h2>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.7 }}
              className="text-xl text-white/80 mb-12 leading-relaxed max-w-lg"
            >
              Crea tu cuenta y comienza a automatizar tu gestión financiera en minutos. Sin contratos largos, sin instalaciones complejas.
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
                  icon: CheckCircle,
                  title: 'Setup instantáneo',
                  description: 'Empieza a usar el sistema en menos de 5 minutos',
                },
                {
                  icon: Shield,
                  title: 'Datos seguros',
                  description: 'Cifrado de nivel bancario y aislamiento total',
                },
                {
                  icon: Zap,
                  title: 'Sin compromisos',
                  description: 'Cancela cuando quieras, sin penalizaciones',
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

            {/* Trust Indicators */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.2 }}
              className="mt-16 grid grid-cols-3 gap-8"
            >
              {[
                { value: '500+', label: 'Empresas' },
                { value: '99.9%', label: 'Uptime' },
                { value: 'ISO', label: 'Certificado' },
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

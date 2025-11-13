# 🚀 ContaFlow Design System V3 - AI-Driven Modern Interface

Sistema de diseño moderno, minimalista y profesional con estética AI-driven.

---

## 🎨 Nueva Paleta de Colores

### Primary - Slate Professional
**Base: `#0f172a`** (Slate 900)

```tsx
// Tonos de gris slate moderno
bg-slate-50    // #f8fafc - Backgrounds
bg-slate-100   // #f1f5f9 - Subtle cards
bg-slate-200   // #e2e8f0 - Borders
bg-slate-600   // #475569 - Secondary text
bg-slate-900   // #0f172a - Primary text & UI ⭐
```

### Accent - Electric Blue (AI Accent)
**Base: `#3b82f6`** (Blue 500)

```tsx
// Para elementos interactivos y AI
bg-blue-500    // #3b82f6 - Primary actions ⭐
bg-blue-600    // #2563eb - Hover states
bg-cyan-500    // #06b6d4 - AI indicators
```

### Success - Emerald
**Base: `#10b981`** (Emerald 500)

```tsx
bg-emerald-500 // #10b981 - Success states ⭐
bg-emerald-600 // #059669 - Success hover
```

### Semantic Colors
```tsx
// Warning
bg-amber-500   // #f59e0b

// Error
bg-red-500     // #ef4444

// Info
bg-sky-500     // #0ea5e9
```

---

## ✨ Efectos Modernos

### Glass Morphism (Cristal)
```tsx
<div className="backdrop-blur-xl bg-white/80 dark:bg-slate-900/80
                border border-white/20 shadow-2xl">
  Card con efecto cristal
</div>
```

### Subtle Glow (AI Accent)
```tsx
// Glow sutil para elementos AI
<div className="shadow-[0_0_15px_rgba(59,130,246,0.1)]
                hover:shadow-[0_0_30px_rgba(59,130,246,0.2)]">
  Elemento con glow AI
</div>
```

### Gradient Mesh Background
```tsx
<div className="relative overflow-hidden">
  {/* Mesh gradient background */}
  <div className="absolute inset-0 bg-gradient-to-br from-blue-50 via-white to-cyan-50
                  dark:from-slate-900 dark:via-slate-800 dark:to-slate-900" />

  {/* Subtle animated orbs */}
  <div className="absolute top-20 left-20 w-72 h-72 bg-blue-400/10 rounded-full
                  blur-3xl animate-pulse" />
  <div className="absolute bottom-20 right-20 w-96 h-96 bg-cyan-400/10 rounded-full
                  blur-3xl animate-pulse delay-1000" />
</div>
```

---

## 🎯 Componentes Modernos

### Modern Card
```tsx
<div className="group relative">
  {/* Background with subtle gradient */}
  <div className="absolute inset-0 bg-gradient-to-br from-slate-50 to-white
                  dark:from-slate-800 dark:to-slate-900 rounded-2xl" />

  {/* Border with gradient on hover */}
  <div className="absolute inset-0 rounded-2xl border border-slate-200/50
                  dark:border-slate-700/50
                  group-hover:border-blue-500/50 transition-colors" />

  {/* Content */}
  <div className="relative p-6">
    <div className="flex items-start justify-between">
      <div>
        <p className="text-sm text-slate-600 dark:text-slate-400 font-medium">
          Total Revenue
        </p>
        <p className="text-3xl font-semibold text-slate-900 dark:text-white mt-2">
          $45,231.89
        </p>
        <p className="text-sm text-emerald-600 dark:text-emerald-400 mt-2 flex items-center gap-1">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
          <span>+12.5%</span>
        </p>
      </div>

      {/* AI Badge */}
      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full
                      bg-blue-500/10 border border-blue-500/20">
        <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
        <span className="text-xs font-medium text-blue-600 dark:text-blue-400">AI</span>
      </div>
    </div>
  </div>
</div>
```

### Modern Button
```tsx
// Primary Button
<button className="group relative inline-flex items-center justify-center gap-2
                   px-6 py-2.5 rounded-xl
                   bg-slate-900 dark:bg-white
                   text-white dark:text-slate-900
                   text-sm font-medium
                   hover:bg-slate-800 dark:hover:bg-slate-50
                   transition-all duration-200
                   shadow-lg shadow-slate-900/10 dark:shadow-white/10
                   hover:shadow-xl hover:-translate-y-0.5">
  <span>Create Invoice</span>
  <svg className="w-4 h-4 group-hover:translate-x-0.5 transition-transform"
       fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
  </svg>
</button>

// Secondary Button (Glass)
<button className="inline-flex items-center justify-center gap-2
                   px-6 py-2.5 rounded-xl
                   backdrop-blur-xl bg-white/50 dark:bg-slate-800/50
                   border border-slate-200/50 dark:border-slate-700/50
                   text-slate-900 dark:text-white
                   text-sm font-medium
                   hover:bg-white/80 dark:hover:bg-slate-800/80
                   hover:border-blue-500/50
                   transition-all duration-200">
  <span>Cancel</span>
</button>
```

### Modern Input
```tsx
<div className="relative">
  {/* Floating label */}
  <input
    type="text"
    id="email"
    placeholder=" "
    className="peer w-full px-4 py-3 rounded-xl
               bg-white dark:bg-slate-900
               border border-slate-200 dark:border-slate-700
               text-slate-900 dark:text-white
               placeholder-transparent
               focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10
               transition-all duration-200
               outline-none"
  />
  <label
    htmlFor="email"
    className="absolute left-4 -top-2.5 px-1
               bg-white dark:bg-slate-900
               text-xs font-medium text-slate-600 dark:text-slate-400
               peer-placeholder-shown:text-base
               peer-placeholder-shown:top-3
               peer-placeholder-shown:text-slate-400
               peer-focus:-top-2.5 peer-focus:text-xs peer-focus:text-blue-600
               transition-all duration-200"
  >
    Email address
  </label>
</div>
```

### Modern Dropdown (Select)
```tsx
<div className="relative group">
  <button className="w-full inline-flex items-center justify-between gap-2
                     px-4 py-3 rounded-xl
                     backdrop-blur-xl bg-white dark:bg-slate-900
                     border border-slate-200 dark:border-slate-700
                     text-slate-900 dark:text-white text-sm
                     hover:border-blue-500/50
                     transition-all duration-200">
    <span>Select option</span>
    <svg className="w-4 h-4 text-slate-400 group-hover:text-blue-500 transition-colors"
         fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  </button>

  {/* Dropdown menu with glass effect */}
  <div className="absolute z-50 w-full mt-2 py-2 rounded-xl
                  backdrop-blur-2xl bg-white/95 dark:bg-slate-900/95
                  border border-slate-200/50 dark:border-slate-700/50
                  shadow-2xl shadow-slate-900/10 dark:shadow-black/50
                  opacity-0 invisible group-focus-within:opacity-100 group-focus-within:visible
                  transition-all duration-200">
    <button className="w-full px-4 py-2.5 text-left text-sm
                       text-slate-900 dark:text-white
                       hover:bg-slate-100/50 dark:hover:bg-slate-800/50
                       transition-colors">
      Option 1
    </button>
    <button className="w-full px-4 py-2.5 text-left text-sm
                       text-slate-900 dark:text-white
                       hover:bg-slate-100/50 dark:hover:bg-slate-800/50
                       transition-colors">
      Option 2
    </button>
  </div>
</div>
```

### Modern Badge
```tsx
// Status Badge - Success
<span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full
               backdrop-blur-xl bg-emerald-500/10
               border border-emerald-500/20
               text-xs font-medium text-emerald-700 dark:text-emerald-400">
  <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
  Active
</span>

// AI Processing Badge
<span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full
               backdrop-blur-xl bg-blue-500/10
               border border-blue-500/20
               text-xs font-medium text-blue-700 dark:text-blue-400">
  <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
  AI Processing
</span>
```

### AI Indicator
```tsx
<div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full
                backdrop-blur-xl bg-gradient-to-r from-blue-500/10 to-cyan-500/10
                border border-blue-500/20">
  {/* Animated gradient border */}
  <div className="relative">
    <div className="absolute inset-0 rounded-full bg-gradient-to-r from-blue-500 to-cyan-500
                    blur-sm opacity-50 animate-pulse" />
    <svg className="relative w-4 h-4 text-blue-600 dark:text-blue-400"
         fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M13 10V3L4 14h7v7l9-11h-7z" />
    </svg>
  </div>
  <span className="text-xs font-medium bg-gradient-to-r from-blue-600 to-cyan-600
                   dark:from-blue-400 dark:to-cyan-400 bg-clip-text text-transparent">
    AI-Powered
  </span>
</div>
```

---

## 🎨 Iconografía Moderna

### Usar Lucide Icons con stroke más delgado
```tsx
import { icons } from 'lucide-react';

// Configuración global para iconos más delgados y modernos
<Icon className="w-5 h-5" strokeWidth={1.5} />

// Ejemplos
<FileText strokeWidth={1.5} className="w-5 h-5 text-slate-600" />
<Sparkles strokeWidth={1.5} className="w-5 h-5 text-blue-500" />
<Brain strokeWidth={1.5} className="w-5 h-5 text-cyan-500" />
```

---

## 🌐 Layout Moderno

### Sidebar Moderno
```tsx
<aside className="w-64 h-screen fixed left-0 top-0
                  backdrop-blur-2xl bg-white/80 dark:bg-slate-900/80
                  border-r border-slate-200/50 dark:border-slate-800/50">
  {/* Logo */}
  <div className="p-6 border-b border-slate-200/50 dark:border-slate-800/50">
    <div className="flex items-center gap-3">
      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500
                      flex items-center justify-center">
        <span className="text-white text-sm font-bold">CF</span>
      </div>
      <span className="text-lg font-semibold text-slate-900 dark:text-white">
        ContaFlow
      </span>
    </div>
  </div>

  {/* Navigation */}
  <nav className="p-4 space-y-1">
    {/* Active item */}
    <a href="#" className="flex items-center gap-3 px-4 py-3 rounded-xl
                           bg-slate-100 dark:bg-slate-800
                           text-slate-900 dark:text-white
                           border border-slate-200/50 dark:border-slate-700/50
                           group">
      <FileText strokeWidth={1.5} className="w-5 h-5" />
      <span className="text-sm font-medium">Invoices</span>
      <div className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-500" />
    </a>

    {/* Inactive item */}
    <a href="#" className="flex items-center gap-3 px-4 py-3 rounded-xl
                           text-slate-600 dark:text-slate-400
                           hover:bg-slate-100/50 dark:hover:bg-slate-800/50
                           hover:text-slate-900 dark:hover:text-white
                           transition-all duration-200 group">
      <BarChart3 strokeWidth={1.5} className="w-5 h-5" />
      <span className="text-sm font-medium">Analytics</span>
    </a>
  </nav>
</aside>
```

### Header Moderno
```tsx
<header className="sticky top-0 z-40 w-full
                   backdrop-blur-2xl bg-white/80 dark:bg-slate-900/80
                   border-b border-slate-200/50 dark:border-slate-800/50">
  <div className="container mx-auto px-6 py-4">
    <div className="flex items-center justify-between">
      {/* Search */}
      <div className="relative flex-1 max-w-md">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4
                          text-slate-400" strokeWidth={1.5} />
        <input
          type="search"
          placeholder="Search..."
          className="w-full pl-11 pr-4 py-2.5 rounded-xl
                     backdrop-blur-xl bg-white dark:bg-slate-900
                     border border-slate-200/50 dark:border-slate-800/50
                     text-sm text-slate-900 dark:text-white
                     placeholder-slate-400
                     focus:border-blue-500/50 focus:ring-4 focus:ring-blue-500/10
                     transition-all duration-200"
        />
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 ml-6">
        {/* Notifications */}
        <button className="relative p-2.5 rounded-xl
                          hover:bg-slate-100 dark:hover:bg-slate-800
                          transition-colors">
          <Bell strokeWidth={1.5} className="w-5 h-5 text-slate-600 dark:text-slate-400" />
          <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-blue-500
                          border-2 border-white dark:border-slate-900" />
        </button>

        {/* Profile */}
        <button className="flex items-center gap-3 px-3 py-2 rounded-xl
                          hover:bg-slate-100 dark:hover:bg-slate-800
                          transition-colors">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500" />
          <span className="text-sm font-medium text-slate-900 dark:text-white">
            John Doe
          </span>
        </button>
      </div>
    </div>
  </div>
</header>
```

---

## 🎯 Reglas de Diseño

### ✅ DO
- Usar glassmorphism con moderación
- Mantener jerarquía visual clara
- Usar espaciado consistente (múltiplos de 4)
- Iconos con strokeWidth={1.5} para look moderno
- Transiciones suaves (200-300ms)
- Sombras sutiles, no dramáticas
- Indicadores AI discretos pero visibles

### ❌ DON'T
- Colores saturados o neón brillante
- Sombras muy marcadas
- Iconos "filled" o muy gruesos
- Animaciones exageradas
- Demasiados gradientes
- Bordes muy gruesos (max 1-2px)

---

## 🚀 Migración desde V2

1. **Colores**: Reemplazar `primary-500` (#11446e) → `slate-900` + `blue-500` para accents
2. **Botones**: Actualizar a diseño más plano con hover sutiles
3. **Cards**: Agregar glassmorphism y bordes sutiles
4. **Iconos**: Cambiar todos a strokeWidth={1.5}
5. **Inputs**: Implementar floating labels
6. **Dropdowns**: Agregar efectos de blur

---

**Versión:** 3.0 - AI-Driven Modern Interface
**Última actualización:** Noviembre 2025

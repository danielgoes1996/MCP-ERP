# 🎨 ContaFlow Design System

Sistema de diseño completo con los colores corporativos de ContaFlow.

---

## 🎯 Colores Principales

### Primary - Azul Marino Profesional
**Base: `#11446E`**

```tsx
// Uso en componentes
<div className="bg-primary-500 text-white">
  Azul marino - Color principal de ContaFlow
</div>

// Gradiente de tonos
bg-primary-50   // #e8f0f7 - Muy claro (fondos)
bg-primary-100  // #d1e1ef - Claro
bg-primary-200  // #a3c3df
bg-primary-300  // #75a5cf
bg-primary-400  // #4787bf
bg-primary-500  // #11446E - Base ⭐
bg-primary-600  // #0e3a5c - Oscuro
bg-primary-700  // #0b2f4a - Muy oscuro
bg-primary-800  // #082538
bg-primary-900  // #051a26
```

**Cuándo usar:**
- ✅ Botones principales (CTAs)
- ✅ Headers y navegación
- ✅ Links importantes
- ✅ Títulos principales

---

### Secondary - Verde Menta/Éxito
**Base: `#60B97B`**

```tsx
// Uso en componentes
<div className="bg-secondary-500 text-white">
  Verde - Color de éxito y crecimiento
</div>

// Gradiente de tonos
bg-secondary-50   // #f0f9f4 - Muy claro
bg-secondary-100  // #e1f3e9
bg-secondary-200  // #c3e7d3
bg-secondary-300  // #a5dbbd
bg-secondary-400  // #87cfa7
bg-secondary-500  // #60B97B - Base ⭐
bg-secondary-600  // #4d9462
bg-secondary-700  // #3a6f4a
bg-secondary-800  // #274a31
bg-secondary-900  // #142519
```

**Cuándo usar:**
- ✅ Estados de éxito
- ✅ Botones secundarios
- ✅ Badges de completado
- ✅ Métricas positivas (ingresos, ganancias)
- ✅ Iconos de confirmación

---

## 🎨 Gradientes Premium

### Gradiente Primary (Azul degradado)
```tsx
<div className="bg-gradient-primary text-white p-6 rounded-xl">
  Gradiente azul - Profesional y elegante
</div>

// O usando Tailwind directamente
<div className="bg-gradient-to-r from-primary-500 to-primary-400">
```

### Gradiente Secondary (Verde degradado)
```tsx
<div className="bg-gradient-secondary text-white p-6 rounded-xl">
  Gradiente verde - Éxito y crecimiento
</div>
```

### Gradiente Premium (Azul → Verde)
```tsx
<div className="bg-gradient-premium text-white p-6 rounded-xl">
  Gradiente completo - Elementos especiales
</div>

// Versión extendida
<div className="bg-gradient-to-r from-primary-500 via-primary-400 to-secondary-500">
```

---

## ✨ Efectos Especiales

### Glow Effect (Resplandor)
```tsx
// Glow azul
<button className="shadow-glow-primary hover:shadow-glow-premium transition-shadow">
  Botón con glow
</button>

// Glow verde
<div className="shadow-glow-secondary">
  Card con resplandor verde
</div>

// Glow premium (azul + verde)
<div className="shadow-glow-premium">
  Elemento premium con doble glow
</div>
```

### Animación de Glow
```tsx
<div className="animate-glow bg-primary-500 rounded-lg p-6">
  Elemento que pulsa con resplandor
</div>
```

### Shimmer Effect (Brillo deslizante)
```tsx
<div className="relative overflow-hidden">
  <div className="absolute inset-0 bg-shimmer bg-[length:200%_100%] animate-shimmer" />
  <div className="relative">Contenido con shimmer</div>
</div>
```

---

## 🎬 Animaciones

### Slide In (deslizar desde arriba)
```tsx
<div className="animate-slide-in">
  Aparece deslizándose desde arriba
</div>
```

### Slide Up (deslizar hacia arriba)
```tsx
<div className="animate-slide-up">
  Aparece deslizándose hacia arriba
</div>
```

### Fade In Up (aparecer + subir)
```tsx
<div className="animate-fade-in-up">
  Aparece y sube suavemente
</div>
```

### Gradient Animation (gradiente animado)
```tsx
<div className="bg-gradient-to-r from-primary-500 via-secondary-500 to-primary-500
                bg-[length:200%_auto] animate-gradient">
  Gradiente que se mueve
</div>
```

---

## 📦 Componentes de Ejemplo

### Card Premium con Glow
```tsx
<div className="group relative">
  {/* Glow effect background */}
  <div className="absolute -inset-0.5 bg-gradient-premium rounded-xl blur opacity-30
                  group-hover:opacity-100 transition duration-1000" />

  {/* Card content */}
  <div className="relative bg-white dark:bg-gray-900 rounded-xl p-6
                  border border-primary-100 shadow-xl">
    <h3 className="text-2xl font-bold text-primary-500">
      Total de Ingresos
    </h3>
    <p className="text-4xl font-extrabold mt-2 bg-gradient-premium bg-clip-text text-transparent">
      $45,678.90
    </p>
  </div>
</div>
```

### Botón Primary con Efectos
```tsx
<button className="relative group px-6 py-3 rounded-lg overflow-hidden
                   bg-gradient-primary text-white font-semibold
                   shadow-glow-primary hover:shadow-glow-premium
                   transform hover:-translate-y-1 transition-all duration-300">
  {/* Shimmer effect */}
  <span className="absolute inset-0 bg-shimmer bg-[length:200%_100%]
                   opacity-0 group-hover:opacity-100 group-hover:animate-shimmer" />

  {/* Button text */}
  <span className="relative">Crear Gasto</span>
</button>
```

### Badge de Éxito
```tsx
<span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full
               bg-secondary-50 text-secondary-700 border border-secondary-200
               shadow-sm">
  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" />
  </svg>
  Aprobado
</span>
```

### Card con Glassmorphism
```tsx
<div className="relative backdrop-blur-xl bg-white/70 dark:bg-gray-900/70
                border border-white/20 rounded-2xl p-6
                shadow-xl shadow-primary-500/10">
  <div className="absolute inset-0 bg-gradient-premium opacity-5 rounded-2xl" />

  <div className="relative">
    <h3 className="text-lg font-semibold text-primary-900">
      Estado de Cuenta
    </h3>
    <p className="text-gray-600 mt-2">
      Balance actualizado en tiempo real
    </p>
  </div>
</div>
```

### Input con Glow on Focus
```tsx
<input
  type="text"
  className="w-full px-4 py-3 rounded-lg
             border-2 border-gray-200
             focus:border-primary-500 focus:shadow-glow-primary
             transition-all duration-300
             bg-white dark:bg-gray-900"
  placeholder="Buscar transacciones..."
/>
```

---

## 🌙 Dark Mode

Todos los componentes soportan dark mode automáticamente:

```tsx
// Texto adaptable
<p className="text-gray-900 dark:text-white">
  Texto que cambia en dark mode
</p>

// Fondo adaptable
<div className="bg-white dark:bg-gray-900">
  Card que se adapta al tema
</div>

// Bordes adaptables
<div className="border-gray-200 dark:border-gray-700">
  Borde que se adapta
</div>
```

---

## 📊 Uso en el Dashboard

### Métricas con Colores Semánticos

```tsx
// Ingreso (positivo) - Verde
<div className="bg-gradient-to-br from-secondary-50 to-secondary-100
                border border-secondary-200 rounded-xl p-6">
  <p className="text-sm text-secondary-700 font-medium">
    Ingresos del mes
  </p>
  <p className="text-3xl font-bold text-secondary-900 mt-2">
    $25,450.00
  </p>
  <div className="flex items-center gap-1 mt-2 text-secondary-600">
    <svg className="w-4 h-4">↑</svg>
    <span className="text-xs">+12.5% vs mes anterior</span>
  </div>
</div>

// Gasto (neutral) - Azul
<div className="bg-gradient-to-br from-primary-50 to-primary-100
                border border-primary-200 rounded-xl p-6">
  <p className="text-sm text-primary-700 font-medium">
    Gastos del mes
  </p>
  <p className="text-3xl font-bold text-primary-900 mt-2">
    $15,230.00
  </p>
</div>
```

---

## 🎯 Reglas de Uso

### ✅ DO (Hacer)
- Usa `primary-500` para acciones principales
- Usa `secondary-500` para éxitos y positivos
- Combina gradientes para elementos premium
- Usa efectos de glow con moderación
- Mantén consistencia en todo el app

### ❌ DON'T (No hacer)
- No uses más de 2 gradientes en la misma vista
- No abuses de las animaciones (menos es más)
- No combines glow effects de diferentes colores en elementos cercanos
- No uses `primary` y `secondary` para lo mismo

---

## 🚀 Próximos Pasos

1. **Aplicar a componentes existentes**
   - Actualizar Button component
   - Actualizar Card component
   - Actualizar Input component

2. **Crear componentes nuevos**
   - GradientCard
   - GlowButton
   - MetricCard con animaciones

3. **Implementar dark mode**
   - Sistema de tema
   - Toggle de tema
   - Persistencia en localStorage

---

## 📚 Referencias

- Tailwind CSS: https://tailwindcss.com/docs
- Color Tool: https://coolors.co/
- Gradient Generator: https://cssgradient.io/
- Glassmorphism: https://css.glass/

---

**Última actualización:** Noviembre 2025
**Versión:** 2.0 - ContaFlow Brand Colors

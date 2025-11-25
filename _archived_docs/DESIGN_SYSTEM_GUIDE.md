# Guía del Sistema de Diseño ContaFlow
**Look & Feel Estándar para Toda la Aplicación**

Fecha: 3 de Noviembre, 2025

---

## 🎨 VISIÓN GENERAL

El diseño de **bank-reconciliation** define el estándar visual para toda la aplicación ContaFlow. Esta guía documenta todos los componentes, colores y patrones que deben usarse consistentemente.

---

## 🌈 PALETA DE COLORES

### Colores Principales

```css
/* ContaFlow Blue - Color de Marca */
--brand-500: #11446e;
--brand-600: #0f3c61;
--brand-700: #0c314f;

/* Verde Secundario - Accent */
--accent-500: #60b97b;
--accent-600: #3d8a5d;

/* Gradientes de Marca */
--grad-brand-accent: linear-gradient(90deg, #11446e, #3d8a5d);
--grad-brand-deep: linear-gradient(90deg, #0f3c61, #0a263d);
```

### Grises y Neutros

```css
--gray-50:  #f9fafb;
--gray-100: #f3f4f6;
--gray-200: #e5e7eb;
--gray-300: #d1d5db;
--gray-500: #6b7280;
--gray-700: #374151;
--gray-900: #111827;
```

### Background Estándar

```html
<!-- TODAS las páginas deben usar este background -->
<body class="bg-slate-100 min-h-screen">
```

---

## 📦 COMPONENTES PRINCIPALES

### 1. Page Header (Hero Section)

El header de página con gradiente sutil y acciones.

```html
<div class="page-header">
    <div class="page-header__content">
        <div class="page-header__meta">
            <h1 class="page-header__title">
                <i class="fas fa-chart-line"></i>
                Título de la Página
            </h1>
            <p class="page-header__subtitle">
                Descripción breve de la funcionalidad
            </p>
        </div>
        <div class="page-header__actions">
            <button class="btn btn--secondary">
                <i class="fas fa-filter"></i>
                Filtrar
            </button>
            <button class="btn btn--primary">
                <i class="fas fa-plus"></i>
                Nuevo
            </button>
        </div>
    </div>
</div>
```

**Resultado:**
- Gradiente sutil de marca (azul + verde)
- Título grande con icono
- Acciones alineadas a la derecha
- Responsive (stack vertical en mobile)

---

### 2. Stat Cards (Métricas)

Cards para mostrar estadísticas importantes.

```html
<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
    <!-- Success Card -->
    <div class="stat-card" data-intent="success">
        <div class="stat-card__icon">
            <i class="fas fa-check-circle"></i>
        </div>
        <div class="stat-card__body">
            <p class="stat-card__label">Total Ingresos</p>
            <h3 class="stat-card__value">$125,430.00</h3>
            <p class="stat-card__meta">+12% vs mes anterior</p>
        </div>
        <div class="stat-card__delta">
            <i class="fas fa-arrow-up"></i> 12%
        </div>
    </div>

    <!-- Warning Card -->
    <div class="stat-card" data-intent="warning">
        <div class="stat-card__icon">
            <i class="fas fa-clock"></i>
        </div>
        <div class="stat-card__body">
            <p class="stat-card__label">Pendientes</p>
            <h3 class="stat-card__value">23</h3>
            <p class="stat-card__meta">Requieren revisión</p>
        </div>
    </div>

    <!-- Danger Card -->
    <div class="stat-card" data-intent="danger">
        <div class="stat-card__icon">
            <i class="fas fa-exclamation-triangle"></i>
        </div>
        <div class="stat-card__body">
            <p class="stat-card__label">Sin CFDI</p>
            <h3 class="stat-card__value">8</h3>
            <p class="stat-card__meta">Faltan facturas</p>
        </div>
    </div>
</div>
```

**Intents disponibles:** `success`, `warning`, `danger` (cambia color del icono)

---

### 3. Data Table

Tabla estándar para datos.

```html
<div class="data-table">
    <!-- Filtros opcionales -->
    <div class="flex gap-3 items-center mb-4">
        <div class="segmented">
            <button class="segment segment--active">Todos</button>
            <button class="segment">Completados</button>
            <button class="segment">Pendientes</button>
        </div>
    </div>

    <!-- Tabla -->
    <div class="data-table__wrapper">
        <table>
            <thead>
                <tr>
                    <th>Fecha</th>
                    <th>Descripción</th>
                    <th class="is-numeric">Monto</th>
                    <th>Estado</th>
                    <th>Acciones</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>2025-11-03</td>
                    <td>Gasolina - PEMEX</td>
                    <td class="is-numeric">$850.00</td>
                    <td>
                        <span class="status-pill status-pill--success">
                            <i class="fas fa-check-circle"></i>
                            Completado
                        </span>
                    </td>
                    <td>
                        <button class="btn btn--sm btn--ghost">
                            <i class="fas fa-eye"></i>
                        </button>
                    </td>
                </tr>
                <!-- más rows -->
            </tbody>
        </table>
    </div>
</div>
```

**Características:**
- Header sticky
- Columnas numéricas alineadas a la derecha (`is-numeric`)
- Hover state en rows
- Scroll horizontal responsive

---

### 4. Botones

Sistema completo de botones.

```html
<!-- Primary (Acción principal) -->
<button class="btn btn--primary">
    <i class="fas fa-save"></i>
    Guardar
</button>

<!-- Secondary (Acción secundaria) -->
<button class="btn btn--secondary">
    <i class="fas fa-download"></i>
    Descargar
</button>

<!-- Ghost (Acción terciaria) -->
<button class="btn btn--ghost">
    <i class="fas fa-times"></i>
    Cancelar
</button>

<!-- Danger (Acción destructiva) -->
<button class="btn btn--danger">
    <i class="fas fa-trash"></i>
    Eliminar
</button>

<!-- Small size -->
<button class="btn btn--sm btn--primary">
    <i class="fas fa-edit"></i>
    Editar
</button>

<!-- Loading state -->
<button class="btn btn--primary btn--loading">
    Procesando...
</button>

<!-- Disabled -->
<button class="btn btn--primary" disabled>
    No disponible
</button>
```

**Variantes:**
- `btn--primary` - Azul ContaFlow, acción principal
- `btn--secondary` - Blanco con borde, acción secundaria
- `btn--ghost` - Transparente, acción terciaria
- `btn--danger` - Rojo, acciones destructivas
- `btn--sm` - Tamaño pequeño
- `btn--loading` - Estado de carga

---

### 5. Status Pills (Badges)

Badges para estados.

```html
<!-- Success -->
<span class="status-pill status-pill--success">
    <i class="fas fa-check-circle"></i>
    Completado
</span>

<!-- Warning -->
<span class="status-pill status-pill--warning">
    <i class="fas fa-clock"></i>
    Pendiente
</span>

<!-- Danger -->
<span class="status-pill status-pill--danger">
    <i class="fas fa-exclamation-circle"></i>
    Rechazado
</span>

<!-- Info -->
<span class="status-pill status-pill--info">
    <i class="fas fa-info-circle"></i>
    En revisión
</span>
```

**Colores semánticos:**
- `success` - Verde (completado, activo, correcto)
- `warning` - Ámbar (pendiente, atención)
- `danger` - Rojo (error, rechazado)
- `info` - Azul (información, proceso)

---

### 6. Tabs

Navegación por tabs.

```html
<div class="tabs mb-6">
    <a href="#general" class="tab tab--active">
        <i class="fas fa-home"></i>
        General
    </a>
    <a href="#details" class="tab">
        <i class="fas fa-list"></i>
        Detalles
    </a>
    <a href="#history" class="tab">
        <i class="fas fa-history"></i>
        Historial
    </a>
</div>
```

**Características:**
- Tab activo con gradiente de marca
- Underline animado
- Responsive (scroll horizontal en mobile)

---

### 7. Segmented Control

Control segmentado para filtros.

```html
<div class="segmented">
    <button class="segment segment--active">Todos</button>
    <button class="segment">Activos</button>
    <button class="segment">Inactivos</button>
</div>
```

**Uso:** Filtros, vistas, toggles

---

### 8. Cards

Cards estándar para contenido.

```html
<!-- Card simple -->
<div class="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
    <h3 class="text-lg font-semibold mb-2">Título del Card</h3>
    <p class="text-gray-600">Contenido del card</p>
</div>

<!-- Card con gradiente (destacado) -->
<div class="page-header__content">
    <!-- Contenido destacado -->
</div>
```

**Estilos estándar:**
- Background: `bg-white`
- Border: `border border-gray-200`
- Border radius: `rounded-xl` (12px)
- Shadow: `shadow-sm`
- Padding: `p-6` (24px)

---

## 🎯 PLANTILLA ESTÁNDAR DE PÁGINA

```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Título · ContaFlow</title>
    <link rel="icon" type="image/x-icon" href="/static/favicon.ico">

    <!-- CSS Stack -->
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="/static/css/contaflow-theme.css">
    <link rel="stylesheet" href="/static/css/contaflow-typography.css">
    <link rel="stylesheet" href="/static/css/contaflow-icons.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">

    <!-- Components -->
    <script src="/static/components/components.js" defer></script>
</head>
<body class="bg-slate-100 min-h-screen">
    <!-- Global Header -->
    <div data-include="/static/components/global-header.html"></div>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">

        <!-- Page Header -->
        <div class="page-header">
            <div class="page-header__content">
                <div class="page-header__meta">
                    <h1 class="page-header__title">
                        <i class="fas fa-icon"></i>
                        Título de la Página
                    </h1>
                    <p class="page-header__subtitle">
                        Descripción de la funcionalidad
                    </p>
                </div>
                <div class="page-header__actions">
                    <button class="btn btn--primary">
                        <i class="fas fa-plus"></i>
                        Acción Principal
                    </button>
                </div>
            </div>
        </div>

        <!-- Stats (opcional) -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div class="stat-card" data-intent="success">
                <div class="stat-card__icon">
                    <i class="fas fa-check"></i>
                </div>
                <div class="stat-card__body">
                    <p class="stat-card__label">Métrica</p>
                    <h3 class="stat-card__value">123</h3>
                </div>
            </div>
        </div>

        <!-- Content Area -->
        <div class="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <!-- Tu contenido aquí -->
        </div>

    </main>

</body>
</html>
```

---

## ✅ CHECKLIST DE DISEÑO

Antes de publicar una página, verifica:

### Estructura
- [ ] Usa `<body class="bg-slate-100 min-h-screen">`
- [ ] Incluye global-header
- [ ] Main content en container `max-w-7xl mx-auto px-4 py-6`
- [ ] Usa page-header para el título

### Componentes
- [ ] Botones usan clases `btn btn--variant`
- [ ] Badges usan `status-pill status-pill--intent`
- [ ] Tablas usan estructura `data-table`
- [ ] Cards tienen `bg-white rounded-xl border shadow-sm`
- [ ] Métricas usan `stat-card`

### Colores
- [ ] No usa colores custom inline
- [ ] Usa variables CSS del theme
- [ ] Primary: ContaFlow Blue (#11446e)
- [ ] Secondary: Verde (#60b97b)
- [ ] Estados: Verde/Ámbar/Rojo

### Tipografía
- [ ] No define font-family inline
- [ ] Usa clases de contaflow-typography.css
- [ ] Headings usan elementos semánticos

### Iconos
- [ ] Usa Font Awesome 6.4.0
- [ ] Iconos tienen espaciado (`icon-mr-2`)
- [ ] No usa emojis nativos

---

## 🎨 EJEMPLOS DE PATRONES COMUNES

### Página de Lista/Tabla

```html
<main class="max-w-7xl mx-auto px-4 py-6">
    <!-- Header -->
    <div class="page-header">...</div>

    <!-- Stats -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <!-- 4 stat cards -->
    </div>

    <!-- Filters + Table -->
    <div class="data-table">
        <div class="flex gap-3 mb-4">
            <div class="segmented">
                <button class="segment segment--active">Todos</button>
                <button class="segment">Filtro 1</button>
            </div>
        </div>
        <div class="data-table__wrapper">
            <table>...</table>
        </div>
    </div>
</main>
```

### Página de Detalle/Form

```html
<main class="max-w-4xl mx-auto px-4 py-6">
    <!-- Header -->
    <div class="page-header">...</div>

    <!-- Content Card -->
    <div class="bg-white rounded-xl border border-gray-200 shadow-sm">
        <!-- Tabs (opcional) -->
        <div class="tabs p-6 pb-0">
            <button class="tab tab--active">General</button>
            <button class="tab">Detalles</button>
        </div>

        <!-- Form Content -->
        <div class="p-6">
            <form>
                <!-- Form fields -->
            </form>
        </div>

        <!-- Actions -->
        <div class="flex gap-3 justify-end p-6 border-t border-gray-200">
            <button class="btn btn--ghost">Cancelar</button>
            <button class="btn btn--primary">Guardar</button>
        </div>
    </div>
</main>
```

### Dashboard/Overview

```html
<main class="max-w-7xl mx-auto px-4 py-6">
    <!-- Header -->
    <div class="page-header">...</div>

    <!-- Stats Grid -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <!-- 4 stat cards -->
    </div>

    <!-- Content Sections -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Card izquierdo -->
        <div class="bg-white rounded-xl border p-6">
            <h3 class="font-semibold mb-4">Sección 1</h3>
            <!-- Contenido -->
        </div>

        <!-- Card derecho -->
        <div class="bg-white rounded-xl border p-6">
            <h3 class="font-semibold mb-4">Sección 2</h3>
            <!-- Contenido -->
        </div>
    </div>
</main>
```

---

## 📐 SISTEMA DE ESPACIADO

Usa el sistema de 4pt:

```css
--sp-1: 4px   /* 0.25rem */
--sp-2: 8px   /* 0.5rem */
--sp-3: 12px  /* 0.75rem */
--sp-4: 16px  /* 1rem */
--sp-5: 20px  /* 1.25rem */
--sp-6: 24px  /* 1.5rem */
--sp-8: 32px  /* 2rem */
--sp-10: 40px /* 2.5rem */
```

**Tailwind equivalentes:**
- `p-1` = 4px
- `p-2` = 8px
- `p-3` = 12px
- `p-4` = 16px
- `p-6` = 24px
- `p-8` = 32px

---

## 🚀 MIGRACIÓN DE PÁGINAS EXISTENTES

### Paso 1: Actualizar <body>

```html
<!-- ❌ ANTES -->
<body class="bg-gray-50">

<!-- ✅ DESPUÉS -->
<body class="bg-slate-100 min-h-screen">
```

### Paso 2: Agregar page-header

```html
<!-- Reemplazar header custom por: -->
<div class="page-header">
    <div class="page-header__content">
        <div class="page-header__meta">
            <h1 class="page-header__title">
                <i class="fas fa-icon"></i>
                Título
            </h1>
            <p class="page-header__subtitle">Descripción</p>
        </div>
        <div class="page-header__actions">
            <button class="btn btn--primary">Acción</button>
        </div>
    </div>
</div>
```

### Paso 3: Actualizar botones

```html
<!-- ❌ ANTES -->
<button class="bg-blue-600 text-white px-4 py-2 rounded">

<!-- ✅ DESPUÉS -->
<button class="btn btn--primary">
```

### Paso 4: Actualizar tablas

Envolver tabla en:
```html
<div class="data-table">
    <div class="data-table__wrapper">
        <table>...</table>
    </div>
</div>
```

---

## 📚 RECURSOS

- **Archivo de tema:** `/static/css/contaflow-theme.css`
- **Ejemplo de referencia:** bank-reconciliation.html
- **Variables CSS:** Ver `:root` en contaflow-theme.css
- **Font Awesome 6.4.0:** https://fontawesome.com/icons

---

**Última actualización:** 3 de Noviembre, 2025
**Versión del theme:** 1.0
**Mantenedor:** Equipo ContaFlow

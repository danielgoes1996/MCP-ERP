# Componentes UI Base

Este repositorio expone un set de componentes reutilizables para las pantallas estáticas y los dashboards React. Se apoyan en los design tokens definidos en `static/css/contaflow-theme.css`.

## Tokens Clave
- **Brand**: `--brand-50` … `--brand-800`
- **Accent**: `--accent-500`, `--accent-600`
- **Neutros**: `--gray-50` … `--gray-900`
- **Tipografía**: `--font-sans`, `--font-xs` … `--font-2xl`
- **Espaciados**: `--sp-1`, `--sp-2`, `--sp-3`, `--sp-4`, `--sp-6`, `--sp-8`
- **Radios**: `--radius-sm`, `--radius-md`, `--radius-lg`
- **Sombras**: `--shadow-sm`, `--shadow-md`, `--shadow-lg`
- **Focus ring**: `--focus-ring`
- **Gradiente**: `--grad-brand-accent`

## Componentes en `static/components/`
- `page-header.html`: estructura para títulos/separadores.
- `stat-card.html`: tarjeta KPI con variant `data-intent` (`neutral|success|warning|danger`).
- `button.html`: variantes `btn--primary|secondary|ghost|danger`, tamaños opcionales (`btn--sm`, `btn--md`).
- `tabs.html`: tabs con `.tab`/`.tab--active` y control segmentado `.segment`.
- `data-table.html`: tabla con header sticky, zebra opcional y estados `data-table__empty`.
- `toast.html`: toast con variantes `toast--info|success|warning|danger`.
- `components.js`: utilidades para activar tabs/segmentos y `Toast.show(...)`.

## Uso en HTML Estático
1. Incluir `contaflow-theme.css` y `components.js`.
2. Copiar el snippet del componente o renderizarlo server-side.
3. Ajustar contenido dinámico via data attributes o JS de cada vista.

Ejemplo:
```html
<link rel="stylesheet" href="/static/css/contaflow-theme.css" />
<script src="/static/components/components.js" defer></script>

<header class="page-header">
  <div class="page-header__content">
    <div class="page-header__meta">
      <h1 class="page-header__title">Centro de Control de Gastos</h1>
      <p class="page-header__subtitle">Resumen del periodo actual</p>
    </div>
    <div class="page-header__actions">
      <button class="btn btn--primary">Nuevo gasto</button>
    </div>
  </div>
</header>
```

## Uso en React
Los mismos tokens se reflejan en `tailwind.config.js`. Los componentes se exportarán desde `dashboard-react/src/ui/`.

Ejemplo de API:
```tsx
<PageHeader
  title="Dashboard de Auditoría"
  subtitle="Coherencia BD ↔ API ↔ UI"
  actions={<Button variant="primary">Exportar</Button>}
/>

<StatCard
  label="Tickets Procesados"
  value="156"
  delta={{ value: '+12%', intent: 'success' }}
  icon={<TicketIcon />}
/>
```

## Pendientes
- Añadir tamaños (`btn--sm`, `stat-card--compact`).
- Documentar `<DataTable>` con selección y bulk actions.
- Publicar Storybook y Playwright visual tests.


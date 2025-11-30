# Sistema de Tipografía - ContaFlow Design System

Guía de tamaños de texto consistentes para toda la aplicación.

## Escala de Tamaños

### Títulos y Encabezados

| Clase | Tamaño | Uso |
|-------|--------|-----|
| `text-2xl` | 24px | Títulos de página principales (PageHeader) |
| `text-xl` | 20px | Títulos de secciones grandes |
| `text-lg` | 18px | Títulos de cards, subtítulos importantes |
| `text-base` | 16px | **Evitar** - Usar text-sm en su lugar |

### Texto de Cuerpo

| Clase | Tamaño | Uso |
|-------|--------|-----|
| `text-sm` | 14px | **Predeterminado** - Labels, inputs, selects, botones, texto de body |
| `text-xs` | 12px | Texto de ayuda, badges pequeños, metadatos |

### Texto Destacado

| Clase | Tamaño | Uso |
|-------|--------|-----|
| `text-3xl` | 30px | Números grandes en dashboards (stats) |
| `text-2xl` | 24px | Números medianos en cards de stats |

## Componentes del Design System

### Input
```tsx
- Label: text-sm font-semibold
- Input: text-sm
- Helper text: text-sm
- Error text: text-sm
- Padding: py-3 (reducido de py-3.5)
```

### Select
```tsx
- Label: text-sm font-semibold
- Button: text-sm
- Options: text-sm
- Padding button: py-3
- Padding options: py-2.5
```

### Button
```tsx
- Small: text-sm
- Medium: text-sm
- Large: text-sm (mantener consistencia)
```

### PageHeader
```tsx
- Title: text-2xl font-bold (reducido de text-3xl)
- Subtitle: text-sm (reducido de text-base)
```

### Card
```tsx
- Title: text-lg font-bold
- Subtitle: text-sm
```

### StatCard
```tsx
- Value: text-2xl o text-3xl font-bold
- Label: text-sm
- Change: text-sm
```

### EmptyState
```tsx
- Title: text-lg font-semibold
- Description: text-sm
```

## Reglas Generales

1. **Usar `text-sm` como predeterminado** para todo texto de interfaz (labels, inputs, botones, body text)
2. **Evitar `text-base`** - es demasiado grande para interfaces modernas
3. **Títulos de página**: `text-2xl` (no más de text-3xl)
4. **Subtítulos**: Siempre `text-sm`
5. **Números grandes**: `text-2xl` o `text-3xl` solo para stats/dashboards
6. **Texto de ayuda/metadata**: `text-xs`
7. **Consistencia**: Todos los inputs, selects y botones usan `text-sm`

## Padding Vertical Consistente

- **Inputs/Selects**: `py-3` (12px arriba/abajo)
- **Opciones de dropdown**: `py-2.5` (10px arriba/abajo)
- **Botones pequeños**: `py-2`
- **Botones medianos**: `py-3`

## Migración

Al actualizar componentes existentes:
1. ✅ Cambiar `py-3.5` → `py-3`
2. ✅ Agregar `text-sm` a inputs/selects sin tamaño especificado
3. ✅ Reducir títulos de `text-3xl` → `text-2xl`
4. ✅ Reducir subtítulos de `text-base` → `text-sm`

---

**Última actualización**: 2025-11-29
**Versión**: 1.0

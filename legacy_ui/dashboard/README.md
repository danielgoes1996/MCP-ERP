# 🔍 MCP Audit Dashboard

Dashboard de Auditoría de Funcionalidades para el Sistema MCP Server. Herramienta integral para visualizar coherencia arquitectónica, dependencias críticas y trazabilidad BD ↔ API ↔ UI.

## 📋 Características Principales

### ✅ Fase 1 Implementada (Core)
- **Vista de tablero principal** con 23 funcionalidades auditadas
- **Estado por capa** (BD, API, UI) con semáforos visuales
- **Identificación de SPOFs** y dependencias circulares
- **Campos faltantes** detectados con scripts SQL de corrección
- **Trazabilidad completa** BD ↔ API ↔ UI por funcionalidad

### 🎯 Fase 2 (Nice to have) - Incluida
- **Panel HTML/UI preview** con snippets de código
- **JSON de request/response** de ejemplo para funcionalidades clave
- **Visualización interactiva** de dependencias y flujos

## 🚀 Instalación y Configuración

### Prerequisitos
- Node.js 18+
- npm o yarn
- React 18+

### Instalación

```bash
# Clonar e instalar dependencias
cd dashboard
npm install

# Instalar dependencias específicas
npm install react react-dom @heroicons/react tailwindcss @tailwindcss/forms
```

### Configuración de Tailwind CSS

```bash
# Si no tienes Tailwind configurado
npx tailwindcss init -p

# El archivo tailwind.config.js ya está incluido con configuración personalizada
```

### Ejecución

```bash
# Desarrollo
npm start

# Build para producción
npm run build

# Preview de producción
npm run preview
```

## 📁 Estructura del Proyecto

```
dashboard/
├── components/                 # Componentes React modulares
│   ├── Dashboard.jsx          # Componente principal
│   ├── FunctionalityCard.jsx  # Card individual de funcionalidad
│   ├── SystemMetrics.jsx      # Métricas generales del sistema
│   ├── SPOFPanel.jsx          # Panel de Single Points of Failure
│   ├── CircularDependencies.jsx # Visualización de dependencias circulares
│   ├── MissingFieldsPanel.jsx # Panel de campos faltantes con SQL
│   └── FieldTraceability.jsx  # Trazabilidad BD ↔ API ↔ UI
├── data/
│   └── auditData.json         # Datos de auditoría (mock/API)
├── dashboard.js               # Archivo central de ensamblaje
├── package.json              # Dependencias y scripts
├── tailwind.config.js        # Configuración personalizada de Tailwind
└── README.md                 # Esta documentación
```

## 🎨 Componentes Principales

### 1. Dashboard (Componente Principal)
```jsx
import { Dashboard } from './dashboard.js';

<Dashboard />
```
**Funcionalidades:**
- Vista ejecutiva con KPIs del sistema
- Filtrado por categorías (Core/Business/Intelligence)
- Vista avanzada con campos faltantes
- Plan de fortalecimiento del sistema

### 2. FunctionalityCard (Funcionalidad Individual)
```jsx
import { FunctionalityCard } from './dashboard.js';

<FunctionalityCard
  functionality={expensesFunctionality}
  isExpanded={true}
  onToggle={handleToggle}
  getCoherenceColor={getCoherenceColor}
  getCriticalityColor={getCriticalityColor}
/>
```
**Muestra:**
- Estado actual (seguridad, performance, coherencia)
- Trazabilidad de campos BD ↔ API ↔ UI
- Dependencias críticas y flujos principales
- Ejemplos de Request/Response
- Scripts SQL de corrección

### 3. SystemMetrics (Métricas Ejecutivas)
```jsx
import { SystemMetrics } from './dashboard.js';

<SystemMetrics
  data={auditData.systemMetrics}
  categoryStats={auditData.categoryStats}
/>
```
**KPIs incluidos:**
- 23 funcionalidades identificadas
- 71% coherencia global (objetivo 91%)
- 147+ dependencias mapeadas
- 3 SPOFs críticos detectados

### 4. SPOFPanel (Single Points of Failure)
```jsx
import { SPOFPanel } from './dashboard.js';

<SPOFPanel spofs={auditData.spofs} />
```
**Identifica:**
- Base de datos SQLite (afecta 96% del sistema)
- FastAPI Framework (78% del sistema)
- Modelos Pydantic (65% del sistema)

### 5. FieldTraceability (Trazabilidad de Campos)
```jsx
import { FieldTraceability } from './dashboard.js';

<FieldTraceability fields={functionality.fields} />
```
**Visualiza:**
- Estado de cada campo en BD, API, UI
- Semáforos de coherencia (✅ ⚠️ ❌)
- Estadísticas de completeness

## 📊 Ejemplo de Uso - Funcionalidad "Gestión de Gastos"

```javascript
// Datos de ejemplo para Gestión de Gastos
const expensesFunctionality = {
  id: 5,
  name: "Gestión de Gastos",
  category: "business",
  coherence: 74,
  criticality: "maxima",
  icon: "💰",
  description: "CRUD de gastos con validación y categorización",

  // Trazabilidad de campos
  fields: {
    "descripcion": { bd: true, api: true, ui: true, status: "complete" },
    "monto_total": { bd: true, api: true, ui: true, status: "complete" },
    "deducible": { bd: false, api: true, ui: true, status: "missing_bd" },
    "centro_costo": { bd: false, api: true, ui: true, status: "missing_bd" }
  },

  // Ejemplos de API
  sampleRequest: {
    descripcion: "Gasolina para vehículo empresa",
    monto_total: 850.00,
    fecha_gasto: "2024-09-25",
    deducible: true,
    centro_costo: "Ventas"
  },

  sampleResponse: {
    id: 123,
    descripcion: "Gasolina para vehículo empresa",
    monto_total: 850.00,
    estado: "pendiente"
  }
}
```

## 🛠️ Scripts SQL Incluidos

El dashboard genera automáticamente scripts de corrección:

```sql
-- PRIORIDAD CRÍTICA
ALTER TABLE expenses ADD COLUMN deducible BOOLEAN DEFAULT TRUE;
ALTER TABLE expenses ADD COLUMN centro_costo TEXT;
ALTER TABLE expenses ADD COLUMN proyecto TEXT;
ALTER TABLE expenses ADD COLUMN tags JSON;

-- PRIORIDAD MEDIA
ALTER TABLE invoices ADD COLUMN subtotal DECIMAL(10,2);
ALTER TABLE invoices ADD COLUMN iva_amount DECIMAL(10,2);

-- ÍNDICES RECOMENDADOS
CREATE INDEX IF NOT EXISTS idx_expenses_deducible ON expenses(deducible);
CREATE INDEX IF NOT EXISTS idx_expenses_centro_costo ON expenses(centro_costo);
```

## 🔧 Utilidades de Desarrollo

### Consola de Desarrollo
Una vez cargado el dashboard, tienes acceso a utilidades en consola:

```javascript
// Exportar datos a CSV
window.MCPAuditDashboard.exportToCSV(functionalities);

// Calcular estadísticas de coherencia
window.MCPAuditDashboard.calculateCoherenceStats(functionalities);

// Filtrar por categoría
window.MCPAuditDashboard.filterByCategory(functionalities, 'core');

// Acceder a datos de auditoría
window.MCPAuditDashboard.auditData;
```

### Componentes de Ejemplo

```jsx
import { ExampleUsage } from './dashboard.js';

// Renderizar ejemplos de todos los componentes
<ExampleUsage />
```

### Testing Individual de Componentes

```jsx
import { DevelopmentComponents } from './dashboard.js';

// Renderizar componente específico
const MyComponent = () => {
  return DevelopmentComponents.renderComponent('SystemMetrics', {
    data: auditData.systemMetrics,
    categoryStats: auditData.categoryStats
  });
};
```

## 📈 Métricas y KPIs

### Estado Actual del Sistema
| Métrica | Valor | Estado | Objetivo |
|---------|-------|---------|----------|
| Funcionalidades | 23 | ✅ Completo | 23 |
| Coherencia Global | 71% | ⚠️ Mejorar | 91% |
| SPOFs Críticos | 3 | 🔴 Alto Riesgo | 0 |
| Campos sin BD | 23 | 🔴 Crítico | 0 |

### Por Capa Arquitectónica
- **Core System**: 4 funcionalidades, 78% coherencia, riesgo medio
- **Business Logic**: 11 funcionalidades, 69% coherencia, riesgo alto
- **Intelligence Layer**: 8 funcionalidades, 72% coherencia, riesgo medio

## 🎯 Roadmap y Mejoras

### Implementado ✅
- [x] Dashboard principal con todas las funcionalidades
- [x] Trazabilidad BD ↔ API ↔ UI completa
- [x] Detección y visualización de SPOFs
- [x] Scripts SQL de corrección automática
- [x] Ejemplos de Request/Response para APIs
- [x] Panel de dependencias circulares
- [x] Filtrado por categorías
- [x] Exportación a CSV
- [x] Componentes modulares y reutilizables

### Posibles Mejoras 🚀
- [ ] Integración con API real (actualmente usa datos mock)
- [ ] Gráficos interactivos (Chart.js/D3.js)
- [ ] Notificaciones en tiempo real
- [ ] Historial de auditorías
- [ ] Modo oscuro
- [ ] Exportación a PDF/Excel
- [ ] Dashboard móvil responsivo avanzado
- [ ] Integración con CI/CD para auditorías automáticas

## 🤝 Contribución

Para contribuir al desarrollo:

1. Fork el repositorio
2. Crear feature branch: `git checkout -b feature/nueva-funcionalidad`
3. Commit cambios: `git commit -m 'Add nueva funcionalidad'`
4. Push a branch: `git push origin feature/nueva-funcionalidad`
5. Crear Pull Request

## 📝 Notas de Implementación

### Integración con Sistema Real

Para usar con datos reales en lugar de mock:

1. **Reemplazar carga de datos en Dashboard.jsx:**
```jsx
useEffect(() => {
  const loadAuditData = async () => {
    const response = await fetch('/api/audit-data');
    const data = await response.json();
    setAuditData(data);
  };
}, []);
```

2. **Endpoint de API esperado:**
```
GET /api/audit-data
```
Debe retornar la estructura definida en `auditData.json`

### Personalización de Estilos

El archivo `tailwind.config.js` incluye:
- Colores personalizados para auditoría
- Utilidades específicas para coherencia
- Sombras especiales para SPOFs críticos
- Animaciones sutiles para UX

### Performance

- Componentes optimizados con React.memo (donde aplica)
- Lazy loading para funcionalidades expandidas
- Virtualización recomendada para +100 funcionalidades

## 📞 Soporte

Para soporte técnico o preguntas:
- Crear issue en GitHub
- Revisar documentación de componentes en código
- Consultar ejemplos en `ExampleUsage`

---

**✨ Dashboard desarrollado específicamente para auditoría del Sistema MCP Server**
**📅 Versión: 1.0.0 | Fecha: 2024-09-25**
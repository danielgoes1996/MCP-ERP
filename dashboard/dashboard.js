/**
 * Dashboard Principal - MCP Server Audit Dashboard
 * Archivo central que ensambla todos los componentes
 *
 * Uso:
 * 1. npm install react react-dom @heroicons/react tailwindcss
 * 2. Configurar Tailwind CSS
 * 3. Importar este archivo en tu aplicación React
 */

import React from 'react';
import ReactDOM from 'react-dom/client';

// Importar componentes del dashboard
import Dashboard from './components/Dashboard.jsx';
import FunctionalityCard from './components/FunctionalityCard.jsx';
import SystemMetrics from './components/SystemMetrics.jsx';
import SPOFPanel from './components/SPOFPanel.jsx';
import CircularDependencies from './components/CircularDependencies.jsx';
import MissingFieldsPanel from './components/MissingFieldsPanel.jsx';
import FieldTraceability from './components/FieldTraceability.jsx';

// Datos de auditoría (en producción vendría de API)
import auditData from './data/auditData.json';

/**
 * Aplicación principal del Dashboard
 * Punto de entrada para el sistema de auditoría
 */
const App = () => {
  return (
    <div className="App">
      <Dashboard />
    </div>
  );
};

/**
 * Configuración de desarrollo/testing
 * Permite renderizar componentes individuales para testing
 */
export const DevelopmentComponents = {
  // Componente principal
  Dashboard,

  // Componentes individuales para testing
  FunctionalityCard,
  SystemMetrics,
  SPOFPanel,
  CircularDependencies,
  MissingFieldsPanel,
  FieldTraceability,

  // Datos mock para desarrollo
  auditData,

  // Función para renderizar un componente específico
  renderComponent: (componentName, props = {}) => {
    const Component = DevelopmentComponents[componentName];
    if (!Component) {
      console.error(`Component ${componentName} not found`);
      return null;
    }

    return <Component {...props} />;
  }
};

/**
 * Ejemplo de uso individual de componentes
 */
export const ExampleUsage = () => {
  // Ejemplo 1: Renderizar solo la funcionalidad de "Gestión de Gastos"
  const expensesFunctionality = auditData.functionalities.find(f => f.id === 5);

  const handleToggle = (id) => {
    console.log('Toggle functionality:', id);
  };

  const getCoherenceColor = (coherence) => {
    if (coherence >= 80) return 'text-green-600 bg-green-100';
    if (coherence >= 70) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  const getCriticalityColor = (criticality) => {
    switch(criticality) {
      case 'maxima': return 'bg-red-500 text-white';
      case 'alta': return 'bg-orange-500 text-white';
      case 'media': return 'bg-yellow-500 text-white';
      default: return 'bg-gray-500 text-white';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">
        Ejemplos de Componentes - MCP Audit Dashboard
      </h1>

      <div className="space-y-8">
        {/* Ejemplo 1: Funcionalidad Individual */}
        <section>
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            📝 Ejemplo: Funcionalidad Individual (Gestión de Gastos)
          </h2>
          <FunctionalityCard
            functionality={expensesFunctionality}
            isExpanded={true}
            onToggle={() => handleToggle(expensesFunctionality.id)}
            getCoherenceColor={getCoherenceColor}
            getCriticalityColor={getCriticalityColor}
          />
        </section>

        {/* Ejemplo 2: Métricas del Sistema */}
        <section>
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            📊 Ejemplo: Métricas del Sistema
          </h2>
          <SystemMetrics
            data={auditData.systemMetrics}
            categoryStats={auditData.categoryStats}
          />
        </section>

        {/* Ejemplo 3: Panel de SPOFs */}
        <section>
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            🚨 Ejemplo: Single Points of Failure
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <SPOFPanel spofs={auditData.spofs} />
            <CircularDependencies dependencies={auditData.circularDependencies} />
          </div>
        </section>

        {/* Ejemplo 4: Trazabilidad de Campos */}
        <section>
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            🔗 Ejemplo: Trazabilidad de Campos
          </h2>
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h3 className="font-medium text-gray-900 mb-4">
              Campos de Gestión de Gastos
            </h3>
            <FieldTraceability fields={expensesFunctionality.fields} />
          </div>
        </section>

        {/* Ejemplo 5: Campos Faltantes */}
        <section>
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            🔧 Ejemplo: Campos Faltantes con SQL
          </h2>
          <div className="bg-white rounded-lg shadow-sm p-6">
            <MissingFieldsPanel missingFields={auditData.missingFields} />
          </div>
        </section>
      </div>
    </div>
  );
};

/**
 * Utilidades para integración con otros sistemas
 */
export const DashboardUtils = {
  // Filtrar funcionalidades por categoría
  filterByCategory: (functionalities, category) => {
    if (category === 'all') return functionalities;
    return functionalities.filter(f => f.category === category);
  },

  // Calcular estadísticas de coherencia
  calculateCoherenceStats: (functionalities) => {
    const coherenceValues = functionalities.map(f => f.coherence);
    return {
      average: Math.round(coherenceValues.reduce((a, b) => a + b, 0) / coherenceValues.length),
      min: Math.min(...coherenceValues),
      max: Math.max(...coherenceValues),
      count: coherenceValues.length
    };
  },

  // Generar reporte de campos faltantes
  generateMissingFieldsReport: (functionalities) => {
    const report = {
      totalFunctionalities: functionalities.length,
      functionalitiesWithMissingFields: 0,
      missingBDFields: 0,
      missingAPIFields: 0,
      missingUIFields: 0
    };

    functionalities.forEach(func => {
      if (func.fields) {
        let hasMissingFields = false;
        Object.values(func.fields).forEach(field => {
          if (!field.bd) {
            report.missingBDFields++;
            hasMissingFields = true;
          }
          if (!field.api) {
            report.missingAPIFields++;
            hasMissingFields = true;
          }
          if (!field.ui) {
            report.missingUIFields++;
            hasMissingFields = true;
          }
        });
        if (hasMissingFields) {
          report.functionalitiesWithMissingFields++;
        }
      }
    });

    return report;
  },

  // Exportar datos para otros formatos
  exportToCSV: (functionalities) => {
    const headers = ['ID', 'Nombre', 'Categoría', 'Coherencia', 'Criticidad', 'SPOF'];
    const rows = functionalities.map(f => [
      f.id,
      f.name,
      f.category,
      f.coherence,
      f.criticality,
      f.isSPOF ? 'Sí' : 'No'
    ]);

    const csvContent = [headers, ...rows]
      .map(row => row.join(','))
      .join('\n');

    return csvContent;
  }
};

// Inicialización del dashboard si es llamado directamente
if (typeof window !== 'undefined') {
  // Verificar si estamos en el browser
  const rootElement = document.getElementById('audit-dashboard-root');
  if (rootElement) {
    const root = ReactDOM.createRoot(rootElement);
    root.render(<App />);
  }

  // Exportar utilidades al objeto global para acceso desde consola
  window.MCPAuditDashboard = {
    ...DevelopmentComponents,
    ...DashboardUtils,
    ExampleUsage
  };

  // Mostrar ayuda en consola
  console.log(`
🔍 MCP Audit Dashboard cargado exitosamente!

Comandos disponibles en consola:
- window.MCPAuditDashboard.auditData: Datos de auditoría
- window.MCPAuditDashboard.exportToCSV(): Exportar a CSV
- window.MCPAuditDashboard.calculateCoherenceStats(): Estadísticas
- window.MCPAuditDashboard.ExampleUsage: Ejemplos de uso

Componentes disponibles:
- Dashboard (principal)
- FunctionalityCard
- SystemMetrics
- SPOFPanel
- CircularDependencies
- MissingFieldsPanel
- FieldTraceability

Para mostrar ejemplos: renderizar <ExampleUsage />
  `);
}

// Exportaciones por defecto
export default App;
export {
  Dashboard,
  FunctionalityCard,
  SystemMetrics,
  SPOFPanel,
  CircularDependencies,
  MissingFieldsPanel,
  FieldTraceability,
  auditData
};
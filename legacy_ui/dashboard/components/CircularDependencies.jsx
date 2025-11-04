/**
 * Componente para visualizar dependencias circulares
 * Muestra loops de dependencia y riesgos asociados
 */
import React from 'react';
import {
  ArrowPathIcon,
  ExclamationTriangleIcon,
  LightBulbIcon
} from '@heroicons/react/24/outline';

const CircularDependencies = ({ dependencies }) => {
  const getRiskColor = (dependency) => {
    if (dependency.risk.includes('Deadlock') || dependency.risk.includes('deadlock')) {
      return 'bg-red-100 border-red-300 text-red-800';
    } else if (dependency.risk.includes('inconsistency') || dependency.risk.includes('loop')) {
      return 'bg-orange-100 border-orange-300 text-orange-800';
    } else {
      return 'bg-yellow-100 border-yellow-300 text-yellow-800';
    }
  };

  const getRiskIcon = (dependency) => {
    if (dependency.risk.includes('Deadlock') || dependency.risk.includes('deadlock')) {
      return <ExclamationTriangleIcon className="h-5 w-5 text-red-500" />;
    } else {
      return <ArrowPathIcon className="h-5 w-5 text-orange-500" />;
    }
  };

  const getSolutionIcon = (solution) => {
    return <LightBulbIcon className="h-4 w-4 text-blue-500" />;
  };

  const parseCircularFlow = (name) => {
    // Convertir "A ↔ B ↔ C" en array para mejor visualización
    return name.split(' ↔ ').map(item => item.trim());
  };

  return (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">
          🔄 Dependencias Circulares
        </h3>
        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
          dependencies.length === 0 ? 'bg-green-100 text-green-800' :
          dependencies.length <= 2 ? 'bg-yellow-100 text-yellow-800' :
          'bg-red-100 text-red-800'
        }`}>
          {dependencies.length} {dependencies.length === 1 ? 'Ciclo' : 'Ciclos'}
        </span>
      </div>

      {dependencies.length === 0 ? (
        <div className="text-center py-8">
          <div className="text-green-500 mb-2">
            <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="text-green-700 font-medium">¡Arquitectura Limpia!</p>
          <p className="text-green-600 text-sm">No se detectaron dependencias circulares</p>
        </div>
      ) : (
        <div className="space-y-4">
          {dependencies.map((dependency, index) => {
            const flowComponents = parseCircularFlow(dependency.name);

            return (
              <div
                key={index}
                className={`border rounded-lg p-4 ${getRiskColor(dependency)}`}
              >
                {/* Header con icono y nombre */}
                <div className="flex items-start space-x-3 mb-3">
                  {getRiskIcon(dependency)}
                  <div className="flex-1">
                    <h4 className="font-semibold text-lg mb-2">
                      Ciclo {index + 1}: {dependency.name.split(' ↔ ')[0]} → ... → {dependency.name.split(' ↔ ').slice(-1)[0]}
                    </h4>

                    {/* Visualización del flujo circular */}
                    <div className="bg-white bg-opacity-50 rounded-lg p-3 mb-3">
                      <div className="flex items-center justify-center space-x-2 text-sm font-medium">
                        {flowComponents.map((component, idx) => (
                          <React.Fragment key={idx}>
                            <span className="px-2 py-1 bg-white rounded shadow-sm border">
                              {component}
                            </span>
                            {idx < flowComponents.length - 1 && (
                              <ArrowPathIcon className="h-4 w-4 text-gray-500" />
                            )}
                          </React.Fragment>
                        ))}
                        {/* Flecha de retorno al inicio */}
                        <ArrowPathIcon className="h-4 w-4 text-red-500" />
                        <span className="px-2 py-1 bg-white rounded shadow-sm border opacity-50">
                          {flowComponents[0]}
                        </span>
                      </div>
                    </div>

                    {/* Descripción del riesgo */}
                    <div className="mb-3">
                      <div className="flex items-center space-x-2 mb-1">
                        <ExclamationTriangleIcon className="h-4 w-4" />
                        <span className="font-medium text-sm">Riesgo Identificado:</span>
                      </div>
                      <p className="text-sm pl-6">{dependency.risk}</p>
                    </div>

                    {/* Solución propuesta */}
                    <div className="bg-blue-50 bg-opacity-50 rounded-lg p-3">
                      <div className="flex items-start space-x-2">
                        {getSolutionIcon(dependency.solution)}
                        <div>
                          <div className="font-medium text-sm text-blue-800 mb-1">
                            Solución Recomendada:
                          </div>
                          <p className="text-sm text-blue-700">{dependency.solution}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}

          {/* Panel de recomendaciones generales */}
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
              <div className="flex items-start space-x-2">
                <LightBulbIcon className="h-5 w-5 text-orange-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="font-medium text-orange-800 mb-2">
                    Estrategias Generales para Romper Ciclos
                  </h4>
                  <ul className="text-sm text-orange-700 space-y-1">
                    <li>• <strong>Event-Driven Architecture:</strong> Usar eventos asincrónos en lugar de llamadas directas</li>
                    <li>• <strong>Dependency Injection:</strong> Invertir dependencias usando interfaces</li>
                    <li>• <strong>Mediator Pattern:</strong> Introducir un mediador para coordinar interacciones</li>
                    <li>• <strong>Saga Pattern:</strong> Para transacciones distribuidas complejas</li>
                    <li>• <strong>Circuit Breaker:</strong> Prevenir cascadas de fallos en bucles ML</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>

          {/* Métricas de dependencias */}
          <div className="mt-4 pt-4 border-t border-gray-200">
            <h4 className="text-sm font-semibold text-gray-700 mb-3">📊 Análisis de Impacto</h4>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-lg font-bold text-red-600">
                  {dependencies.filter(d => d.risk.includes('Deadlock')).length}
                </div>
                <div className="text-xs text-gray-600">Riesgo Crítico</div>
              </div>
              <div>
                <div className="text-lg font-bold text-orange-600">
                  {dependencies.filter(d => d.risk.includes('inconsistency')).length}
                </div>
                <div className="text-xs text-gray-600">Inconsistencia</div>
              </div>
              <div>
                <div className="text-lg font-bold text-yellow-600">
                  {dependencies.filter(d => d.risk.includes('loop')).length}
                </div>
                <div className="text-xs text-gray-600">Bucles ML</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CircularDependencies;
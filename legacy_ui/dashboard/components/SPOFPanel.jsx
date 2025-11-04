/**
 * Panel para visualizar Single Points of Failure (SPOFs)
 * Muestra riesgos críticos y tiempos de recuperación
 */
import React from 'react';
import {
  ExclamationTriangleIcon,
  ClockIcon,
  ShieldExclamationIcon
} from '@heroicons/react/24/outline';

const SPOFPanel = ({ spofs }) => {
  const getSeverityColor = (severity) => {
    switch(severity) {
      case 'critical': return 'bg-red-100 border-red-300 text-red-800';
      case 'high': return 'bg-orange-100 border-orange-300 text-orange-800';
      case 'medium': return 'bg-yellow-100 border-yellow-300 text-yellow-800';
      case 'low': return 'bg-green-100 border-green-300 text-green-800';
      default: return 'bg-gray-100 border-gray-300 text-gray-800';
    }
  };

  const getSeverityIcon = (severity) => {
    switch(severity) {
      case 'critical': return <ShieldExclamationIcon className="h-5 w-5 text-red-500" />;
      case 'high': return <ExclamationTriangleIcon className="h-5 w-5 text-orange-500" />;
      case 'medium': return <ExclamationTriangleIcon className="h-5 w-5 text-yellow-500" />;
      default: return <ClockIcon className="h-5 w-5 text-gray-500" />;
    }
  };

  const getRecoveryTimeColor = (recoveryTime) => {
    if (recoveryTime.includes('8')) return 'text-red-600';
    if (recoveryTime.includes('4')) return 'text-orange-600';
    if (recoveryTime.includes('2')) return 'text-yellow-600';
    return 'text-green-600';
  };

  return (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">
          🚨 Single Points of Failure (SPOFs)
        </h3>
        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
          spofs.length === 0 ? 'bg-green-100 text-green-800' :
          spofs.length <= 2 ? 'bg-yellow-100 text-yellow-800' :
          'bg-red-100 text-red-800'
        }`}>
          {spofs.length} {spofs.length === 1 ? 'SPOF' : 'SPOFs'}
        </span>
      </div>

      {spofs.length === 0 ? (
        <div className="text-center py-8">
          <div className="text-green-500 mb-2">
            <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="text-green-700 font-medium">¡Excelente!</p>
          <p className="text-green-600 text-sm">No hay SPOFs críticos identificados</p>
        </div>
      ) : (
        <div className="space-y-4">
          {spofs.map((spof, index) => (
            <div
              key={index}
              className={`border rounded-lg p-4 ${getSeverityColor(spof.severity)}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start space-x-3">
                  {getSeverityIcon(spof.severity)}
                  <div className="flex-1">
                    <h4 className="font-semibold text-lg mb-1">{spof.name}</h4>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                      <div className="flex items-center space-x-2">
                        <span className="font-medium">Impacto:</span>
                        <span className="font-bold">{spof.affects}</span>
                        <span>del sistema</span>
                      </div>

                      <div className="flex items-center space-x-2">
                        <ClockIcon className="h-4 w-4" />
                        <span className="font-medium">Recovery:</span>
                        <span className={`font-bold ${getRecoveryTimeColor(spof.recoveryTime)}`}>
                          {spof.recoveryTime}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-bold uppercase ${
                  spof.severity === 'critical' ? 'bg-red-500 text-white' :
                  spof.severity === 'high' ? 'bg-orange-500 text-white' :
                  spof.severity === 'medium' ? 'bg-yellow-500 text-white' :
                  'bg-gray-500 text-white'
                }`}>
                  {spof.severity}
                </div>
              </div>

              {/* Barra de impacto visual */}
              <div className="mt-3">
                <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                  <span>Impacto en el Sistema</span>
                  <span>{spof.affects}</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${
                      spof.severity === 'critical' ? 'bg-red-500' :
                      spof.severity === 'high' ? 'bg-orange-500' :
                      spof.severity === 'medium' ? 'bg-yellow-500' :
                      'bg-gray-500'
                    }`}
                    style={{ width: spof.affects }}
                  ></div>
                </div>
              </div>
            </div>
          ))}

          {/* Resumen de impacto */}
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <div className="flex items-start space-x-2">
                <ExclamationTriangleIcon className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="font-medium text-red-800 mb-1">Recomendaciones Críticas</h4>
                  <ul className="text-sm text-red-700 space-y-1">
                    {spofs.filter(s => s.severity === 'critical').length > 0 && (
                      <li>• <strong>Urgente:</strong> Migrar SQLite a PostgreSQL con clustering</li>
                    )}
                    {spofs.length > 1 && (
                      <li>• Implementar redundancia en componentes críticos</li>
                    )}
                    <li>• Establecer monitoreo 24/7 de componentes SPOF</li>
                    <li>• Crear runbooks de recuperación automatizada</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Métricas de SPOF */}
      {spofs.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <h4 className="text-sm font-semibold text-gray-700 mb-3">📊 Análisis de Riesgo</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <div className="text-lg font-bold text-red-600">
                {spofs.filter(s => s.severity === 'critical').length}
              </div>
              <div className="text-xs text-gray-600">Críticos</div>
            </div>
            <div>
              <div className="text-lg font-bold text-orange-600">
                {spofs.filter(s => s.severity === 'high').length}
              </div>
              <div className="text-xs text-gray-600">Altos</div>
            </div>
            <div>
              <div className="text-lg font-bold text-yellow-600">
                {spofs.filter(s => s.severity === 'medium').length}
              </div>
              <div className="text-xs text-gray-600">Medios</div>
            </div>
            <div>
              <div className="text-lg font-bold text-gray-600">
                {Math.max(...spofs.map(s => parseInt(s.recoveryTime.split('-')[1] || s.recoveryTime.split('-')[0])))}h
              </div>
              <div className="text-xs text-gray-600">Max Recovery</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SPOFPanel;
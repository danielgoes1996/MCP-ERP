/**
 * Panel para mostrar campos faltantes por prioridad
 * Incluye scripts SQL de corrección
 */
import React, { useState } from 'react';
import {
  ExclamationTriangleIcon,
  DocumentTextIcon,
  ClipboardDocumentIcon
} from '@heroicons/react/24/outline';

const MissingFieldsPanel = ({ missingFields }) => {
  const [copiedSQL, setCopiedSQL] = useState(null);

  const getPriorityColor = (priority) => {
    switch(priority) {
      case 'critical': return 'bg-red-100 border-red-300 text-red-800';
      case 'medium': return 'bg-yellow-100 border-yellow-300 text-yellow-800';
      case 'low': return 'bg-gray-100 border-gray-300 text-gray-800';
      default: return 'bg-gray-100 border-gray-300 text-gray-800';
    }
  };

  const getPriorityIcon = (priority) => {
    switch(priority) {
      case 'critical': return <ExclamationTriangleIcon className="h-4 w-4 text-red-500" />;
      case 'medium': return <ExclamationTriangleIcon className="h-4 w-4 text-yellow-500" />;
      case 'low': return <DocumentTextIcon className="h-4 w-4 text-gray-500" />;
      default: return <DocumentTextIcon className="h-4 w-4 text-gray-500" />;
    }
  };

  const generateSQL = (fields) => {
    return fields.map(field => {
      const defaultClause = field.default ? ` DEFAULT ${field.default}` : '';
      return `ALTER TABLE ${field.table} ADD COLUMN ${field.field} ${field.type}${defaultClause};`;
    }).join('\n');
  };

  const copyToClipboard = async (text, priority) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedSQL(priority);
      setTimeout(() => setCopiedSQL(null), 2000);
    } catch (err) {
      console.error('Error copying to clipboard:', err);
    }
  };

  const totalMissingFields = Object.values(missingFields).reduce((total, fields) => total + fields.length, 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-gray-900">
          🔧 Campos Faltantes por Prioridad
        </h4>
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-orange-100 text-orange-800">
          {totalMissingFields} Campos Total
        </span>
      </div>

      {Object.entries(missingFields).map(([priority, fields]) => {
        if (fields.length === 0) return null;

        const sqlScript = generateSQL(fields);

        return (
          <div key={priority} className={`border rounded-lg p-4 ${getPriorityColor(priority)}`}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2">
                {getPriorityIcon(priority)}
                <h5 className="font-medium">
                  Prioridad {priority.charAt(0).toUpperCase() + priority.slice(1)}
                  <span className="ml-2 text-sm opacity-75">({fields.length} campos)</span>
                </h5>
              </div>

              <button
                onClick={() => copyToClipboard(sqlScript, priority)}
                className="flex items-center space-x-1 px-2 py-1 text-xs bg-white bg-opacity-50 hover:bg-opacity-75 rounded border transition-colors"
                title="Copiar script SQL"
              >
                <ClipboardDocumentIcon className="h-3 w-3" />
                <span>{copiedSQL === priority ? 'Copiado!' : 'Copiar SQL'}</span>
              </button>
            </div>

            {/* Lista de campos */}
            <div className="space-y-2 mb-4">
              {fields.map((field, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between bg-white bg-opacity-50 rounded px-3 py-2"
                >
                  <div className="flex items-center space-x-3">
                    <code className="text-sm font-medium">{field.table}</code>
                    <span className="text-gray-500">→</span>
                    <code className="text-sm font-medium">{field.field}</code>
                  </div>
                  <div className="text-xs text-gray-600">
                    <span className="font-medium">{field.type}</span>
                    {field.default && (
                      <span className="ml-1 text-gray-500">= {field.default}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Script SQL */}
            <div className="bg-gray-900 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <h6 className="text-xs font-medium text-gray-300">
                  Script SQL - Prioridad {priority.charAt(0).toUpperCase() + priority.slice(1)}
                </h6>
              </div>
              <pre className="text-xs text-gray-100 overflow-x-auto">
                {sqlScript}
              </pre>
            </div>
          </div>
        );
      })}

      {/* Script completo */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h5 className="font-medium text-gray-900">📄 Script SQL Completo</h5>
          <button
            onClick={() => copyToClipboard(
              Object.entries(missingFields)
                .map(([priority, fields]) => `-- Prioridad ${priority.toUpperCase()}\n${generateSQL(fields)}`)
                .join('\n\n'),
              'complete'
            )}
            className="flex items-center space-x-1 px-3 py-1 text-sm bg-blue-500 hover:bg-blue-600 text-white rounded transition-colors"
          >
            <ClipboardDocumentIcon className="h-4 w-4" />
            <span>{copiedSQL === 'complete' ? '¡Copiado!' : 'Copiar Todo'}</span>
          </button>
        </div>

        <div className="bg-gray-900 rounded-lg p-4">
          <pre className="text-xs text-gray-100 overflow-x-auto max-h-40">
{Object.entries(missingFields).map(([priority, fields]) =>
`-- ===== PRIORIDAD ${priority.toUpperCase()} =====
${generateSQL(fields)}`
).join('\n\n')}

-- ===== CREAR ÍNDICES RECOMENDADOS =====
CREATE INDEX IF NOT EXISTS idx_expenses_deducible ON expenses(deducible);
CREATE INDEX IF NOT EXISTS idx_expenses_centro_costo ON expenses(centro_costo);
CREATE INDEX IF NOT EXISTS idx_expenses_proyecto ON expenses(proyecto);
CREATE INDEX IF NOT EXISTS idx_invoices_subtotal ON invoices(subtotal);
CREATE INDEX IF NOT EXISTS idx_bank_movements_decision ON bank_movements(decision);
          </pre>
        </div>

        <div className="mt-3 text-xs text-gray-600">
          <p>
            💡 <strong>Recomendación:</strong> Ejecutar scripts en orden de prioridad (critical → medium → low).
            Realizar backup antes de aplicar cambios.
          </p>
        </div>
      </div>
    </div>
  );
};

export default MissingFieldsPanel;
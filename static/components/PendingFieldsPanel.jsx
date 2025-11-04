const PendingFieldsPanel = ({
  expenseFields,
  getFieldValue,
  handleFieldChange,
  isPredictingCategory,
  categoryPrediction,
  onClearCategoryPrediction,
  paymentAccounts = [],
  className = '',
}) => {
  const clearCategoryPrediction = React.useCallback(() => {
    if (typeof onClearCategoryPrediction === 'function') {
      onClearCategoryPrediction();
    }
  }, [onClearCategoryPrediction]);

  const renderCategoryAssist = (value) => {
    const confidence = categoryPrediction?.confianza ?? 0;

    return (
      <div className="mt-2 space-y-2">
        {isPredictingCategory && (
          <div className="flex items-center text-xs text-blue-600">
            <i className="fas fa-robot fa-spin mr-2"></i>
            Prediciendo categoría con IA...
          </div>
        )}

        {categoryPrediction && !value && confidence < 0.8 && (
          <div className="p-2 bg-blue-50 rounded-md border border-blue-200">
            <div className="text-xs font-medium text-blue-800 mb-1">
              🤖 IA sugiere: {categoryPrediction.categoria_sugerida}
              <span className="ml-1 text-blue-600">
                ({Math.round(confidence * 100)}% confianza)
              </span>
            </div>
            {categoryPrediction.razonamiento && (
              <div className="text-xs text-blue-700 mb-2">
                {categoryPrediction.razonamiento}
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => {
                  handleFieldChange('categoria', categoryPrediction.categoria_sugerida);
                  clearCategoryPrediction();
                }}
                className="px-2 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700"
              >
                ✅ Aplicar
              </button>
              <button
                type="button"
                onClick={clearCategoryPrediction}
                className="px-2 py-1 bg-gray-400 text-white text-xs rounded hover:bg-gray-500"
              >
                ❌ Rechazar
              </button>
            </div>

            {Array.isArray(categoryPrediction.alternativas) && categoryPrediction.alternativas.length > 0 && (
              <div className="mt-2">
                <div className="text-xs text-blue-700 mb-1">Alternativas:</div>
                <div className="flex flex-wrap gap-1">
                  {categoryPrediction.alternativas.map((alt, idx) => (
                    <button
                      key={`${alt.categoria}-${idx}`}
                      type="button"
                      onClick={() => {
                        handleFieldChange('categoria', alt.categoria);
                        clearCategoryPrediction();
                      }}
                      className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded hover:bg-blue-200"
                      title={alt.razon || alt.categoria}
                    >
                      {alt.categoria} ({Math.round((alt.confianza ?? 0) * 100)}%)
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {value && categoryPrediction && (
          <div className="text-xs text-green-600">
            ✅ Categoría aplicada por IA: {value}
            ({categoryPrediction.metodo_prediccion === 'llm' ? 'GPT' : 'Reglas'})
          </div>
        )}

        {!categoryPrediction && !isPredictingCategory && (
          <div className="text-xs text-gray-500">
            💡 Completa la descripción para sugerencia automática
          </div>
        )}
      </div>
    );
  };

  const renderFieldInput = (fieldKey, fieldConfig, value) => {
    if (fieldConfig?.type === 'select') {
      return (
        <div>
          <select
            value={value || ''}
            onChange={(e) => handleFieldChange(fieldKey, e.target.value)}
            className="w-full p-2 border border-gray-300 rounded-md text-sm"
          >
            <option value="">Selecciona una opción</option>
            {fieldConfig.options?.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {fieldKey === 'categoria' && renderCategoryAssist(value)}
        </div>
      );
    }

    if (fieldConfig?.type === 'payment_account') {
      return (
        <div>
          <select
            value={value || ''}
            onChange={(e) => handleFieldChange(fieldKey, parseInt(e.target.value, 10) || '')}
            className="w-full p-2 border border-gray-300 rounded-md text-sm"
          >
            <option value="">-- Selecciona cuenta --</option>
            {paymentAccounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.nombre} - Saldo: ${(account.saldo_actual || 0).toLocaleString('es-MX')}
              </option>
            ))}
          </select>
          {paymentAccounts.length === 0 && (
            <p className="text-xs text-amber-600 mt-1">
              ⚠️ No hay cuentas de pago disponibles. Crea una en /payment-accounts
            </p>
          )}
        </div>
      );
    }

    if (fieldConfig?.type === 'number') {
      return (
        <input
          type="number"
          value={value || ''}
          onChange={(e) => handleFieldChange(fieldKey, parseFloat(e.target.value) || 0)}
          placeholder={fieldConfig.placeholder}
          className="w-full p-2 border border-gray-300 rounded-md text-sm"
          step="0.01"
          min="0"
        />
      );
    }

    if (fieldConfig?.type === 'date') {
      return (
        <input
          type="date"
          value={value || ''}
          onChange={(e) => handleFieldChange(fieldKey, e.target.value)}
          className="w-full p-2 border border-gray-300 rounded-md text-sm"
          max={new Date().toISOString().split('T')[0]}
        />
      );
    }

    if (fieldConfig?.type === 'textarea') {
      return (
        <textarea
          value={value || ''}
          onChange={(e) => handleFieldChange(fieldKey, e.target.value)}
          placeholder={fieldConfig.placeholder}
          className="w-full p-2 border border-gray-300 rounded-md text-sm"
          rows={3}
        />
      );
    }

    return (
      <input
        type="text"
        value={value || ''}
        onChange={(e) => handleFieldChange(fieldKey, e.target.value)}
        placeholder={fieldConfig?.placeholder}
        className="w-full p-2 border border-gray-300 rounded-md text-sm"
      />
    );
  };

  return (
    <div className={`bg-white rounded-lg shadow-md p-4 ${className}`.trim()}>
      <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center gap-2">
        <i className="fas fa-list text-orange-500"></i>
        Campos Pendientes
      </h3>

      <div className="space-y-4">
        {Object.entries(expenseFields || {}).map(([fieldKey, fieldConfig]) => {
          const value = getFieldValue(fieldKey);
          if (value) return null;

          const containerClass = fieldConfig?.required
            ? 'border-orange-200 bg-orange-50'
            : 'border-gray-200 bg-gray-50';

          return (
            <div key={fieldKey} className={`border rounded-lg p-3 ${containerClass}`}>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {fieldConfig?.name || fieldKey}
                {fieldConfig?.required && <span className="text-red-500 ml-1">*</span>}
              </label>

              {renderFieldInput(fieldKey, fieldConfig, value)}

              {fieldConfig?.help && (
                <p className="text-xs text-gray-500 mt-1">{fieldConfig.help}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

if (typeof window !== 'undefined') {
  window.PendingFieldsPanel = PendingFieldsPanel;
}

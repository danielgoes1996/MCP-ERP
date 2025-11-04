/**
 * PlaceholderCompletionModal Component
 *
 * Modal para completar campos faltantes de placeholders.
 * Carga automáticamente los campos faltantes desde el backend.
 *
 * CÓMO INCORPORAR EN TU UI EXISTENTE:
 *
 * 1. Importar en voice-expenses.source.jsx:
 *    import PlaceholderCompletionModal from './components/PlaceholderCompletionModal.jsx';
 *
 * 2. Agregar state para el modal:
 *    const [showPlaceholderModal, setShowPlaceholderModal] = useState(false);
 *
 * 3. Renderizar en tu JSX:
 *    {showPlaceholderModal && (
 *        <PlaceholderCompletionModal
 *            onClose={() => setShowPlaceholderModal(false)}
 *            onComplete={() => {
 *                setShowPlaceholderModal(false);
 *                // Refrescar tu lista de gastos
 *                refreshExpenses();
 *            }}
 *        />
 *    )}
 */

const { useState, useEffect } = React;

function PlaceholderCompletionModal({ onClose, onComplete }) {
    const [pendingList, setPendingList] = useState([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [currentExpense, setCurrentExpense] = useState(null);
    const [promptData, setPromptData] = useState(null);
    const [completedFields, setCompletedFields] = useState({});
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState(null);

    // Cargar lista de pendientes al abrir
    useEffect(() => {
        fetchPendingList();
    }, []);

    // Cargar detalles del expense actual
    useEffect(() => {
        if (pendingList.length > 0 && currentIndex < pendingList.length) {
            fetchPromptData(pendingList[currentIndex].expense_id);
        }
    }, [currentIndex, pendingList]);

    const fetchPendingList = async () => {
        try {
            const response = await fetch('/api/expenses/placeholder-completion/pending?company_id=default&limit=50');
            const data = await response.json();
            setPendingList(data);
            setLoading(false);
        } catch (err) {
            setError('Error al cargar gastos pendientes');
            setLoading(false);
        }
    };

    const fetchPromptData = async (expenseId) => {
        try {
            setLoading(true);
            const response = await fetch(`/api/expenses/placeholder-completion/prompt/${expenseId}`);
            const data = await response.json();
            setCurrentExpense(pendingList[currentIndex]);
            setPromptData(data);
            setCompletedFields({});
            setLoading(false);
        } catch (err) {
            setError('Error al cargar detalles del gasto');
            setLoading(false);
        }
    };

    const handleSubmit = async () => {
        if (!currentExpense) return;

        setSubmitting(true);
        setError(null);

        try {
            const response = await fetch('/api/expenses/placeholder-completion/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    expense_id: currentExpense.expense_id,
                    completed_fields: completedFields,
                    company_id: 'default'
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Error al actualizar');
            }

            const result = await response.json();

            // Si quedan más pendientes, ir al siguiente
            if (currentIndex < pendingList.length - 1) {
                setCurrentIndex(currentIndex + 1);
            } else {
                // Si era el último, cerrar y notificar
                onComplete();
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setSubmitting(false);
        }
    };

    const handleSkip = () => {
        if (currentIndex < pendingList.length - 1) {
            setCurrentIndex(currentIndex + 1);
        } else {
            onClose();
        }
    };

    const handleFieldChange = (fieldName, value) => {
        setCompletedFields({
            ...completedFields,
            [fieldName]: value
        });
    };

    if (loading) {
        return (
            <div className="modal-overlay">
                <div className="modal-container">
                    <div className="loading-spinner">⏳ Cargando...</div>
                </div>
            </div>
        );
    }

    if (pendingList.length === 0) {
        return (
            <div className="modal-overlay" onClick={onClose}>
                <div className="modal-container" onClick={(e) => e.stopPropagation()}>
                    <div className="modal-header">
                        <h2>🎉 ¡Todo completo!</h2>
                        <button className="btn-close" onClick={onClose}>✕</button>
                    </div>
                    <div className="modal-body">
                        <p>No hay gastos pendientes de completar en este momento.</p>
                    </div>
                    <div className="modal-footer">
                        <button className="btn-primary" onClick={onClose}>Cerrar</button>
                    </div>
                </div>
            </div>
        );
    }

    if (!currentExpense || !promptData) {
        return null;
    }

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-container modal-large" onClick={(e) => e.stopPropagation()}>
                {/* Header */}
                <div className="modal-header">
                    <div>
                        <h2>Completar Gasto {currentIndex + 1} de {pendingList.length}</h2>
                        <p className="subtitle">{currentExpense.descripcion}</p>
                    </div>
                    <button className="btn-close" onClick={onClose}>✕</button>
                </div>

                {/* Progress bar */}
                <div className="progress-bar">
                    <div
                        className="progress-fill"
                        style={{ width: `${((currentIndex + 1) / pendingList.length) * 100}%` }}
                    />
                </div>

                {/* Body */}
                <div className="modal-body">
                    {error && (
                        <div className="alert alert-error">
                            ⚠️ {error}
                        </div>
                    )}

                    {/* Datos prefilled */}
                    <div className="prefilled-section">
                        <h3>Datos existentes:</h3>
                        <div className="info-grid">
                            <div className="info-item">
                                <span className="label">Monto:</span>
                                <span className="value">${currentExpense.monto_total}</span>
                            </div>
                            <div className="info-item">
                                <span className="label">Fecha:</span>
                                <span className="value">{currentExpense.fecha_gasto}</span>
                            </div>
                            {currentExpense.proveedor_nombre && (
                                <div className="info-item">
                                    <span className="label">Proveedor:</span>
                                    <span className="value">{currentExpense.proveedor_nombre}</span>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Campos faltantes */}
                    <div className="missing-fields-section">
                        <h3>⚠️ Campos requeridos ({promptData.missing_fields.length}):</h3>

                        {promptData.missing_fields.map((field) => (
                            <div key={field.field_name} className="form-group">
                                <label>
                                    {field.display_name}
                                    {field.required && <span className="required">*</span>}
                                </label>

                                {field.field_type === 'select' ? (
                                    <select
                                        value={completedFields[field.field_name] || ''}
                                        onChange={(e) => handleFieldChange(field.field_name, e.target.value)}
                                        className="form-control"
                                    >
                                        <option value="">Selecciona...</option>
                                        {field.options?.map((opt) => (
                                            <option key={opt.value} value={opt.value}>
                                                {opt.label}
                                            </option>
                                        ))}
                                    </select>
                                ) : (
                                    <input
                                        type={field.field_type || 'text'}
                                        value={completedFields[field.field_name] || ''}
                                        onChange={(e) => handleFieldChange(field.field_name, e.target.value)}
                                        placeholder={field.placeholder || ''}
                                        className="form-control"
                                    />
                                )}

                                {field.help_text && (
                                    <small className="help-text">{field.help_text}</small>
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                {/* Footer */}
                <div className="modal-footer">
                    <button
                        className="btn-secondary"
                        onClick={handleSkip}
                        disabled={submitting}
                    >
                        Saltar
                    </button>

                    <button
                        className="btn-primary"
                        onClick={handleSubmit}
                        disabled={submitting || Object.keys(completedFields).length === 0}
                    >
                        {submitting ? '⏳ Guardando...' : 'Guardar y Continuar'}
                    </button>
                </div>
            </div>
        </div>
    );
}

// Estilos CSS para agregar
const styles = `
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
}

.modal-container {
    background: white;
    border-radius: 12px;
    max-width: 600px;
    width: 90%;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-large {
    max-width: 800px;
}

.modal-header {
    padding: 20px 24px;
    border-bottom: 1px solid #e0e0e0;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.modal-header h2 {
    margin: 0;
    font-size: 20px;
}

.modal-header .subtitle {
    margin: 4px 0 0;
    font-size: 14px;
    color: #666;
}

.btn-close {
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #999;
}

.btn-close:hover {
    color: #333;
}

.progress-bar {
    height: 4px;
    background: #e0e0e0;
}

.progress-fill {
    height: 100%;
    background: #4caf50;
    transition: width 0.3s;
}

.modal-body {
    padding: 24px;
    overflow-y: auto;
    flex: 1;
}

.prefilled-section {
    background: #f5f5f5;
    padding: 16px;
    border-radius: 8px;
    margin-bottom: 24px;
}

.prefilled-section h3 {
    margin: 0 0 12px;
    font-size: 14px;
    color: #666;
}

.info-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
}

.info-item {
    display: flex;
    flex-direction: column;
}

.info-item .label {
    font-size: 12px;
    color: #999;
    margin-bottom: 4px;
}

.info-item .value {
    font-weight: 500;
}

.missing-fields-section h3 {
    margin: 0 0 16px;
    font-size: 16px;
}

.form-group {
    margin-bottom: 20px;
}

.form-group label {
    display: block;
    margin-bottom: 8px;
    font-weight: 500;
}

.required {
    color: #dc3545;
    margin-left: 4px;
}

.form-control {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid #ddd;
    border-radius: 6px;
    font-size: 14px;
}

.form-control:focus {
    outline: none;
    border-color: #4caf50;
    box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.1);
}

.help-text {
    display: block;
    margin-top: 4px;
    font-size: 12px;
    color: #999;
}

.alert {
    padding: 12px 16px;
    border-radius: 6px;
    margin-bottom: 16px;
}

.alert-error {
    background: #fee;
    color: #c33;
    border: 1px solid #fcc;
}

.modal-footer {
    padding: 16px 24px;
    border-top: 1px solid #e0e0e0;
    display: flex;
    gap: 12px;
    justify-content: flex-end;
}

.btn-primary, .btn-secondary {
    padding: 10px 20px;
    border: none;
    border-radius: 6px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-primary {
    background: #4caf50;
    color: white;
}

.btn-primary:hover:not(:disabled) {
    background: #45a049;
}

.btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.btn-secondary {
    background: #f5f5f5;
    color: #666;
}

.btn-secondary:hover:not(:disabled) {
    background: #e0e0e0;
}

.loading-spinner {
    text-align: center;
    padding: 40px;
    font-size: 18px;
}
`;

export default PlaceholderCompletionModal;

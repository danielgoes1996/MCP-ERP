/**
 * PlaceholderBadge Component
 *
 * Badge que muestra el contador de placeholders pendientes.
 * Se actualiza automáticamente cada 30 segundos.
 *
 * CÓMO INCORPORAR EN TU UI EXISTENTE:
 *
 * 1. Importar en voice-expenses.source.jsx:
 *    import PlaceholderBadge from './components/PlaceholderBadge.jsx';
 *
 * 2. Agregar en el navbar (busca donde tienes "Facturas pendientes"):
 *    <PlaceholderBadge onClick={() => setShowPlaceholderModal(true)} />
 */

const { useState, useEffect } = React;

function PlaceholderBadge({ onClick }) {
    const [pendingCount, setPendingCount] = useState(0);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Función para obtener el contador
        const fetchPendingCount = async () => {
            try {
                const response = await fetch('/api/expenses/placeholder-completion/stats/detailed?company_id=default');
                const data = await response.json();
                setPendingCount(data.total_pending);
                setLoading(false);
            } catch (error) {
                console.error('Error fetching placeholder count:', error);
                setLoading(false);
            }
        };

        // Fetch inicial
        fetchPendingCount();

        // Polling cada 30 segundos
        const interval = setInterval(fetchPendingCount, 30000);

        return () => clearInterval(interval);
    }, []);

    if (loading) {
        return (
            <button className="btn-placeholder-badge" disabled>
                <span>⏳</span>
            </button>
        );
    }

    if (pendingCount === 0) {
        return null; // No mostrar nada si no hay pendientes
    }

    return (
        <button
            className="btn-placeholder-badge"
            onClick={onClick}
            title={`${pendingCount} gasto${pendingCount > 1 ? 's' : ''} pendiente${pendingCount > 1 ? 's' : ''} de completar`}
        >
            <span className="icon">⚠️</span>
            <span className="label">Completar Gastos</span>
            <span className="badge">{pendingCount}</span>
        </button>
    );
}

// Estilos CSS para agregar en tu archivo de estilos
const styles = `
.btn-placeholder-badge {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    background: #fff3cd;
    border: 2px solid #ffc107;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 500;
    transition: all 0.2s;
}

.btn-placeholder-badge:hover {
    background: #ffc107;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(255, 193, 7, 0.3);
}

.btn-placeholder-badge .icon {
    font-size: 18px;
}

.btn-placeholder-badge .badge {
    background: #dc3545;
    color: white;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: bold;
    min-width: 20px;
    text-align: center;
}

.btn-placeholder-badge:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}
`;

export default PlaceholderBadge;

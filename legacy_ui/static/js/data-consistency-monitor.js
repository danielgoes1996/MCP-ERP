/**
 * Monitor de consistencia de datos para UI/Backend
 */

class DataConsistencyMonitor {
    constructor() {
        this.apiBase = 'http://localhost:8000/invoicing';
        this.validationCache = new Map();
        this.inconsistentTickets = new Set();
    }

    /**
     * Validar consistencia de un ticket específico
     */
    async validateTicket(ticketId) {
        try {
            const response = await fetch(`${this.apiBase}/tickets/${ticketId}/validate-consistency`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            const validation = result.validation;

            // Cache del resultado
            this.validationCache.set(ticketId, validation);

            // Marcar como inconsistente si hay problemas
            if (!validation.is_consistent) {
                this.inconsistentTickets.add(ticketId);
                this.showInconsistencyWarning(ticketId, validation.inconsistencies);
            } else {
                this.inconsistentTickets.delete(ticketId);
                this.hideInconsistencyWarning(ticketId);
            }

            return validation;

        } catch (error) {
            console.error(`Error validating ticket ${ticketId}:`, error);
            return { error: error.message };
        }
    }

    /**
     * Mostrar warning de inconsistencia en el UI
     */
    showInconsistencyWarning(ticketId, inconsistencies) {
        // Buscar el elemento del ticket en el UI
        const ticketElement = document.querySelector(`[data-ticket-id="${ticketId}"]`);
        if (!ticketElement) return;

        // Crear o actualizar warning
        let warningElement = ticketElement.querySelector('.consistency-warning');
        if (!warningElement) {
            warningElement = document.createElement('div');
            warningElement.className = 'consistency-warning bg-yellow-50 border border-yellow-200 rounded p-2 mt-2';
            ticketElement.appendChild(warningElement);
        }

        const severityIcon = inconsistencies.some(i => i.severity === 'high') ? '🚨' : '⚠️';

        warningElement.innerHTML = `
            <div class="flex items-center text-yellow-800 text-sm">
                <span class="mr-2">${severityIcon}</span>
                <span>Datos inconsistentes detectados</span>
                <button onclick="dataMonitor.showInconsistencyDetails(${ticketId})"
                        class="ml-2 text-blue-600 underline hover:text-blue-800">
                    Ver detalles
                </button>
            </div>
        `;
    }

    /**
     * Ocultar warning de inconsistencia
     */
    hideInconsistencyWarning(ticketId) {
        const ticketElement = document.querySelector(`[data-ticket-id="${ticketId}"]`);
        if (!ticketElement) return;

        const warningElement = ticketElement.querySelector('.consistency-warning');
        if (warningElement) {
            warningElement.remove();
        }
    }

    /**
     * Mostrar detalles de inconsistencias
     */
    showInconsistencyDetails(ticketId) {
        const validation = this.validationCache.get(ticketId);
        if (!validation || validation.is_consistent) return;

        const details = validation.inconsistencies.map(inc =>
            `• ${inc.field}: "${inc.direct_field}" ≠ "${inc.llm_analysis}" (${inc.severity})`
        ).join('\n');

        alert(`Inconsistencias en Ticket ${ticketId}:\n\n${details}\n\nEjecuta una nueva extracción para corregir.`);
    }

    /**
     * Validar todos los tickets visibles
     */
    async validateVisibleTickets() {
        const ticketElements = document.querySelectorAll('[data-ticket-id]');
        const validationPromises = [];

        ticketElements.forEach(element => {
            const ticketId = parseInt(element.dataset.ticketId);
            if (ticketId) {
                validationPromises.push(this.validateTicket(ticketId));
            }
        });

        const results = await Promise.allSettled(validationPromises);

        console.log('Validation Results:', results);
        return results;
    }

    /**
     * Ejecutar auto-fix de inconsistencias
     */
    async fixAllInconsistencies() {
        if (!confirm('¿Estás seguro de que quieres corregir todas las inconsistencias? Esta operación puede tomar tiempo.')) {
            return;
        }

        try {
            const response = await fetch(`${this.apiBase}/maintenance/fix-inconsistencies`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            const maintenance = result.maintenance_result;

            alert(`Mantenimiento completado:\n\n• Tickets revisados: ${maintenance.total_checked}\n• Inconsistencias encontradas: ${maintenance.inconsistent_found}\n• Tickets corregidos: ${maintenance.fixed_count}`);

            // Re-validar tickets visibles
            this.validateVisibleTickets();

            return maintenance;

        } catch (error) {
            console.error('Error fixing inconsistencies:', error);
            alert(`Error en mantenimiento: ${error.message}`);
        }
    }

    /**
     * Añadir botón de monitoreo al UI
     */
    addMonitoringButton() {
        // Buscar un lugar apropiado para añadir el botón
        const headerActions = document.querySelector('.header-actions') ||
                             document.querySelector('header') ||
                             document.body;

        const monitorButton = document.createElement('button');
        monitorButton.className = 'bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded text-sm mr-2';
        monitorButton.innerHTML = '🔍 Validar Datos';
        monitorButton.onclick = () => this.validateVisibleTickets();

        const fixButton = document.createElement('button');
        fixButton.className = 'bg-orange-500 hover:bg-orange-600 text-white px-3 py-1 rounded text-sm';
        fixButton.innerHTML = '🔧 Auto-Fix';
        fixButton.onclick = () => this.fixAllInconsistencies();

        headerActions.appendChild(monitorButton);
        headerActions.appendChild(fixButton);
    }

    /**
     * Inicializar el monitor
     */
    init() {
        // Añadir botones de monitoreo
        this.addMonitoringButton();

        // Validar automáticamente cada 30 segundos
        setInterval(() => {
            if (this.inconsistentTickets.size > 0) {
                console.log(`Revalidando ${this.inconsistentTickets.size} tickets inconsistentes...`);
                this.inconsistentTickets.forEach(ticketId => this.validateTicket(ticketId));
            }
        }, 30000);

        console.log('✅ Data Consistency Monitor inicializado');
    }
}

// Instancia global
window.dataMonitor = new DataConsistencyMonitor();

// Auto-inicializar cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => dataMonitor.init());
} else {
    dataMonitor.init();
}
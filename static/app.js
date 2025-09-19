/**
 * MCP Server Web Interface
 * Gestión de gastos por voz con visualización en tiempo real
 */

class MCPVoiceInterface {
    constructor() {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.currentAudioBlob = null;

        this.initializeElements();
        this.bindEvents();
        this.loadExpenseHistory();
    }

    initializeElements() {
        // Botones de control
        this.recordButton = document.getElementById('recordButton');
        this.sendButton = document.getElementById('sendButton');
        this.clearButton = document.getElementById('clearButton');
        this.copyJsonButton = document.getElementById('copyJson');
        this.refreshHistoryButton = document.getElementById('refreshHistory');

        // Elementos de estado
        this.recordStatus = document.getElementById('recordStatus');
        this.audioPlayer = document.getElementById('audioPlayer');
        this.audioPlayerContainer = document.getElementById('audioPlayerContainer');
        this.audioFileInput = document.getElementById('audioFile');

        // Paneles JSON
        this.jsonRequest = document.getElementById('jsonRequest');
        this.jsonResponse = document.getElementById('jsonResponse');

        // Información del gasto
        this.lastExpense = document.getElementById('lastExpense');
        this.expenseHistory = document.getElementById('expenseHistory');

        // Pasos del proceso
        this.steps = {
            1: document.getElementById('step1'),
            2: document.getElementById('step2'),
            3: document.getElementById('step3'),
            4: document.getElementById('step4'),
            5: document.getElementById('step5')
        };

        this.loadings = {
            1: document.getElementById('loading1'),
            2: document.getElementById('loading2'),
            3: document.getElementById('loading3'),
            4: document.getElementById('loading4'),
            5: document.getElementById('loading5')
        };
    }

    bindEvents() {
        this.recordButton.addEventListener('click', () => this.toggleRecording());
        this.sendButton.addEventListener('click', () => this.sendAudioToMCP());
        this.clearButton.addEventListener('click', () => this.clearAudio());
        this.copyJsonButton.addEventListener('click', () => this.copyJsonResponse());
        this.refreshHistoryButton.addEventListener('click', () => this.loadExpenseHistory());
        this.audioFileInput.addEventListener('change', (e) => this.handleFileUpload(e));
    }

    async toggleRecording() {
        if (!this.isRecording) {
            await this.startRecording();
        } else {
            this.stopRecording();
        }
    }

    async startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.mediaRecorder = new MediaRecorder(stream);
            this.audioChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                this.audioChunks.push(event.data);
            };

            this.mediaRecorder.onstop = () => {
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
                this.currentAudioBlob = audioBlob;
                this.displayAudioPlayer(audioBlob);
                this.sendButton.disabled = false;
            };

            this.mediaRecorder.start();
            this.isRecording = true;

            // UI updates
            this.recordButton.classList.add('recording', 'bg-red-600');
            this.recordButton.innerHTML = '<i class="fas fa-stop"></i>';
            this.recordStatus.textContent = 'Grabando... presiona para parar';
            this.recordStatus.classList.add('text-red-500');

        } catch (error) {
            console.error('Error accessing microphone:', error);
            this.showError('No se pudo acceder al micrófono');
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
            this.isRecording = false;

            // UI updates
            this.recordButton.classList.remove('recording', 'bg-red-600');
            this.recordButton.classList.add('bg-red-500');
            this.recordButton.innerHTML = '<i class="fas fa-microphone"></i>';
            this.recordStatus.textContent = 'Audio grabado - listo para enviar';
            this.recordStatus.classList.remove('text-red-500');
            this.recordStatus.classList.add('text-green-500');
        }
    }

    handleFileUpload(event) {
        const file = event.target.files[0];
        if (file && file.type.startsWith('audio/')) {
            this.currentAudioBlob = file;
            this.displayAudioPlayer(file);
            this.sendButton.disabled = false;
            this.recordStatus.textContent = `Archivo seleccionado: ${file.name}`;
            this.recordStatus.classList.add('text-blue-500');
        }
    }

    displayAudioPlayer(audioBlob) {
        const audioURL = URL.createObjectURL(audioBlob);
        this.audioPlayer.src = audioURL;
        this.audioPlayerContainer.classList.remove('hidden');
    }

    clearAudio() {
        this.currentAudioBlob = null;
        this.audioPlayerContainer.classList.add('hidden');
        this.sendButton.disabled = true;
        this.recordStatus.textContent = 'Presiona para grabar';
        this.recordStatus.className = 'mt-2 text-gray-600';
        this.audioFileInput.value = '';
        this.resetSteps();
        this.jsonRequest.textContent = '{\n  "esperando": "archivo de audio..."\n}';
        this.jsonResponse.textContent = '{\n  "esperando": "respuesta del servidor..."\n}';
    }

    async sendAudioToMCP() {
        if (!this.currentAudioBlob) {
            this.showError('No hay audio para enviar');
            return;
        }

        const formData = new FormData();
        formData.append('file', this.currentAudioBlob, 'audio.mp3');

        // Mostrar request en JSON
        this.jsonRequest.textContent = '{\n  "method": "POST",\n  "endpoint": "/voice_mcp_enhanced",\n  "file": "audio.mp3",\n  "processing": true\n}';

        // Iniciar animación de pasos
        this.animateProcessingSteps();

        try {
            // Usar el endpoint mejorado con validación
            const response = await fetch('/voice_mcp_enhanced', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            // Verificar si necesita completar campos
            if (result.completion_form && result.completeness_score < 80) {
                this.showCompletionForm(result);
                return;
            }

            // Mostrar response
            this.jsonResponse.textContent = JSON.stringify(result, null, 2);

            // Completar pasos
            this.completeAllSteps();

            // Mostrar información del gasto
            if (result.success && result.mcp_response) {
                this.displayExpenseInfo(result);
                this.loadExpenseHistory(); // Actualizar historial
            }

            // Reproducir audio de respuesta si está disponible
            if (result.audio_file_url) {
                this.playResponseAudio(result.audio_file_url);
            }

        } catch (error) {
            console.error('Error sending audio:', error);
            this.showError('Error enviando audio al servidor');
            this.resetSteps();
        }
    }

    animateProcessingSteps() {
        this.resetSteps();

        // Paso 1: Recibir audio
        setTimeout(() => this.activateStep(1), 200);

        // Paso 2: Transcripción
        setTimeout(() => {
            this.completeStep(1);
            this.activateStep(2);
        }, 1000);

        // Paso 3: NLP
        setTimeout(() => {
            this.completeStep(2);
            this.activateStep(3);
        }, 3000);

        // Paso 4: Odoo
        setTimeout(() => {
            this.completeStep(3);
            this.activateStep(4);
        }, 4000);

        // Paso 5: Respuesta
        setTimeout(() => {
            this.completeStep(4);
            this.activateStep(5);
        }, 5500);
    }

    activateStep(stepNumber) {
        const step = this.steps[stepNumber];
        const loading = this.loadings[stepNumber];

        step.classList.remove('completed');
        step.classList.add('active');
        loading.classList.remove('hidden');
    }

    completeStep(stepNumber) {
        const step = this.steps[stepNumber];
        const loading = this.loadings[stepNumber];

        step.classList.remove('active');
        step.classList.add('completed');
        loading.classList.add('hidden');
    }

    completeAllSteps() {
        [1, 2, 3, 4, 5].forEach(num => this.completeStep(num));
    }

    resetSteps() {
        [1, 2, 3, 4, 5].forEach(num => {
            const step = this.steps[num];
            const loading = this.loadings[num];

            step.classList.remove('active', 'completed');
            loading.classList.add('hidden');
        });
    }

    displayExpenseInfo(result) {
        const mcp = result.mcp_response;

        document.getElementById('expenseId').textContent = mcp.odoo_id || mcp.expense_id;
        document.getElementById('expenseAmount').textContent = mcp.amount || '0';
        document.getElementById('expenseDesc').textContent = mcp.description || result.transcript;
        document.getElementById('expenseStatus').textContent = mcp.status || 'unknown';

        this.lastExpense.classList.remove('hidden');
    }

    async playResponseAudio(audioUrl) {
        try {
            const audio = new Audio(audioUrl);
            audio.play();
        } catch (error) {
            console.warn('No se pudo reproducir audio de respuesta:', error);
        }
    }

    copyJsonResponse() {
        const jsonText = this.jsonResponse.textContent;
        navigator.clipboard.writeText(jsonText).then(() => {
            // Feedback visual
            this.copyJsonButton.innerHTML = '<i class="fas fa-check mr-1"></i>Copiado';
            this.copyJsonButton.classList.add('bg-green-500');

            setTimeout(() => {
                this.copyJsonButton.innerHTML = '<i class="fas fa-copy mr-1"></i>Copiar';
                this.copyJsonButton.classList.remove('bg-green-500');
            }, 2000);
        });
    }

    async loadExpenseHistory() {
        try {
            const response = await fetch('/mcp', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    method: 'get_expenses',
                    params: { limit: 10 }
                })
            });

            const result = await response.json();

            if (result.success && result.data && result.data.expenses) {
                this.displayExpenseHistory(result.data.expenses);
            } else {
                this.expenseHistory.innerHTML = '<p class="text-gray-500 text-center">No hay gastos en el historial</p>';
            }

        } catch (error) {
            console.error('Error loading expense history:', error);
            this.expenseHistory.innerHTML = '<p class="text-red-500 text-center">Error cargando historial</p>';
        }
    }

    displayExpenseHistory(expenses) {
        if (!expenses || expenses.length === 0) {
            this.expenseHistory.innerHTML = '<p class="text-gray-500 text-center">No hay gastos registrados</p>';
            return;
        }

        const expenseHtml = expenses.map(expense => `
            <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg border">
                <div class="flex items-center space-x-3">
                    <div class="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                        <i class="fas fa-receipt text-blue-600 text-sm"></i>
                    </div>
                    <div>
                        <p class="font-medium">${expense.description || expense.name}</p>
                        <p class="text-sm text-gray-500">ID: ${expense.id} • ${expense.date || 'Sin fecha'}</p>
                    </div>
                </div>
                <div class="text-right">
                    <p class="font-bold text-lg">$${expense.total_amount || expense.amount || '0'}</p>
                    <p class="text-sm text-gray-500">${expense.state || expense.status || 'Pendiente'}</p>
                </div>
            </div>
        `).join('');

        this.expenseHistory.innerHTML = expenseHtml;
    }

    showCompletionForm(result) {
        // Mostrar formulario de completado de campos
        const formHtml = this.generateCompletionFormHTML(result);

        // Crear modal
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4';
        modal.innerHTML = formHtml;

        document.body.appendChild(modal);

        // Bind eventos del formulario
        this.bindCompletionFormEvents(modal, result);
    }

    generateCompletionFormHTML(result) {
        const form = result.completion_form;

        let sectionsHtml = '';
        form.sections.forEach(section => {
            let fieldsHtml = '';
            section.fields.forEach(field => {
                fieldsHtml += this.generateFieldHTML(field);
            });

            sectionsHtml += `
                <div class="mb-6">
                    <h3 class="text-lg font-semibold mb-2">${section.title}</h3>
                    <p class="text-gray-600 mb-4">${section.description}</p>
                    <div class="space-y-4">
                        ${fieldsHtml}
                    </div>
                </div>
            `;
        });

        return `
            <div class="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
                <div class="p-6">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-2xl font-bold">${form.title}</h2>
                        <button class="close-modal text-gray-500 hover:text-gray-700">
                            <i class="fas fa-times text-xl"></i>
                        </button>
                    </div>

                    <div class="mb-4 p-4 bg-blue-50 rounded-lg">
                        <p class="text-blue-800">${form.subtitle}</p>
                        <p class="text-sm text-blue-600 mt-1">Score actual: ${result.completeness_score}%</p>
                    </div>

                    <form id="completionForm">
                        ${sectionsHtml}

                        <div class="flex space-x-4 pt-4 border-t">
                            <button type="button" class="skip-btn flex-1 bg-gray-500 hover:bg-gray-600 text-white py-2 px-4 rounded-lg">
                                <i class="fas fa-skip-forward mr-2"></i>
                                Crear con datos actuales (${result.completeness_score}%)
                            </button>
                            <button type="submit" class="flex-1 bg-green-500 hover:bg-green-600 text-white py-2 px-4 rounded-lg">
                                <i class="fas fa-check mr-2"></i>
                                Completar y crear gasto
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        `;
    }

    generateFieldHTML(field) {
        switch (field.type) {
            case 'select':
                let optionsHtml = '';
                field.options.forEach(option => {
                    optionsHtml += `<option value="${option.value}">${option.label}</option>`;
                });

                return `
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">${field.label}</label>
                        <select name="${field.id}" class="w-full p-2 border border-gray-300 rounded-lg">
                            <option value="">Seleccionar...</option>
                            ${optionsHtml}
                        </select>
                        <p class="text-xs text-gray-500 mt-1">${field.help}</p>
                    </div>
                `;

            case 'number':
                return `
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">${field.label}</label>
                        <input type="number" name="${field.id}" placeholder="${field.placeholder}"
                               class="w-full p-2 border border-gray-300 rounded-lg" step="0.01">
                        <p class="text-xs text-gray-500 mt-1">${field.help}</p>
                    </div>
                `;

            case 'date':
                return `
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">${field.label}</label>
                        <input type="date" name="${field.id}" value="${field.placeholder}"
                               class="w-full p-2 border border-gray-300 rounded-lg">
                        <p class="text-xs text-gray-500 mt-1">${field.help}</p>
                    </div>
                `;

            case 'textarea':
                return `
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">${field.label}</label>
                        <textarea name="${field.id}" placeholder="${field.placeholder}" rows="3"
                                  class="w-full p-2 border border-gray-300 rounded-lg"></textarea>
                        <p class="text-xs text-gray-500 mt-1">${field.help}</p>
                    </div>
                `;

            default: // text
                return `
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">${field.label}</label>
                        <input type="text" name="${field.id}" placeholder="${field.placeholder}"
                               class="w-full p-2 border border-gray-300 rounded-lg">
                        <p class="text-xs text-gray-500 mt-1">${field.help}</p>
                    </div>
                `;
        }
    }

    bindCompletionFormEvents(modal, result) {
        // Cerrar modal
        modal.querySelector('.close-modal').addEventListener('click', () => {
            document.body.removeChild(modal);
        });

        // Skip - crear con datos actuales
        modal.querySelector('.skip-btn').addEventListener('click', async () => {
            await this.createExpenseDirectly(result.enhanced_data);
            document.body.removeChild(modal);
        });

        // Completar formulario
        modal.querySelector('#completionForm').addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData(e.target);
            const userCompletions = {};

            for (let [key, value] of formData.entries()) {
                if (value) {
                    userCompletions[key] = value;
                }
            }

            await this.createExpenseWithCompletions(result.enhanced_data, userCompletions);
            document.body.removeChild(modal);
        });
    }

    async createExpenseDirectly(enhancedData) {
        try {
            const response = await fetch('/complete_expense', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    enhanced_data: enhancedData,
                    user_completions: {}
                })
            });

            const result = await response.json();
            this.handleExpenseCreationResult(result);

        } catch (error) {
            this.showError('Error creando gasto: ' + error.message);
        }
    }

    async createExpenseWithCompletions(enhancedData, userCompletions) {
        try {
            const response = await fetch('/complete_expense', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    enhanced_data: enhancedData,
                    user_completions: userCompletions
                })
            });

            const result = await response.json();
            this.handleExpenseCreationResult(result);

        } catch (error) {
            this.showError('Error creando gasto: ' + error.message);
        }
    }

    handleExpenseCreationResult(result) {
        this.jsonResponse.textContent = JSON.stringify(result, null, 2);
        this.completeAllSteps();

        if (result.success) {
            this.displayExpenseInfo({
                mcp_response: {
                    odoo_id: result.expense_id,
                    amount: result.odoo_data?.total_amount || 'N/A',
                    description: result.odoo_data?.name || 'Gasto creado',
                    status: 'pending_approval'
                }
            });

            // Actualizar historial
            this.loadExpenseHistory();

            // Reproducir audio de respuesta si está disponible
            if (result.audio_file_url) {
                this.playResponseAudio(result.audio_file_url);
            }
        }
    }

    showError(message) {
        // Crear notificación de error
        const errorDiv = document.createElement('div');
        errorDiv.className = 'fixed top-4 right-4 bg-red-500 text-white p-4 rounded-lg shadow-lg z-50';
        errorDiv.innerHTML = `
            <div class="flex items-center">
                <i class="fas fa-exclamation-triangle mr-2"></i>
                ${message}
                <button class="ml-4 text-white hover:text-gray-200" onclick="this.parentElement.parentElement.remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;

        document.body.appendChild(errorDiv);

        // Auto-remove después de 5 segundos
        setTimeout(() => {
            if (errorDiv.parentElement) {
                errorDiv.remove();
            }
        }, 5000);
    }
}

// Inicializar la interfaz cuando se carga la página
document.addEventListener('DOMContentLoaded', () => {
    new MCPVoiceInterface();
});
const { useState, useCallback, useEffect, useRef } = React;

const AdvancedCompleteExpenses = () => {
    // Core state
    const [currentView, setCurrentView] = useState('main');
    const [expensesData, setExpensesData] = useState([]);
    const [formData, setFormData] = useState({});
    const [isRecording, setIsRecording] = useState(false);
    const [transcript, setTranscript] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    // Advanced features state
    const [bankMovements, setBankMovements] = useState([]);
    const [pendingInvoices, setPendingInvoices] = useState([]);
    const [reconciliationSuggestions, setReconciliationSuggestions] = useState([]);
    const [uploadProgress, setUploadProgress] = useState({});
    const [processingStatus, setProcessingStatus] = useState({});
    const [bankEntries, setBankEntries] = useState([]);
    const [expenseReconciliation, setExpenseReconciliation] = useState([]);

    // Helper functions (defined first to avoid dependency issues)
    const handleFieldChange = useCallback((field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    }, []);

    const getFieldValue = (field) => {
        return formData[field] || '';
    };

    // Load all data
    const loadAllData = useCallback(async () => {
        try {
            const [expensesRes, bankRes, invoicesRes, entriesRes, reconRes] = await Promise.all([
                fetch('/expenses'),
                fetch('/bank-movements'),
                fetch('/pending-invoices'),
                fetch('/bank-entries'),
                fetch('/expense-reconciliation')
            ]);

            if (expensesRes.ok) {
                const expenses = await expensesRes.json();
                setExpensesData(expenses);
            }

            if (bankRes.ok) {
                const movements = await bankRes.json();
                setBankMovements(movements);
            }

            if (invoicesRes.ok) {
                const invoices = await invoicesRes.json();
                setPendingInvoices(invoices);
            }

            if (entriesRes.ok) {
                const entries = await entriesRes.json();
                setBankEntries(entries);
            }

            if (reconRes.ok) {
                const reconciliation = await reconRes.json();
                setExpenseReconciliation(reconciliation);
            }
        } catch (error) {
            console.error('Error loading data:', error);
        }
    }, []);

    // Bank reconciliation functions
    const loadReconciliationSuggestions = useCallback(async () => {
        try {
            const response = await fetch('/bank-reconciliation/suggestions');
            if (response.ok) {
                const suggestions = await response.json();
                setReconciliationSuggestions(suggestions);
            }
        } catch (error) {
            console.error('Error loading reconciliation suggestions:', error);
        }
    }, []);

    const approveReconciliation = useCallback(async (movementId, expenseId) => {
        try {
            const response = await fetch('/bank-reconciliation/approve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ movement_id: movementId, expense_id: expenseId })
            });

            if (response.ok) {
                alert('✅ Conciliación aprobada');
                loadReconciliationSuggestions();
                loadAllData();
            } else {
                alert('❌ Error en conciliación');
            }
        } catch (error) {
            console.error('Error approving reconciliation:', error);
            alert('❌ Error en conciliación: ' + error.message);
        }
    }, [loadReconciliationSuggestions, loadAllData]);

    // Bank entries functions
    const createBankEntry = useCallback(async (entryData) => {
        try {
            const response = await fetch('/bank-entries', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(entryData)
            });

            if (response.ok) {
                alert('✅ Asiento bancario creado');
                loadAllData();
            } else {
                alert('❌ Error creando asiento bancario');
            }
        } catch (error) {
            console.error('Error creating bank entry:', error);
            alert('❌ Error: ' + error.message);
        }
    }, [loadAllData]);

    const generateAutomaticBankEntries = useCallback(async () => {
        try {
            setIsLoading(true);
            const response = await fetch('/bank-entries/generate-automatic', {
                method: 'POST'
            });

            if (response.ok) {
                const result = await response.json();
                alert(`✅ ${result.count} asientos bancarios generados automáticamente`);
                loadAllData();
            } else {
                alert('❌ Error generando asientos automáticos');
            }
        } catch (error) {
            console.error('Error generating automatic entries:', error);
            alert('❌ Error: ' + error.message);
        } finally {
            setIsLoading(false);
        }
    }, [loadAllData]);

    // Expense reconciliation functions
    const performExpenseReconciliation = useCallback(async () => {
        try {
            setIsLoading(true);
            const response = await fetch('/expense-reconciliation/perform', {
                method: 'POST'
            });

            if (response.ok) {
                const result = await response.json();
                alert(`✅ Conciliación completada: ${result.matched} gastos conciliados`);
                loadAllData();
            } else {
                alert('❌ Error en conciliación de gastos');
            }
        } catch (error) {
            console.error('Error in expense reconciliation:', error);
            alert('❌ Error: ' + error.message);
        } finally {
            setIsLoading(false);
        }
    }, [loadAllData]);

    const markExpenseAsReconciled = useCallback(async (expenseId, bankMovementId) => {
        try {
            const response = await fetch('/expense-reconciliation/mark', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ expense_id: expenseId, bank_movement_id: bankMovementId })
            });

            if (response.ok) {
                alert('✅ Gasto marcado como conciliado');
                loadAllData();
            } else {
                alert('❌ Error marcando gasto como conciliado');
            }
        } catch (error) {
            console.error('Error marking expense as reconciled:', error);
            alert('❌ Error: ' + error.message);
        }
    }, [loadAllData]);

    // Massive XML processing
    const handleMassiveXMLUpload = useCallback(async (files) => {
        if (!files || files.length === 0) return;

        setIsLoading(true);
        const totalFiles = files.length;
        let processedFiles = 0;

        for (const file of files) {
            try {
                setProcessingStatus(prev => ({
                    ...prev,
                    [file.name]: 'processing'
                }));

                const formData = new FormData();
                formData.append('file', file);

                const response = await fetch('/invoices/parse-xml', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const result = await response.json();
                    setProcessingStatus(prev => ({
                        ...prev,
                        [file.name]: 'completed'
                    }));

                    // Auto-create expense from XML data
                    if (result.success) {
                        await fetch('/expenses', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                descripcion: result.concept || 'Gasto desde XML',
                                monto_total: result.total || 0,
                                fecha_gasto: result.date || new Date().toISOString().split('T')[0],
                                proveedor: { nombre: result.issuer_name || 'Proveedor XML' },
                                rfc: result.issuer_rfc || '',
                                factura_uuid: result.uuid || '',
                                estado_factura: 'facturado',
                                will_have_cfdi: true,
                                forma_pago: 'transferencia',
                                paid_by: 'company_account'
                            })
                        });
                    }
                } else {
                    setProcessingStatus(prev => ({
                        ...prev,
                        [file.name]: 'error'
                    }));
                }

                processedFiles++;
                setUploadProgress({
                    current: processedFiles,
                    total: totalFiles,
                    percentage: Math.round((processedFiles / totalFiles) * 100)
                });

            } catch (error) {
                console.error(`Error processing ${file.name}:`, error);
                setProcessingStatus(prev => ({
                    ...prev,
                    [file.name]: 'error'
                }));
            }
        }

        setIsLoading(false);
        loadAllData();
        alert(`✅ Procesamiento completado: ${processedFiles}/${totalFiles} archivos`);
    }, [loadAllData]);

    // Voice recognition with advanced parsing
    const startAdvancedVoiceRecording = useCallback(() => {
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            alert('⚠️ Reconocimiento de voz no soportado en este navegador');
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();

        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'es-ES';

        recognition.onstart = () => {
            setIsRecording(true);
            setTranscript('');
        };

        recognition.onresult = (event) => {
            const result = event.results[0][0].transcript;
            setTranscript(result);

            // Advanced parsing with AI-like intelligence
            const lowerResult = result.toLowerCase();

            // Extract amount with various formats
            const amountMatch = result.match(/(\d+(?:[.,]\d+)?)\s*(?:pesos|euros|dólares|$|usd|eur|mxn)?/i);
            if (amountMatch) {
                const amount = parseFloat(amountMatch[1].replace(',', '.'));
                handleFieldChange('monto_total', amount);
            }

            // Extract provider/merchant
            const providerPatterns = [
                /(?:en|de|del|en el|en la)\s+([a-záéíóúñ\s]+?)(?:\s+(?:por|de|con|para|el|la|los|las|un|una|$))/i,
                /(?:proveedor|empresa|tienda|restaurante|hotel|gasolinera)\s+([a-záéíóúñ\s]+?)(?:\s+(?:por|de|con|para|el|la|$))/i
            ];

            for (const pattern of providerPatterns) {
                const match = result.match(pattern);
                if (match && match[1].trim().length > 2) {
                    handleFieldChange('proveedor.nombre', match[1].trim());
                    break;
                }
            }

            // Set description
            handleFieldChange('descripcion', result);

            // Advanced category detection
            const categoryMappings = {
                'combustible': ['gasolina', 'pemex', 'bp', 'shell', 'mobil', 'combustible', 'diésel'],
                'alimentos': ['comida', 'restaurante', 'café', 'desayuno', 'almuerzo', 'cena', 'pizza', 'hamburguesa', 'tacos'],
                'hospedaje': ['hotel', 'motel', 'hospedaje', 'alojamiento', 'habitación', 'posada'],
                'transporte': ['taxi', 'uber', 'avión', 'vuelo', 'autobús', 'metro', 'estacionamiento', 'parking'],
                'material_oficina': ['papelería', 'office depot', 'staples', 'plumas', 'papel', 'impresora', 'tóner'],
                'tecnologia': ['computadora', 'laptop', 'software', 'licencia', 'microsoft', 'apple', 'dell', 'hp'],
                'marketing': ['publicidad', 'facebook ads', 'google ads', 'marketing', 'promoción', 'volantes']
            };

            for (const [category, keywords] of Object.entries(categoryMappings)) {
                if (keywords.some(keyword => lowerResult.includes(keyword))) {
                    handleFieldChange('categoria', category);
                    break;
                }
            }

            // Payment method detection
            if (lowerResult.includes('efectivo') || lowerResult.includes('cash')) {
                handleFieldChange('forma_pago', 'efectivo');
            } else if (lowerResult.includes('tarjeta empresa') || lowerResult.includes('tarjeta corporativa')) {
                handleFieldChange('forma_pago', 'tarjeta_empresa');
                handleFieldChange('paid_by', 'company_account');
            } else if (lowerResult.includes('transferencia') || lowerResult.includes('transfer')) {
                handleFieldChange('forma_pago', 'transferencia');
            }
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            setIsRecording(false);
            alert('❌ Error en reconocimiento de voz: ' + event.error);
        };

        recognition.onend = () => {
            setIsRecording(false);
        };

        recognition.start();
    }, [handleFieldChange]);

    // Load data on mount
    useEffect(() => {
        loadAllData();
        loadReconciliationSuggestions();
    }, [loadAllData, loadReconciliationSuggestions]);

    // Bank Reconciliation View
    if (currentView === 'bank-reconciliation') {
        return React.createElement('div', {
            className: 'max-w-7xl mx-auto px-4 py-6 space-y-6'
        }, [
            // Header
            React.createElement('div', {
                key: 'header',
                className: 'flex justify-between items-center'
            }, [
                React.createElement('h2', {
                    key: 'title',
                    className: 'text-2xl font-bold text-gray-900'
                }, '🏦 Conciliación Bancaria'),
                React.createElement('button', {
                    key: 'back',
                    onClick: () => setCurrentView('main'),
                    className: 'px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600'
                }, 'Volver')
            ]),

            // Stats
            React.createElement('div', {
                key: 'stats',
                className: 'grid grid-cols-1 md:grid-cols-3 gap-4'
            }, [
                React.createElement('div', {
                    key: 'movements',
                    className: 'bg-blue-50 border border-blue-200 rounded-lg p-4'
                }, [
                    React.createElement('h3', {
                        key: 'title',
                        className: 'text-lg font-semibold text-blue-800'
                    }, 'Movimientos Bancarios'),
                    React.createElement('p', {
                        key: 'count',
                        className: 'text-2xl font-bold text-blue-600'
                    }, bankMovements.length)
                ]),
                React.createElement('div', {
                    key: 'suggestions',
                    className: 'bg-green-50 border border-green-200 rounded-lg p-4'
                }, [
                    React.createElement('h3', {
                        key: 'title',
                        className: 'text-lg font-semibold text-green-800'
                    }, 'Sugerencias'),
                    React.createElement('p', {
                        key: 'count',
                        className: 'text-2xl font-bold text-green-600'
                    }, reconciliationSuggestions.length)
                ]),
                React.createElement('div', {
                    key: 'pending',
                    className: 'bg-orange-50 border border-orange-200 rounded-lg p-4'
                }, [
                    React.createElement('h3', {
                        key: 'title',
                        className: 'text-lg font-semibold text-orange-800'
                    }, 'Pendientes'),
                    React.createElement('p', {
                        key: 'count',
                        className: 'text-2xl font-bold text-orange-600'
                    }, bankMovements.filter(m => !m.reconciled).length)
                ])
            ]),

            // Reconciliation suggestions
            React.createElement('div', {
                key: 'suggestions',
                className: 'bg-white border border-gray-200 rounded-lg p-6'
            }, [
                React.createElement('h3', {
                    key: 'title',
                    className: 'text-lg font-semibold text-gray-900 mb-4'
                }, '🤖 Sugerencias Inteligentes'),
                reconciliationSuggestions.length > 0
                    ? React.createElement('div', {
                        key: 'list',
                        className: 'space-y-4'
                    }, reconciliationSuggestions.map((suggestion, index) =>
                        React.createElement('div', {
                            key: index,
                            className: 'border border-gray-200 rounded-lg p-4'
                        }, [
                            React.createElement('div', {
                                key: 'header',
                                className: 'flex justify-between items-start mb-3'
                            }, [
                                React.createElement('div', {
                                    key: 'info'
                                }, [
                                    React.createElement('p', {
                                        key: 'confidence',
                                        className: `text-sm font-medium ${
                                            suggestion.confidence > 0.8 ? 'text-green-600' :
                                            suggestion.confidence > 0.6 ? 'text-yellow-600' : 'text-red-600'
                                        }`
                                    }, `Confianza: ${Math.round(suggestion.confidence * 100)}%`),
                                    React.createElement('p', {
                                        key: 'amount',
                                        className: 'text-lg font-bold text-gray-900'
                                    }, `$${suggestion.amount}`),
                                    React.createElement('p', {
                                        key: 'description',
                                        className: 'text-gray-600'
                                    }, suggestion.description)
                                ]),
                                React.createElement('button', {
                                    key: 'approve',
                                    onClick: () => approveReconciliation(suggestion.movement_id, suggestion.expense_id),
                                    className: 'px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700'
                                }, 'Aprobar')
                            ]),
                            React.createElement('div', {
                                key: 'details',
                                className: 'text-sm text-gray-500'
                            }, [
                                React.createElement('p', {
                                    key: 'movement'
                                }, `Movimiento: ${suggestion.movement_description}`),
                                React.createElement('p', {
                                    key: 'expense'
                                }, `Gasto: ${suggestion.expense_description}`)
                            ])
                        ])
                    ))
                    : React.createElement('p', {
                        key: 'empty',
                        className: 'text-gray-500 text-center py-8'
                    }, 'No hay sugerencias de conciliación disponibles')
            ])
        ]);
    }

    // Massive Invoice Processing View
    if (currentView === 'massive-invoices') {
        return React.createElement('div', {
            className: 'max-w-7xl mx-auto px-4 py-6 space-y-6'
        }, [
            // Header
            React.createElement('div', {
                key: 'header',
                className: 'flex justify-between items-center'
            }, [
                React.createElement('h2', {
                    key: 'title',
                    className: 'text-2xl font-bold text-gray-900'
                }, '📄 Procesamiento Masivo de XML'),
                React.createElement('button', {
                    key: 'back',
                    onClick: () => setCurrentView('main'),
                    className: 'px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600'
                }, 'Volver')
            ]),

            // Upload area
            React.createElement('div', {
                key: 'upload',
                className: 'bg-white border border-gray-200 rounded-lg p-6'
            }, [
                React.createElement('h3', {
                    key: 'title',
                    className: 'text-lg font-semibold text-gray-900 mb-4'
                }, 'Cargar Archivos XML'),
                React.createElement('label', {
                    key: 'drop-zone',
                    className: 'block border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-gray-400'
                }, [
                    React.createElement('input', {
                        key: 'input',
                        type: 'file',
                        multiple: true,
                        accept: '.xml',
                        onChange: (e) => handleMassiveXMLUpload(Array.from(e.target.files)),
                        className: 'hidden'
                    }),
                    React.createElement('i', {
                        key: 'icon',
                        className: 'fas fa-cloud-upload-alt text-4xl text-gray-400 mb-4 block'
                    }),
                    React.createElement('p', {
                        key: 'text',
                        className: 'text-lg font-medium text-gray-600'
                    }, 'Arrastra archivos XML aquí o haz clic para seleccionar'),
                    React.createElement('p', {
                        key: 'help',
                        className: 'text-sm text-gray-500 mt-2'
                    }, 'Soporta múltiples archivos XML de CFDI')
                ])
            ]),

            // Progress
            Object.keys(uploadProgress).length > 0 && React.createElement('div', {
                key: 'progress',
                className: 'bg-white border border-gray-200 rounded-lg p-6'
            }, [
                React.createElement('h3', {
                    key: 'title',
                    className: 'text-lg font-semibold text-gray-900 mb-4'
                }, 'Progreso de Procesamiento'),
                React.createElement('div', {
                    key: 'bar',
                    className: 'w-full bg-gray-200 rounded-full h-2 mb-4'
                }, [
                    React.createElement('div', {
                        key: 'fill',
                        className: 'bg-blue-600 h-2 rounded-full transition-all duration-300',
                        style: { width: `${uploadProgress.percentage || 0}%` }
                    })
                ]),
                React.createElement('p', {
                    key: 'text',
                    className: 'text-center text-gray-600'
                }, `${uploadProgress.current || 0} de ${uploadProgress.total || 0} archivos procesados`)
            ]),

            // Processing status
            Object.keys(processingStatus).length > 0 && React.createElement('div', {
                key: 'status',
                className: 'bg-white border border-gray-200 rounded-lg p-6'
            }, [
                React.createElement('h3', {
                    key: 'title',
                    className: 'text-lg font-semibold text-gray-900 mb-4'
                }, 'Estado de Archivos'),
                React.createElement('div', {
                    key: 'files',
                    className: 'space-y-2'
                }, Object.entries(processingStatus).map(([filename, status]) =>
                    React.createElement('div', {
                        key: filename,
                        className: 'flex justify-between items-center py-2 px-3 border border-gray-200 rounded'
                    }, [
                        React.createElement('span', {
                            key: 'name',
                            className: 'text-gray-900'
                        }, filename),
                        React.createElement('span', {
                            key: 'status',
                            className: `text-sm font-medium ${
                                status === 'completed' ? 'text-green-600' :
                                status === 'processing' ? 'text-blue-600' :
                                status === 'error' ? 'text-red-600' : 'text-gray-600'
                            }`
                        }, {
                            'completed': '✅ Completado',
                            'processing': '⏳ Procesando...',
                            'error': '❌ Error',
                            'pending': '⏸️ Pendiente'
                        }[status] || status)
                    ])
                ))
            ])
        ]);
    }

    // Main dashboard view
    if (currentView === 'main') {
        return React.createElement('div', {
        className: 'max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6'
    }, [
        // Success notification
        React.createElement('div', {
            key: 'success',
            className: 'bg-green-50 border border-green-200 rounded-lg p-4 text-center'
        }, [
            React.createElement('div', {
                key: 'icon',
                className: 'text-3xl mb-2'
            }, '✅'),
            React.createElement('h3', {
                key: 'title',
                className: 'text-lg font-semibold text-green-800 mb-1'
            }, '¡Sistema Completo Restaurado!'),
            React.createElement('p', {
                key: 'message',
                className: 'text-green-600 text-sm'
            }, 'Todas las funcionalidades avanzadas disponibles sin badges molestos')
        ]),

        // Header
        React.createElement('div', {
            key: 'header',
            className: 'text-center space-y-4'
        }, [
            React.createElement('h2', {
                key: 'title',
                className: 'text-3xl font-bold text-gray-900'
            }, '📊 Centro de Control de Gastos'),
            React.createElement('p', {
                key: 'description',
                className: 'text-gray-600'
            }, 'Captura por voz o ticket, vincula facturas y concilia con el banco en un solo flujo.')
        ]),

        // Advanced feature cards
        React.createElement('div', {
            key: 'features',
            className: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4'
        }, [
            React.createElement('div', {
                key: 'voice',
                className: 'bg-blue-50 border border-blue-200 rounded-lg p-6 cursor-pointer hover:bg-blue-100 transition-colors',
                onClick: () => setCurrentView('expense-form')
            }, [
                React.createElement('div', {
                    key: 'header',
                    className: 'flex items-center mb-3'
                }, [
                    React.createElement('i', {
                        key: 'icon',
                        className: 'fas fa-microphone text-2xl text-blue-600 mr-3'
                    }),
                    React.createElement('h3', {
                        key: 'title',
                        className: 'text-lg font-semibold text-blue-800'
                    }, 'Captura por Voz')
                ]),
                React.createElement('p', {
                    key: 'description',
                    className: 'text-blue-600 text-sm'
                }, 'Reconocimiento de voz avanzado con IA para extraer datos automáticamente')
            ]),

            React.createElement('div', {
                key: 'bank',
                className: 'bg-green-50 border border-green-200 rounded-lg p-6 cursor-pointer hover:bg-green-100 transition-colors',
                onClick: () => setCurrentView('bank-reconciliation')
            }, [
                React.createElement('div', {
                    key: 'header',
                    className: 'flex items-center mb-3'
                }, [
                    React.createElement('i', {
                        key: 'icon',
                        className: 'fas fa-university text-2xl text-green-600 mr-3'
                    }),
                    React.createElement('h3', {
                        key: 'title',
                        className: 'text-lg font-semibold text-green-800'
                    }, 'Conciliación Bancaria')
                ]),
                React.createElement('p', {
                    key: 'description',
                    className: 'text-green-600 text-sm'
                }, 'Sugerencias inteligentes para conciliar movimientos bancarios con gastos')
            ]),

            // Bank entries button
            React.createElement('div', {
                key: 'bank-entries',
                className: 'bg-blue-50 border border-blue-200 rounded-lg p-6 cursor-pointer hover:bg-blue-100 transition-colors',
                onClick: () => setCurrentView('bank-entries')
            }, [
                React.createElement('div', {
                    key: 'header',
                    className: 'flex items-center mb-3'
                }, [
                    React.createElement('i', {
                        key: 'icon',
                        className: 'fas fa-clipboard-list text-2xl text-blue-600 mr-3'
                    }),
                    React.createElement('h3', {
                        key: 'title',
                        className: 'text-lg font-semibold text-blue-800'
                    }, 'Asientos Bancarios')
                ]),
                React.createElement('p', {
                    key: 'description',
                    className: 'text-blue-600 text-sm'
                }, 'Genera y gestiona asientos contables de movimientos bancarios')
            ]),

            // Expense reconciliation button
            React.createElement('div', {
                key: 'expense-reconciliation',
                className: 'bg-purple-50 border border-purple-200 rounded-lg p-6 cursor-pointer hover:bg-purple-100 transition-colors',
                onClick: () => setCurrentView('expense-reconciliation')
            }, [
                React.createElement('div', {
                    key: 'header',
                    className: 'flex items-center mb-3'
                }, [
                    React.createElement('i', {
                        key: 'icon',
                        className: 'fas fa-balance-scale text-2xl text-purple-600 mr-3'
                    }),
                    React.createElement('h3', {
                        key: 'title',
                        className: 'text-lg font-semibold text-purple-800'
                    }, 'Conciliación de Gastos')
                ]),
                React.createElement('p', {
                    key: 'description',
                    className: 'text-purple-600 text-sm'
                }, 'Reconcilia y valida gastos contra facturas y pagos')
            ]),

            React.createElement('div', {
                key: 'xml',
                className: 'bg-purple-50 border border-purple-200 rounded-lg p-6 cursor-pointer hover:bg-purple-100 transition-colors',
                onClick: () => setCurrentView('massive-invoices')
            }, [
                React.createElement('div', {
                    key: 'header',
                    className: 'flex items-center mb-3'
                }, [
                    React.createElement('i', {
                        key: 'icon',
                        className: 'fas fa-file-code text-2xl text-purple-600 mr-3'
                    }),
                    React.createElement('h3', {
                        key: 'title',
                        className: 'text-lg font-semibold text-purple-800'
                    }, 'XML Masivo')
                ]),
                React.createElement('p', {
                    key: 'description',
                    className: 'text-purple-600 text-sm'
                }, 'Procesamiento masivo de archivos XML de CFDI con extracción automática')
            ]),

            React.createElement('div', {
                key: 'ocr',
                className: 'bg-orange-50 border border-orange-200 rounded-lg p-6 cursor-pointer hover:bg-orange-100 transition-colors',
                onClick: () => setCurrentView('expense-form')
            }, [
                React.createElement('div', {
                    key: 'header',
                    className: 'flex items-center mb-3'
                }, [
                    React.createElement('i', {
                        key: 'icon',
                        className: 'fas fa-camera text-2xl text-orange-600 mr-3'
                    }),
                    React.createElement('h3', {
                        key: 'title',
                        className: 'text-lg font-semibold text-orange-800'
                    }, 'OCR Inteligente')
                ]),
                React.createElement('p', {
                    key: 'description',
                    className: 'text-orange-600 text-sm'
                }, 'Extracción automática de datos de tickets y facturas con IA')
            ]),

            React.createElement('div', {
                key: 'dashboard',
                className: 'bg-indigo-50 border border-indigo-200 rounded-lg p-6 cursor-pointer hover:bg-indigo-100 transition-colors',
                onClick: () => setCurrentView('dashboard')
            }, [
                React.createElement('div', {
                    key: 'header',
                    className: 'flex items-center mb-3'
                }, [
                    React.createElement('i', {
                        key: 'icon',
                        className: 'fas fa-chart-bar text-2xl text-indigo-600 mr-3'
                    }),
                    React.createElement('h3', {
                        key: 'title',
                        className: 'text-lg font-semibold text-indigo-800'
                    }, 'Analytics Avanzado')
                ]),
                React.createElement('p', {
                    key: 'description',
                    className: 'text-indigo-600 text-sm'
                }, 'Dashboard con KPIs, tendencias y análisis predictivo de gastos')
            ]),

            React.createElement('a', {
                key: 'tickets',
                href: '/advanced-ticket-dashboard.html',
                className: 'bg-red-50 border border-red-200 rounded-lg p-6 hover:bg-red-100 transition-colors block'
            }, [
                React.createElement('div', {
                    key: 'header',
                    className: 'flex items-center mb-3'
                }, [
                    React.createElement('i', {
                        key: 'icon',
                        className: 'fas fa-receipt text-2xl text-red-600 mr-3'
                    }),
                    React.createElement('h3', {
                        key: 'title',
                        className: 'text-lg font-semibold text-red-800'
                    }, 'Dashboard Tickets')
                ]),
                React.createElement('p', {
                    key: 'description',
                    className: 'text-red-600 text-sm'
                }, 'Sistema avanzado de gestión y análisis de tickets automáticos')
            ])
        ]),

        // Quick stats
        React.createElement('div', {
            key: 'stats',
            className: 'grid grid-cols-2 md:grid-cols-4 gap-4'
        }, [
            React.createElement('div', {
                key: 'expenses',
                className: 'bg-white border border-gray-200 rounded-lg p-4 text-center'
            }, [
                React.createElement('p', {
                    key: 'value',
                    className: 'text-2xl font-bold text-gray-900'
                }, expensesData.length),
                React.createElement('p', {
                    key: 'label',
                    className: 'text-xs text-gray-500 uppercase'
                }, 'Gastos')
            ]),
            React.createElement('div', {
                key: 'bank',
                className: 'bg-white border border-gray-200 rounded-lg p-4 text-center'
            }, [
                React.createElement('p', {
                    key: 'value',
                    className: 'text-2xl font-bold text-green-600'
                }, bankMovements.length),
                React.createElement('p', {
                    key: 'label',
                    className: 'text-xs text-gray-500 uppercase'
                }, 'Mov. Bancarios')
            ]),
            React.createElement('div', {
                key: 'suggestions',
                className: 'bg-white border border-gray-200 rounded-lg p-4 text-center'
            }, [
                React.createElement('p', {
                    key: 'value',
                    className: 'text-2xl font-bold text-blue-600'
                }, reconciliationSuggestions.length),
                React.createElement('p', {
                    key: 'label',
                    className: 'text-xs text-gray-500 uppercase'
                }, 'Sugerencias')
            ]),
            React.createElement('div', {
                key: 'invoices',
                className: 'bg-white border border-gray-200 rounded-lg p-4 text-center'
            }, [
                React.createElement('p', {
                    key: 'value',
                    className: 'text-2xl font-bold text-purple-600'
                }, pendingInvoices.length),
                React.createElement('p', {
                    key: 'label',
                    className: 'text-xs text-gray-500 uppercase'
                }, 'Facturas')
            ])
        ])
    ]);
    }

    // Expense Form View with Voice Recognition
    if (currentView === 'expense-form') {
        return React.createElement('div', {
            className: 'max-w-4xl mx-auto px-4 py-6 space-y-6'
        }, [
            // Header
            React.createElement('div', {
                key: 'header',
                className: 'flex justify-between items-center'
            }, [
                React.createElement('h2', {
                    key: 'title',
                    className: 'text-2xl font-bold text-gray-900'
                }, '🎤 Captura de Gastos por Voz'),
                React.createElement('button', {
                    key: 'back',
                    onClick: () => setCurrentView('main'),
                    className: 'px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600'
                }, 'Volver')
            ]),

            // Voice Recording Card
            React.createElement('div', {
                key: 'voice-card',
                className: 'bg-white rounded-lg shadow-sm border p-8'
            }, [
                React.createElement('div', {
                    key: 'voice-section',
                    className: 'text-center'
                }, [
                    React.createElement('div', {
                        key: 'mic-button',
                        onClick: startAdvancedVoiceRecording,
                        className: `w-24 h-24 mx-auto mb-6 rounded-full flex items-center justify-center cursor-pointer transition-all ${
                            isRecording
                                ? 'bg-red-500 recording-ring'
                                : 'bg-blue-500 hover:bg-blue-600'
                        }`
                    }, [
                        React.createElement('i', {
                            key: 'mic-icon',
                            className: `fas fa-microphone text-3xl text-white ${
                                isRecording ? 'pulse-animation' : ''
                            }`
                        })
                    ]),
                    React.createElement('h3', {
                        key: 'title',
                        className: 'text-xl font-semibold text-gray-800 mb-2'
                    }, isRecording ? '🔴 Grabando...' : '🎙️ Haz clic para grabar'),
                    React.createElement('p', {
                        key: 'instruction',
                        className: 'text-gray-600 mb-4'
                    }, 'Describe tu gasto: "Gasté 150 pesos en comida en Starbucks el lunes"'),

                    // Transcript Display
                    transcript && React.createElement('div', {
                        key: 'transcript',
                        className: 'mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg'
                    }, [
                        React.createElement('h4', {
                            key: 'transcript-title',
                            className: 'font-semibold text-blue-800 mb-2'
                        }, '📝 Transcripción:'),
                        React.createElement('p', {
                            key: 'transcript-text',
                            className: 'text-blue-700'
                        }, transcript)
                    ])
                ])
            ]),

            // Complete Manual Form (all fields like original)
            React.createElement('div', {
                key: 'manual-form',
                className: 'bg-white rounded-lg shadow-sm border p-6'
            }, [
                React.createElement('h3', {
                    key: 'form-title',
                    className: 'text-lg font-semibold text-gray-800 mb-4'
                }, '✏️ Formulario completo de gastos:'),

                // Primera fila de campos
                React.createElement('div', {
                    key: 'form-grid-1',
                    className: 'grid grid-cols-1 md:grid-cols-3 gap-4 mb-4'
                }, [
                    React.createElement('div', {
                        key: 'description-field'
                    }, [
                        React.createElement('label', {
                            key: 'desc-label',
                            className: 'block text-sm font-medium text-gray-700 mb-1'
                        }, 'Descripción *'),
                        React.createElement('input', {
                            key: 'desc-input',
                            type: 'text',
                            value: getFieldValue('descripcion'),
                            onChange: (e) => handleFieldChange('descripcion', e.target.value),
                            className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                            placeholder: 'Ej: Comida en Starbucks'
                        })
                    ]),
                    React.createElement('div', {
                        key: 'amount-field'
                    }, [
                        React.createElement('label', {
                            key: 'amount-label',
                            className: 'block text-sm font-medium text-gray-700 mb-1'
                        }, 'Monto total *'),
                        React.createElement('input', {
                            key: 'amount-input',
                            type: 'number',
                            step: '0.01',
                            value: getFieldValue('monto_total'),
                            onChange: (e) => handleFieldChange('monto_total', parseFloat(e.target.value) || 0),
                            className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                            placeholder: 'Ej: 150.00'
                        })
                    ]),
                    React.createElement('div', {
                        key: 'date-field'
                    }, [
                        React.createElement('label', {
                            key: 'date-label',
                            className: 'block text-sm font-medium text-gray-700 mb-1'
                        }, 'Fecha del gasto *'),
                        React.createElement('input', {
                            key: 'date-input',
                            type: 'date',
                            value: getFieldValue('fecha_gasto'),
                            onChange: (e) => handleFieldChange('fecha_gasto', e.target.value),
                            className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
                        })
                    ])
                ]),

                // Segunda fila de campos
                React.createElement('div', {
                    key: 'form-grid-2',
                    className: 'grid grid-cols-1 md:grid-cols-3 gap-4 mb-4'
                }, [
                    React.createElement('div', {
                        key: 'category-field'
                    }, [
                        React.createElement('label', {
                            key: 'category-label',
                            className: 'block text-sm font-medium text-gray-700 mb-1'
                        }, 'Categoría *'),
                        React.createElement('select', {
                            key: 'category-select',
                            value: getFieldValue('categoria'),
                            onChange: (e) => handleFieldChange('categoria', e.target.value),
                            className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
                        }, [
                            React.createElement('option', { key: 'cat-0', value: '' }, 'Seleccionar categoría'),
                            React.createElement('option', { key: 'cat-1', value: 'alimentacion' }, 'Alimentación'),
                            React.createElement('option', { key: 'cat-2', value: 'transporte' }, 'Transporte'),
                            React.createElement('option', { key: 'cat-3', value: 'hospedaje' }, 'Hospedaje'),
                            React.createElement('option', { key: 'cat-4', value: 'oficina' }, 'Material de oficina'),
                            React.createElement('option', { key: 'cat-5', value: 'servicios' }, 'Servicios'),
                            React.createElement('option', { key: 'cat-6', value: 'combustible' }, 'Combustible'),
                            React.createElement('option', { key: 'cat-7', value: 'marketing' }, 'Marketing'),
                            React.createElement('option', { key: 'cat-8', value: 'tecnologia' }, 'Tecnología'),
                            React.createElement('option', { key: 'cat-9', value: 'otros' }, 'Otros')
                        ])
                    ]),
                    React.createElement('div', {
                        key: 'currency-field'
                    }, [
                        React.createElement('label', {
                            key: 'currency-label',
                            className: 'block text-sm font-medium text-gray-700 mb-1'
                        }, 'Moneda'),
                        React.createElement('select', {
                            key: 'currency-select',
                            value: getFieldValue('moneda') || 'MXN',
                            onChange: (e) => handleFieldChange('moneda', e.target.value),
                            className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
                        }, [
                            React.createElement('option', { key: 'mxn', value: 'MXN' }, 'MXN (Pesos)'),
                            React.createElement('option', { key: 'usd', value: 'USD' }, 'USD (Dólares)'),
                            React.createElement('option', { key: 'eur', value: 'EUR' }, 'EUR (Euros)')
                        ])
                    ]),
                    React.createElement('div', {
                        key: 'employee-field'
                    }, [
                        React.createElement('label', {
                            key: 'employee-label',
                            className: 'block text-sm font-medium text-gray-700 mb-1'
                        }, 'Empleado'),
                        React.createElement('input', {
                            key: 'employee-input',
                            type: 'text',
                            value: getFieldValue('empleado') || 'Usuario Demo',
                            onChange: (e) => handleFieldChange('empleado', e.target.value),
                            className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                            placeholder: 'Nombre del empleado'
                        })
                    ])
                ]),

                // Tercera fila de campos
                React.createElement('div', {
                    key: 'form-grid-3',
                    className: 'grid grid-cols-1 md:grid-cols-2 gap-4 mb-4'
                }, [
                    React.createElement('div', {
                        key: 'supplier-field'
                    }, [
                        React.createElement('label', {
                            key: 'supplier-label',
                            className: 'block text-sm font-medium text-gray-700 mb-1'
                        }, 'Proveedor'),
                        React.createElement('input', {
                            key: 'supplier-input',
                            type: 'text',
                            value: getFieldValue('proveedor_nombre'),
                            onChange: (e) => handleFieldChange('proveedor_nombre', e.target.value),
                            className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                            placeholder: 'Ej: Starbucks, Uber, etc.'
                        })
                    ]),
                    React.createElement('div', {
                        key: 'reference-field'
                    }, [
                        React.createElement('label', {
                            key: 'reference-label',
                            className: 'block text-sm font-medium text-gray-700 mb-1'
                        }, 'Referencia'),
                        React.createElement('input', {
                            key: 'reference-input',
                            type: 'text',
                            value: getFieldValue('referencia'),
                            onChange: (e) => handleFieldChange('referencia', e.target.value),
                            className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                            placeholder: 'Número de transacción, folio, etc.'
                        })
                    ])
                ]),

                // Cuarta fila - campos adicionales
                React.createElement('div', {
                    key: 'form-grid-4',
                    className: 'grid grid-cols-1 md:grid-cols-3 gap-4 mb-4'
                }, [
                    React.createElement('div', {
                        key: 'project-field'
                    }, [
                        React.createElement('label', {
                            key: 'project-label',
                            className: 'block text-sm font-medium text-gray-700 mb-1'
                        }, 'Proyecto'),
                        React.createElement('select', {
                            key: 'project-select',
                            value: getFieldValue('proyecto'),
                            onChange: (e) => handleFieldChange('proyecto', e.target.value),
                            className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
                        }, [
                            React.createElement('option', { key: 'proj-0', value: '' }, 'Sin proyecto'),
                            React.createElement('option', { key: 'proj-1', value: 'proyecto-a' }, 'Proyecto A'),
                            React.createElement('option', { key: 'proj-2', value: 'proyecto-b' }, 'Proyecto B'),
                            React.createElement('option', { key: 'proj-3', value: 'proyecto-c' }, 'Proyecto C'),
                            React.createElement('option', { key: 'proj-4', value: 'operaciones' }, 'Operaciones'),
                            React.createElement('option', { key: 'proj-5', value: 'administracion' }, 'Administración')
                        ])
                    ]),
                    React.createElement('div', {
                        key: 'account-field'
                    }, [
                        React.createElement('label', {
                            key: 'account-label',
                            className: 'block text-sm font-medium text-gray-700 mb-1'
                        }, 'Cuenta contable'),
                        React.createElement('input', {
                            key: 'account-input',
                            type: 'text',
                            value: getFieldValue('cuenta_contable'),
                            onChange: (e) => handleFieldChange('cuenta_contable', e.target.value),
                            className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                            placeholder: 'Ej: 5101, 5201, etc.'
                        })
                    ]),
                    React.createElement('div', {
                        key: 'cost-center-field'
                    }, [
                        React.createElement('label', {
                            key: 'cost-center-label',
                            className: 'block text-sm font-medium text-gray-700 mb-1'
                        }, 'Centro de costo'),
                        React.createElement('select', {
                            key: 'cost-center-select',
                            value: getFieldValue('centro_costo'),
                            onChange: (e) => handleFieldChange('centro_costo', e.target.value),
                            className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
                        }, [
                            React.createElement('option', { key: 'cc-0', value: '' }, 'Sin centro de costo'),
                            React.createElement('option', { key: 'cc-1', value: 'ventas' }, 'Ventas'),
                            React.createElement('option', { key: 'cc-2', value: 'marketing' }, 'Marketing'),
                            React.createElement('option', { key: 'cc-3', value: 'operaciones' }, 'Operaciones'),
                            React.createElement('option', { key: 'cc-4', value: 'administracion' }, 'Administración'),
                            React.createElement('option', { key: 'cc-5', value: 'tecnologia' }, 'Tecnología')
                        ])
                    ])
                ]),

                // Campo de notas
                React.createElement('div', {
                    key: 'notes-field',
                    className: 'mb-4'
                }, [
                    React.createElement('label', {
                        key: 'notes-label',
                        className: 'block text-sm font-medium text-gray-700 mb-1'
                    }, 'Notas adicionales'),
                    React.createElement('textarea', {
                        key: 'notes-input',
                        value: getFieldValue('notas'),
                        onChange: (e) => handleFieldChange('notas', e.target.value),
                        rows: 3,
                        className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                        placeholder: 'Detalles adicionales del gasto, justificación, etc.'
                    })
                ]),
                React.createElement('div', {
                    key: 'form-actions',
                    className: 'mt-6 flex gap-3'
                }, [
                    React.createElement('button', {
                        key: 'save-btn',
                        onClick: async () => {
                            try {
                                const response = await fetch('/expenses', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify(formData)
                                });

                                if (response.ok) {
                                    alert('✅ Gasto guardado exitosamente');
                                    setFormData({});
                                    setTranscript('');
                                    loadAllData();
                                } else {
                                    alert('❌ Error guardando el gasto');
                                }
                            } catch (error) {
                                alert('❌ Error: ' + error.message);
                            }
                        },
                        disabled: !getFieldValue('descripcion') || !getFieldValue('monto_total'),
                        className: 'px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed'
                    }, '💾 Guardar Gasto'),
                    React.createElement('button', {
                        key: 'clear-btn',
                        onClick: () => {
                            setFormData({});
                            setTranscript('');
                        },
                        className: 'px-6 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600'
                    }, '🗑️ Limpiar')
                ])
            ])
        ]);
    }

    // Bank Entries View
    if (currentView === 'bank-entries') {
        return React.createElement('div', {
            className: 'max-w-7xl mx-auto px-4 py-6 space-y-6'
        }, [
            // Header
            React.createElement('div', {
                key: 'header',
                className: 'flex justify-between items-center'
            }, [
                React.createElement('h2', {
                    key: 'title',
                    className: 'text-2xl font-bold text-gray-900'
                }, '📋 Asientos Bancarios'),
                React.createElement('button', {
                    key: 'back',
                    onClick: () => setCurrentView('main'),
                    className: 'px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600'
                }, 'Volver')
            ]),

            // Actions
            React.createElement('div', {
                key: 'actions',
                className: 'flex gap-4'
            }, [
                React.createElement('button', {
                    key: 'generate',
                    onClick: generateAutomaticBankEntries,
                    disabled: isLoading,
                    className: 'px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50'
                }, isLoading ? 'Generando...' : '🤖 Generar Automático'),
                React.createElement('button', {
                    key: 'manual',
                    onClick: () => {
                        const amount = prompt('Monto:');
                        const description = prompt('Descripción:');
                        const account = prompt('Cuenta:');
                        if (amount && description && account) {
                            createBankEntry({ amount, description, account });
                        }
                    },
                    className: 'px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700'
                }, '✏️ Crear Manual')
            ]),

            // Bank entries list
            React.createElement('div', {
                key: 'entries',
                className: 'bg-white rounded-lg shadow-sm border'
            }, [
                React.createElement('div', {
                    key: 'header',
                    className: 'px-6 py-4 border-b'
                }, [
                    React.createElement('h3', {
                        key: 'title',
                        className: 'text-lg font-semibold'
                    }, `Asientos Bancarios (${bankEntries.length})`)
                ]),
                React.createElement('div', {
                    key: 'content',
                    className: 'p-6'
                }, bankEntries.length > 0
                    ? bankEntries.map((entry, index) =>
                        React.createElement('div', {
                            key: `entry-${index}`,
                            className: 'border border-gray-200 rounded-lg p-4 mb-4'
                        }, [
                            React.createElement('div', {
                                key: 'info',
                                className: 'flex justify-between items-start'
                            }, [
                                React.createElement('div', {
                                    key: 'details'
                                }, [
                                    React.createElement('p', {
                                        key: 'amount',
                                        className: 'text-lg font-bold text-gray-900'
                                    }, `$${entry.amount}`),
                                    React.createElement('p', {
                                        key: 'description',
                                        className: 'text-gray-600'
                                    }, entry.description),
                                    React.createElement('p', {
                                        key: 'account',
                                        className: 'text-sm text-gray-500'
                                    }, `Cuenta: ${entry.account}`)
                                ]),
                                React.createElement('span', {
                                    key: 'status',
                                    className: `px-3 py-1 rounded-full text-xs font-medium ${
                                        entry.status === 'processed' ? 'bg-green-100 text-green-800' :
                                        entry.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                                        'bg-gray-100 text-gray-800'
                                    }`
                                }, entry.status || 'new')
                            ])
                        ])
                    )
                    : React.createElement('p', {
                        key: 'empty',
                        className: 'text-gray-500 text-center py-8'
                    }, 'No hay asientos bancarios disponibles')
                )
            ])
        ]);
    }

    // Expense Reconciliation View
    if (currentView === 'expense-reconciliation') {
        return React.createElement('div', {
            className: 'max-w-7xl mx-auto px-4 py-6 space-y-6'
        }, [
            // Header
            React.createElement('div', {
                key: 'header',
                className: 'flex justify-between items-center'
            }, [
                React.createElement('h2', {
                    key: 'title',
                    className: 'text-2xl font-bold text-gray-900'
                }, '⚖️ Conciliación de Gastos'),
                React.createElement('button', {
                    key: 'back',
                    onClick: () => setCurrentView('main'),
                    className: 'px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600'
                }, 'Volver')
            ]),

            // Actions
            React.createElement('div', {
                key: 'actions',
                className: 'flex gap-4'
            }, [
                React.createElement('button', {
                    key: 'perform',
                    onClick: performExpenseReconciliation,
                    disabled: isLoading,
                    className: 'px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50'
                }, isLoading ? 'Conciliando...' : '🔄 Iniciar Conciliación'),
                React.createElement('button', {
                    key: 'manual',
                    onClick: () => {
                        const expenseId = prompt('ID del Gasto:');
                        const bankMovementId = prompt('ID del Movimiento Bancario:');
                        if (expenseId && bankMovementId) {
                            markExpenseAsReconciled(expenseId, bankMovementId);
                        }
                    },
                    className: 'px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700'
                }, '✓ Marcar Manual')
            ]),

            // Reconciliation list
            React.createElement('div', {
                key: 'reconciliation',
                className: 'bg-white rounded-lg shadow-sm border'
            }, [
                React.createElement('div', {
                    key: 'header',
                    className: 'px-6 py-4 border-b'
                }, [
                    React.createElement('h3', {
                        key: 'title',
                        className: 'text-lg font-semibold'
                    }, `Gastos Conciliados (${expenseReconciliation.length})`)
                ]),
                React.createElement('div', {
                    key: 'content',
                    className: 'p-6'
                }, expenseReconciliation.length > 0
                    ? expenseReconciliation.map((recon, index) =>
                        React.createElement('div', {
                            key: `recon-${index}`,
                            className: 'border border-gray-200 rounded-lg p-4 mb-4'
                        }, [
                            React.createElement('div', {
                                key: 'info',
                                className: 'flex justify-between items-start'
                            }, [
                                React.createElement('div', {
                                    key: 'details'
                                }, [
                                    React.createElement('p', {
                                        key: 'amount',
                                        className: 'text-lg font-bold text-gray-900'
                                    }, `$${recon.amount}`),
                                    React.createElement('p', {
                                        key: 'expense',
                                        className: 'text-gray-600'
                                    }, `Gasto: ${recon.expense_description}`),
                                    React.createElement('p', {
                                        key: 'movement',
                                        className: 'text-sm text-gray-500'
                                    }, `Movimiento: ${recon.bank_movement_description}`)
                                ]),
                                React.createElement('span', {
                                    key: 'status',
                                    className: `px-3 py-1 rounded-full text-xs font-medium ${
                                        recon.status === 'reconciled' ? 'bg-green-100 text-green-800' :
                                        recon.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                                        'bg-gray-100 text-gray-800'
                                    }`
                                }, recon.status || 'new')
                            ])
                        ])
                    )
                    : React.createElement('p', {
                        key: 'empty',
                        className: 'text-gray-500 text-center py-8'
                    }, 'No hay gastos conciliados disponibles')
                )
            ])
        ]);
    }
};

console.log('Advanced complete expenses system loaded');

// Renderizar la aplicación
const root = ReactDOM.createRoot(document.getElementById('app-root'));
root.render(React.createElement(AdvancedCompleteExpenses, null));
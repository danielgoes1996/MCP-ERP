const { useState, useCallback, useEffect, useRef } = React;

const CompleteExpenses = () => {
    // Core state
    const [showExpenseForm, setShowExpenseForm] = useState(false);
    const [expensesData, setExpensesData] = useState([]);
    const [formData, setFormData] = useState({});
    const [isRecording, setIsRecording] = useState(false);
    const [transcript, setTranscript] = useState('');
    const [showDashboard, setShowDashboard] = useState(false);
    const [isLoading, setIsLoading] = useState(false);

    // Simple field change handler (defined first)
    const handleFieldChange = useCallback((field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    }, []);

    // Get field value helper (defined second)
    const getFieldValue = (field) => {
        return formData[field] || '';
    };

    // OCR file processing
    const handleFileUpload = useCallback(async (file) => {
        if (!file) return;

        setIsLoading(true);
        try {
            const formDataFile = new FormData();
            formDataFile.append('file', file);

            const response = await fetch('/process_ticket', {
                method: 'POST',
                body: formDataFile
            });

            if (response.ok) {
                const result = await response.json();

                // Auto-fill form with OCR results
                if (result.merchant_name) handleFieldChange('proveedor.nombre', result.merchant_name);
                if (result.total) handleFieldChange('monto_total', parseFloat(result.total));
                if (result.date) handleFieldChange('fecha_gasto', result.date);
                if (result.category) handleFieldChange('categoria', result.category);

                alert('✅ Ticket procesado exitosamente');
            } else {
                alert('❌ Error procesando ticket');
            }
        } catch (error) {
            console.error('OCR Error:', error);
            alert('❌ Error en OCR: ' + error.message);
        } finally {
            setIsLoading(false);
        }
    }, [handleFieldChange]);

    // Voice recognition
    const startVoiceRecording = useCallback(() => {
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

            // Simple parsing for common patterns
            const lowerResult = result.toLowerCase();

            // Extract amount
            const amountMatch = result.match(/(\d+(?:[.,]\d+)?)\s*(?:pesos|euros|dólares|$)?/i);
            if (amountMatch) {
                const amount = parseFloat(amountMatch[1].replace(',', '.'));
                handleFieldChange('monto_total', amount);
            }

            // Extract basic description
            handleFieldChange('descripcion', result);

            // Common categories
            if (lowerResult.includes('gasolina') || lowerResult.includes('pemex')) {
                handleFieldChange('categoria', 'combustible');
            } else if (lowerResult.includes('comida') || lowerResult.includes('restaurante')) {
                handleFieldChange('categoria', 'alimentos');
            } else if (lowerResult.includes('hotel') || lowerResult.includes('hospedaje')) {
                handleFieldChange('categoria', 'hospedaje');
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

    // Form submission
    const handleSubmit = useCallback(async () => {
        if (!formData.descripcion || !formData.monto_total) {
            alert('⚠️ Completa al menos descripción y monto');
            return;
        }

        setIsLoading(true);
        try {
            const response = await fetch('/expenses', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...formData,
                    fecha_gasto: formData.fecha_gasto || new Date().toISOString().split('T')[0],
                    categoria: formData.categoria || 'otros',
                    forma_pago: formData.forma_pago || 'tarjeta_empresa',
                    will_have_cfdi: formData.will_have_cfdi !== false,
                    paid_by: formData.paid_by || 'company_account'
                })
            });

            if (response.ok) {
                alert('✅ Gasto guardado exitosamente');
                setFormData({});
                setTranscript('');
                setShowExpenseForm(false);
                loadExpenses(); // Reload expenses
            } else {
                throw new Error('Error del servidor');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('❌ Error guardando gasto: ' + error.message);
        } finally {
            setIsLoading(false);
        }
    }, [formData]);

    // Load expenses
    const loadExpenses = useCallback(async () => {
        try {
            const response = await fetch('/expenses');
            if (response.ok) {
                const data = await response.json();
                setExpensesData(data);
            }
        } catch (error) {
            console.error('Error loading expenses:', error);
        }
    }, []);

    // Load expenses on mount
    useEffect(() => {
        loadExpenses();
    }, [loadExpenses]);

    // Categories for dropdown
    const categories = [
        { value: 'combustible', label: '⛽ Combustible' },
        { value: 'alimentos', label: '🍽️ Alimentos y Bebidas' },
        { value: 'transporte', label: '🚗 Transporte' },
        { value: 'hospedaje', label: '🏨 Hospedaje' },
        { value: 'material_oficina', label: '📎 Material de Oficina' },
        { value: 'tecnologia', label: '💻 Tecnología' },
        { value: 'marketing', label: '📢 Marketing' },
        { value: 'otros', label: '📋 Otros' }
    ];

    // Main dashboard view
    if (showDashboard) {
        const totalAmount = expensesData.reduce((sum, expense) => sum + (expense.monto_total || 0), 0);
        const facturedCount = expensesData.filter(exp => exp.estado_factura === 'facturado').length;
        const pendingCount = expensesData.filter(exp => exp.estado_factura === 'pendiente').length;

        return React.createElement('div', {
            className: 'max-w-6xl mx-auto px-4 py-6 space-y-6'
        }, [
            // Header
            React.createElement('div', {
                key: 'header',
                className: 'flex justify-between items-center'
            }, [
                React.createElement('h2', {
                    key: 'title',
                    className: 'text-2xl font-bold text-gray-900'
                }, '📊 Dashboard de Gastos'),
                React.createElement('button', {
                    key: 'close',
                    onClick: () => setShowDashboard(false),
                    className: 'px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600'
                }, 'Cerrar')
            ]),

            // Stats cards
            React.createElement('div', {
                key: 'stats',
                className: 'grid grid-cols-1 md:grid-cols-4 gap-4'
            }, [
                React.createElement('div', {
                    key: 'total',
                    className: 'bg-white border border-gray-200 rounded-lg p-4'
                }, [
                    React.createElement('p', {
                        key: 'label',
                        className: 'text-xs text-gray-500 uppercase tracking-wide'
                    }, 'Total gastos'),
                    React.createElement('p', {
                        key: 'value',
                        className: 'text-2xl font-bold text-gray-900'
                    }, expensesData.length)
                ]),
                React.createElement('div', {
                    key: 'amount',
                    className: 'bg-white border border-gray-200 rounded-lg p-4'
                }, [
                    React.createElement('p', {
                        key: 'label',
                        className: 'text-xs text-gray-500 uppercase tracking-wide'
                    }, 'Monto total'),
                    React.createElement('p', {
                        key: 'value',
                        className: 'text-2xl font-bold text-green-600'
                    }, `$${totalAmount.toFixed(2)}`)
                ]),
                React.createElement('div', {
                    key: 'factured',
                    className: 'bg-white border border-gray-200 rounded-lg p-4'
                }, [
                    React.createElement('p', {
                        key: 'label',
                        className: 'text-xs text-gray-500 uppercase tracking-wide'
                    }, 'Facturados'),
                    React.createElement('p', {
                        key: 'value',
                        className: 'text-2xl font-bold text-blue-600'
                    }, facturedCount)
                ]),
                React.createElement('div', {
                    key: 'pending',
                    className: 'bg-white border border-gray-200 rounded-lg p-4'
                }, [
                    React.createElement('p', {
                        key: 'label',
                        className: 'text-xs text-gray-500 uppercase tracking-wide'
                    }, 'Pendientes'),
                    React.createElement('p', {
                        key: 'value',
                        className: 'text-2xl font-bold text-orange-600'
                    }, pendingCount)
                ])
            ]),

            // Expenses list
            React.createElement('div', {
                key: 'list',
                className: 'bg-white border border-gray-200 rounded-lg p-6'
            }, [
                React.createElement('h3', {
                    key: 'title',
                    className: 'text-lg font-semibold text-gray-900 mb-4'
                }, 'Todos los Gastos'),
                React.createElement('div', {
                    key: 'manual_expenses',
                    className: 'space-y-3'
                }, expensesData.map((expense, index) =>
                    React.createElement('div', {
                        key: expense.id || index,
                        className: 'flex justify-between items-center py-3 px-4 border border-gray-100 rounded hover:bg-gray-50'
                    }, [
                        React.createElement('div', {
                            key: 'info'
                        }, [
                            React.createElement('p', {
                                key: 'desc',
                                className: 'font-medium text-gray-900'
                            }, expense.descripcion || 'Sin descripción'),
                            React.createElement('p', {
                                key: 'date',
                                className: 'text-sm text-gray-500'
                            }, expense.fecha_gasto || 'Sin fecha')
                        ]),
                        React.createElement('div', {
                            key: 'amount',
                            className: 'text-right'
                        }, [
                            React.createElement('p', {
                                key: 'money',
                                className: 'font-semibold text-gray-900'
                            }, `$${(expense.monto_total || 0).toFixed(2)}`),
                            React.createElement('p', {
                                key: 'category',
                                className: 'text-xs text-gray-500'
                            }, expense.categoria || 'otros')
                        ])
                    ])
                ))
            ])
        ]);
    }

    // Expense form view
    if (showExpenseForm) {
        return React.createElement('div', {
            className: 'max-w-4xl mx-auto px-4 py-6'
        }, [
            // Header
            React.createElement('div', {
                key: 'header',
                className: 'flex justify-between items-center mb-6'
            }, [
                React.createElement('h2', {
                    key: 'title',
                    className: 'text-2xl font-bold text-gray-900'
                }, '📝 Registrar Gasto'),
                React.createElement('button', {
                    key: 'close',
                    onClick: () => setShowExpenseForm(false),
                    className: 'px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600'
                }, 'Cerrar')
            ]),

            // Voice transcript display
            transcript && React.createElement('div', {
                key: 'transcript',
                className: 'bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6'
            }, [
                React.createElement('p', {
                    key: 'label',
                    className: 'text-sm font-medium text-blue-700 mb-2'
                }, '🎤 Transcripción:'),
                React.createElement('p', {
                    key: 'text',
                    className: 'text-blue-800'
                }, transcript)
            ]),

            // Input methods
            React.createElement('div', {
                key: 'input-methods',
                className: 'grid grid-cols-1 md:grid-cols-3 gap-4 mb-6'
            }, [
                React.createElement('button', {
                    key: 'voice',
                    onClick: startVoiceRecording,
                    disabled: isRecording,
                    className: `p-4 border-2 border-dashed rounded-lg text-center transition-colors ${
                        isRecording
                            ? 'border-red-300 bg-red-50 text-red-600'
                            : 'border-blue-300 bg-blue-50 text-blue-600 hover:border-blue-400'
                    }`
                }, [
                    React.createElement('i', {
                        key: 'icon',
                        className: `fas fa-microphone text-2xl mb-2 ${isRecording ? 'animate-pulse' : ''}`
                    }),
                    React.createElement('p', {
                        key: 'text',
                        className: 'font-medium'
                    }, isRecording ? 'Grabando...' : 'Voz (dictado)')
                ]),
                React.createElement('label', {
                    key: 'file',
                    className: 'p-4 border-2 border-dashed border-green-300 bg-green-50 text-green-600 rounded-lg text-center cursor-pointer hover:border-green-400'
                }, [
                    React.createElement('input', {
                        key: 'input',
                        type: 'file',
                        accept: 'image/*,.pdf',
                        onChange: (e) => handleFileUpload(e.target.files[0]),
                        className: 'hidden'
                    }),
                    React.createElement('i', {
                        key: 'icon',
                        className: 'fas fa-camera text-2xl mb-2 block'
                    }),
                    React.createElement('p', {
                        key: 'text',
                        className: 'font-medium'
                    }, 'Subir ticket (OCR)')
                ]),
                React.createElement('div', {
                    key: 'manual',
                    className: 'p-4 border-2 border-dashed border-gray-300 bg-gray-50 text-gray-600 rounded-lg text-center'
                }, [
                    React.createElement('i', {
                        key: 'icon',
                        className: 'fas fa-keyboard text-2xl mb-2 block'
                    }),
                    React.createElement('p', {
                        key: 'text',
                        className: 'font-medium'
                    }, 'Texto (manual)')
                ])
            ]),

            // Form fields
            React.createElement('div', {
                key: 'form',
                className: 'bg-white border border-gray-200 rounded-lg p-6 space-y-4'
            }, [
                // Description
                React.createElement('div', { key: 'description' }, [
                    React.createElement('label', {
                        key: 'label',
                        className: 'block text-sm font-medium text-gray-700 mb-2'
                    }, 'Descripción *'),
                    React.createElement('input', {
                        key: 'input',
                        type: 'text',
                        value: getFieldValue('descripcion'),
                        onChange: (e) => handleFieldChange('descripcion', e.target.value),
                        className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                        placeholder: 'Ej: Comida en restaurante...'
                    })
                ]),

                // Amount
                React.createElement('div', { key: 'amount' }, [
                    React.createElement('label', {
                        key: 'label',
                        className: 'block text-sm font-medium text-gray-700 mb-2'
                    }, 'Monto *'),
                    React.createElement('input', {
                        key: 'input',
                        type: 'number',
                        step: '0.01',
                        value: getFieldValue('monto_total'),
                        onChange: (e) => handleFieldChange('monto_total', parseFloat(e.target.value) || 0),
                        className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                        placeholder: '0.00'
                    })
                ]),

                // Date
                React.createElement('div', { key: 'date' }, [
                    React.createElement('label', {
                        key: 'label',
                        className: 'block text-sm font-medium text-gray-700 mb-2'
                    }, 'Fecha'),
                    React.createElement('input', {
                        key: 'input',
                        type: 'date',
                        value: getFieldValue('fecha_gasto') || new Date().toISOString().split('T')[0],
                        onChange: (e) => handleFieldChange('fecha_gasto', e.target.value),
                        className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
                    })
                ]),

                // Category
                React.createElement('div', { key: 'category' }, [
                    React.createElement('label', {
                        key: 'label',
                        className: 'block text-sm font-medium text-gray-700 mb-2'
                    }, 'Categoría'),
                    React.createElement('select', {
                        key: 'select',
                        value: getFieldValue('categoria'),
                        onChange: (e) => handleFieldChange('categoria', e.target.value),
                        className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
                    }, [
                        React.createElement('option', { key: 'empty', value: '' }, 'Seleccionar categoría...'),
                        ...categories.map(cat =>
                            React.createElement('option', {
                                key: cat.value,
                                value: cat.value
                            }, cat.label)
                        )
                    ])
                ]),

                // Provider
                React.createElement('div', { key: 'provider' }, [
                    React.createElement('label', {
                        key: 'label',
                        className: 'block text-sm font-medium text-gray-700 mb-2'
                    }, 'Proveedor'),
                    React.createElement('input', {
                        key: 'input',
                        type: 'text',
                        value: getFieldValue('proveedor.nombre'),
                        onChange: (e) => handleFieldChange('proveedor.nombre', e.target.value),
                        className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                        placeholder: 'Nombre del proveedor...'
                    })
                ]),

                // Actions
                React.createElement('div', {
                    key: 'actions',
                    className: 'flex gap-4 pt-4'
                }, [
                    React.createElement('button', {
                        key: 'save',
                        onClick: handleSubmit,
                        disabled: isLoading,
                        className: `px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 ${
                            isLoading ? 'cursor-not-allowed' : ''
                        }`
                    }, isLoading ? 'Guardando...' : 'Guardar'),
                    React.createElement('button', {
                        key: 'cancel',
                        onClick: () => setShowExpenseForm(false),
                        className: 'px-6 py-2 bg-gray-500 text-white rounded hover:bg-gray-600'
                    }, 'Cancelar')
                ])
            ])
        ]);
    }

    // Main view
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
            }, '¡Badges eliminados exitosamente!'),
            React.createElement('p', {
                key: 'message',
                className: 'text-green-600 text-sm'
            }, 'Todas las funcionalidades avanzadas están disponibles sin elementos molestos')
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

        // Stats
        React.createElement('div', {
            key: 'stats',
            className: 'grid grid-cols-1 md:grid-cols-4 gap-4'
        }, [
            React.createElement('div', {
                key: 'total',
                className: 'bg-white border border-gray-200 rounded-lg p-4 text-center'
            }, [
                React.createElement('p', {
                    key: 'label',
                    className: 'text-xs text-gray-500 uppercase tracking-wide'
                }, 'Total gastos'),
                React.createElement('p', {
                    key: 'value',
                    className: 'text-2xl font-bold text-gray-900'
                }, expensesData.length)
            ]),
            React.createElement('div', {
                key: 'actions',
                className: 'bg-white border border-gray-200 rounded-lg p-4 text-center'
            }, [
                React.createElement('button', {
                    key: 'new-expense',
                    onClick: () => setShowExpenseForm(true),
                    className: 'w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors'
                }, [
                    React.createElement('i', {
                        key: 'icon',
                        className: 'fas fa-plus mr-2'
                    }),
                    'Nuevo Gasto'
                ])
            ]),
            React.createElement('div', {
                key: 'dashboard',
                className: 'bg-white border border-gray-200 rounded-lg p-4 text-center'
            }, [
                React.createElement('button', {
                    key: 'dashboard-btn',
                    onClick: () => setShowDashboard(true),
                    className: 'w-full px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors'
                }, [
                    React.createElement('i', {
                        key: 'icon',
                        className: 'fas fa-chart-bar mr-2'
                    }),
                    'Dashboard'
                ])
            ]),
            React.createElement('div', {
                key: 'tickets',
                className: 'bg-white border border-gray-200 rounded-lg p-4 text-center'
            }, [
                React.createElement('a', {
                    key: 'link',
                    href: '/advanced-ticket-dashboard.html',
                    className: 'block w-full px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors'
                }, [
                    React.createElement('i', {
                        key: 'icon',
                        className: 'fas fa-receipt mr-2'
                    }),
                    'Dashboard Tickets'
                ])
            ])
        ]),

        // Recent expenses
        React.createElement('div', {
            key: 'recent',
            className: 'bg-white border border-gray-200 rounded-lg p-6'
        }, [
            React.createElement('div', {
                key: 'header',
                className: 'flex justify-between items-center mb-4'
            }, [
                React.createElement('h3', {
                    key: 'title',
                    className: 'text-lg font-semibold text-gray-900'
                }, 'Gastos Recientes'),
                React.createElement('button', {
                    key: 'view-all',
                    onClick: () => setShowDashboard(true),
                    className: 'text-blue-600 hover:text-blue-800 text-sm'
                }, 'Ver todos →')
            ]),
            expensesData.length > 0
                ? React.createElement('div', {
                    key: 'list',
                    className: 'space-y-2'
                }, expensesData.slice(0, 5).map((expense, index) =>
                    React.createElement('div', {
                        key: expense.id || index,
                        className: 'flex justify-between items-center py-2 border-b border-gray-100 last:border-b-0'
                    }, [
                        React.createElement('div', {
                            key: 'info'
                        }, [
                            React.createElement('span', {
                                key: 'desc',
                                className: 'text-gray-900 font-medium'
                            }, expense.descripcion || 'Sin descripción'),
                            React.createElement('span', {
                                key: 'date',
                                className: 'text-gray-500 text-sm ml-2'
                            }, expense.fecha_gasto || '')
                        ]),
                        React.createElement('span', {
                            key: 'amount',
                            className: 'font-semibold text-gray-700'
                        }, `$${(expense.monto_total || 0).toFixed(2)}`)
                    ])
                ))
                : React.createElement('p', {
                    key: 'empty',
                    className: 'text-gray-500 text-center py-8'
                }, 'No hay gastos registrados. ¡Crea tu primer gasto!')
        ])
    ]);
};

console.log('Complete expenses component loaded');

// Renderizar la aplicación
const root = ReactDOM.createRoot(document.getElementById('app-root'));
root.render(React.createElement(CompleteExpenses, null));
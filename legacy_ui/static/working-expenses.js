const { useState, useCallback, useEffect } = React;

const WorkingExpenses = () => {
    const [showExpenseForm, setShowExpenseForm] = useState(false);
    const [expensesData, setExpensesData] = useState([]);
    const [formData, setFormData] = useState({});

    // Simple field change handler
    const handleFieldChange = useCallback((field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    }, []);

    // Simple form submission
    const handleSubmit = useCallback(async () => {
        try {
            const response = await fetch('/expenses', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            if (response.ok) {
                alert('Gasto guardado exitosamente');
                setFormData({});
                setShowExpenseForm(false);
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Error guardando gasto');
        }
    }, [formData]);

    // Load expenses
    useEffect(() => {
        fetch('/expenses')
            .then(res => res.json())
            .then(data => setExpensesData(data))
            .catch(err => console.error('Error loading expenses:', err));
    }, []);

    if (showExpenseForm) {
        return React.createElement('div', {
            className: 'max-w-4xl mx-auto px-4 py-6'
        }, [
            React.createElement('div', {
                key: 'header',
                className: 'flex justify-between items-center mb-6'
            }, [
                React.createElement('h2', {
                    key: 'title',
                    className: 'text-2xl font-bold text-gray-900'
                }, 'Registrar Gasto'),
                React.createElement('button', {
                    key: 'close',
                    onClick: () => setShowExpenseForm(false),
                    className: 'px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600'
                }, 'Cerrar')
            ]),
            React.createElement('div', {
                key: 'form',
                className: 'bg-white border border-gray-200 rounded-lg p-6 space-y-4'
            }, [
                React.createElement('div', {
                    key: 'description'
                }, [
                    React.createElement('label', {
                        key: 'label',
                        className: 'block text-sm font-medium text-gray-700 mb-2'
                    }, 'Descripción'),
                    React.createElement('input', {
                        key: 'input',
                        type: 'text',
                        value: formData.descripcion || '',
                        onChange: (e) => handleFieldChange('descripcion', e.target.value),
                        className: 'w-full px-3 py-2 border border-gray-300 rounded-md'
                    })
                ]),
                React.createElement('div', {
                    key: 'amount'
                }, [
                    React.createElement('label', {
                        key: 'label',
                        className: 'block text-sm font-medium text-gray-700 mb-2'
                    }, 'Monto'),
                    React.createElement('input', {
                        key: 'input',
                        type: 'number',
                        value: formData.monto_total || '',
                        onChange: (e) => handleFieldChange('monto_total', parseFloat(e.target.value)),
                        className: 'w-full px-3 py-2 border border-gray-300 rounded-md'
                    })
                ]),
                React.createElement('div', {
                    key: 'actions',
                    className: 'flex gap-4'
                }, [
                    React.createElement('button', {
                        key: 'save',
                        onClick: handleSubmit,
                        className: 'px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700'
                    }, 'Guardar'),
                    React.createElement('button', {
                        key: 'cancel',
                        onClick: () => setShowExpenseForm(false),
                        className: 'px-6 py-2 bg-gray-500 text-white rounded hover:bg-gray-600'
                    }, 'Cancelar')
                ])
            ])
        ]);
    }

    return React.createElement('div', {
        className: 'max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6'
    }, [
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
            }, 'Captura por voz o ticket, vincula facturas y concilia con el banco en un solo flujo.'),
            React.createElement('div', {
                key: 'success-notice',
                className: 'bg-green-50 border border-green-200 rounded-lg p-4 max-w-2xl mx-auto'
            }, [
                React.createElement('div', {
                    key: 'icon',
                    className: 'text-center text-2xl mb-2'
                }, '✅'),
                React.createElement('p', {
                    key: 'message',
                    className: 'text-green-800 font-medium text-center'
                }, 'Badges de empresa eliminados exitosamente'),
                React.createElement('p', {
                    key: 'sub',
                    className: 'text-green-600 text-sm text-center mt-1'
                }, 'La interfaz ahora está limpia y funcional')
            ])
        ]),
        React.createElement('div', {
            key: 'stats',
            className: 'grid grid-cols-1 md:grid-cols-3 gap-4'
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
                    className: 'px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors'
                }, [
                    React.createElement('i', {
                        key: 'icon',
                        className: 'fas fa-plus mr-2'
                    }),
                    'Nuevo Gasto'
                ])
            ]),
            React.createElement('div', {
                key: 'dashboard-link',
                className: 'bg-white border border-gray-200 rounded-lg p-4 text-center'
            }, [
                React.createElement('a', {
                    key: 'link',
                    href: '/advanced-ticket-dashboard.html',
                    className: 'px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors inline-block'
                }, [
                    React.createElement('i', {
                        key: 'icon',
                        className: 'fas fa-receipt mr-2'
                    }),
                    'Dashboard Tickets'
                ])
            ])
        ]),
        React.createElement('div', {
            key: 'expenses-list',
            className: 'bg-white border border-gray-200 rounded-lg p-6'
        }, [
            React.createElement('h3', {
                key: 'title',
                className: 'text-lg font-semibold text-gray-900 mb-4'
            }, 'Gastos Recientes'),
            expensesData.length > 0
                ? React.createElement('div', {
                    key: 'list',
                    className: 'space-y-2'
                }, expensesData.slice(0, 5).map((expense, index) =>
                    React.createElement('div', {
                        key: expense.id || index,
                        className: 'flex justify-between items-center py-2 border-b border-gray-100'
                    }, [
                        React.createElement('span', {
                            key: 'desc',
                            className: 'text-gray-900'
                        }, expense.descripcion || 'Sin descripción'),
                        React.createElement('span', {
                            key: 'amount',
                            className: 'font-semibold text-gray-700'
                        }, `$${expense.monto_total || 0}`)
                    ])
                ))
                : React.createElement('p', {
                    key: 'empty',
                    className: 'text-gray-500 text-center py-8'
                }, 'No hay gastos registrados')
        ])
    ]);
};

console.log('Working expenses component loaded');

// Renderizar la aplicación
const root = ReactDOM.createRoot(document.getElementById('app-root'));
root.render(React.createElement(WorkingExpenses, null));
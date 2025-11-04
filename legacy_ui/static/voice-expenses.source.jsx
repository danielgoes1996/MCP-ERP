const { useState, useCallback, useRef, useEffect, useMemo } = React;

const MISSION_DETAILS = {
    '1': {
        title: 'Misión 1: Crear un gasto',
        description: 'Registra un gasto demo y vive la captura multicanal (voz, ticket o texto).',
        steps: [
            'Selecciona “Voz (dictado)”, “Subir ticket (OCR)” o “Texto (manual)”.',
            'Completa los campos clave (monto, fecha, proveedor) con la información demo.',
            'Guarda el gasto y verifica que aparece en tu tablero demo.'
        ],
        ctaLabel: 'Ir a los canales de captura',
        action: 'capture',
        next: '2'
    },
    '2': {
        title: 'Misión 2: Vincular la factura',
        description: 'Adjunta una factura demo para ver cómo cambia el estatus del gasto automáticamente.',
        steps: [
            'Abre “Facturas pendientes” en la parte superior.',
            'Carga el CFDI/PDF demo o vincula la factura sugerida.',
            'Confirma que el estatus del gasto pasa a “facturado”.'
        ],
        ctaLabel: 'Abrir facturas demo',
        action: 'pendingInvoices',
        next: '3'
    },
    '3': {
        title: 'Misión 3: Conciliación bancaria',
        description: 'Revisa los movimientos demo, acepta sugerencias y entiende los pagos fragmentados.',
        steps: [
            'Abre la “Conciliación bancaria” para ver los movimientos ficticios.',
            'Aprueba o rechaza sugerencias inteligentes según el gasto demo.',
            'Analiza el ejemplo de pago dividido en varios cargos.'
        ],
        ctaLabel: 'Revisar conciliación demo',
        action: 'bank',
        next: '4'
    },
    '4': {
        title: 'Misión 4: Reportes y control',
        description: 'Explora el dashboard demo y prueba filtros en tiempo real.',
        steps: [
            'Abre el dashboard de gastos demo.',
            'Filtra por categoría, proveedor o estatus para entender la visibilidad.',
            'Revisa los indicadores clave y detecta patrones.'
        ],
        ctaLabel: 'Ir al dashboard de gastos',
        action: 'dashboard',
        next: null
    }
};

        const formatCurrency = (amount) => `$${(amount || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}`;

        const INVOICE_STATUS_MAP = {
            facturado: 'facturado',
            pagado: 'facturado',
            timbrado: 'facturado',
            cerrada: 'facturado',
            cerrada_factura: 'facturado',
            cerrada_con_factura: 'facturado',
            factura_pagada: 'facturado',
            pendiente: 'pendiente',
            pendiente_factura: 'pendiente',
            registrada: 'pendiente',
            en_revision: 'pendiente',
            en_proceso: 'pendiente',
            recibida: 'pendiente',
            capturado: 'pendiente',
            captura: 'pendiente',
            sin_factura: 'sin_factura',
            no_requiere: 'sin_factura',
            cerrado_sin_factura: 'sin_factura',
            cancelada: 'sin_factura'
        };

        const BANK_STATUS_MAP = {
            conciliado: 'conciliado_banco',
            conciliado_banco: 'conciliado_banco',
            conciliado_manual: 'conciliado_banco',
            conciliado_parcial: 'conciliado_banco',
            pendiente_bancaria: 'pendiente_bancaria',
            pendiente_pago: 'pendiente_bancaria',
            por_conciliar: 'pendiente_bancaria',
            pendiente_banco: 'pendiente_bancaria',
            pendiente_factura: 'pendiente_factura',
            sin_factura: 'sin_factura',
            no_requiere: 'sin_factura'
        };

        const INVOICE_STATUS_META = {
            pendiente: {
                label: 'Pendiente de factura',
                description: 'Sube o vincula el CFDI para continuar al banco.',
                stageIndex: 0,
                accent: 'orange'
            },
            facturado: {
                label: 'Factura lista',
                description: 'Puedes avanzar a conciliación bancaria.',
                stageIndex: 1,
                accent: 'green'
            },
            sin_factura: {
                label: 'Cerrado sin factura',
                description: 'El gasto se documentó sin requerir CFDI.',
                stageIndex: 0,
                accent: 'slate'
            }
        };

        const BANK_STATUS_META = {
            pendiente_factura: {
                label: 'Esperando factura',
                description: 'Primero adjunta la factura para poder conciliar.',
                accent: 'orange'
            },
            pendiente_bancaria: {
                label: 'Listo para conciliar en bancos',
                description: 'Revisa los detalles del gasto y luego pasa a conciliación bancaria.',
                accent: 'emerald'
            },
            conciliado_banco: {
                label: 'Conciliado',
                description: 'El gasto ya está vinculado a un movimiento.',
                accent: 'green'
            },
            sin_factura: {
                label: 'Sin factura',
                description: 'El flujo terminó sin requerir conciliación.',
                accent: 'slate'
            }
        };

        const normalizeInvoiceStatusValue = (status, willHaveCfdi = true) => {
            if (!willHaveCfdi) {
                return 'sin_factura';
            }
            const value = (status || '').toString().trim().toLowerCase();
            if (!value) {
                return 'pendiente';
            }
            if (INVOICE_STATUS_MAP[value]) {
                return INVOICE_STATUS_MAP[value];
            }
            if (value.includes('fact')) {
                return 'facturado';
            }
            if (value.includes('sin') || value.includes('no requiere')) {
                return 'sin_factura';
            }
            return 'pendiente';
        };

        const normalizeBankStatusValue = (status, invoiceStatus, hasBankLink = false) => {
            const value = (status || '').toString().trim().toLowerCase();
            if (value && BANK_STATUS_MAP[value]) {
                return BANK_STATUS_MAP[value];
            }
            if (invoiceStatus === 'facturado') {
                return hasBankLink ? 'conciliado_banco' : 'pendiente_bancaria';
            }
            if (invoiceStatus === 'pendiente') {
                return 'pendiente_factura';
            }
            return 'sin_factura';
        };

        const getInvoiceStatusMeta = (status) => {
            const key = (status || '').toString().trim().toLowerCase();
            return INVOICE_STATUS_META[key] || {
                label: 'Seguimiento en curso',
                description: 'Revisa los detalles del gasto para continuar.',
                stageIndex: 0,
                accent: 'slate'
            };
        };

        const getBankStatusMeta = (status) => {
            const key = (status || '').toString().trim().toLowerCase();
            return BANK_STATUS_META[key] || {
                label: 'Sin conciliación',
                description: 'Aún no se ha conciliado contra el banco.',
                accent: 'slate'
            };
        };

        const isPendingInvoiceStatus = (status) => {
            const key = (status || '').toString().trim().toLowerCase();
            return key === 'pendiente' || key === 'pendiente_factura';
        };

        const getBadgeClassName = (accent = 'slate') => {
            switch (accent) {
                case 'green':
                    return 'bg-green-100 border border-green-200 text-green-700';
                case 'emerald':
                    return 'bg-emerald-100 border border-emerald-200 text-emerald-700';
                case 'orange':
                    return 'bg-orange-100 border border-orange-200 text-orange-700';
                case 'indigo':
                    return 'bg-indigo-100 border border-indigo-200 text-indigo-700';
                default:
                    return 'bg-slate-100 border border-slate-200 text-slate-700';
            }
        };

        // Componente de Dashboard de Gastos
        const DashboardContent = ({ expensesData, selectedMonth, setSelectedMonth, selectedCategoryFilter, setSelectedCategoryFilter, categorias, getCategoryInfo, onOpenQuickView }) => {
            try {
            const dataset = Array.isArray(expensesData) ? expensesData : [];
            // Filtrar gastos por mes
            const expensesInMonth = dataset.filter(expense => {
                const expenseMonth = expense.fecha_gasto?.slice(0, 7) || expense.fecha_creacion?.slice(0, 7);
                return expenseMonth === selectedMonth;
            });

            // Filtrar por categoría
            const filteredExpenses = selectedCategoryFilter === 'todos'
                ? expensesInMonth
                : expensesInMonth.filter(expense => expense.categoria === selectedCategoryFilter);

            // Estadísticas
            const totalAmount = filteredExpenses.reduce((sum, expense) => sum + (expense.monto_total || 0), 0);
            const categoryStats = categorias.map(cat => {
                const categoryExpenses = expensesInMonth.filter(exp => exp.categoria === cat.value);
                const total = categoryExpenses.reduce((sum, exp) => sum + (exp.monto_total || 0), 0);
                return {
                    ...cat,
                    count: categoryExpenses.length,
                    total: total
                };
            }).filter(cat => cat.count > 0);

            // AI Insights - Análisis inteligente de gastos
            const generateInsights = () => {
                const insights = [];

                // Mes anterior para comparación
                const currentDate = new Date(selectedMonth + '-01');
                const previousMonth = new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1);
                const previousMonthStr = previousMonth.toISOString().slice(0, 7);

                const previousMonthExpenses = dataset.filter(expense => {
                    const expenseMonth = expense.fecha_gasto?.slice(0, 7) || expense.fecha_creacion?.slice(0, 7);
                    return expenseMonth === previousMonthStr;
                });

                const previousTotal = previousMonthExpenses.reduce((sum, exp) => sum + (exp.monto_total || 0), 0);

                // Insight 1: Comparación con mes anterior
                if (previousTotal > 0) {
                    const change = ((totalAmount - previousTotal) / previousTotal) * 100;
                    const changeText = change > 0 ? 'aumentaron' : 'disminuyeron';
                    const changeIcon = change > 0 ? '📈' : '📉';
                    const changeColor = change > 0 ? 'text-red-600' : 'text-green-600';

                    insights.push({
                        icon: changeIcon,
                        text: `Los gastos ${changeText} ${Math.abs(change).toFixed(1)}% vs mes anterior`,
                        detail: `${formatCurrency(previousTotal)} → ${formatCurrency(totalAmount)}`,
                        color: changeColor,
                        type: 'comparison'
                    });
                }

                // Insight 2: Categoría dominante
                if (categoryStats.length > 0) {
                    const topCategory = categoryStats.reduce((max, cat) => cat.total > max.total ? cat : max);
                    const percentage = ((topCategory.total / totalAmount) * 100).toFixed(1);

                    insights.push({
                        icon: '🎯',
                        text: `${topCategory.label} representa el ${percentage}% del gasto total`,
                        detail: `${formatCurrency(topCategory.total)} en ${topCategory.count} transacciones`,
                        color: 'text-blue-600',
                        type: 'category'
                    });
                }

                // Insight 3: Alerta de gastos altos
                const highExpenses = filteredExpenses.filter(exp => exp.monto_total > 1000);
                if (highExpenses.length > 0) {
                    const totalHigh = highExpenses.reduce((sum, exp) => sum + exp.monto_total, 0);

                    insights.push({
                        icon: '⚠️',
                        text: `${highExpenses.length} gastos superiores a $1,000`,
                        detail: `Total: ${formatCurrency(totalHigh)}`,
                        color: 'text-orange-600',
                        type: 'alert'
                    });
                }

                // Insight 4: Proyección mensual (si estamos a mitad de mes)
                const today = new Date();
                const currentMonthStr = today.toISOString().slice(0, 7);
                if (selectedMonth === currentMonthStr) {
                    const dayOfMonth = today.getDate();
                    const daysInMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();
                    const monthProgress = dayOfMonth / daysInMonth;

                    if (monthProgress < 0.9) { // Solo mostrar si no estamos al final del mes
                        const projectedTotal = totalAmount / monthProgress;
                        insights.push({
                            icon: '📊',
                            text: `Proyección del mes: ${formatCurrency(projectedTotal)}`,
                            detail: `Basado en ${dayOfMonth} días de ${daysInMonth}`,
                            color: 'text-purple-600',
                            type: 'projection'
                        });
                    }
                }

                return insights;
            };

            const aiInsights = generateInsights();

            const stageCounter = expensesInMonth.reduce((acc, expense) => {
                const invoiceStatus = (expense.estado_factura || '').toLowerCase();
                const bankStatus = (expense.estado_conciliacion || '').toLowerCase();

                if (invoiceStatus === 'sin_factura') {
                    acc.noInvoice += 1;
                } else if (invoiceStatus === 'facturado') {
                    acc.facturado += 1;
                    if (bankStatus === 'conciliado_banco') {
                        acc.conciliado += 1;
                    }
                } else {
                    acc.pendiente += 1;
                }

                return acc;
            }, { pendiente: 0, facturado: 0, conciliado: 0, noInvoice: 0 });

            const invoiceStageData = [
                {
                    key: 'pendiente',
                    label: 'Pendiente de factura',
                    accent: 'orange',
                    count: stageCounter.pendiente,
                    helper: stageCounter.pendiente === 0 ? 'Sin pendientes este mes.' : 'Sube o vincula la factura para avanzar.',
                },
                {
                    key: 'facturado',
                    label: 'Factura lista',
                    accent: 'green',
                    count: stageCounter.facturado,
                    helper: stageCounter.facturado === 0
                        ? 'Aún no hay facturas registradas.'
                        : `${Math.max(stageCounter.facturado - stageCounter.conciliado, 0)} pendientes de conciliar.`,
                },
                {
                    key: 'conciliado',
                    label: 'Conciliado en banco',
                    accent: 'indigo',
                    count: stageCounter.conciliado,
                    helper: stageCounter.conciliado === 0 ? 'Cuando concilies aparecerán aquí.' : 'Ciclo cerrado con movimiento bancario.',
                },
            ];

            const getStageCircleClass = (accent, count) => {
                if (!count) {
                    return 'bg-gray-200 text-gray-500 border border-gray-300';
                }
                switch (accent) {
                    case 'orange':
                        return 'bg-orange-500 text-white shadow-md shadow-orange-200';
                    case 'green':
                        return 'bg-green-500 text-white shadow-md shadow-green-200';
                    case 'indigo':
                        return 'bg-indigo-500 text-white shadow-md shadow-indigo-200';
                    default:
                        return 'bg-slate-600 text-white';
                }
            };

            const getConnectorClass = (currentStep, nextStep) => {
                if (!nextStep) {
                    return 'bg-gray-200';
                }
                if (currentStep.count === 0 && nextStep.count === 0) {
                    return 'bg-gray-200';
                }
                if (currentStep.accent === 'orange') {
                    return nextStep.count > 0 ? 'bg-gradient-to-r from-orange-400 to-green-400' : 'bg-orange-200';
                }
                if (currentStep.accent === 'green') {
                    return nextStep.count > 0 ? 'bg-gradient-to-r from-green-400 to-indigo-400' : 'bg-green-200';
                }
                return nextStep.count > 0 ? 'bg-indigo-400' : 'bg-indigo-200';
            };

            return (
                <div className="p-6 space-y-6">
                    {/* Controles de filtro */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Mes</label>
                            <input
                                type="month"
                                value={selectedMonth}
                                onChange={(e) => setSelectedMonth(e.target.value)}
                                className="w-full p-2 border border-gray-300 rounded-lg"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Categoría</label>
                            <select
                                value={selectedCategoryFilter}
                                onChange={(e) => setSelectedCategoryFilter(e.target.value)}
                                className="w-full p-2 border border-gray-300 rounded-lg"
                            >
                                <option value="todos">Todas las categorías</option>
                                {categorias.map(cat => (
                                    <option key={cat.value} value={cat.value}>{cat.label}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    {/* Estadísticas generales */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                            <div className="flex items-center">
                                <i className="fas fa-calculator text-blue-600 text-2xl mr-3"></i>
                                <div>
                                    <p className="text-sm text-blue-600">Total del mes</p>
                                    <p className="text-2xl font-bold text-blue-800">
                                        ${totalAmount.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                                    </p>
                                </div>
                            </div>
                        </div>
                        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                            <div className="flex items-center">
                                <i className="fas fa-receipt text-green-600 text-2xl mr-3"></i>
                                <div>
                                    <p className="text-sm text-green-600">Gastos registrados</p>
                                    <p className="text-2xl font-bold text-green-800">{filteredExpenses.length}</p>
                                </div>
                            </div>
                        </div>
                        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
                            <div className="flex items-center">
                                <i className="fas fa-tags text-orange-600 text-2xl mr-3"></i>
                                <div>
                                    <p className="text-sm text-orange-600">Categorías activas</p>
                                    <p className="text-2xl font-bold text-orange-800">{categoryStats.length}</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Visualizador de estatus de factura */}
                    <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm">
                        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                            <div>
                                <h3 className="text-lg font-semibold text-gray-900">Visualizador de estatus</h3>
                                <p className="text-sm text-gray-600">Sigue el recorrido del gasto desde la captura hasta la conciliación bancaria.</p>
                            </div>
                            <span className="text-xs text-gray-500">Período: {selectedMonth}</span>
                        </div>

                        <div className="mt-6 flex flex-col md:flex-row md:items-center md:justify-between md:gap-4 space-y-4 md:space-y-0">
                            {invoiceStageData.map((step, index) => (
                                <React.Fragment key={step.key}>
                                    <div className="flex flex-col items-center text-center md:w-40 bg-slate-50 md:bg-transparent border border-slate-200 md:border-none rounded-lg md:rounded-none px-4 py-3 md:px-0 md:py-0">
                                        <div className={`w-14 h-14 rounded-full flex items-center justify-center text-lg font-semibold transition-colors ${getStageCircleClass(step.accent, step.count)}`}>
                                            {step.count}
                                        </div>
                                        <p className="mt-2 text-sm font-medium text-gray-700">{step.label}</p>
                                        <p className="text-xs text-gray-500 mt-1">{step.helper}</p>
                                    </div>
                                    {index < invoiceStageData.length - 1 && (
                                        <div className={`hidden md:block flex-1 h-1 ${getConnectorClass(step, invoiceStageData[index + 1])}`}></div>
                                    )}
                                </React.Fragment>
                            ))}
                        </div>

                        <div className="mt-4 flex items-center gap-2 text-xs text-gray-500 bg-slate-100 border border-slate-200 rounded-lg px-3 py-2">
                            <i className="fas fa-receipt text-slate-500"></i>
                            <span>{stageCounter.noInvoice} gastos marcados como sin factura en el periodo.</span>
                        </div>
                    </div>

                    {/* AI Insights - Análisis Inteligente */}
                    {aiInsights.length > 0 && (
                        <div>
                            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                                <i className="fas fa-brain text-pink-600 mr-2"></i>
                                Insights IA
                                <span className="ml-2 px-2 py-1 bg-pink-100 text-pink-700 text-xs rounded-full">
                                    Análisis Inteligente
                                </span>
                            </h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                                {aiInsights.map((insight, index) => (
                                    <div key={index} className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow">
                                        <div className="flex items-start space-x-3">
                                            <span className="text-2xl flex-shrink-0">{insight.icon}</span>
                                            <div className="flex-1">
                                                <p className={`font-medium ${insight.color}`}>
                                                    {insight.text}
                                                </p>
                                                <p className="text-sm text-gray-600 mt-1">
                                                    {insight.detail}
                                                </p>
                                                <span className="inline-block mt-2 px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded">
                                                    {insight.type === 'comparison' && 'Comparación'}
                                                    {insight.type === 'category' && 'Análisis de categorías'}
                                                    {insight.type === 'alert' && 'Alerta'}
                                                    {insight.type === 'projection' && 'Proyección'}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Desglose por categorías */}
                    <div>
                        <h3 className="text-lg font-semibold text-gray-900 mb-4">Desglose por Categorías</h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {categoryStats.map(cat => (
                                <div key={cat.value} className={`p-4 rounded-lg border ${cat.color.replace('text-', 'border-').replace('-800', '-200')}`}>
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center">
                                            <span className="text-2xl mr-3">{cat.label.split(' ')[0]}</span>
                                            <div>
                                                <h4 className="font-medium text-gray-900">{cat.label.substring(2)}</h4>
                                                <p className="text-sm text-gray-600">{cat.count} gastos</p>
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <p className="text-lg font-bold text-gray-900">
                                                ${cat.total.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                                            </p>
                                            <p className="text-sm text-gray-500">
                                                {totalAmount > 0 ? Math.round((cat.total / totalAmount) * 100) : 0}%
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Lista detallada de gastos */}
                    <div>
                        <h3 className="text-lg font-semibold text-gray-900 mb-4">Detalle de Gastos</h3>
                        <div className="max-h-96 overflow-y-auto">
                            <div className="space-y-3">
                                {filteredExpenses.map(expense => {
                                    const categoryInfo = getCategoryInfo(expense.categoria);
                                    return (
                                        <div
                                            key={expense.id}
                                            className={`bg-white border border-gray-200 rounded-lg p-4 ${onOpenQuickView ? 'hover:border-blue-300 transition cursor-pointer' : ''}`}
                                            onClick={() => onOpenQuickView && onOpenQuickView(expense)}
                                        >
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-3">
                                                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${categoryInfo.color}`}>
                                                        {categoryInfo.label}
                                                    </span>
                                                    <div>
                                                        <h4 className="font-medium text-gray-900">{expense.descripcion}</h4>
                                                        <p className="text-sm text-gray-600">
                                                            {(expense['proveedor.nombre'] || (typeof expense.proveedor === 'string' ? expense.proveedor : expense.proveedor?.nombre) || 'Sin proveedor')} • {expense.fecha_gasto}
                                                        </p>
                                                    </div>
                                                </div>
                                                <div className="text-right">
                                                    <p className="text-lg font-bold text-gray-900">
                                                        ${(expense.monto_total || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                                                    </p>
                                                    <p className={`text-xs ${
                                                        expense.estado_factura === 'pendiente' ? 'text-orange-600' :
                                                        expense.estado_factura === 'no_requiere' ? 'text-gray-500' : 'text-green-600'
                                                    }`}>
                                                        {expense.estado_factura === 'pendiente' ? '⏳ Pendiente factura' :
                                                         expense.estado_factura === 'no_requiere' ? '➖ Sin factura' : '✅ Facturado'}
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                                {filteredExpenses.length === 0 && (
                                    <div className="text-center py-8 text-gray-500">
                                        <i className="fas fa-inbox text-4xl mb-4"></i>
                                        <p>No hay gastos registrados para este período</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            );
            } catch (error) {
                console.error('DashboardContent error:', error);
                const message = error?.message || 'Error desconocido';
                return (
                    <div className="p-4 text-red-600 bg-red-50 border border-red-200 rounded-lg">
                        Error al mostrar dashboard de gastos: {message}
                    </div>
                );
            }
        };

        // Componente de Facturas Pendientes
        const PendingInvoicesContent = ({
            expensesData,
            onRegisterInvoice,
            onMarkInvoiced,
            onCloseNoInvoice,
            onOpenNonReconciliation,
        }) => {
            try {
            const dataset = Array.isArray(expensesData) ? expensesData : [];
            const pendingInvoices = dataset.filter(expense => expense.estado_factura === 'pendiente');
            const [invoiceFormExpense, setInvoiceFormExpense] = useState(null);
            const [invoiceFormData, setInvoiceFormData] = useState({ invoiceId: '', invoiceUrl: '' });
            const [invoiceFormError, setInvoiceFormError] = useState('');
            const [confirmNoInvoiceExpense, setConfirmNoInvoiceExpense] = useState(null);
            const [confirmMarkInvoicedExpense, setConfirmMarkInvoicedExpense] = useState(null);
            const [isSavingInvoice, setIsSavingInvoice] = useState(false);
            const [isConfirmingMark, setIsConfirmingMark] = useState(false);
            const [isConfirmingNoInvoice, setIsConfirmingNoInvoice] = useState(false);

            // AI Analysis - Análisis inteligente de urgencia
            const analyzeUrgency = (expense) => {
                const daysOld = expense.fecha_gasto ?
                    Math.floor((new Date() - new Date(expense.fecha_gasto)) / (1000 * 60 * 60 * 24)) : 0;

                const amount = expense.monto_total || 0;

                let urgencyLevel = 'low';
                let urgencyColor = 'text-green-600';
                let urgencyIcon = '🟢';
                let urgencyText = 'Baja prioridad';

                // Lógica de urgencia basada en días y monto
                if (daysOld > 25 || amount > 5000) {
                    urgencyLevel = 'critical';
                    urgencyColor = 'text-red-600';
                    urgencyIcon = '🔴';
                    urgencyText = 'Crítico';
                } else if (daysOld > 15 || amount > 2000) {
                    urgencyLevel = 'high';
                    urgencyColor = 'text-orange-600';
                    urgencyIcon = '🟡';
                    urgencyText = 'Alta prioridad';
                } else if (daysOld > 7 || amount > 1000) {
                    urgencyLevel = 'medium';
                    urgencyColor = 'text-yellow-600';
                    urgencyIcon = '🟠';
                    urgencyText = 'Prioridad media';
                }

                return {
                    level: urgencyLevel,
                    color: urgencyColor,
                    icon: urgencyIcon,
                    text: urgencyText,
                    daysOld,
                    reasons: [
                        daysOld > 25 && 'Más de 25 días sin facturar',
                        daysOld > 15 && daysOld <= 25 && 'Más de 15 días sin facturar',
                        daysOld > 7 && daysOld <= 15 && 'Más de 7 días sin facturar',
                        amount > 5000 && 'Monto superior a $5,000',
                        amount > 2000 && amount <= 5000 && 'Monto superior a $2,000',
                        amount > 1000 && amount <= 2000 && 'Monto superior a $1,000'
                    ].filter(Boolean)
                };
            };

            // Ordenar por urgencia
            const sortedPendingInvoices = [...pendingInvoices].sort((a, b) => {
                const urgencyA = analyzeUrgency(a);
                const urgencyB = analyzeUrgency(b);

                const urgencyOrder = { critical: 4, high: 3, medium: 2, low: 1 };
                return urgencyOrder[urgencyB.level] - urgencyOrder[urgencyA.level];
            });

            // Estadísticas de urgencia
            const urgencyStats = {
                critical: pendingInvoices.filter(exp => analyzeUrgency(exp).level === 'critical').length,
                high: pendingInvoices.filter(exp => analyzeUrgency(exp).level === 'high').length,
                medium: pendingInvoices.filter(exp => analyzeUrgency(exp).level === 'medium').length,
                low: pendingInvoices.filter(exp => analyzeUrgency(exp).level === 'low').length
            };

            const registerInvoice = (expense) => {
                const defaultUrl = expense.factura_url || `https://erp.tuempresa.com/facturas/${expense.factura_id || ''}`;
                setInvoiceFormExpense(expense);
                setInvoiceFormData({
                    invoiceId: expense.factura_id || '',
                    invoiceUrl: defaultUrl
                });
                setInvoiceFormError('');
            };

            const markAsInvoiced = (expenseId) => {
                const expense = dataset.find(exp => exp.id === expenseId);
                if (!expense) return;

                if (!expense.factura_id) {
                    registerInvoice(expense);
                    return;
                }

                setConfirmMarkInvoicedExpense(expense);
            };

            const markAsNoInvoice = (expense) => {
                setConfirmNoInvoiceExpense(expense);
            };

            const handleInvoiceFormSubmit = async () => {
                if (!invoiceFormExpense) {
                    return;
                }

                const trimmedId = invoiceFormData.invoiceId.trim();
                const trimmedUrl = (invoiceFormData.invoiceUrl || '').trim() || `https://erp.tuempresa.com/facturas/${trimmedId}`;

                if (!trimmedId) {
                    setInvoiceFormError('Ingresa el folio de la factura.');
                    return;
                }

                if (!onRegisterInvoice) {
                    return;
                }

                try {
                    setIsSavingInvoice(true);
                    await onRegisterInvoice(invoiceFormExpense.id, {
                        uuid: trimmedId,
                        folio: trimmedId,
                        url: trimmedUrl,
                        actor: 'ui',
                    });
                    setInvoiceFormExpense(null);
                    setInvoiceFormData({ invoiceId: '', invoiceUrl: '' });
                    setInvoiceFormError('');
                } catch (error) {
                    console.error('Error registrando factura:', error);
                    setInvoiceFormError(error?.message || 'No se pudo registrar la factura');
                } finally {
                    setIsSavingInvoice(false);
                }
            };

            const handleConfirmMarkInvoiced = async () => {
                if (!confirmMarkInvoicedExpense) {
                    return;
                }

                if (!onMarkInvoiced) {
                    return;
                }

                try {
                    setIsConfirmingMark(true);
                    await onMarkInvoiced(confirmMarkInvoicedExpense.id);
                    setConfirmMarkInvoicedExpense(null);
                } catch (error) {
                    console.error('Error marcando como facturado:', error);
                } finally {
                    setIsConfirmingMark(false);
                }
            };

            const handleConfirmNoInvoice = async () => {
                if (!confirmNoInvoiceExpense) {
                    return;
                }

                if (!onCloseNoInvoice) {
                    return;
                }

                try {
                    setIsConfirmingNoInvoice(true);
                    await onCloseNoInvoice(confirmNoInvoiceExpense.id);
                    setConfirmNoInvoiceExpense(null);
                } catch (error) {
                    console.error('Error cerrando sin factura:', error);
                } finally {
                    setIsConfirmingNoInvoice(false);
                }
            };

            const openNonReconciliationModal = (expense) => {
                if (typeof onOpenNonReconciliation === 'function') {
                    onOpenNonReconciliation(expense);
                }
            };

            return (
                <>
                <div className="p-6 space-y-4">
                    <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 mb-4">
                        <h3 className="font-medium text-orange-800 mb-2">
                            📋 {pendingInvoices.length} gastos pendientes de facturación
                        </h3>
                        <p className="text-sm text-orange-700">
                            Estos gastos requieren factura CFDI pero aún no han sido procesados
                        </p>
                    </div>

                    {/* AI Urgency Analysis */}
                    {pendingInvoices.length > 0 && (
                        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4">
                            <h4 className="font-medium text-gray-900 mb-3 flex items-center">
                                <i className="fas fa-brain text-pink-600 mr-2"></i>
                                Análisis de Urgencia IA
                            </h4>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                <div className="text-center p-3 bg-red-50 rounded-lg">
                                    <div className="text-2xl mb-1">🔴</div>
                                    <div className="text-lg font-bold text-red-600">{urgencyStats.critical}</div>
                                    <div className="text-xs text-red-700">Crítico</div>
                                </div>
                                <div className="text-center p-3 bg-orange-50 rounded-lg">
                                    <div className="text-2xl mb-1">🟡</div>
                                    <div className="text-lg font-bold text-orange-600">{urgencyStats.high}</div>
                                    <div className="text-xs text-orange-700">Alta</div>
                                </div>
                                <div className="text-center p-3 bg-yellow-50 rounded-lg">
                                    <div className="text-2xl mb-1">🟠</div>
                                    <div className="text-lg font-bold text-yellow-600">{urgencyStats.medium}</div>
                                    <div className="text-xs text-yellow-700">Media</div>
                                </div>
                                <div className="text-center p-3 bg-green-50 rounded-lg">
                                    <div className="text-2xl mb-1">🟢</div>
                                    <div className="text-lg font-bold text-green-600">{urgencyStats.low}</div>
                                    <div className="text-xs text-green-700">Baja</div>
                                </div>
                            </div>
                        </div>
                    )}

                    <div className="max-h-96 overflow-y-auto space-y-3">
                        {sortedPendingInvoices.map(expense => {
                            const urgencyAnalysis = analyzeUrgency(expense);
                            return (
                            <div key={expense.id} className="border border-gray-200 rounded-lg p-4 bg-white">
                                <div className="flex items-center justify-between mb-2">
                                    <div className="flex-1">
                                        <h4 className="font-medium text-gray-900">{expense.descripcion}</h4>
                                        <div className="flex items-center gap-2 mt-1">
                                            <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${urgencyAnalysis.color} bg-opacity-10`}>
                                                {urgencyAnalysis.icon} {urgencyAnalysis.text}
                                            </span>
                                            <span className="text-xs text-gray-500">
                                                {urgencyAnalysis.daysOld} días
                                            </span>
                                        </div>
                                        {urgencyAnalysis.reasons.length > 0 && (
                                            <div className="mt-1 text-xs text-gray-500">
                                                {urgencyAnalysis.reasons.join(', ')}
                                            </div>
                                        )}
                                    </div>
                                    <span className="text-lg font-bold text-gray-900">
                                        {formatCurrency(expense.monto_total)}
                                    </span>
                                </div>
                                <div className="text-sm text-gray-600 mb-3">
                                    <p>Proveedor: {expense['proveedor.nombre'] || (typeof expense.proveedor === 'string' ? expense.proveedor : expense.proveedor?.nombre) || 'Sin especificar'}</p>
                                    <p>Fecha: {expense.fecha_gasto}</p>
                                    {expense.rfc && <p>RFC: {expense.rfc}</p>}
                                    <p className="text-xs text-gray-500">Flujo: {expense.workflow_status === 'facturado' ? 'Facturado' : expense.workflow_status === 'pendiente_factura' ? 'Pendiente de factura' : 'Cerrado sin factura'}</p>
                                    {expense.factura_id ? (
                                        <p className="mt-2 text-xs text-blue-700 flex items-center gap-2">
                                            <i className="fas fa-file-invoice"></i>
                                            Factura registrada: {expense.factura_id}
                                        </p>
                                    ) : (
                                        <p className="mt-2 text-xs text-red-600 flex items-center gap-2">
                                            <i className="fas fa-exclamation-triangle"></i>
                                            Falta adjuntar la factura CFDI
                                        </p>
                                    )}
                                    {expense.tax_info && (
                                        <div className="mt-2 text-xs text-blue-600">
                                            IVA acreditable: ${Number(expense.tax_info.iva_amount || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                                        </div>
                                    )}
                                </div>
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => registerInvoice(expense)}
                                        className="px-3 py-1 bg-blue-50 text-blue-700 text-sm rounded-lg border border-blue-200 hover:bg-blue-100 transition-colors"
                                    >
                                        📄 Registrar/editar factura
                                    </button>
                                    <button
                                        onClick={() => markAsInvoiced(expense.id)}
                                        className="px-3 py-1 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 transition-colors"
                                    >
                                        ✅ Conciliar con factura
                                    </button>
                                    <button className="px-3 py-1 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors">
                                        📄 Ver detalles
                                    </button>
                                    <button
                                        onClick={() => markAsNoInvoice(expense)}
                                        className="px-3 py-1 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                                    >
                                        🚫 No se pudo facturar
                                    </button>
                                    <button
                                        onClick={() => openNonReconciliationModal(expense)}
                                        className="px-3 py-1 text-sm text-orange-600 border border-orange-300 rounded-lg hover:bg-orange-50 transition-colors"
                                    >
                                        ⚠️ No se puede conciliar
                                    </button>
                                </div>
                            </div>
                            );
                        })}

                        {pendingInvoices.length === 0 && (
                            <div className="text-center py-8 text-gray-500">
                                <i className="fas fa-check-circle text-4xl mb-4"></i>
                                <p>No hay facturas pendientes</p>
                                <p className="text-sm">Todos los gastos que requieren factura están al día</p>
                            </div>
                        )}
                    </div>
                </div>
                {invoiceFormExpense && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                        <div className="bg-white rounded-lg shadow-xl max-w-lg w-full">
                            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
                                <div>
                                    <h3 className="text-lg font-semibold text-gray-900">Registrar factura CFDI</h3>
                                    <p className="text-sm text-gray-600">Completa los datos para {invoiceFormExpense.descripcion}</p>
                                </div>
                                <button
                                    onClick={() => setInvoiceFormExpense(null)}
                                    className="text-gray-400 hover:text-gray-600"
                                    aria-label="Cerrar formulario de factura"
                                >
                                    <i className="fas fa-times text-xl"></i>
                                </button>
                            </div>
                            <div className="p-6 space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Folio CFDI</label>
                                    <input
                                        type="text"
                                        value={invoiceFormData.invoiceId}
                                        onChange={(e) => {
                                            setInvoiceFormData((prev) => ({ ...prev, invoiceId: e.target.value }));
                                            setInvoiceFormError('');
                                        }}
                                        className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                                        placeholder="UUID o folio de la factura"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">URL de consulta</label>
                                    <input
                                        type="url"
                                        value={invoiceFormData.invoiceUrl}
                                        onChange={(e) => setInvoiceFormData((prev) => ({ ...prev, invoiceUrl: e.target.value }))}
                                        className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                                        placeholder="https://"
                                    />
                                </div>
                                {!invoiceFormExpense.tax_info && (
                                    <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 rounded-lg px-3 py-2 text-sm">
                                        No se detectaron impuestos en el CFDI. Puedes completar esta información más tarde.
                                    </div>
                                )}
                                {invoiceFormError && (
                                    <div className="text-sm text-red-600">{invoiceFormError}</div>
                                )}
                            </div>
                            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
                                <button
                                    onClick={() => setInvoiceFormExpense(null)}
                                    className="px-4 py-2 text-sm text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg"
                                >
                                    Cancelar
                                </button>
                                <button
                                    onClick={handleInvoiceFormSubmit}
                                        className="px-4 py-2 text-sm text-white bg-orange-600 hover:bg-orange-700 rounded-lg disabled:opacity-50"
                                        disabled={isSavingInvoice}
                                    >
                                        {isSavingInvoice ? 'Guardando...' : 'Guardar factura'}
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                {confirmMarkInvoicedExpense && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                        <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
                            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
                                <h3 className="text-lg font-semibold text-gray-900">Confirmar conciliación</h3>
                                <button
                                    onClick={() => setConfirmMarkInvoicedExpense(null)}
                                    className="text-gray-400 hover:text-gray-600"
                                    aria-label="Cerrar confirmación de conciliación"
                                >
                                    <i className="fas fa-times text-xl"></i>
                                </button>
                            </div>
                            <div className="p-6 space-y-3 text-sm text-gray-700">
                                <p>
                                    ¿Marcar el gasto <strong>{confirmMarkInvoicedExpense.descripcion}</strong> como facturado?
                                </p>
                                <p className="text-gray-500">
                                    Se moverá al estatus “pendiente de conciliación bancaria”.
                                </p>
                            </div>
                            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
                                <button
                                    onClick={() => setConfirmMarkInvoicedExpense(null)}
                                    className="px-4 py-2 text-sm text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg"
                                >
                                    Cancelar
                                </button>
                                    <button
                                        onClick={handleConfirmMarkInvoiced}
                                        className="px-4 py-2 text-sm text-white bg-green-600 hover:bg-green-700 rounded-lg disabled:opacity-50"
                                        disabled={isConfirmingMark}
                                    >
                                        {isConfirmingMark ? 'Marcando...' : 'Marcar como facturado'}
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                {confirmNoInvoiceExpense && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                        <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
                            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
                                <h3 className="text-lg font-semibold text-gray-900">Cerrar sin factura</h3>
                                <button
                                    onClick={() => setConfirmNoInvoiceExpense(null)}
                                    className="text-gray-400 hover:text-gray-600"
                                    aria-label="Cerrar confirmación sin factura"
                                >
                                    <i className="fas fa-times text-xl"></i>
                                </button>
                            </div>
                            <div className="p-6 space-y-3 text-sm text-gray-700">
                                <p>
                                    ¿Confirmas que el gasto <strong>{confirmNoInvoiceExpense.descripcion}</strong> no tendrá factura CFDI?
                                </p>
                                <p className="text-gray-500">
                                    El flujo se cerrará como “sin factura” y se quitarán datos fiscales.
                                </p>
                            </div>
                            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
                                <button
                                    onClick={() => setConfirmNoInvoiceExpense(null)}
                                    className="px-4 py-2 text-sm text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg"
                                >
                                    Cancelar
                                </button>
                                    <button
                                        onClick={handleConfirmNoInvoice}
                                        className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50"
                                        disabled={isConfirmingNoInvoice}
                                    >
                                        {isConfirmingNoInvoice ? 'Cerrando...' : 'Cerrar sin factura'}
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}
                </>
            );
            } catch (error) {
                console.error('PendingInvoicesContent error:', error);
                const message = error?.message || 'Error desconocido';
                return (
                    <div className="p-4 text-red-600 bg-red-50 border border-red-200 rounded-lg">
                        Error al mostrar facturas pendientes: {message}
                    </div>
                );
            }
        };

        const SAMPLE_BANK_MOVEMENTS = [
            {
                movement_id: 'MOV-001',
                id: 'MOV-001',
                movement_date: '2024-09-01',
                fecha: '2024-09-01',
                bank: 'BBVA',
                banco: 'BBVA',
                description: 'Cargo Tarjeta Empresarial - Pemex',
                descripcion: 'Cargo Tarjeta Empresarial - Pemex',
                amount: 845.32,
                monto: 845.32,
                currency: 'MXN',
                tags: ['combustible', 'tarjeta_empresa']
            },
            {
                movement_id: 'MOV-002',
                id: 'MOV-002',
                movement_date: '2024-09-02',
                fecha: '2024-09-02',
                bank: 'Santander',
                banco: 'Santander',
                description: 'Cargo Tarjeta Empresarial - Restaurante',
                descripcion: 'Cargo Tarjeta Empresarial - Restaurante',
                amount: 562.10,
                monto: 562.10,
                currency: 'MXN',
                tags: ['alimentos', 'tarjeta_empresa']
            },
            {
                movement_id: 'MOV-003',
                id: 'MOV-003',
                movement_date: '2024-09-03',
                fecha: '2024-09-03',
                bank: 'Banorte',
                banco: 'Banorte',
                description: 'Transferencia a proveedor ACME',
                descripcion: 'Transferencia a proveedor ACME',
                amount: 2100.00,
                monto: 2100.00,
                currency: 'MXN',
                tags: ['proveedor', 'transferencia']
            },
            {
                movement_id: 'MOV-004',
                id: 'MOV-004',
                movement_date: '2024-09-05',
                fecha: '2024-09-05',
                bank: 'HSBC',
                banco: 'HSBC',
                description: 'Cargo Uber Business',
                descripcion: 'Cargo Uber Business',
                amount: 152.75,
                monto: 152.75,
                currency: 'MXN',
                tags: ['transporte', 'tarjeta_empresa']
            }
        ];

        // Componente de Carga de Facturas
        const InvoiceUploadContent = ({ expensesData, setExpensesData, normalizeExpenseFn, companyId }) => {
            const [selectedFiles, setSelectedFiles] = useState([]);
            const [isUploading, setIsUploading] = useState(false);
            const [uploadResults, setUploadResults] = useState([]);
            const [uploadSummary, setUploadSummary] = useState(null);
            const [showTable, setShowTable] = useState(false);

            const handleFileSelection = (files) => {
                setSelectedFiles(Array.from(files));
                setUploadResults([]);
                setUploadSummary(null);
                setShowTable(false);
            };

            const processInvoices = async () => {
                if (selectedFiles.length === 0) {
                    return;
                }

                console.log('📂 Preparando carga masiva de facturas', selectedFiles.map((file) => ({ name: file.name, size: file.size })));
                setIsUploading(true);
                const preliminaryResults = [];
                const invoicesPayload = [];

                for (const file of selectedFiles) {
                    const extension = (file.name.split('.').pop() || '').toLowerCase();
                    if (extension !== 'xml') {
                        preliminaryResults.push({
                            filename: file.name,
                            status: 'unsupported',
                            message: 'Solo se pueden procesar archivos XML CFDI en esta versión.',
                        });
                        continue;
                    }

                    let fileText;
                    try {
                        fileText = await file.text();
                    } catch (error) {
                        preliminaryResults.push({
                            filename: file.name,
                            status: 'error',
                            message: 'No se pudo leer el archivo local.',
                        });
                        continue;
                    }

                    const formData = new FormData();
                    formData.append('file', file, file.name);

                    try {
                        console.log('📤 Enviando CFDI a /invoices/parse', file.name);
                        const response = await fetch('/invoices/parse', {
                            method: 'POST',
                            body: formData,
                        });

                        if (!response.ok) {
                            const text = await response.text();
                            preliminaryResults.push({
                                filename: file.name,
                                status: 'error',
                                message: `Error interpretando CFDI: ${text || response.status}`,
                            });
                            continue;
                        }

                        const parsed = await response.json();
                        console.log('🧾 CFDI interpretado', { file: file.name, total: parsed.total, uuid: parsed.uuid });
                        invoicesPayload.push({
                            filename: file.name,
                            uuid: parsed.uuid || null,
                            total: parsed.total,
                            issued_at: parsed.issued_at || parsed.fecha_emision || null,
                            rfc_emisor: parsed.emitter?.rfc || null,
                            folio: parsed.folio || null,
                            raw_xml: fileText,
                        });
                    } catch (error) {
                        console.error('Error parsing invoice', error);
                        preliminaryResults.push({
                            filename: file.name,
                            status: 'error',
                            message: 'Error interno al enviar el archivo al servidor.',
                        });
                    }
                }

                let matchResults = [];
                if (invoicesPayload.length > 0) {
                    try {
                        console.log('🔎 Enviando lote a /invoices/bulk-match', invoicesPayload);
                        const response = await fetch('/invoices/bulk-match', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                company_id: companyId || 'default',
                                invoices: invoicesPayload,
                                auto_mark_invoiced: true,
                            }),
                        });

                        if (!response.ok) {
                            const text = await response.text();
                            preliminaryResults.push({
                                filename: undefined,
                                status: 'error',
                                message: `Error conciliando facturas: ${text || response.status}`,
                            });
                            console.error('❌ Error conciliando facturas', text || response.status);
                        } else {
                            const result = await response.json();
                            matchResults = result?.results || [];
                            console.log('🔗 Resultado de conciliación masiva', matchResults);

                            const linkedExpenses = matchResults
                                .filter((item) => item.status === 'linked' && item.expense)
                                .map((item) => item.expense);

                            if (linkedExpenses.length > 0 && typeof setExpensesData === 'function') {
                                setExpensesData((prevExpenses) => {
                                    const map = new Map(prevExpenses.map((exp) => [exp.id, exp]));
                                    linkedExpenses.forEach((expense) => {
                                        const normalized = typeof normalizeExpenseFn === 'function'
                                            ? normalizeExpenseFn(expense)
                                            : expense;
                                        map.set(normalized.id, normalized);
                                    });
                                    return Array.from(map.values());
                                });
                            }
                        }
                    } catch (error) {
                        console.error('Error matching invoices', error);
                        preliminaryResults.push({
                            filename: undefined,
                            status: 'error',
                            message: 'Error interno al conciliar las facturas.',
                        });
                    }
                }

                const finalResults = [
                    ...matchResults,
                    ...preliminaryResults,
                ];

                setUploadResults(finalResults);
                setUploadSummary({
                    total: selectedFiles.length,
                    sent_to_match: invoicesPayload.length,
                    linked: finalResults.filter((r) => r.status === 'linked').length,
                    needs_review: finalResults.filter((r) => r.status === 'needs_review').length,
                    errors: finalResults.filter((r) => r.status === 'error').length,
                });
                setSelectedFiles([]);
                setIsUploading(false);
                setShowTable(true);
                console.log('📊 Resumen conciliación', {
                    total: selectedFiles.length,
                    enviados: invoicesPayload.length,
                    resultados: finalResults,
                });
            };

            return (
                <div className="p-4 sm:p-6 space-y-4">
                    <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
                        <h3 className="font-medium text-green-800 mb-2">
                            📤 Carga masiva de facturas
                        </h3>
                        <p className="text-sm text-green-700">
                            Sube múltiples facturas XML/PDF para procesamiento automático
                        </p>
                    </div>

                    <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 sm:p-8 text-center">
                        <input
                            type="file"
                            id="invoice-files"
                            multiple
                            accept=".xml,.pdf"
                            className="hidden"
                            onChange={(e) => handleFileSelection(e.target.files)}
                        />
                        <label htmlFor="invoice-files" className="cursor-pointer">
                            <i className="fas fa-cloud-upload-alt text-4xl text-gray-400 mb-4"></i>
                            <p className="text-lg font-medium text-gray-700">Arrastra facturas aquí o haz clic para seleccionar</p>
                            <p className="text-sm text-gray-500 mt-2">Soporta archivos XML y PDF</p>
                        </label>
                    </div>

                    {selectedFiles.length > 0 && (
                        <div className="space-y-2">
                            <h4 className="font-medium text-gray-900">Archivos seleccionados:</h4>
                            {selectedFiles.map((file, index) => (
                                <div key={index} className="flex items-center justify-between bg-gray-50 p-2 rounded">
                                    <span className="text-sm">{file.name}</span>
                                    <span className="text-xs text-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB</span>
                                </div>
                            ))}
                            <button
                                onClick={processInvoices}
                                disabled={isUploading}
                                className="w-full mt-4 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                            >
                                {isUploading ? 'Procesando...' : `Procesar ${selectedFiles.length} facturas`}
                            </button>
                        </div>
                    )}

                    {uploadSummary && (
                        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-4">
                            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                                <div>
                                    <h4 className="font-medium text-gray-900 flex items-center gap-2">
                                        <i className="fas fa-clipboard-check text-green-600"></i>
                                        Resumen de conciliación
                                    </h4>
                                    <p className="text-sm text-gray-600">{uploadSummary.linked}/{uploadSummary.sent_to_match} facturas conciliadas automáticamente</p>
                                </div>
                                <div className="text-right">
                                    <p className="text-xs text-gray-500">{uploadSummary.total} archivos subidos</p>
                                    <button
                                        onClick={() => {
                                            const headers = ['Archivo', 'UUID', 'Estado', 'Mensaje'];
                                            const rows = uploadResults.map((item) => [
                                                item.filename || '',
                                                item.uuid || '',
                                                item.status,
                                                item.message || '',
                                            ]);
                                            const csv = [headers.join(','), ...rows.map(row => row.map(value => `"${String(value).replace(/"/g, '""')}"`).join(','))].join('\n');
                                            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
                                            const url = URL.createObjectURL(blob);
                                            const link = document.createElement('a');
                                            link.href = url;
                                            link.setAttribute('download', `resumen-conciliacion-${Date.now()}.csv`);
                                            document.body.appendChild(link);
                                            link.click();
                                            document.body.removeChild(link);
                                            URL.revokeObjectURL(url);
                                        }}
                                        className="inline-flex items-center gap-2 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                                    >
                                        <i className="fas fa-download"></i>
                                        Descargar reporte
                                    </button>
                                </div>
                            </div>

                            {(() => {
                                const totalConciliadas = uploadSummary.linked;
                                const totalProcesadas = uploadSummary.sent_to_match || 1;
                                const percentage = Math.round((totalConciliadas / totalProcesadas) * 100);
                                return (
                                    <div className="bg-emerald-100 border border-emerald-200 rounded-lg p-3 space-y-2">
                                        <div className="flex items-center justify-between text-xs font-semibold text-emerald-700">
                                            <span>{totalConciliadas}/{totalProcesadas} facturas conciliadas automáticamente</span>
                                            <span>{percentage}%</span>
                                        </div>
                                        <div className="w-full h-2 bg-emerald-200 rounded-full overflow-hidden">
                                            <div
                                                className="h-full bg-emerald-500 transition-all duration-700"
                                                style={{ width: `${percentage}%` }}
                                            ></div>
                                        </div>
                                        <p className="text-sm text-emerald-900 font-medium">
                                            {percentage >= 70
                                                ? '¡Buen trabajo! La mayoría se conciliaron solas, revisa las pendientes 👀'
                                                : 'Vamos bien, revisa las pendientes para cerrar el ciclo 🚀'}
                                        </p>
                                    </div>
                                );
                            })()}

                            <div className="grid grid-cols-2 gap-3 text-sm">
                                <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
                                    <p className="text-emerald-700 font-semibold">{uploadSummary.linked}</p>
                                    <p className="text-emerald-600">Facturas conciliadas automáticamente</p>
                                </div>
                                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                                    <p className="text-yellow-700 font-semibold">{uploadSummary.needs_review}</p>
                                    <p className="text-yellow-600">Revisiones manuales sugeridas</p>
                                </div>
                                <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                                    <p className="text-red-700 font-semibold">{uploadSummary.errors}</p>
                                    <p className="text-red-600">Errores durante la carga</p>
                                </div>
                                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                                    <p className="text-slate-700 font-semibold">{uploadSummary.sent_to_match}/{uploadSummary.total}</p>
                                    <p className="text-slate-600">CFDI enviados a conciliación</p>
                                </div>
                            </div>

                            {showTable && uploadResults.length > 0 && (
                                <div className="space-y-3">
                                    <div className="hidden md:block overflow-auto">
                                        <table className="min-w-full text-xs border border-gray-200 rounded-lg">
                                            <thead className="bg-gray-50 text-gray-600 uppercase tracking-wide">
                                                <tr>
                                                    <th className="px-3 py-2 text-left">Folio / UUID</th>
                                                    <th className="px-3 py-2 text-left">Proveedor</th>
                                                    <th className="px-3 py-2 text-left">Monto</th>
                                                    <th className="px-3 py-2 text-left">Fecha</th>
                                                    <th className="px-3 py-2 text-left">Resultado</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-gray-200 bg-white">
                                                {uploadResults.map((item, index) => {
                                                    const statusConfig = {
                                                        linked: { label: 'Conciliada automáticamente', color: 'bg-emerald-100 text-emerald-700 border-emerald-200', icon: 'fas fa-check-circle' },
                                                        needs_review: { label: 'Revisión manual', color: 'bg-yellow-100 text-yellow-700 border-yellow-200', icon: 'fas fa-exclamation-triangle' },
                                                        no_match: { label: 'Sin coincidencia', color: 'bg-slate-100 text-slate-700 border-slate-200', icon: 'fas fa-search' },
                                                        error: { label: 'Error', color: 'bg-red-100 text-red-700 border-red-200', icon: 'fas fa-times-circle' },
                                                        unsupported: { label: 'Formato no soportado', color: 'bg-gray-100 text-gray-700 border-gray-200', icon: 'fas fa-ban' },
                                                    };
                                                    const config = statusConfig[item.status] || statusConfig.no_match;
                                                    const mainCandidate = Array.isArray(item.candidates) && item.candidates.length > 0 ? item.candidates[0] : null;
                                                    const expenseFromResult = item.expense || null;
                                                    const providerName = mainCandidate?.provider_name || expenseFromResult?.proveedor?.nombre || '—';
                                                    const providerRfc = mainCandidate?.provider_rfc || expenseFromResult?.proveedor?.rfc || expenseFromResult?.rfc;
                                                    const amountDisplay = mainCandidate
                                                        ? formatCurrency(mainCandidate.monto_total)
                                                        : expenseFromResult
                                                            ? formatCurrency(expenseFromResult.monto_total)
                                                            : '—';
                                                    const dateDisplay = mainCandidate?.fecha_gasto || expenseFromResult?.fecha_gasto || '—';
                                                    return (
                                                        <tr key={`${item.filename || 'invoice'}-${index}`} className="hover:bg-gray-50">
                                                            <td className="px-3 py-2">
                                                                <div className="font-semibold text-gray-800">{item.uuid || 'Sin UUID'}</div>
                                                                <div className="text-gray-500">{item.filename || 'Factura'}</div>
                                                            </td>
                                                            <td className="px-3 py-2">
                                                                {providerName}
                                                                {providerRfc && (
                                                                    <div className="text-gray-500">RFC: {providerRfc}</div>
                                                                )}
                                                            </td>
                                                            <td className="px-3 py-2">{amountDisplay}</td>
                                                            <td className="px-3 py-2">{dateDisplay}</td>
                                                            <td className="px-3 py-2">
                                                                <span className={`inline-flex items-center gap-1 px-2 py-1 text-[11px] font-semibold rounded-full border ${config.color}`}>
                                                                    <i className={config.icon}></i>
                                                                    {config.label}
                                                                </span>
                                                                {item.message && (
                                                                    <div className="mt-1 text-[11px] text-gray-600">{item.message}</div>
                                                                )}
                                                            </td>
                                                        </tr>
                                                    );
                                                })}
                                            </tbody>
                                        </table>
                                    </div>
                                    <div className="md:hidden space-y-2">
                                        {uploadResults.map((item, index) => {
                                            const statusConfig = {
                                                linked: { label: 'Conciliada automáticamente', color: 'bg-emerald-100 text-emerald-700 border-emerald-200', icon: 'fas fa-check-circle' },
                                                needs_review: { label: 'Revisión manual', color: 'bg-yellow-100 text-yellow-700 border-yellow-200', icon: 'fas fa-exclamation-triangle' },
                                                no_match: { label: 'Sin coincidencia', color: 'bg-slate-100 text-slate-700 border-slate-200', icon: 'fas fa-search' },
                                                error: { label: 'Error', color: 'bg-red-100 text-red-700 border-red-200', icon: 'fas fa-times-circle' },
                                                unsupported: { label: 'Formato no soportado', color: 'bg-gray-100 text-gray-700 border-gray-200', icon: 'fas fa-ban' },
                                            };
                                            const config = statusConfig[item.status] || statusConfig.no_match;
                                            const mainCandidate = Array.isArray(item.candidates) && item.candidates.length > 0 ? item.candidates[0] : null;
                                            const expenseFromResult = item.expense || null;
                                            const providerName = mainCandidate?.provider_name || expenseFromResult?.proveedor?.nombre || '—';
                                            const providerRfc = mainCandidate?.provider_rfc || expenseFromResult?.proveedor?.rfc || expenseFromResult?.rfc;
                                            const amountDisplay = mainCandidate
                                                ? formatCurrency(mainCandidate.monto_total)
                                                : expenseFromResult
                                                    ? formatCurrency(expenseFromResult.monto_total)
                                                    : '—';
                                            const dateDisplay = mainCandidate?.fecha_gasto || expenseFromResult?.fecha_gasto || '—';
                                            return (
                                                <div key={`${item.filename || 'invoice-mobile'}-${index}`} className="border border-gray-200 rounded-lg p-3 bg-white space-y-2">
                                                    <div className="flex items-center justify-between">
                                                        <div>
                                                            <p className="text-sm font-semibold text-gray-800">{item.filename || 'Factura'}</p>
                                                            <p className="text-xs text-gray-500">UUID: {item.uuid || 'Sin UUID'}</p>
                                                        </div>
                                                        <span className={`inline-flex items-center gap-1 px-2 py-1 text-[11px] font-semibold rounded-full border ${config.color}`}>
                                                            <i className={config.icon}></i>
                                                            {config.label}
                                                        </span>
                                                    </div>
                                                    <div className="text-xs text-gray-600 space-y-1">
                                                        <p><strong>Proveedor:</strong> {providerName}</p>
                                                        {providerRfc && <p><strong>RFC:</strong> {providerRfc}</p>}
                                                        <p><strong>Monto:</strong> {amountDisplay}</p>
                                                        <p><strong>Fecha:</strong> {dateDisplay}</p>
                                                        {item.message && <p className="text-[11px] text-gray-500">{item.message}</p>}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                    <p className="text-xs text-gray-500">Tip: abre la pestaña “Conciliar Gastos” para resolver rápidamente las facturas en revisión manual.</p>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            );
        };

        // Componente de Conciliación
        const ReconciliationContent = ({ expensesData, onOpenBulkUpload }) => {
            const pendingExpenses = expensesData.filter((expense) => isPendingInvoiceStatus(expense.estado_factura));
            const facturadoExpenses = expensesData.filter((expense) => expense.estado_factura === 'facturado');
            const conciliatedExpenses = facturadoExpenses.filter((expense) => expense.estado_conciliacion === 'conciliado_banco');

            const conciliatedPercentage = facturadoExpenses.length === 0
                ? '0.0'
                : ((conciliatedExpenses.length / facturadoExpenses.length) * 100).toFixed(1);

            return (
                <div className="p-6 space-y-4">
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                            <div>
                                <h3 className="font-medium text-blue-800 mb-1 flex items-center gap-2">
                                    <i className="fas fa-route"></i>
                                    Flujo guiado: captura → factura → banco
                                </h3>
                                <p className="text-sm text-blue-700">
                                    Revisa la columna izquierda para saber qué gastos aún necesitan factura y usa la derecha para monitorear los que ya están listos o conciliados con el banco.
                                </p>
                            </div>
                            <button
                                onClick={() => typeof onOpenBulkUpload === 'function' && onOpenBulkUpload()}
                                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-green-600 text-white rounded-lg hover:bg-green-700"
                            >
                                <i className="fas fa-file-upload"></i>
                                Carga masiva de facturas
                            </button>
                        </div>
                    </div>

                    <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 mb-4">
                        <h3 className="font-medium text-purple-800 mb-2">
                            ⚖️ Conciliador de Gastos vs Facturas
                        </h3>
                        <p className="text-sm text-purple-700">
                            Revisa el avance del ciclo gasto → factura y verifica qué gastos ya están listos para pasar a conciliación bancaria.
                        </p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="bg-white border border-gray-200 rounded-lg p-4">
                            <h4 className="font-medium text-gray-900 mb-3 flex items-center">
                                <i className="fas fa-exclamation-circle text-orange-500 mr-2"></i>
                                Gastos sin conciliar ({pendingExpenses.length})
                            </h4>
                            <div className="space-y-2 max-h-64 overflow-y-auto">
                                {pendingExpenses.map(expense => (
                                    <div key={expense.id} className="p-3 bg-orange-50 border border-orange-200 rounded">
                                        <p className="font-medium text-sm">{expense.descripcion}</p>
                                        <p className="text-xs text-gray-600">{formatCurrency(expense.monto_total)} • {expense.fecha_gasto}</p>
                                        {(() => {
                                            const invoiceMeta = expense.invoice_status_meta || getInvoiceStatusMeta(expense.estado_factura);
                                            const badgeClass = getBadgeClassName(invoiceMeta.accent);
                                            return (
                                                <div className="mt-2 space-y-1">
                                                    <span className={`inline-flex items-center px-2 py-1 text-xs font-medium rounded ${badgeClass}`}>
                                                        <i className="fas fa-file-invoice mr-1"></i>
                                                        {invoiceMeta.label}
                                                    </span>
                                                    <p className="text-xs text-orange-700 flex items-start gap-1">
                                                        <i className="fas fa-lightbulb mt-0.5"></i>
                                                        <span>{invoiceMeta.description}</span>
                                                    </p>
                                                </div>
                                            );
                                        })()}
                                        {!expense.factura_id && (
                                            <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                                                <i className="fas fa-upload"></i>
                                                Sube el CFDI o marca si no requiere factura.
                                            </p>
                                        )}
                                    </div>
                                ))}

                                {pendingExpenses.length === 0 && (
                                    <div className="text-center text-sm text-gray-500 py-6">
                                        <i className="fas fa-check text-green-500 text-2xl mb-2"></i>
                                        <p>Todos los gastos con factura ya están conciliados.</p>
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="bg-white border border-gray-200 rounded-lg p-4">
                            <h4 className="font-medium text-gray-900 mb-3 flex items-center">
                                <i className="fas fa-check-circle text-green-500 mr-2"></i>
                                Conciliación de gastos ({facturadoExpenses.length})
                            </h4>
                            <div className="space-y-4 max-h-64 overflow-y-auto pr-1">
                                <div>
                                    <div className="flex items-center justify-between mb-2">
                                        <h5 className="text-sm font-semibold text-emerald-700 flex items-center gap-2">
                                            <i className="fas fa-layer-group"></i>
                                            Listos para conciliación bancaria ({readyForBankStage.length})
                                        </h5>
                                        {readyForBankStage.length > 0 && (
                                            <span className="text-xs text-emerald-600">Da clic en “Conciliar Gastos” para avanzar al banco</span>
                                        )}
                                    </div>
                                    <div className="space-y-2">
                                        {readyForBankStage.map(expense => {
                                            const movimientos = expense.movimientos_bancarios || (expense.movimiento_bancario ? [expense.movimiento_bancario] : []);
                                            const bankMeta = expense.bank_status_meta || getBankStatusMeta(expense.estado_conciliacion);
                                            const bankBadgeClass = getBadgeClassName(bankMeta.accent);
                                            const invoiceMeta = expense.invoice_status_meta || getInvoiceStatusMeta(expense.estado_factura);
                                            return (
                                                <div key={`ready-${expense.id}`} className="p-3 bg-emerald-50 border border-emerald-200 rounded space-y-2">
                                                    <div className="flex items-center justify-between gap-2">
                                                        <p className="font-medium text-sm text-emerald-900">{expense.descripcion}</p>
                                                        <span className={`inline-flex items-center px-2 py-1 text-xs font-medium rounded ${bankBadgeClass}`}>
                                                            <i className="fas fa-traffic-light mr-1"></i>
                                                            {bankMeta.label}
                                                        </span>
                                                    </div>
                                                    <p className="text-xs text-gray-600">{formatCurrency(expense.monto_total)} • {expense.fecha_gasto}</p>
                                                    <div className="mt-1 text-xs text-green-700 flex flex-wrap items-center gap-2">
                                                        <i className="fas fa-file-invoice"></i>
                                                        <span>Factura {expense.factura_id || (expense.factura_url ? 'registrada' : 'sin folio')}</span>
                                                        {expense.factura_url && (
                                                            <a
                                                                href={expense.factura_url}
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                className="text-blue-600 hover:underline"
                                                            >
                                                                Abrir factura
                                                            </a>
                                                        )}
                                                        <span className={`inline-flex items-center px-2 py-1 text-xs font-medium rounded ${getBadgeClassName(invoiceMeta.accent)}`}>
                                                            <i className="fas fa-layer-group mr-1"></i>
                                                            {invoiceMeta.label}
                                                        </span>
                                                    </div>
                                                    <p className="text-xs text-emerald-700 flex items-start gap-1">
                                                        <i className="fas fa-info-circle mt-0.5"></i>
                                                        <span>{bankMeta.description}</span>
                                                    </p>
                                                    {movimientos.length > 0 && (
                                                        <div className="text-xs text-indigo-700 space-y-1">
                                                            {movimientos.map((mov, idx) => (
                                                                <div key={idx} className="flex items-center justify-between">
                                                                    <span className="flex items-center gap-2">
                                                                        <i className="fas fa-university"></i>
                                                                        {mov.bank || mov.banco || 'Movimiento bancario'} • {mov.description || mov.descripcion || 'Sin descripción'}
                                                                    </span>
                                                                    <span>{formatCurrency(mov.amount || mov.monto || 0)}</span>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })}

                                        {readyForBankStage.length === 0 && (
                                            <div className="text-xs text-gray-500 px-3 py-4 bg-emerald-50 border border-dashed border-emerald-200 rounded">
                                                <i className="fas fa-smile mr-1 text-emerald-500"></i>
                                                Todos los gastos facturados ya fueron conciliados en banco.
                                            </div>
                                        )}
                                    </div>
                                </div>

                                <div className="pt-3 border-t border-gray-200">
                                    <div className="flex items-center justify-between mb-2">
                                        <h5 className="text-sm font-semibold text-indigo-700 flex items-center gap-2">
                                            <i className="fas fa-university"></i>
                                            Conciliados en banco ({conciliatedExpenses.length})
                                        </h5>
                                        {conciliatedExpenses.length > 0 && (
                                            <span className="text-xs text-indigo-600">Consulta los movimientos asociados</span>
                                        )}
                                    </div>
                                    <div className="space-y-2">
                                        {conciliatedExpenses.map(expense => {
                                            const movimientos = expense.movimientos_bancarios || (expense.movimiento_bancario ? [expense.movimiento_bancario] : []);
                                            const totalConciliado = movimientos.reduce((sum, mov) => sum + (mov.amount || mov.monto || 0), 0);
                                            const bankMeta = expense.bank_status_meta || getBankStatusMeta(expense.estado_conciliacion);
                                            const badgeClass = getBadgeClassName(bankMeta.accent);
                                            return (
                                                <div key={`bank-${expense.id}`} className="p-3 bg-green-50 border border-green-200 rounded space-y-2">
                                                    <div className="flex items-center justify-between">
                                                        <div>
                                                            <p className="font-medium text-sm">{expense.descripcion}</p>
                                                            <p className="text-xs text-gray-600">Factura {expense.factura_id || 'sin folio'} • {expense.fecha_gasto}</p>
                                                        </div>
                                                        <span className={`inline-flex items-center px-2 py-1 text-xs font-medium rounded ${badgeClass}`}>
                                                            <i className="fas fa-check mr-1"></i>
                                                            {bankMeta.label}
                                                        </span>
                                                    </div>
                                                    <div className="text-xs text-green-700 space-y-1">
                                                        {movimientos.map((mov, idx) => (
                                                            <div key={idx} className="flex items-center justify-between">
                                                                <span className="flex items-center gap-2">
                                                                    <i className="fas fa-university"></i>
                                                                    {mov.bank} • {mov.description}
                                                                </span>
                                                                <span>{formatCurrency(mov.amount || mov.monto || 0)}</span>
                                                            </div>
                                                        ))}
                                                        <div className="flex items-center gap-2">
                                                            <i className="fas fa-calendar-day"></i>
                                                            <span>Conciliado el {new Date(expense.fecha_conciliacion_bancaria || expense.fecha_facturacion || new Date()).toLocaleDateString('es-MX')}</span>
                                                        </div>
                                                    </div>
                                                    <div className="mt-2 flex items-center gap-2">
                                                        <a
                                                            className="text-blue-600 text-xs hover:underline"
                                                            href={expense.factura_url || '#'}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                        >
                                                            Ver factura
                                                        </a>
                                                        <span className="text-gray-400 text-xs">•</span>
                                                        <button
                                                            onClick={() => handleLinkMovement(expense, null)}
                                                            className="text-xs text-red-600 hover:text-red-700"
                                                        >
                                                            Desasociar movimiento
                                                        </button>
                                                    </div>
                                                    <div className="text-xs text-gray-500">
                                                        Total conciliado: {formatCurrency(totalConciliado || expense.monto_total)}
                                                    </div>
                                                </div>
                                            );
                                        })}

                                        {conciliatedExpenses.length === 0 && (
                                            <div className="text-xs text-gray-500 px-3 py-4 bg-gray-50 border border-dashed border-gray-200 rounded">
                                                <i className="fas fa-info-circle mr-1 text-gray-500"></i>
                                                Aún no hay movimientos bancarios confirmados para este periodo.
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {facturadoExpenses.length === 0 && (
                                    <div className="text-center text-sm text-gray-500 py-6">
                                        <i className="fas fa-file-invoice text-gray-400 text-2xl mb-2"></i>
                                        <p>Aquí verás los gastos que ya tienen factura y avanzan a conciliación.</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                        <div className="flex items-center justify-between flex-wrap gap-3">
                            <div>
                                <h4 className="font-medium text-gray-900">Resumen de Conciliación</h4>
                                <p className="text-sm text-gray-600">{conciliatedPercentage}% de los gastos con factura ya están conciliados contra el banco.</p>
                            </div>
                            <button className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors text-sm">
                                📊 Reporte de conciliación
                            </button>
                        </div>
                    </div>
                </div>
            );
        };

        const BankReconciliationContent = ({ expensesData, onUpdateExpense, companyId, onMissionComplete }) => {
            const resolvedCompany = companyId || 'default';
            const readyForBank = expensesData.filter(expense => expense.estado_factura === 'facturado');
            const reconciledWithBank = readyForBank.filter(expense => expense.estado_conciliacion === 'conciliado_banco');
            const pendingBankLink = readyForBank.filter(expense => expense.estado_conciliacion !== 'conciliado_banco');

            const [bankMovements, setBankMovements] = useState(SAMPLE_BANK_MOVEMENTS);
            const [suggestionsByExpense, setSuggestionsByExpense] = useState({});
            const [loadingSuggestions, setLoadingSuggestions] = useState({});
            const [feedbackStatus, setFeedbackStatus] = useState({});

            const fetchMovements = useCallback(async () => {
                try {
                    const response = await fetch(`/bank_reconciliation/movements?company_id=${encodeURIComponent(resolvedCompany)}`);
                    if (!response.ok) {
                        throw new Error('Error obteniendo movimientos bancarios');
                    }
                    const data = await response.json();
                    if (data?.movements) {
                        setBankMovements(data.movements);
                    }
                } catch (error) {
                    console.error('Error fetching bank movements:', error);
                }
            }, [resolvedCompany]);

            useEffect(() => {
                fetchMovements();
            }, [fetchMovements]);

        const normalizeMovement = useCallback((movement) => ({
            ...movement,
            movement_id: movement.movement_id || movement.id,
            id: movement.movement_id || movement.id,
            amount: movement.amount || movement.monto || 0,
            movement_date: movement.movement_date || movement.fecha || movement.fecha_movimiento,
            description: movement.description || movement.descripcion || '',
            bank: movement.bank || movement.banco || '',
            currency: movement.currency || movement.moneda || 'MXN',
            tags: movement.tags || [],
        }), []);

            const normalizedBankMovements = useMemo(
                () => bankMovements.map(normalizeMovement),
                [bankMovements, normalizeMovement]
            );

            const movementIndex = useMemo(() => {
                const result = {};
                normalizedBankMovements.forEach((movement) => {
                    if (movement.movement_id) {
                        result[movement.movement_id] = movement;
                    }
                });
                return result;
            }, [normalizedBankMovements]);

            const assignedMovementIds = useMemo(() => {
                const identifiers = new Set();
                reconciledWithBank.forEach((expense) => {
                    const linkedList = expense.movimientos_bancarios || [];
                    if (linkedList.length > 0) {
                        linkedList.forEach(linked => {
                            const identifier = linked.movement_id || linked.id;
                            if (identifier) {
                                identifiers.add(identifier);
                            }
                        });
                    } else {
                        const linked = expense.movimiento_bancario || {};
                        const identifier = linked.movement_id || linked.id;
                        if (identifier) {
                            identifiers.add(identifier);
                        }
                    }
                });
                return identifiers;
            }, [reconciledWithBank]);

            const availableMovements = useMemo(
                () => normalizedBankMovements.filter(mov => !assignedMovementIds.has(mov.movement_id)),
                [normalizedBankMovements, assignedMovementIds]
            );

            const sendFeedback = useCallback(async ({ expenseId, movementId, confidence, decision, metadata }) => {
                try {
                    await fetch('/bank_reconciliation/feedback', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            expense_id: expenseId,
                            movement_id: movementId,
                            confidence,
                            decision,
                            metadata,
                            company_id: resolvedCompany,
                        })
                    });
                } catch (error) {
                    console.error('Error enviando feedback de conciliación bancaria:', error);
                }
            }, [resolvedCompany]);

            const handleLinkMovement = useCallback((expense, movementInput, options = {}) => {
                const movementsArray = Array.isArray(movementInput) ? movementInput : movementInput ? [movementInput] : [];

                if (movementsArray.length === 0) {
                    onUpdateExpense(expense.id, () => ({
                        movimiento_bancario: null,
                        movimientos_bancarios: [],
                        estado_conciliacion: 'pendiente_bancaria',
                        fecha_conciliacion_bancaria: null,
                        conciliacion_detalle: null,
                    }));
                    setFeedbackStatus(prev => ({ ...prev, [expense.id]: { type: 'cleared', message: 'Movimiento desasociado' } }));
                    return;
                }

                const normalizedArray = movementsArray.map(normalizeMovement);
                const totalConciliado = normalizedArray.reduce((sum, mov) => sum + (mov.amount || 0), 0);

                onUpdateExpense(expense.id, () => ({
                    movimiento_bancario: normalizedArray[0],
                    movimientos_bancarios: normalizedArray,
                    estado_conciliacion: 'conciliado_banco',
                    fecha_conciliacion_bancaria: new Date().toISOString(),
                    conciliacion_detalle: {
                        movimientos: normalizedArray.length,
                        total_conciliado: totalConciliado,
                        origen: options.decision || 'manual',
                    }
                }));

                normalizedArray.forEach((mov) => {
                    const movementId = mov.movement_id || mov.id;
                    if (!movementId) return;
                    sendFeedback({
                        expenseId: expense.id,
                        movementId,
                        confidence: options.confidence ?? 0,
                        decision: options.decision ?? 'manual',
                        metadata: {
                            ...(options.metadata || {}),
                            component_amount: mov.amount,
                        },
                    });
                });

                setFeedbackStatus(prev => ({
                    ...prev,
                    [expense.id]: {
                        type: options.decision === 'accepted' ? 'accepted' : 'manual',
                        message: options.decision === 'accepted'
                            ? `Conciliación automática aplicada (${normalizedArray.length} cargos)`
                            : normalizedArray.length > 1
                                ? `Relacionaste ${normalizedArray.length} cargos manualmente`
                                : 'Movimiento asociado manualmente',
                    }
                }));

                if (typeof onMissionComplete === 'function') {
                    onMissionComplete();
                }
            }, [onUpdateExpense, sendFeedback, normalizeMovement]);

            const loadSuggestions = useCallback(async (expense) => {
                try {
                    setLoadingSuggestions(prev => ({ ...prev, [expense.id]: true }));
                    const response = await fetch('/bank_reconciliation/suggestions', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            expense_id: expense.id,
                            amount: expense.monto_total || expense.amount || 0,
                            currency: expense.currency || 'MXN',
                            description: expense.descripcion || expense.description,
                            date: expense.fecha_gasto,
                            provider_name: expense['proveedor.nombre'] || (typeof expense.proveedor === 'string' ? expense.proveedor : expense.proveedor?.nombre),
                            paid_by: expense.paid_by,
                            company_id: resolvedCompany,
                            metadata: {
                                categoria: expense.categoria,
                                forma_pago: expense.forma_pago,
                            }
                        })
                    });

                    if (!response.ok) {
                        throw new Error('Error obteniendo sugerencias');
                    }

                    const data = await response.json();
                    const suggestions = data?.suggestions || [];

                    setSuggestionsByExpense(prev => ({
                        ...prev,
                        [expense.id]: {
                            suggestions,
                            top: suggestions.length > 0 ? suggestions[0] : null,
                        }
                    }));
                } catch (error) {
                    console.error('Error loading bank suggestions:', error);
                } finally {
                    setLoadingSuggestions(prev => {
                        const next = { ...prev };
                        delete next[expense.id];
                        return next;
                    });
                }
            }, [resolvedCompany]);

            useEffect(() => {
                pendingBankLink.forEach(expense => {
                    if (!suggestionsByExpense[expense.id] && !loadingSuggestions[expense.id]) {
                        loadSuggestions(expense);
                    }
                });
            }, [pendingBankLink, suggestionsByExpense, loadingSuggestions, loadSuggestions]);

            const handleAcceptSuggestion = useCallback((expense, suggestionEntry) => {
                if (!suggestionEntry) return;
                const normalizedMovements = (suggestionEntry.movements || (suggestionEntry.movement ? [suggestionEntry.movement] : []))
                    .map(normalizeMovement);

                normalizedMovements.forEach((mov) => {
                    if (!movementIndex[mov.movement_id]) {
                        setBankMovements(prev => [...prev, mov]);
                    }
                });

                handleLinkMovement(expense, normalizedMovements, {
                    decision: 'accepted',
                    confidence: suggestionEntry.confidence,
                    metadata: {
                        reasons: suggestionEntry.reasons,
                        score_breakdown: suggestionEntry.score_breakdown,
                    }
                });
                setSuggestionsByExpense(prev => ({
                    ...prev,
                    [expense.id]: {
                        ...prev[expense.id],
                        accepted: true,
                    }
                }));
            }, [handleLinkMovement, normalizeMovement, movementIndex]);

            const handleRejectSuggestion = useCallback((expense, suggestionEntry) => {
                if (!suggestionEntry) return;
                const normalizedMovements = (suggestionEntry.movements || (suggestionEntry.movement ? [suggestionEntry.movement] : []))
                    .map(normalizeMovement);

                normalizedMovements.forEach((movement) => {
                    const movementId = movement.movement_id;
                    if (!movementId) return;
                    sendFeedback({
                        expenseId: expense.id,
                        movementId,
                        confidence: suggestionEntry.confidence,
                        decision: 'rejected',
                        metadata: {
                            reasons: suggestionEntry.reasons,
                            score_breakdown: suggestionEntry.score_breakdown,
                        }
                    });
                });
                setSuggestionsByExpense(prev => ({
                    ...prev,
                    [expense.id]: {
                        ...prev[expense.id],
                        dismissed: true,
                    }
                }));
            }, [normalizeMovement, sendFeedback]);

            const confidenceBadge = (confidence) => {
                if (confidence >= 90) return 'bg-green-100 text-green-800 border border-green-200';
                if (confidence >= 75) return 'bg-yellow-100 text-yellow-800 border border-yellow-200';
                return 'bg-gray-100 text-gray-700 border border-gray-200';
            };

            return (
                <div className="p-6 space-y-6">
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <h3 className="font-medium text-blue-800 mb-2">💳 Conciliación bancaria (Paso 4)</h3>
                        <p className="text-sm text-blue-700">
                            Aquí solo aparecen los gastos que ya pasaron por “Conciliación de gastos” y están listos para vincularse con un movimiento bancario.
                            Acepta la sugerencia o selecciona un cargo para cerrar el ciclo.
                        </p>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-4">
                            <div className="flex items-center justify-between">
                                <h4 className="font-medium text-gray-900">Pendientes de asociar a banco</h4>
                                <span className="text-sm text-gray-500">{pendingBankLink.length} gastos</span>
                            </div>

                            {pendingBankLink.length === 0 && (
                                <div className="text-center text-sm text-gray-500 py-8">
                                    <i className="fas fa-check-circle text-green-500 text-3xl mb-2"></i>
                                    <p>Todo lo facturado ya está vinculado a un movimiento bancario.</p>
                                </div>
                            )}

                            <div className="space-y-3 max-h-96 overflow-y-auto">
                                {pendingBankLink.map(expense => {
                                    const suggestionEntry = suggestionsByExpense[expense.id]?.top || null;
                                    const movementsSource = suggestionEntry?.movements || (suggestionEntry?.movement ? [suggestionEntry.movement] : []);
                                    const normalizedSuggestionMovements = movementsSource.map(normalizeMovement);
                                    const combinedAmount = suggestionEntry?.combined_amount || normalizedSuggestionMovements.reduce((s, mov) => s + (mov.amount || 0), 0);
                                    const isLoading = !!loadingSuggestions[expense.id];
                                    const suggestionDismissed = suggestionsByExpense[expense.id]?.dismissed;
                                    const bankMeta = expense.bank_status_meta || getBankStatusMeta(expense.estado_conciliacion);
                                    const badgeClass = getBadgeClassName(bankMeta.accent);

                                    return (
                                        <div key={expense.id} className="border border-blue-200 bg-blue-50 rounded-lg p-4 space-y-3">
                                            <div className="flex items-center justify-between">
                                                <div>
                                                    <p className="font-medium text-gray-900">{expense.descripcion}</p>
                                                    <p className="text-xs text-gray-600">Factura {expense.factura_id || 'sin folio'} • {expense.fecha_gasto}</p>
                                                </div>
                                                <span className="text-sm font-semibold text-gray-900">{formatCurrency(expense.monto_total)}</span>
                                            </div>

                                            <div className="flex items-center justify-between flex-wrap gap-2">
                                                <span className={`inline-flex items-center px-2 py-1 text-xs font-medium rounded ${badgeClass}`}>
                                                    <i className="fas fa-info-circle mr-1"></i>
                                                    {bankMeta.label}
                                                </span>
                                                <p className="text-xs text-blue-700 flex items-start gap-1">
                                                    <i className="fas fa-lightbulb mt-0.5"></i>
                                                    <span>{bankMeta.description}</span>
                                                </p>
                                            </div>

                                            {isLoading && (
                                                <div className="bg-white border border-blue-100 rounded-lg p-3 text-sm text-blue-600 flex items-center gap-2">
                                                    <i className="fas fa-spinner fa-spin"></i>
                                                    Analizando movimientos bancarios…
                                                </div>
                                            )}

                                            {!isLoading && suggestionEntry && !suggestionDismissed && (
                                                <div className="bg-white border border-blue-200 rounded-lg p-3 space-y-2">
                                                    <div className="flex items-center justify-between">
                                                        <div>
                                                            <p className="text-sm text-gray-800 font-medium">
                                                                {suggestionEntry.type === 'combination' ? `Sugerencia IA (pago en ${normalizedSuggestionMovements.length} cargos)` : 'Sugerencia IA'}
                                                            </p>
                                                            {suggestionEntry.type === 'combination' ? (
                                                                <p className="text-xs text-gray-600">{normalizedSuggestionMovements.map(mov => `${mov.movement_date} • ${mov.bank}`).join(' + ')}</p>
                                                            ) : (
                                                                <p className="text-xs text-gray-600">{normalizedSuggestionMovements[0]?.description}</p>
                                                            )}
                                                    </div>
                                                    <span className={`px-2 py-1 rounded-full text-xs font-semibold ${confidenceBadge(suggestionEntry.confidence)}`}>
                                                        Confianza {Math.round(suggestionEntry.confidence)}%
                                                    </span>
                                                    <div className="flex flex-wrap gap-2 mt-2">
                                                        {suggestionEntry.split_payment && (
                                                            <span className="px-2 py-1 rounded-full bg-purple-100 text-purple-700 text-xs font-semibold">
                                                                Pago fragmentado
                                                            </span>
                                                        )}
                                                        {suggestionEntry.linked_match && (
                                                            <span className="px-2 py-1 rounded-full bg-emerald-100 text-emerald-700 text-xs font-semibold">
                                                                Coincide con el gasto
                                                            </span>
                                                        )}
                                                        {suggestionEntry.group_id && (
                                                            <span className="px-2 py-1 rounded-full bg-gray-100 text-gray-600 text-xs">
                                                                Grupo: {suggestionEntry.group_id}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                                    <div className="text-xs text-gray-600 flex flex-wrap gap-2">
                                                        {suggestionEntry.type === 'combination' ? (
                                                            <span><strong>Total</strong> • {formatCurrency(combinedAmount)}</span>
                                                        ) : (
                                                            <span><strong>{normalizedSuggestionMovements[0]?.movement_date}</strong> • {normalizedSuggestionMovements[0]?.bank}</span>
                                                        )}
                                                        {suggestionEntry.type === 'combination' && (
                                                            <span>Componentes: {normalizedSuggestionMovements.map(mov => formatCurrency(mov.amount)).join(' + ')}</span>
                                                        )}
                                                        {suggestionEntry.type !== 'combination' && (
                                                            <span>{formatCurrency(normalizedSuggestionMovements[0]?.amount || 0)}</span>
                                                        )}
                                                    </div>
                                                    <div className="text-xs text-gray-500 space-y-1">
                                                        {suggestionEntry.reasons.map((reason, idx) => (
                                                            <div key={idx} className="flex items-center gap-2">
                                                                <i className="fas fa-check text-green-500"></i>
                                                                <span>{reason}</span>
                                                            </div>
                                                        ))}
                                                        {Array.isArray(suggestionEntry.movement_ids) && suggestionEntry.movement_ids.length > 1 && (
                                                            <div className="flex items-center gap-2 text-[11px] text-gray-500">
                                                                <i className="fas fa-link text-blue-400"></i>
                                                                <span>Movimientos: {suggestionEntry.movement_ids.join(' + ')}</span>
                                                            </div>
                                                        )}
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <button
                                                            onClick={() => handleAcceptSuggestion(expense, suggestionEntry)}
                                                            className="flex-1 px-3 py-1 bg-green-600 text-white text-xs rounded-md hover:bg-green-700"
                                                        >
                                                            ✅ Aceptar sugerencia
                                                        </button>
                                                        <button
                                                            onClick={() => handleRejectSuggestion(expense, suggestionEntry)}
                                                            className="px-3 py-1 bg-white border border-red-200 text-red-600 text-xs rounded-md hover:bg-red-50"
                                                        >
                                                            Rechazar
                                                        </button>
                                                    </div>
                                                </div>
                                            )}

                                            <div>
                                                <label className="block text-xs text-gray-600 mb-1">Vincular con movimiento bancario</label>
                                                <select
                                                    value=""
                                                    onChange={(e) => {
                                                        const selected = movementIndex[e.target.value];
                                                        if (selected) {
                                                            handleLinkMovement(expense, selected, {
                                                                decision: 'manual',
                                                                metadata: { source: 'manual_select' },
                                                            });
                                                        }
                                                    }}
                                                    className="w-full border border-gray-300 rounded-md text-sm p-2"
                                                    disabled={availableMovements.length === 0}
                                                >
                                                    <option value="">Selecciona un movimiento</option>
                                                    {availableMovements.map(movement => (
                                                        <option key={movement.movement_id} value={movement.movement_id}>
                                                            {movement.movement_date} • {movement.bank} • {formatCurrency(movement.amount)} → {movement.description}
                                                        </option>
                                                    ))}
                                                </select>

                                                {availableMovements.length === 0 && (
                                                    <p className="text-xs text-gray-500 mt-2">
                                                        Todos los movimientos disponibles ya están asociados. Carga más movimientos bancarios para continuar conciliando.
                                                    </p>
                                                )}
                                            </div>

                                            {feedbackStatus[expense.id] && (
                                                <div className="text-xs text-green-700 flex items-center gap-2">
                                                    <i className="fas fa-check-circle"></i>
                                                    <span>{feedbackStatus[expense.id].message}</span>
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-4">
                            <div className="flex items-center justify-between">
                                <h4 className="font-medium text-gray-900">Gastos conciliados con banco</h4>
                                <span className="text-sm text-gray-500">{reconciledWithBank.length} gastos</span>
                            </div>

                            {reconciledWithBank.length === 0 && (
                                <div className="text-center text-sm text-gray-500 py-8">
                                    <i className="fas fa-piggy-bank text-blue-500 text-3xl mb-2"></i>
                                    <p>Aquí aparecerán los gastos facturados que ya tienen un movimiento bancario asociado.</p>
                                </div>
                            )}

                            <div className="space-y-3 max-h-96 overflow-y-auto">
                                {reconciledWithBank.map(expense => {
                                    const movimientos = expense.movimientos_bancarios || (expense.movimiento_bancario ? [expense.movimiento_bancario] : []);
                                    const totalConciliado = movimientos.reduce((sum, mov) => sum + (mov.amount || mov.monto || 0), 0);
                                    const bankMeta = expense.bank_status_meta || getBankStatusMeta(expense.estado_conciliacion);
                                    const badgeClass = getBadgeClassName(bankMeta.accent);
                                    return (
                                        <div key={expense.id} className="border border-green-200 bg-green-50 rounded-lg p-4 space-y-2">
                                            <div className="flex items-center justify-between">
                                                <div>
                                                    <p className="font-medium text-gray-900">{expense.descripcion}</p>
                                                    <p className="text-xs text-gray-600">Factura {expense.factura_id || 'sin folio'} • {expense.fecha_gasto}</p>
                                                </div>
                                                <span className="text-sm font-semibold text-gray-900">{formatCurrency(totalConciliado || expense.monto_total)}</span>
                                            </div>
                                            <span className={`inline-flex items-center px-2 py-1 text-xs font-medium rounded ${badgeClass}`}>
                                                <i className="fas fa-check mr-1"></i>
                                                {bankMeta.label}
                                            </span>
                                            <div className="text-xs text-green-700 space-y-1">
                                                {movimientos.map((mov, idx) => (
                                                    <div key={idx} className="flex items-center justify-between">
                                                        <span className="flex items-center gap-2">
                                                            <i className="fas fa-university"></i>
                                                            {mov.bank} • {mov.description}
                                                        </span>
                                                        <span>{formatCurrency(mov.amount || mov.monto || 0)}</span>
                                                    </div>
                                                ))}
                                                <div className="flex items-center gap-2">
                                                    <i className="fas fa-calendar-day"></i>
                                                    <span>Conciliado el {new Date(expense.fecha_conciliacion_bancaria || expense.fecha_facturacion || new Date()).toLocaleDateString('es-MX')}</span>
                                                </div>
                                            </div>
                                            <div className="mt-2 flex items-center gap-2">
                                                <a
                                                    className="text-blue-600 text-xs hover:underline"
                                                    href={expense.factura_url || '#'}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                >
                                                    Ver factura
                                                </a>
                                                <span className="text-gray-400 text-xs">•</span>
                                                <button
                                                    onClick={() => handleLinkMovement(expense, null)}
                                                    className="text-xs text-red-600 hover:text-red-700"
                                                >
                                                    Desasociar movimiento
                                                </button>
                                            </div>
                                            {expense.conciliacion_detalle && (
                                                <div className="text-xs text-gray-500">
                                                    Registro: {expense.conciliacion_detalle.movimientos || movimientos.length} cargos • {expense.conciliacion_detalle.origen === 'accepted' ? 'Aceptado automáticamente' : 'Manual'}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    </div>

                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                        <h4 className="font-medium text-gray-900 mb-2">Próximos pasos</h4>
                        <p className="text-sm text-gray-600">
                            Con esta información podremos generar reportes por proveedor y por banco en la siguiente etapa. Ya tenemos identificados los gastos conciliados y listos para cruzarse con los movimientos bancarios.
                        </p>
                    </div>
                </div>
            );
        };

        // Componente de Vista de Completitud y Asientos Contables
        const CompletenessView = ({ expensesData, getCategoryInfo }) => {
            const [selectedExpense, setSelectedExpense] = useState(null);
            const [filterStatus, setFilterStatus] = useState('todos');

            console.log('🔍 CompletenessView - expensesData:', expensesData?.length, expensesData);
            console.log('🔍 CompletenessView - getCategoryInfo:', typeof getCategoryInfo);

            if (!expensesData || expensesData.length === 0) {
                return (
                    <div className="p-6 text-center">
                        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                            <h3 className="font-medium text-yellow-800 mb-2">
                                ⚠️ No hay datos disponibles
                            </h3>
                            <p className="text-sm text-yellow-700 mb-4">
                                No se encontraron gastos para mostrar. Esto puede deberse a:
                            </p>
                            <ul className="text-sm text-yellow-700 text-left space-y-1">
                                <li>• Los datos dummy no se generaron correctamente</li>
                                <li>• Hay un error en la carga de datos</li>
                                <li>• El localStorage está vacío</li>
                            </ul>
                            <button
                                onClick={() => window.location.reload()}
                                className="mt-4 px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700"
                            >
                                🔄 Recargar página
                            </button>
                        </div>
                    </div>
                );
            }

            const filteredExpenses = expensesData.filter(expense => {
                if (filterStatus === 'todos') return true;
                return expense.completitud?.estado === filterStatus;
            });

            const getCompletenessColor = (estado) => {
                switch (estado) {
                    case 'completo': return 'text-green-600 bg-green-50 border-green-200';
                    case 'parcial': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
                    case 'incompleto': return 'text-red-600 bg-red-50 border-red-200';
                    default: return 'text-gray-600 bg-gray-50 border-gray-200';
                }
            };

            const getStatusIcon = (estado) => {
                switch (estado) {
                    case 'completo': return '✅';
                    case 'parcial': return '⚠️';
                    case 'incompleto': return '❌';
                    default: return '❓';
                }
            };

            return (
                <div className="p-6 space-y-6">
                    {/* Header con estadísticas */}
                    <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4 mb-4">
                        <h3 className="font-medium text-indigo-800 mb-2">
                            📊 Vista Contable y Completitud
                        </h3>
                        <p className="text-sm text-indigo-700">
                            Revisa el estado contable y completitud de cada transacción
                        </p>
                    </div>

                    {/* Filtros de estado */}
                    <div className="flex gap-3 mb-4">
                        {['todos', 'completo', 'parcial', 'incompleto'].map(status => (
                            <button
                                key={status}
                                onClick={() => setFilterStatus(status)}
                                className={`px-3 py-1 text-sm rounded-lg border transition-colors ${
                                    filterStatus === status
                                        ? 'bg-indigo-600 text-white border-indigo-600'
                                        : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                                }`}
                            >
                                {status === 'todos' ? 'Todos' : status.charAt(0).toUpperCase() + status.slice(1)}
                            </button>
                        ))}
                    </div>

                    {/* Resumen de completitud */}
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                        {['completo', 'parcial', 'incompleto'].map(estado => {
                            const count = expensesData.filter(exp => exp.completitud?.estado === estado).length;
                            const percentage = Math.round((count / expensesData.length) * 100) || 0;
                            return (
                                <div key={estado} className={`p-4 rounded-lg border ${getCompletenessColor(estado)}`}>
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-sm font-medium">{getStatusIcon(estado)} {estado.charAt(0).toUpperCase() + estado.slice(1)}</p>
                                            <p className="text-2xl font-bold">{count}</p>
                                        </div>
                                        <div className="text-right">
                                            <p className="text-sm">{percentage}%</p>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                        <div className="p-4 rounded-lg border bg-blue-50 border-blue-200 text-blue-600">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm font-medium">📈 Total</p>
                                    <p className="text-2xl font-bold">{expensesData.length}</p>
                                </div>
                                <div className="text-right">
                                    <p className="text-sm">100%</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Lista de gastos con completitud */}
                    <div className="space-y-3">
                        {filteredExpenses.map(expense => (
                            <div key={expense.id} className="bg-white border border-gray-200 rounded-lg p-4">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="flex items-center gap-3">
                                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                            getCategoryInfo(expense.categoria).color
                                        }`}>
                                            {getCategoryInfo(expense.categoria).label}
                                        </span>
                                        <h4 className="font-medium text-gray-900">{expense.descripcion}</h4>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <span className={`px-2 py-1 rounded-lg text-xs font-medium border ${
                                            getCompletenessColor(expense.completitud?.estado)
                                        }`}>
                                            {getStatusIcon(expense.completitud?.estado)} {expense.completitud?.porcentaje || 0}% Completo
                                        </span>
                                        <span className="text-lg font-bold text-gray-900">
                                            ${(expense.monto_total || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                                        </span>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                                    <div>
                                        <p className="text-gray-600">Proveedor: {expense['proveedor.nombre'] || (typeof expense.proveedor === 'string' ? expense.proveedor : expense.proveedor?.nombre) || 'Sin especificar'}</p>
                                        <p className="text-gray-600">Fecha: {expense.fecha_gasto}</p>
                                        <p className="text-gray-600">RFC: {expense.rfc || 'N/A'}</p>
                                    </div>
                                    <div>
                                        <p className={`${
                                            expense.estado_factura === 'pendiente' ? 'text-orange-600' :
                                            expense.estado_factura === 'no_requiere' ? 'text-gray-500' : 'text-green-600'
                                        }`}>
                                            Estado factura: {expense.estado_factura === 'pendiente' ? '⏳ Pendiente' :
                                                              expense.estado_factura === 'no_requiere' ? '➖ Sin factura' : '✅ Facturado'}
                                        </p>
                                        {expense.factura_id && (
                                            <p className="text-gray-600">Factura: {expense.factura_id}</p>
                                        )}
                                        <p className="text-gray-600">
                                            Asiento: {expense.asientos_contables?.numero_poliza || 'N/A'}
                                        </p>
                                    </div>
                                    <div>
                                        <p className="text-gray-600">CFDI requerido: {expense.will_have_cfdi ? 'Sí' : 'No'}</p>
                                        <p className="text-gray-600">Pagado por: {expense.paid_by === 'company_account' ? 'Empresa' : 'Empleado'}</p>
                                        <p className="text-gray-600">Forma de pago: {expense.forma_pago || 'N/A'}</p>
                                    </div>
                                </div>

                                {/* Criterios de completitud */}
                                <div className="mt-3 border-t border-gray-200 pt-3">
                                    <p className="text-sm font-medium text-gray-700 mb-2">Criterios de completitud:</p>
                                    <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
                                        {expense.completitud?.criterios && Object.entries(expense.completitud.criterios).map(([key, value]) => (
                                            <div key={key} className={`flex items-center gap-1 ${value ? 'text-green-600' : 'text-red-600'}`}>
                                                <span>{value ? '✅' : '❌'}</span>
                                                <span>{key.replace(/_/g, ' ')}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Botones de acción */}
                                <div className="flex gap-2 mt-3">
                                    <button
                                        onClick={() => setSelectedExpense(selectedExpense === expense.id ? null : expense.id)}
                                        className="px-3 py-1 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 transition-colors"
                                    >
                                        {selectedExpense === expense.id ? '🔼' : '🔽'} Ver Asientos Contables
                                    </button>
                                    {expense.estado_factura === 'pendiente' && (
                                        <button className="px-3 py-1 bg-orange-600 text-white text-sm rounded-lg hover:bg-orange-700 transition-colors">
                                            ⚡ Acelerar facturación
                                        </button>
                                    )}
                                </div>

                                {/* Asientos contables expandidos */}
                                {selectedExpense === expense.id && expense.asientos_contables && (
                                    <div className="mt-4 border-t border-gray-200 pt-4">
                                        <h5 className="font-medium text-gray-900 mb-3">📋 Asientos Contables</h5>
                                        <div className="bg-gray-50 rounded-lg p-4">
                                            <div className="grid grid-cols-2 gap-4 mb-3 text-sm">
                                                <div>
                                                    <p><strong>Póliza:</strong> {expense.asientos_contables.numero_poliza}</p>
                                                    <p><strong>Tipo:</strong> {expense.asientos_contables.tipo_poliza}</p>
                                                </div>
                                                <div>
                                                    <p><strong>Fecha:</strong> {expense.asientos_contables.fecha_asiento}</p>
                                                    <p><strong>Concepto:</strong> {expense.asientos_contables.concepto}</p>
                                                </div>
                                            </div>

                                            <div className="overflow-x-auto">
                                                <table className="w-full text-sm">
                                                    <thead className="bg-gray-100">
                                                        <tr>
                                                            <th className="text-left p-2">Cuenta</th>
                                                            <th className="text-left p-2">Nombre de Cuenta</th>
                                                            <th className="text-right p-2">Debe</th>
                                                            <th className="text-right p-2">Haber</th>
                                                            <th className="text-left p-2">Tipo</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {expense.asientos_contables.movimientos.map((mov, index) => (
                                                            <tr key={index} className="border-t border-gray-200">
                                                                <td className="p-2 font-mono">{mov.cuenta}</td>
                                                                <td className="p-2">{mov.nombre_cuenta}</td>
                                                                <td className="p-2 text-right font-mono">
                                                                    {parseFloat(mov.debe) > 0 ? `$${parseFloat(mov.debe).toLocaleString('es-MX', { minimumFractionDigits: 2 })}` : '-'}
                                                                </td>
                                                                <td className="p-2 text-right font-mono">
                                                                    {parseFloat(mov.haber) > 0 ? `$${parseFloat(mov.haber).toLocaleString('es-MX', { minimumFractionDigits: 2 })}` : '-'}
                                                                </td>
                                                                <td className="p-2">
                                                                    <span className={`px-2 py-1 rounded text-xs ${
                                                                        mov.tipo === 'gasto' ? 'bg-red-100 text-red-800' :
                                                                        mov.tipo === 'iva_acreditable' ? 'bg-blue-100 text-blue-800' :
                                                                        mov.tipo === 'pasivo' ? 'bg-orange-100 text-orange-800' :
                                                                        'bg-green-100 text-green-800'
                                                                    }`}>
                                                                        {mov.tipo}
                                                                    </span>
                                                                </td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                    <tfoot className="bg-gray-100 font-semibold">
                                                        <tr>
                                                            <td colSpan="2" className="p-2">TOTALES:</td>
                                                            <td className="p-2 text-right font-mono">
                                                                ${parseFloat(expense.asientos_contables.total_debe).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                                                            </td>
                                                            <td className="p-2 text-right font-mono">
                                                                ${parseFloat(expense.asientos_contables.total_haber).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                                                            </td>
                                                            <td className="p-2">
                                                                <span className={`px-2 py-1 rounded text-xs ${
                                                                    expense.asientos_contables.balanceado ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                                                                }`}>
                                                                    {expense.asientos_contables.balanceado ? '✅ Balanceado' : '❌ Desbalanceado'}
                                                                </span>
                                                            </td>
                                                        </tr>
                                                    </tfoot>
                                                </table>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))}

                        {filteredExpenses.length === 0 && (
                            <div className="text-center py-8 text-gray-500">
                                <i className="fas fa-search text-4xl mb-4"></i>
                                <p>No hay gastos que coincidan con el filtro seleccionado</p>
                            </div>
                        )}
                    </div>
                </div>
            );
        };

        // Componente del Modal de No Conciliación
        const NonReconciliationModal = ({ isOpen, onClose, expense, onSubmit, companyId = 'default' }) => {
            const [selectedReason, setSelectedReason] = useState('');
            const [customReason, setCustomReason] = useState('');
            const [notes, setNotes] = useState('');
            const [estimatedDate, setEstimatedDate] = useState('');
            const [reasons, setReasons] = useState([]);
            const [isLoading, setIsLoading] = useState(false);

            useEffect(() => {
                if (isOpen) {
                    fetchReasons();
                }
            }, [isOpen, companyId]);

            const fetchReasons = async () => {
                try {
                    const response = await fetch(`/expenses/non-reconciliation-reasons?company_id=${encodeURIComponent(companyId || 'default')}`);
                    const data = await response.json();
                    setReasons(data.reasons);
                } catch (error) {
                    console.error('Error fetching reasons:', error);
                }
            };

            const handleSubmit = async () => {
                if (!selectedReason) {
                    alert('Por favor selecciona un motivo');
                    return;
                }

                setIsLoading(true);

                const reasonText = selectedReason === 'other' ? customReason :
                    reasons.find(r => r.code === selectedReason)?.title || '';

                const data = {
                    expense_id: expense.id,
                    reason_code: selectedReason,
                    reason_text: reasonText,
                    notes: notes,
                    estimated_resolution_date: estimatedDate || null
                };

                try {
                    const response = await fetch(`/expenses/${expense.id}/mark-non-reconcilable`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(data)
                    });

                    const result = await response.json();

                    if (result.success) {
                        alert(`Gasto marcado como no conciliable: ${result.message}`);
                        onSubmit(result);
                        onClose();
                    } else {
                        alert(`Error: ${result.message}`);
                    }
                } catch (error) {
                    alert(`Error: ${error.message}`);
                } finally {
                    setIsLoading(false);
                }
            };

            const handleClose = () => {
                setSelectedReason('');
                setCustomReason('');
                setNotes('');
                setEstimatedDate('');
                onClose();
            };

            if (!isOpen || !expense) return null;

            const selectedReasonData = reasons.find(r => r.code === selectedReason);

            return (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
                        <div className="p-6 border-b border-gray-200">
                            <div className="flex items-center justify-between">
                                <div>
                                    <h2 className="text-xl font-bold text-gray-900">⚠️ Marcar como No Conciliable</h2>
                                    <p className="text-gray-600 mt-1">
                                        Gasto: {expense.descripcion} - {formatCurrency(expense.monto_total)}
                                    </p>
                                </div>
                                <button
                                    onClick={handleClose}
                                    className="text-gray-400 hover:text-gray-600"
                                >
                                    <i className="fas fa-times text-xl"></i>
                                </button>
                            </div>
                        </div>

                        <div className="p-6 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Motivo de no conciliación *
                                </label>
                                <select
                                    value={selectedReason}
                                    onChange={(e) => setSelectedReason(e.target.value)}
                                    className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                                >
                                    <option value="">Selecciona un motivo...</option>
                                    {reasons.map(reason => (
                                        <option key={reason.code} value={reason.code}>
                                            {reason.title} - {reason.description}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            {selectedReason === 'other' && (
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Especifica el motivo *
                                    </label>
                                    <input
                                        type="text"
                                        value={customReason}
                                        onChange={(e) => setCustomReason(e.target.value)}
                                        placeholder="Describe el motivo específico..."
                                        className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                                    />
                                </div>
                            )}

                            {selectedReasonData && (
                                <div className="bg-orange-50 border border-orange-200 rounded-lg p-3">
                                    <div className="flex items-start space-x-3">
                                        <div className="text-orange-600">
                                            <i className="fas fa-info-circle"></i>
                                        </div>
                                        <div>
                                            <p className="text-sm text-orange-800 font-medium">
                                                {selectedReasonData.description}
                                            </p>
                                            <p className="text-xs text-orange-600 mt-1">
                                                Tiempo típico de resolución: {selectedReasonData.typical_resolution_days} días
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            )}

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Notas adicionales
                                </label>
                                <textarea
                                    value={notes}
                                    onChange={(e) => setNotes(e.target.value)}
                                    placeholder="Detalles adicionales, acciones tomadas, etc..."
                                    rows="3"
                                    className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Fecha estimada de resolución
                                </label>
                                <input
                                    type="date"
                                    value={estimatedDate}
                                    onChange={(e) => setEstimatedDate(e.target.value)}
                                    className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                                    min={new Date().toISOString().split('T')[0]}
                                />
                            </div>
                        </div>

                        <div className="p-6 border-t border-gray-200 flex justify-end space-x-3">
                            <button
                                onClick={handleClose}
                                className="px-4 py-2 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                                disabled={isLoading}
                            >
                                Cancelar
                            </button>
                            <button
                                onClick={handleSubmit}
                                disabled={!selectedReason || isLoading || (selectedReason === 'other' && !customReason)}
                                className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                            >
                                {isLoading ? (
                                    <>
                                        <i className="fas fa-spinner fa-spin mr-2"></i>
                                        Procesando...
                                    </>
                                ) : (
                                    'Marcar como No Conciliable'
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            );
        };

        // Componente del Asistente Conversacional
        const ConversationalAssistantModal = ({ onClose }) => {
            const [messages, setMessages] = useState([
                {
                    id: 1,
                    type: 'assistant',
                    content: '¡Hola! 🤖 Soy tu asistente de gastos con IA. Puedo ayudarte a consultar información sobre tus gastos empresariales. ¿Qué te gustaría saber?',
                    timestamp: new Date()
                }
            ]);
            const [currentQuery, setCurrentQuery] = useState('');
            const [isProcessing, setIsProcessing] = useState(false);

            const exampleQueries = [
                "¿Cuánto gasté este mes?",
                "Mostrar gastos de combustible",
                "Breakdown por categorías",
                "Gastos de la semana pasada",
                "Gastos en Pemex",
                "Resumen general"
            ];

            const sendQuery = async () => {
                if (!currentQuery.trim() || isProcessing) return;

                const userMessage = {
                    id: Date.now(),
                    type: 'user',
                    content: currentQuery,
                    timestamp: new Date()
                };

                setMessages(prev => [...prev, userMessage]);
                setIsProcessing(true);

                try {
                    const response = await fetch('/expenses/query', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ query: currentQuery, company_id: resolvedCompanyId })
                    });

                    const result = await response.json();

                    const assistantMessage = {
                        id: Date.now() + 1,
                        type: 'assistant',
                        content: result.answer,
                        metadata: {
                            query_type: result.query_type,
                            confidence: result.confidence,
                            has_llm: result.has_llm,
                            sql_executed: result.sql_executed,
                            data: result.data
                        },
                        timestamp: new Date()
                    };

                    setMessages(prev => [...prev, assistantMessage]);
                } catch (error) {
                    const errorMessage = {
                        id: Date.now() + 1,
                        type: 'assistant',
                        content: `❌ Error procesando tu consulta: ${error.message}`,
                        timestamp: new Date()
                    };
                    setMessages(prev => [...prev, errorMessage]);
                }

                setCurrentQuery('');
                setIsProcessing(false);
            };

            const handleKeyPress = (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendQuery();
                }
            };

            const setExampleQuery = (query) => {
                setCurrentQuery(query);
            };

            return (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col">
                        {/* Header */}
                        <div className="p-6 border-b border-gray-200 flex-shrink-0">
                            <div className="flex items-center justify-between">
                                <div>
                                    <h2 className="text-xl font-bold text-gray-900">🤖 Asistente Conversacional IA</h2>
                                    <p className="text-gray-600 mt-1">Consulta información sobre tus gastos en lenguaje natural</p>
                                </div>
                                <button
                                    onClick={onClose}
                                    className="text-gray-400 hover:text-gray-600"
                                >
                                    <i className="fas fa-times text-xl"></i>
                                </button>
                            </div>
                        </div>

                        {/* Examples */}
                        <div className="p-4 bg-gray-50 border-b border-gray-200 flex-shrink-0">
                            <p className="text-sm text-gray-600 mb-3">Ejemplos de consultas:</p>
                            <div className="flex flex-wrap gap-2">
                                {exampleQueries.map((query, index) => (
                                    <button
                                        key={index}
                                        onClick={() => setExampleQuery(query)}
                                        className="px-3 py-1 bg-blue-100 text-blue-700 text-sm rounded-full hover:bg-blue-200 transition-colors"
                                    >
                                        {query}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Chat Messages */}
                        <div className="flex-1 overflow-y-auto p-6 space-y-4">
                            {messages.map((message) => (
                                <div
                                    key={message.id}
                                    className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                                >
                                    <div className={`max-w-[80%] p-4 rounded-lg ${
                                        message.type === 'user'
                                            ? 'bg-blue-600 text-white'
                                            : 'bg-gray-100 text-gray-900 border-l-4 border-pink-500'
                                    }`}>
                                        <div className="whitespace-pre-wrap">{message.content}</div>

                                        {message.metadata && (
                                            <div className="mt-3 pt-3 border-t border-gray-300 text-xs opacity-75">
                                                <div className="flex items-center gap-4 flex-wrap">
                                                    <span>📊 {message.metadata.query_type}</span>
                                                    <span>🎯 {(message.metadata.confidence * 100).toFixed(1)}%</span>
                                                    <span>🧠 {message.metadata.has_llm ? 'LLM' : 'Reglas'}</span>
                                                </div>

                                                {message.metadata.sql_executed && (
                                                    <div className="mt-2">
                                                        <code className="text-xs bg-gray-200 px-2 py-1 rounded">
                                                            {message.metadata.sql_executed}
                                                        </code>
                                                    </div>
                                                )}

                                                {message.metadata.data && Array.isArray(message.metadata.data) && message.metadata.data.length > 0 && (
                                                    <div className="mt-2 p-2 bg-green-50 rounded text-green-800">
                                                        <strong>📋 Datos encontrados: {message.metadata.data.length} resultados</strong>
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        <div className="text-xs opacity-50 mt-2">
                                            {message.timestamp.toLocaleTimeString()}
                                        </div>
                                    </div>
                                </div>
                            ))}

                            {isProcessing && (
                                <div className="flex justify-start">
                                    <div className="bg-gray-100 p-4 rounded-lg border-l-4 border-pink-500">
                                        <div className="flex items-center space-x-2">
                                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-pink-600"></div>
                                            <span>Procesando tu consulta...</span>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Input */}
                        <div className="p-4 border-t border-gray-200 flex-shrink-0">
                            <div className="flex gap-3">
                                <input
                                    type="text"
                                    value={currentQuery}
                                    onChange={(e) => setCurrentQuery(e.target.value)}
                                    onKeyPress={handleKeyPress}
                                    placeholder="Escribe tu consulta aquí..."
                                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                                    disabled={isProcessing}
                                />
                                <button
                                    onClick={sendQuery}
                                    disabled={!currentQuery.trim() || isProcessing}
                                    className="px-6 py-2 bg-pink-600 text-white rounded-lg hover:bg-pink-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                                >
                                    {isProcessing ? (
                                        <i className="fas fa-spinner fa-spin"></i>
                                    ) : (
                                        <i className="fas fa-paper-plane"></i>
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            );
        };

        // Componente principal del registro de gastos
        const ExpenseRegistration = () => {
            // Estados principales
            const [formData, setFormData] = useState({});
            const [transcript, setTranscript] = useState('');
            const [isRecording, setIsRecording] = useState(false);
            const [currentSummary, setCurrentSummary] = useState('');
            const [summaryConfidence, setSummaryConfidence] = useState(0);
            const [inputMode, setInputMode] = useState('voice'); // 'voice', 'ocr', 'text'
            const [audioLevel, setAudioLevel] = useState(0);
            const [isUploading, setIsUploading] = useState(false);
            const [ocrResult, setOcrResult] = useState(null);
            const [invoiceParsing, setInvoiceParsing] = useState({ status: 'idle' });

            // Estados del sistema simplificado
            const [showExpensesDashboard, setShowExpensesDashboard] = useState(false);
            const [expensesData, setExpensesData] = useState([]);
            const [demoMode, setDemoMode] = useState(() => {
                try {
                    return localStorage.getItem('mcp_demo_mode') === 'true';
                } catch (error) {
                    return false;
                }
            });
            const [companyId, setCompanyId] = useState(() => {
                try {
                    return localStorage.getItem('mcp_company_id') || 'default';
                } catch (error) {
                    console.warn('No se pudo leer company_id de localStorage:', error);
                    return 'default';
                }
            });
            const resolvedCompanyId = companyId || 'default';
            const [activeMission, setActiveMission] = useState(() => {
                try {
                    const params = new URLSearchParams(window.location.search);
                    return params.get('mission') || localStorage.getItem('mcp_active_mission') || null;
                } catch (error) {
                    return localStorage.getItem('mcp_active_mission') || null;
                }
            });
            const [completedMissions, setCompletedMissions] = useState(() => {
                try {
                    const raw = localStorage.getItem('mcp_completed_missions');
                    const parsed = raw ? JSON.parse(raw) : [];
                    return Array.isArray(parsed) ? parsed.map(String) : [];
                } catch (error) {
                    return [];
                }
            });
            const [showNavigationDrawer, setShowNavigationDrawer] = useState(false);

            const getLocalExpensesMap = () => {
                try {
                    const raw = localStorage.getItem('expensesData');
                    if (!raw) {
                        return {};
                    }
                    const parsed = JSON.parse(raw);
                    if (Array.isArray(parsed)) {
                        return { default: parsed };
                    }
                    return parsed && typeof parsed === 'object' ? parsed : {};
                } catch (error) {
                    console.warn('No se pudo leer expensesData de localStorage:', error);
                    return {};
                }
            };

            const loadLocalExpenses = useCallback(() => {
                const map = getLocalExpensesMap();
                const list = map[resolvedCompanyId];
                return Array.isArray(list) ? list : [];
            }, [resolvedCompanyId]);

            const saveLocalExpenses = useCallback((list) => {
                const map = getLocalExpensesMap();
                map[resolvedCompanyId] = list;
                localStorage.setItem('expensesData', JSON.stringify(map));
            }, [resolvedCompanyId]);

            const clearLocalExpenses = useCallback(() => {
                const map = getLocalExpensesMap();
                if (map[resolvedCompanyId]) {
                    delete map[resolvedCompanyId];
                    localStorage.setItem('expensesData', JSON.stringify(map));
                }
            }, [resolvedCompanyId]);

            const syncDemoMode = useCallback((value) => {
                setDemoMode(value);
                try {
                    localStorage.setItem('mcp_demo_mode', value ? 'true' : 'false');
                } catch (error) {
                    console.warn('No se pudo actualizar mcp_demo_mode:', error);
                }
            }, []);

            const handleCompanyChange = useCallback((value, options = {}) => {
                const { closeDrawer = false } = options;
                if (value === '__new__') {
                    const manual = prompt('Introduce el identificador de la empresa (company_id):', '');
                    if (manual && manual.trim()) {
                        setCompanyId(manual.trim());
                        if (closeDrawer) {
                            setShowNavigationDrawer(false);
                        }
                    }
                    return;
                }
                setCompanyId((value || 'default'));
                if (closeDrawer) {
                    setShowNavigationDrawer(false);
                }
            }, [setCompanyId, setShowNavigationDrawer]);

            const missionDetails = MISSION_DETAILS;

            const handleMissionAction = (missionKey) => {
                const mission = missionDetails[String(missionKey)];
                if (!mission) {
                    return;
                }
                switch (mission.action) {
                    case 'capture':
                        setInputMode('voice');
                        document.getElementById('capture-mode-section')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        break;
                    case 'pendingInvoices':
                        setShowPendingInvoices(true);
                        break;
                    case 'bank':
                        setShowBankReconciliation(true);
                        break;
                    case 'dashboard':
                        setShowExpensesDashboard(true);
                        break;
                    default:
                        break;
                }
            };

            const markMissionComplete = (missionKey) => {
                const id = String(missionKey);
                if (!completedMissions.includes(id)) {
                    setCompletedMissions([...completedMissions, id]);
                }
            };

            const goToMission = (missionKey) => {
                if (missionKey) {
                    setActiveMission(String(missionKey));
                } else {
                    setActiveMission(null);
                }
                window.scrollTo({ top: 0, behavior: 'smooth' });
            };

            const handleQuickFillDemo = useCallback(() => {
                const today = new Date().toISOString().split('T')[0];
                setTranscript('Compra demo: gasolina corporativa de 845.32 pesos en Pemex con tarjeta de empresa.');
                handleFieldChange('descripcion', 'Carga demo de combustible corporativo');
                handleFieldChange('monto_total', 845.32);
                handleFieldChange('fecha_gasto', today);
                handleFieldChange('proveedor.nombre', 'Gasolinera Pemex Demo');
                handleFieldChange('categoria', 'combustible');
                handleFieldChange('forma_pago', 'tarjeta_empresa');
                handleFieldChange('will_have_cfdi', true);
                handleFieldChange('paid_by', 'company_account');
                handleFieldChange('notas', 'Gasto demo generado desde el onboarding.');
            }, [handleFieldChange]);

            const buildExpenseData = useCallback(() => {
                const proveedorNombre = getFieldValue('proveedor.nombre');
                const provider = proveedorNombre ? { nombre: proveedorNombre } : null;
                return {
                    descripcion: getFieldValue('descripcion') || 'Gasto demo',
                    monto_total: getFieldValue('monto_total') || 0,
                    fecha_gasto: getFieldValue('fecha_gasto'),
                    categoria: getFieldValue('categoria'),
                    proveedor: provider,
                    rfc: getFieldValue('rfc'),
                    forma_pago: getFieldValue('forma_pago'),
                    will_have_cfdi: getFieldValue('will_have_cfdi'),
                    paid_by: getFieldValue('paid_by'),
                    company_id: resolvedCompanyId,
                    notas: getFieldValue('notas'),
                    ticket_file: getFieldValue('ticket_file'),
                    xml_file: getFieldValue('xml_file'),
                    pdf_file: getFieldValue('pdf_file'),
                    tax_info: formData.tax_info || null,
                    factura_uuid: formData.factura_uuid || null,
                    movimientos_bancarios: formData.movimientos_bancarios || [],
                    metadata: formData.metadata || {},
                    workflow_status: formData.workflow_status,
                    estado_factura: formData.estado_factura,
                    estado_conciliacion: formData.estado_conciliacion,
                };
            }, [formData, getFieldValue, resolvedCompanyId]);

            useEffect(() => {
                try {
                    localStorage.setItem('mcp_company_id', resolvedCompanyId);
                } catch (error) {
                    console.warn('No se pudo persistir company_id:', error);
                }
            }, [resolvedCompanyId]);

            const knownCompanies = useMemo(() => {
                const identifiers = new Set([resolvedCompanyId]);
                expensesData.forEach(expense => {
                    if (expense?.company_id) {
                        identifiers.add(expense.company_id);
                    }
                });
                return Array.from(identifiers);
            }, [expensesData, resolvedCompanyId]);

            useEffect(() => {
                setExpensesData([]);
                syncDemoMode(false);
            }, [resolvedCompanyId, syncDemoMode]);

            useEffect(() => {
                try {
                    const event = new CustomEvent('mcp-company-change', {
                        detail: { companyId: resolvedCompanyId },
                    });
                    window.dispatchEvent(event);
                } catch (error) {
                    console.warn('No se pudo notificar cambio de empresa:', error);
                }
            }, [resolvedCompanyId]);

            useEffect(() => {
                try {
                    const params = new URLSearchParams(window.location.search);
                    if (params.has('mission')) {
                        params.delete('mission');
                        const newUrl = window.location.pathname + (params.toString() ? `?${params.toString()}` : '') + window.location.hash;
                        window.history.replaceState({}, '', newUrl);
                    }
                } catch (error) {
                    console.warn('No se pudo limpiar parámetro de misión:', error);
                }
            }, []);

            const formatHeaderLabel = useCallback((value, fallback = 'ContaFlow') => {
                if (!value) return fallback;
                let working = value.trim();
                if (!working || working === 'default') return fallback;
                working = working.replace(/[._-]+/g, ' ');
                const shouldTitleCase = working === working.toLowerCase() || working === working.toUpperCase();
                if (shouldTitleCase) {
                    return working.replace(/\b\w/g, (char) => char.toUpperCase()).trim();
                }
                return working.trim();
            }, []);

            const refreshHeaderContext = useCallback(() => {
                try {
                    let label = formatHeaderLabel(resolvedCompanyId, '');

                    if (!label || label === 'ContaFlow') {
                        const storedLabel = localStorage.getItem('mcp_company_label');
                        if (storedLabel) {
                            label = formatHeaderLabel(storedLabel, label || 'ContaFlow');
                        }
                    }

                    if ((!label || label === 'ContaFlow') && resolvedCompanyId === 'default') {
                        const tenantData = localStorage.getItem('tenant_data');
                        if (tenantData) {
                            try {
                                const tenant = JSON.parse(tenantData);
                                if (tenant?.name) {
                                    label = formatHeaderLabel(tenant.name, label || 'ContaFlow');
                                }
                            } catch (error) {
                                console.warn('No se pudo interpretar tenant_data para header:', error);
                            }
                        }
                    }

                    setHeaderCompany(label || 'ContaFlow');

                    let resolvedUser = 'Usuario demo';
                    const userData = localStorage.getItem('user_data');
                    if (userData) {
                        try {
                            const user = JSON.parse(userData);
                            if (user?.full_name) {
                                resolvedUser = user.full_name;
                            } else if (user?.name) {
                                resolvedUser = user.name;
                            } else if (user?.username) {
                                resolvedUser = formatHeaderLabel(user.username, resolvedUser);
                            } else if (user?.email) {
                                const [localPart] = user.email.split('@');
                                resolvedUser = formatHeaderLabel(localPart, resolvedUser);
                            }
                        } catch (error) {
                            console.warn('No se pudo interpretar user_data para header:', error);
                        }
                    } else {
                        const email = localStorage.getItem('mcp_user_email');
                        if (email) {
                            const [localPart] = email.split('@');
                            resolvedUser = formatHeaderLabel(localPart, resolvedUser);
                        }
                    }
                    setHeaderUser(resolvedUser);
                } catch (error) {
                    console.warn('No se pudo refrescar información del header:', error);
                }
            }, [formatHeaderLabel, resolvedCompanyId]);

            useEffect(() => {
                refreshHeaderContext();
            }, [refreshHeaderContext]);

            useEffect(() => {
                const handler = () => {
                    try {
                        const demoFlag = localStorage.getItem('mcp_demo_mode') === 'true';
                        setDemoMode(demoFlag);
                        const active = localStorage.getItem('mcp_active_mission');
                        setActiveMission(active || null);
                        const completedRaw = localStorage.getItem('mcp_completed_missions');
                        const parsed = completedRaw ? JSON.parse(completedRaw) : [];
                        if (Array.isArray(parsed)) {
                            setCompletedMissions(parsed.map(String));
                        }
                        refreshHeaderContext();
                    } catch (error) {
                        console.warn('No se pudo sincronizar estado del demo:', error);
                    }
                };
                window.addEventListener('storage', handler);
                window.addEventListener('mcp-company-change', handler);
                return () => {
                    window.removeEventListener('storage', handler);
                    window.removeEventListener('mcp-company-change', handler);
                };
            }, [refreshHeaderContext]);

            useEffect(() => {
                try {
                    if (activeMission) {
                        localStorage.setItem('mcp_active_mission', activeMission);
                    } else {
                        localStorage.removeItem('mcp_active_mission');
                    }
                } catch (error) {
                    console.warn('No se pudo guardar misión activa:', error);
                }
            }, [activeMission]);

            useEffect(() => {
                try {
                    const unique = Array.from(new Set(completedMissions.map(String)));
                    localStorage.setItem('mcp_completed_missions', JSON.stringify(unique));
                } catch (error) {
                    console.warn('No se pudo guardar misiones completadas:', error);
                }
            }, [completedMissions]);
            const [selectedMonth, setSelectedMonth] = useState(new Date().toISOString().slice(0, 7));
            const [selectedCategoryFilter, setSelectedCategoryFilter] = useState('todos');
            const [showPendingInvoices, setShowPendingInvoices] = useState(false);
            const [showInvoiceUpload, setShowInvoiceUpload] = useState(false);
            const [showReconciliation, setShowReconciliation] = useState(false);
            const [showBankReconciliation, setShowBankReconciliation] = useState(false);
            const [showCompletenessView, setShowCompletenessView] = useState(false);
            const [showConversationalAssistant, setShowConversationalAssistant] = useState(false);
            const [showNonReconciliationModal, setShowNonReconciliationModal] = useState(false);
            const [selectedExpenseForNonReconciliation, setSelectedExpenseForNonReconciliation] = useState(null);
            const [moreActionsOpen, setMoreActionsOpen] = useState(false);
            const [quickViewExpense, setQuickViewExpense] = useState(null);
            const [headerUser, setHeaderUser] = useState('Usuario demo');
            const [headerCompany, setHeaderCompany] = useState(() => {
                if (resolvedCompanyId && resolvedCompanyId !== 'default') {
                    return resolvedCompanyId;
                }
                try {
                    const tenantData = localStorage.getItem('tenant_data');
                    if (tenantData) {
                        const tenant = JSON.parse(tenantData);
                        if (tenant?.name) {
                            return tenant.name;
                        }
                    }
                } catch (error) {
                    console.warn('No se pudo inicializar headerCompany desde tenant_data:', error);
                }
                return 'ContaFlow';
            });

            // Estados de operaciones
            const [isSaving, setIsSaving] = useState(false);
            const [isSending, setIsSending] = useState(false);
            const [isCheckingDuplicates, setIsCheckingDuplicates] = useState(false);
            const [isPredictingCategory, setIsPredictingCategory] = useState(false);
            const [categoryPrediction, setCategoryPrediction] = useState(null);
            const [lastSaveTime, setLastSaveTime] = useState(null);
            const navItems = useMemo(() => ([
                {
                    label: 'Gastos',
                    href: '/voice-expenses',
                    icon: 'fa-microphone',
                    matches: ['/voice-expenses'],
                },
                {
                    label: 'Facturación & Tickets',
                    href: '/advanced-ticket-dashboard.html',
                    icon: 'fa-receipt',
                    matches: ['/advanced-ticket-dashboard'],
                },
                {
                    label: 'Cuentas de Banco y Efectivo',
                    href: '/payment-accounts',
                    icon: 'fa-wallet',
                    matches: ['/payment-accounts'],
                },
                {
                    label: 'Conciliación Bancaria',
                    href: '/bank-reconciliation',
                    icon: 'fa-balance-scale',
                    matches: ['/bank-reconciliation'],
                },
                {
                    label: 'Configuración de la cuenta',
                    href: '/client-settings',
                    icon: 'fa-sliders-h',
                    matches: ['/client-settings'],
                },
            ]), []);

            const normalizeExpense = useCallback((expense) => {
                const hasInvoice = !!expense.factura_id;
                const willHaveCfdi = expense.will_have_cfdi !== undefined ? expense.will_have_cfdi : hasInvoice;

                const rawInvoiceStatus = expense.estado_factura || expense.invoice_status || expense.invoiceStatus;
                const estadoFactura = normalizeInvoiceStatusValue(rawInvoiceStatus, willHaveCfdi);

                const movimientosBancarios = expense.movimientos_bancarios || (expense.movimiento_bancario ? [expense.movimiento_bancario] : []);
                const companyFromRecord = expense.company_id || resolvedCompanyId;

                const rawBankStatus = expense.estado_conciliacion || expense.bank_status;
                const estadoConciliacion = normalizeBankStatusValue(rawBankStatus, estadoFactura, movimientosBancarios.length > 0);

                let workflowStatus = 'capturado';
                if (estadoFactura === 'facturado') {
                    workflowStatus = estadoConciliacion === 'conciliado_banco' ? 'conciliado_banco' : 'facturado';
                } else if (estadoFactura === 'sin_factura') {
                    workflowStatus = 'cerrado_sin_factura';
                } else {
                    workflowStatus = 'pendiente_factura';
                }

                const taxInfo = expense.tax_info || expense.tax_breakdown || null;
                const invoiceMeta = getInvoiceStatusMeta(estadoFactura);
                const bankMeta = getBankStatusMeta(estadoConciliacion);

                const normalized = {
                    ...expense,
                    company_id: companyFromRecord,
                    will_have_cfdi: willHaveCfdi,
                    estado_factura: estadoFactura,
                    estado_factura_original: rawInvoiceStatus || null,
                    factura_url: hasInvoice ? (expense.factura_url || `https://erp.tuempresa.com/facturas/${expense.factura_id}`) : null,
                    estado_conciliacion: estadoConciliacion,
                    estado_conciliacion_original: rawBankStatus || null,
                    movimientos_bancarios: movimientosBancarios,
                    movimiento_bancario: movimientosBancarios[0] || null,
                    tax_info: taxInfo,
                    workflow_status: workflowStatus,
                    flujo_cerrado: workflowStatus !== 'pendiente_factura',
                    invoice_status_meta: invoiceMeta,
                    bank_status_meta: bankMeta,
                    invoice_stage_index: invoiceMeta.stageIndex,
                };

                normalized.asientos_contables = generateAccountingEntries(normalized);

                return normalized;
            }, [resolvedCompanyId]);

            const updateExpense = useCallback(async (expenseId, updatesProducer) => {
                try {
                    // Encontrar el gasto actual para preparar la actualización
                    const currentExpense = expensesData.find(expense => expense.id == expenseId);
                    if (!currentExpense) {
                        console.error('Gasto no encontrado para actualizar:', expenseId);
                        return;
                    }

                    const updates = typeof updatesProducer === 'function' ? updatesProducer(currentExpense) : updatesProducer;
                    const updatedExpenseData = { ...currentExpense, ...updates };

                    // Preparar datos para el backend
                    const backendExpense = {
                        descripcion: updatedExpenseData.descripcion || 'Gasto sin descripción',
                        monto_total: updatedExpenseData.monto_total || 0,
                        fecha_gasto: updatedExpenseData.fecha_gasto,
                        categoria: updatedExpenseData.categoria,
                        proveedor: updatedExpenseData.proveedor,
                        rfc: updatedExpenseData.rfc,
                        tax_info: updatedExpenseData.tax_info,
                        asientos_contables: updatedExpenseData.asientos_contables,
                        workflow_status: updatedExpenseData.workflow_status || 'draft',
                        estado_factura: updatedExpenseData.estado_factura || 'pendiente',
                        estado_conciliacion: updatedExpenseData.estado_conciliacion || 'pendiente',
                        forma_pago: updatedExpenseData.forma_pago,
                        paid_by: updatedExpenseData.paid_by || 'company_account',
                        will_have_cfdi: updatedExpenseData.will_have_cfdi !== false,
                        movimientos_bancarios: updatedExpenseData.movimientos_bancarios,
                        company_id: updatedExpenseData.company_id || resolvedCompanyId,
                        metadata: updatedExpenseData.metadata || {}
                    };

                    // Intentar actualizar en el backend
                    const response = await fetch(`/expenses/${expenseId}`, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(backendExpense)
                    });

                    if (response.ok) {
                        const updatedExpense = await response.json();
                        const normalizedExpense = normalizeExpense(updatedExpense);

                        // Actualizar estado local
                        setExpensesData(prevExpenses => {
                            const nextExpenses = prevExpenses.map(expense => {
                                if (expense.id == expenseId) {
                                    return normalizedExpense;
                                }
                                return expense;
                            });
                            saveLocalExpenses(nextExpenses);
                            return nextExpenses;
                        });

                        console.log('✅ Gasto actualizado en backend:', normalizedExpense);
                    } else {
                        throw new Error(`Error del servidor: ${response.status}`);
                    }

                } catch (error) {
                    console.error('Error actualizando gasto en backend:', error);

                    // Fallback a localStorage
                    setExpensesData(prevExpenses => {
                        const nextExpenses = prevExpenses.map(expense => {
                            if (expense.id != expenseId) {
                                return expense;
                            }
                            const updates = typeof updatesProducer === 'function' ? updatesProducer(expense) : updatesProducer;
                            return normalizeExpense({ ...expense, ...updates });
                        });
                        saveLocalExpenses(nextExpenses);
                        return nextExpenses;
                    });

                    console.warn('⚠️ Gasto actualizado en localStorage (fallback)');
                }
            }, [expensesData, setExpensesData, normalizeExpense, resolvedCompanyId, saveLocalExpenses]);

            const registerInvoiceForExpense = useCallback(
                async (expenseId, payload) => {
                    const response = await fetch(`/expenses/${expenseId}/invoice`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(payload),
                    });

                    if (!response.ok) {
                        const message = await response.text();
                        throw new Error(message || `Error del servidor: ${response.status}`);
                    }

                    const updatedExpense = await response.json();
                    const normalizedExpense = normalizeExpense(updatedExpense);

                    setExpensesData(prevExpenses => {
                        const nextExpenses = prevExpenses.map(expense => (
                            expense.id === expenseId ? normalizedExpense : expense
                        ));
                        saveLocalExpenses(nextExpenses);
                        return nextExpenses;
                    });

                    if (demoMode) {
                        markMissionComplete('2');
                        if (activeMission === '2') {
                            goToMission('3');
                        }
                    }

                    return normalizedExpense;
                },
                [normalizeExpense, setExpensesData, saveLocalExpenses, demoMode, activeMission],
            );

            const markExpenseAsInvoiced = useCallback(
                async (expenseId) => {
                    const response = await fetch(`/expenses/${expenseId}/mark-invoiced`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ actor: 'ui' }),
                    });

                    if (!response.ok) {
                        const message = await response.text();
                        throw new Error(message || `Error del servidor: ${response.status}`);
                    }

                    const updatedExpense = await response.json();
                    const normalizedExpense = normalizeExpense(updatedExpense);

                    setExpensesData(prevExpenses => {
                        const nextExpenses = prevExpenses.map(expense => (
                            expense.id === expenseId ? normalizedExpense : expense
                        ));
                        saveLocalExpenses(nextExpenses);
                        return nextExpenses;
                    });

                    if (demoMode) {
                        markMissionComplete('2');
                        if (activeMission === '2') {
                            goToMission('3');
                        }
                    }

                    return normalizedExpense;
                },
                [normalizeExpense, setExpensesData, saveLocalExpenses, demoMode, activeMission],
            );

            const closeExpenseWithoutInvoice = useCallback(
                async (expenseId) => {
                    const response = await fetch(`/expenses/${expenseId}/close-no-invoice`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ actor: 'ui' }),
                    });

                    if (!response.ok) {
                        const message = await response.text();
                        throw new Error(message || `Error del servidor: ${response.status}`);
                    }

                    const updatedExpense = await response.json();
                    const normalizedExpense = normalizeExpense(updatedExpense);

                    setExpensesData(prevExpenses => {
                        const nextExpenses = prevExpenses.map(expense => (
                            expense.id === expenseId ? normalizedExpense : expense
                        ));
                        saveLocalExpenses(nextExpenses);
                        return nextExpenses;
                    });

                    return normalizedExpense;
                },
                [normalizeExpense, setExpensesData, saveLocalExpenses],
            );

            // Referencias para Web Speech API
            const recognitionRef = useRef(null);
            const audioContextRef = useRef(null);
            const analyserRef = useRef(null);
            const microphoneRef = useRef(null);
            const animationFrameRef = useRef(null);

            // Configuración de campos de ejemplo
            const EXPENSE_FIELDS = {
                'descripcion': {
                    name: 'Descripción',
                    type: 'text',
                    required: true,
                    placeholder: 'Describe el gasto...',
                    help: 'Descripción breve del gasto realizado'
                },
                'monto_total': {
                    name: 'Monto Total',
                    type: 'number',
                    required: true,
                    placeholder: '0.00',
                    help: 'Monto total del gasto en pesos mexicanos'
                },
                'fecha_gasto': {
                    name: 'Fecha del Gasto',
                    type: 'date',
                    required: true,
                    help: 'Fecha en que se realizó el gasto'
                },
                'proveedor.nombre': {
                    name: 'Proveedor',
                    type: 'text',
                    required: true,
                    placeholder: 'Nombre del proveedor...',
                    help: 'Nombre de la empresa o establecimiento'
                },
                'categoria': {
                    name: 'Categoría',
                    type: 'select',
                    required: false,
                    options: [
                        { value: 'combustible', label: '⛽ Combustible' },
                        { value: 'alimentos', label: '🍽️ Alimentos y Bebidas' },
                        { value: 'transporte', label: '🚗 Transporte' },
                        { value: 'hospedaje', label: '🏨 Hospedaje' },
                        { value: 'oficina', label: '📋 Material de Oficina' },
                        { value: 'tecnologia', label: '💻 Tecnología' },
                        { value: 'marketing', label: '📢 Marketing' },
                        { value: 'capacitacion', label: '🎓 Capacitación' },
                        { value: 'salud', label: '🏥 Salud' },
                        { value: 'otros', label: '📦 Otros Gastos' }
                    ],
                    help: 'Categoría del gasto (detectada automáticamente por IA)'
                },
                'forma_pago': {
                    name: 'Forma de Pago',
                    type: 'select',
                    required: true,
                    options: [
                        { value: 'efectivo', label: 'Efectivo' },
                        { value: 'tarjeta_empresa', label: 'Tarjeta de empresa' },
                        { value: 'tarjeta_empleado', label: 'Tarjeta del empleado' },
                        { value: 'transferencia', label: 'Transferencia' },
                        { value: 'spei', label: 'SPEI' },
                        { value: 'pago_digital', label: 'Pago Digital' }
                    ],
                    help: 'Método de pago utilizado (detectado automáticamente del ticket)'
                },
                'will_have_cfdi': {
                    name: '¿Se va a facturar?',
                    type: 'select',
                    required: true,
                    options: [
                        { value: true, label: 'Sí, habrá factura (CFDI)' },
                        { value: false, label: 'No, sin factura' }
                    ],
                    help: 'Indica si este gasto generará una factura CFDI'
                },
                'paid_by': {
                    name: '¿Quién pagó?',
                    type: 'select',
                    required: true,
                    options: [
                        { value: 'company_account', label: 'Empresa (tarjeta corporativa)' },
                        { value: 'own_account', label: 'Empleado (reembolso)' }
                    ],
                    help: 'Indica si pagó la empresa o el empleado'
                },
                'rfc': {
                    name: 'RFC del Proveedor',
                    type: 'text',
                    required: false,
                    placeholder: 'ABC123456DEF',
                    help: 'RFC necesario cuando se va a facturar'
                },
                'notas': {
                    name: 'Notas Adicionales',
                    type: 'textarea',
                    required: false,
                    placeholder: 'Información adicional del gasto...',
                    help: 'Cualquier información adicional relevante'
                }
            };

            // Función para obtener valor de campo
            const getFieldValue = (path) => {
                // Primero intenta obtener el valor directo con la clave completa
                if (formData[path] !== undefined) {
                    return formData[path];
                }
                // Si no existe, intenta navegar por la ruta anidada (compatibilidad hacia atrás)
                return path.split('.').reduce((current, key) => current?.[key], formData);
            };

            // Función para obtener confianza del campo
            const getFieldConfidence = (fieldKey) => {
                return formData._confidence?.[fieldKey] || 0;
            };

            // Categorías disponibles (simplificadas)
            const CATEGORIAS_DISPONIBLES = [
                { value: 'combustible', label: '⛽ Combustible', color: 'bg-red-100 text-red-800' },
                { value: 'alimentos', label: '🍽️ Alimentos y Bebidas', color: 'bg-orange-100 text-orange-800' },
                { value: 'transporte', label: '🚗 Transporte', color: 'bg-blue-100 text-blue-800' },
                { value: 'hospedaje', label: '🏨 Hospedaje', color: 'bg-purple-100 text-purple-800' },
                { value: 'oficina', label: '📋 Material de Oficina', color: 'bg-gray-100 text-gray-800' },
                { value: 'tecnologia', label: '💻 Tecnología', color: 'bg-indigo-100 text-indigo-800' },
                { value: 'marketing', label: '📢 Marketing', color: 'bg-pink-100 text-pink-800' },
                { value: 'capacitacion', label: '🎓 Capacitación', color: 'bg-green-100 text-green-800' },
                { value: 'salud', label: '🏥 Salud', color: 'bg-teal-100 text-teal-800' },
                { value: 'otros', label: '📦 Otros Gastos', color: 'bg-yellow-100 text-yellow-800' }
            ];

            // Función para obtener información de categoría
            const getCategoryInfo = (categoryValue) => {
                return CATEGORIAS_DISPONIBLES.find(cat => cat.value === categoryValue) || CATEGORIAS_DISPONIBLES[9];
            };

            // Parseador mejorado de gastos
            const parseGasto = (transcript) => {
                const fields = {};
                const confidence = {};
                let summary = '';

                const text = transcript.toLowerCase().trim();

                // Extraer monto con múltiples patrones
                const montoPatterns = [
                    /(\d+(?:[.,]\d+)?)\s*(?:mil\s*)?(?:pesos?|peso|mx|mxn|\$)/i,
                    /\$\s*(\d+(?:[.,]\d+)?)/i,
                    /(?:de|por|cuesta|vale)\s+(\d+(?:[.,]\d+)?)\s*(?:pesos?|peso)?/i
                ];

                for (const pattern of montoPatterns) {
                    const match = transcript.match(pattern);
                    if (match) {
                        let amount = parseFloat(match[1].replace(',', '.'));

                        // Detectar "mil pesos"
                        if (transcript.toLowerCase().includes('mil')) {
                            amount = amount * 1000;
                        }

                        fields.monto_total = amount;
                        confidence.monto_total = 0.85;
                        break;
                    }
                }

                // Extraer proveedores conocidos
                const proveedores = ['pemex', 'oxxo', 'walmart', 'home depot', 'soriana', 'costco', 'liverpool'];
                for (const proveedor of proveedores) {
                    if (text.includes(proveedor)) {
                        fields['proveedor.nombre'] = proveedor.charAt(0).toUpperCase() + proveedor.slice(1);
                        confidence['proveedor.nombre'] = 0.9;
                        break;
                    }
                }

                // Extraer categorías
                const categorias = {
                    'gasolina': 'transporte',
                    'combustible': 'transporte',
                    'taxi': 'transporte',
                    'uber': 'transporte',
                    'comida': 'alimentacion',
                    'comidas': 'alimentacion',
                    'almuerzo': 'alimentacion',
                    'cena': 'alimentacion',
                    'desayuno': 'alimentacion',
                    'restaurante': 'alimentacion',
                    'papelería': 'oficina',
                    'papel': 'oficina',
                    'lapiceros': 'oficina',
                    'plumas': 'oficina',
                    'oficina': 'oficina',
                    'limpieza': 'mantenimiento',
                    'mantenimiento': 'mantenimiento',
                    'reparación': 'mantenimiento'
                };

                for (const [palabra, categoria] of Object.entries(categorias)) {
                    if (text.includes(palabra)) {
                        fields.categoria = categoria;
                        confidence.categoria = 0.7;
                        break;
                    }
                }

                // Forma de pago
                if (text.includes('efectivo')) {
                    fields.forma_pago = 'efectivo';
                    confidence.forma_pago = 0.8;
                } else if (text.includes('tarjeta empresa') || text.includes('tarjeta de la empresa')) {
                    fields.forma_pago = 'tarjeta_empresa';
                    confidence.forma_pago = 0.8;
                } else if (text.includes('tarjeta empleado') || text.includes('tarjeta del empleado')) {
                    fields.forma_pago = 'tarjeta_empleado';
                    confidence.forma_pago = 0.8;
                }

                // Descripción inteligente
                if (transcript.length > 0) {
                    // Limpiar y crear descripción
                    let descripcion = transcript.trim();

                    // Remover palabras de comando
                    descripcion = descripcion.replace(/^(registrar|crear|gasto|de|un|el|la)\s+/i, '');

                    fields.descripcion = descripcion;
                    confidence.descripcion = 0.7;

                    summary = `Gasto detectado: ${descripcion.substring(0, 60)}${descripcion.length > 60 ? '...' : ''}`;
                }

                // Fecha actual por defecto
                fields.fecha_gasto = new Date().toISOString().split('T')[0];
                confidence.fecha_gasto = 1.0;

                // Calcular confianza general
                const confidenceValues = Object.values(confidence);
                const overallConfidence = confidenceValues.length > 0
                    ? confidenceValues.reduce((a, b) => a + b, 0) / confidenceValues.length
                    : 0;

                return {
                    fields,
                    confidence,
                    summary: summary || 'Procesando gasto...',
                    overallConfidence
                };
            };

            // Manejar cambios de campo
            const handleFieldChange = useCallback((fieldKey, value) => {
                setFormData(prevData => {
                    const newData = { ...prevData };

                    // Almacenar el valor usando la clave completa (sin anidar)
                    // Esto mantiene consistencia con cómo el parser almacena los datos
                    newData[fieldKey] = value;

                    // Marcar como editado manualmente
                    if (!newData._manualEdits) {
                        newData._manualEdits = {};
                    }
                    newData._manualEdits[fieldKey] = true;

                    return newData;
                });
            }, []);

            const parseInvoiceXml = useCallback(async (file) => {
                if (!file) return;
                setInvoiceParsing({ status: 'loading', filename: file.name });

                const formDataXml = new FormData();
                formDataXml.append('file', file);

                try {
                    const response = await fetch('/invoices/parse', {
                        method: 'POST',
                        body: formDataXml,
                    });

                    if (!response.ok) {
                        const errorText = await response.text();
                        throw new Error(errorText || 'No se pudo analizar el XML');
                    }

                    const data = await response.json();
                    setInvoiceParsing({ status: 'success', filename: file.name, data });

                    setFormData(prev => ({
                        ...prev,
                        tax_info: data,
                        factura_uuid: data.uuid || prev.factura_uuid,
                        factura_rfc_emisor: data.emitter?.Rfc || prev.factura_rfc_emisor,
                    }));

                    if (!getFieldValue('monto_total') && data.total) {
                        handleFieldChange('monto_total', data.total);
                    }

                    if (!getFieldValue('rfc') && data.emitter?.Rfc) {
                        handleFieldChange('rfc', data.emitter.Rfc);
                    }

                } catch (error) {
                    console.error('Error parsing invoice XML:', error);
                    setInvoiceParsing({ status: 'error', filename: file.name, message: error.message || 'Error analizando CFDI' });
                }
            }, [getFieldValue, handleFieldChange]);

            const handleXmlUpload = useCallback((file) => {
                if (!file) return;
                handleFieldChange('xml_file', file.name);
                handleFieldChange('will_have_cfdi', true);
                parseInvoiceXml(file);
            }, [handleFieldChange, parseInvoiceXml]);

            // Inicializar Web Speech API
            useEffect(() => {
                if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
                    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                    recognitionRef.current = new SpeechRecognition();

                    const recognition = recognitionRef.current;
                    recognition.continuous = true;
                    recognition.interimResults = true;
                    recognition.lang = 'es-MX';

                    recognition.onresult = (event) => {
                        let finalTranscript = '';
                        let interimTranscript = '';

                        for (let i = event.resultIndex; i < event.results.length; i++) {
                            const transcript = event.results[i][0].transcript;
                            if (event.results[i].isFinal) {
                                finalTranscript += transcript;
                            } else {
                                interimTranscript += transcript;
                            }
                        }

                        const fullTranscript = transcript + finalTranscript + interimTranscript;
                        setTranscript(fullTranscript);

                        // Procesar solo si hay contenido final nuevo
                        if (finalTranscript.trim()) {
                            const parseResult = parseGasto(fullTranscript);
                            setFormData(prevData => ({
                                ...prevData,
                                ...parseResult.fields,
                                _confidence: { ...prevData._confidence, ...parseResult.confidence }
                            }));

                            setCurrentSummary(parseResult.summary);
                            setSummaryConfidence(parseResult.overallConfidence);
                        }
                    };

                    recognition.onerror = (event) => {
                        console.error('Speech recognition error:', event.error);
                        setIsRecording(false);
                        if (event.error === 'not-allowed') {
                            alert('Necesitas dar permiso para usar el micrófono. Por favor recarga la página y acepta los permisos.');
                        }
                    };

                    recognition.onend = () => {
                        setIsRecording(false);
                    };
                }

                return () => {
                    if (recognitionRef.current) {
                        recognitionRef.current.stop();
                    }
                };
            }, []);

            // Manejar reconocimiento de voz real
            const handleToggleRecording = useCallback(() => {
                if (!recognitionRef.current) {
                    alert('Tu navegador no soporta reconocimiento de voz. Usa Chrome, Edge o Safari.');
                    return;
                }

                if (isRecording) {
                    recognitionRef.current.stop();
                    setIsRecording(false);
                } else {
                    try {
                        recognitionRef.current.start();
                        setIsRecording(true);
                        setTranscript(''); // Limpiar transcripción anterior
                    } catch (error) {
                        console.error('Error starting speech recognition:', error);
                        alert('Error al iniciar el reconocimiento de voz. Asegúrate de dar permisos al micrófono.');
                    }
                }
            }, [isRecording]);

            // Manejar subida de archivo OCR
            const handleOcrUpload = useCallback(async (file) => {
                if (!file) return;

                setIsUploading(true);
                setOcrResult(null);

                try {
                    const formData = new FormData();
                    formData.append('file', file);
                    formData.append('paid_by', 'company_account'); // default
                    formData.append('will_have_cfdi', 'true'); // default

                    const response = await fetch('http://localhost:8000/ocr/intake', {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok) {
                        throw new Error(`Error ${response.status}: ${response.statusText}`);
                    }

                    const result = await response.json();
                    setOcrResult(result);

                    // Mapear campos del OCR al formulario
                    if (result.fields) {
                        // Crear campos mapeados solo si hay valores válidos
                        const mappedFields = {};
                        const mappedConfidence = {};

                        // Mapear cada campo si existe y es válido
                        if (result.fields.proveedor) {
                            mappedFields['proveedor.nombre'] = result.fields.proveedor;
                            mappedConfidence['proveedor.nombre'] = 0.8;
                        }

                        if (result.fields.total && result.fields.total > 0) {
                            mappedFields['monto_total'] = result.fields.total;
                            mappedConfidence['monto_total'] = 0.9;
                        }

                        if (result.fields.fecha) {
                            mappedFields['fecha_gasto'] = result.fields.fecha;
                            mappedConfidence['fecha_gasto'] = 0.8;
                        }

                        if (result.fields.rfc) {
                            mappedFields['rfc'] = result.fields.rfc;
                            mappedConfidence['rfc'] = 0.7;
                        }

                        // ✅ NUEVOS CAMPOS INTELIGENTES
                        if (result.fields.categoria) {
                            mappedFields['categoria'] = result.fields.categoria.toLowerCase();
                            mappedConfidence['categoria'] = result.fields.confianza_categoria || 0.8;
                        }

                        if (result.fields.forma_pago) {
                            mappedFields['forma_pago'] = result.fields.forma_pago;
                            mappedConfidence['forma_pago'] = 0.9;
                        }

                        // Usar descripción inteligente si está disponible
                        let descripcion = '';
                        if (result.fields.descripcion_inteligente) {
                            descripcion = result.fields.descripcion_inteligente;
                        } else if (result.fields.proveedor) {
                            descripcion = `Gasto en ${result.fields.proveedor}`;
                            if (result.fields.total) {
                                descripcion += ` por $${result.fields.total}`;
                            }
                            descripcion += ' (detectado por OCR)';
                        } else {
                            descripcion = 'Gasto detectado por OCR';
                        }
                        mappedFields['descripcion'] = descripcion;
                        mappedConfidence['descripcion'] = 0.7;

                        // Configurar valores por defecto razonables
                        mappedFields['will_have_cfdi'] = result.fields.rfc ? true : false;
                        mappedFields['paid_by'] = 'company_account';
                        mappedConfidence['will_have_cfdi'] = result.fields.rfc ? 0.8 : 0.6;
                        mappedConfidence['paid_by'] = 0.6;

                        setFormData(prevData => ({
                            ...prevData,
                            ...mappedFields,
                            _confidence: { ...prevData._confidence, ...mappedConfidence },
                            _ocrIntakeId: result.intake_id
                        }));

                        // Crear un resumen más detallado
                        let summary = `OCR procesado exitosamente`;
                        if (result.fields.proveedor && result.fields.total) {
                            summary = `OCR detectó: ${result.fields.proveedor} - $${result.fields.total}`;
                        } else if (result.fields.proveedor) {
                            summary = `OCR detectó proveedor: ${result.fields.proveedor}`;
                        } else if (result.fields.total) {
                            summary = `OCR detectó monto: $${result.fields.total}`;
                        }

                        setCurrentSummary(summary);
                        setSummaryConfidence(result.confidence || 0.8);
                    }

                } catch (error) {
                    console.error('Error en OCR:', error);
                    alert('Error procesando archivo con OCR: ' + error.message);
                } finally {
                    setIsUploading(false);
                }
            }, []);

            // Manejar entrada de texto directo
            const handleTextInput = useCallback((textInput) => {
                if (!textInput.trim()) return;

                // Usar el mismo parser que para la voz
                const parseResult = parseGasto(textInput);

                setFormData(prevData => ({
                    ...prevData,
                    ...parseResult.fields,
                    _confidence: { ...prevData._confidence, ...parseResult.confidence }
                }));

                setCurrentSummary(parseResult.summary);
                setSummaryConfidence(parseResult.overallConfidence);
                setTranscript(textInput);
            }, []);

            // Guardar borrador
            const handleSaveDraft = useCallback(async () => {
                setIsSaving(true);
                try {
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    setLastSaveTime(new Date());
                    console.log('Borrador guardado:', formData);
                } catch (error) {
                    console.error('Error guardando borrador:', error);
                    alert('Error al guardar el borrador');
                } finally {
                    setIsSaving(false);
                }
            }, [formData]);

            const handleSaveDemoExpense = useCallback(async () => {
                if (missingRequiredFields.length > 0) {
                    alert('Completa los campos obligatorios marcados antes de guardar el gasto demo.');
                    return;
                }

                try {
                    const expenseData = buildExpenseData();
                    const savedExpense = await saveExpenseToDatabase(expenseData, true);
                    syncDemoMode(true);
                    markMissionComplete('1');
                    await loadExpenses();
                    alert('¡Gasto demo guardado! Continúa con la misión 2 para vincular una factura.');
                    if (activeMission === '1') {
                        goToMission('2');
                    }
                } catch (error) {
                    console.error('Error guardando gasto demo:', error);
                    alert(error.message || 'No se pudo guardar el gasto demo. Intenta nuevamente.');
                }
            }, [missingRequiredFields, buildExpenseData, saveExpenseToDatabase, syncDemoMode, activeMission, loadExpenses]);

            // Guardar gasto
            const handleSendToOdoo = useCallback(async () => {
                setIsSending(true);
                try {
                    // Verificar duplicados ANTES de procesar
                    console.log('🔍 Verificando duplicados antes de enviar...');

                    const baseData = buildExpenseData();
                    const preliminaryData = {
                        descripcion: baseData.descripcion,
                        monto_total: baseData.monto_total,
                        fecha_gasto: baseData.fecha_gasto,
                        proveedor: baseData.proveedor ? baseData.proveedor.nombre : null,
                        categoria: baseData.categoria,
                        forma_pago: baseData.forma_pago,
                        will_have_cfdi: baseData.will_have_cfdi,
                        paid_by: baseData.paid_by,
                        rfc: baseData.rfc,
                        company_id: resolvedCompanyId,
                    };

                    const duplicateResult = await checkForDuplicates(preliminaryData);

                    // Si hay duplicados de alta confianza, mostrar alerta
                    if (duplicateResult.has_duplicates) {
                        const userWantsToContinue = await showDuplicateAlert(duplicateResult, preliminaryData);
                        if (!userWantsToContinue) {
                            console.log('🚫 Usuario canceló por duplicado detectado');
                            return; // Cancelar el envío
                        }
                        console.log('✅ Usuario decidió continuar a pesar del duplicado');
                    }
                    // Preparar datos usando getFieldValue para compatibilidad con claves planas
                    const expenseData = buildExpenseData();

                    // Determinar el modo de pago basado en los campos
                    let paymentMode = 'own_account';
                    if (getFieldValue('paid_by') === 'company_account') {
                        paymentMode = 'company_account';
                    } else if (getFieldValue('forma_pago') === 'tarjeta_empresa') {
                        paymentMode = 'company_account';
                    }

                    // Preparar descripción enriquecida con información adicional
                    let enrichedDescription = getFieldValue('descripcion') || 'Gasto registrado por voz';

                    // Agregar información de facturación
                    if (getFieldValue('will_have_cfdi')) {
                        enrichedDescription += ' [CFDI: Sí]';
                    } else {
                        enrichedDescription += ' [CFDI: No]';
                    }

                    // Agregar RFC si existe
                    if (getFieldValue('rfc')) {
                        enrichedDescription += ` [RFC: ${getFieldValue('rfc')}]`;
                    }

                    // Agregar notas si existen
                    if (getFieldValue('notas')) {
                        enrichedDescription += ` - ${getFieldValue('notas')}`;
                    }

                    // Agregar información de archivos adjuntos
                    const attachments = [];
                    if (getFieldValue('ticket_file')) attachments.push('Ticket');
                    if (getFieldValue('xml_file')) attachments.push('XML');
                    if (getFieldValue('pdf_file')) attachments.push('PDF');
                    if (attachments.length > 0) {
                        enrichedDescription += ` [Adjuntos: ${attachments.join(', ')}]`;
                    }

                    // Mapear campos correctamente para Odoo (solo campos estándar)
                    const odooData = {
                        name: enrichedDescription,
                        total_amount: getFieldValue('monto_total') || 0,
                        date: getFieldValue('fecha_gasto') || new Date().toISOString().split('T')[0],
                        employee_id: 1, // ID del empleado - necesitas obtenerlo dinámicamente
                        payment_mode: paymentMode,
                        description: enrichedDescription,
                        price_unit: getFieldValue('monto_total') || 0,
                        quantity: 1.0
                    };

                    console.log('Enviando datos a Odoo:', odooData);

                    // Intentar usar el servicio de Expense Router primero si está disponible
                    let response;
                    try {
                        // Preparar datos para Expense Router (incluye todos los campos nuevos)
                        const expenseRouterData = {
                            paid_by: getFieldValue('paid_by') || (paymentMode === 'company_account' ? 'company_account' : 'own_account'),
                            will_have_cfdi: getFieldValue('will_have_cfdi') || false,
                            total: getFieldValue('monto_total') || 0,
                            date: getFieldValue('fecha_gasto') || new Date().toISOString().split('T')[0],
                            provider_name: getFieldValue('proveedor.nombre') || 'Proveedor sin nombre',
                            rfc: getFieldValue('rfc'),
                            company_id: resolvedCompanyId,
                        };

                        console.log('Intentando con Expense Router:', expenseRouterData);

                        // Intentar con el servicio de expense router en puerto 3001
                        const routerResponse = await fetch('http://localhost:3001/intake', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify(expenseRouterData)
                        });

                        if (routerResponse.ok) {
                            const routerResult = await routerResponse.json();
                            console.log('Expense Router exitoso:', routerResult);

                            // Procesar la decisión de ruta
                            const routeResponse = await fetch(`http://localhost:3001/route/${routerResult.intake_id}/decide`, {
                                method: 'POST'
                            });

                            if (routeResponse.ok) {
                                const routeResult = await routeResponse.json();
                                console.log('Decisión de ruta:', routeResult);

                                alert(`¡Gasto procesado exitosamente!\nRuta: ${routeResult.route}\nMotivo: ${routeResult.reason}`);

                                // Limpiar formulario
                                setFormData({});
                                setInvoiceParsing({ status: 'idle' });
                                setTranscript('');
                                setCurrentSummary('');
                                setSummaryConfidence(0);
                                return;
                            }
                        }
                    } catch (routerError) {
                        console.log('Expense Router no disponible, usando endpoint directo de Odoo:', routerError.message);
                    }

                    // Fallback al endpoint directo de Odoo
                    response = await fetch('/simple_expense', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(odooData)
                    });

                    const result = await response.json();

                    if (result.success) {
                        // Guardar también en nuestra base de datos local (skip duplicate check ya que ya se hizo)
                        const savedExpense = await saveExpenseToDatabase(expenseData, true);

                        alert('¡Gasto enviado a Odoo y guardado localmente exitosamente!');
                        // Limpiar formulario
                        setFormData({});
                        setInvoiceParsing({ status: 'idle' });
                        setTranscript('');
                        setCurrentSummary('');
                        setSummaryConfidence(0);
                    } else {
                        throw new Error(result.error || 'Error desconocido');
                    }
                } catch (error) {
                    console.error('Error enviando a Odoo:', error);
                    alert('Error al enviar el gasto a Odoo: ' + error.message);
                } finally {
                    setIsSending(false);
                }
            }, [buildExpenseData, formData]);

            // Cargar gastos desde el backend
            const loadExpenses = useCallback(async () => {
                try {
                    // Get JWT token from localStorage
                    const token = localStorage.getItem('access_token');

                    // 🔒 Si no hay token, redirigir al login
                    if (!token) {
                        console.warn('🔒 No se encontró token de autenticación - Redirigiendo al login...');
                        window.location.href = '/auth-login.html?error=Por favor inicia sesión para continuar.';
                        return;
                    }

                    const headers = {
                        'Content-Type': 'application/json'
                    };

                    if (token) {
                        headers['Authorization'] = `Bearer ${token}`;
                    }

                    const response = await fetch(`/expenses?company_id=${encodeURIComponent(resolvedCompanyId)}`, {
                        headers: headers
                    });

                    // 🔒 Manejar error 401 - Redirigir al login
                    if (response.status === 401) {
                        console.warn('🔒 No autorizado (401) - Redirigiendo al login...');
                        // Limpiar token inválido
                        localStorage.removeItem('access_token');
                        localStorage.removeItem('user_data');
                        localStorage.removeItem('tenant_data');
                        // Redirigir al login con mensaje
                        window.location.href = '/auth-login.html?error=Tu sesión ha expirado. Por favor inicia sesión nuevamente.';
                        return;
                    }

                    if (response.ok) {
                        const backendExpenses = await response.json();
                        if (backendExpenses.length === 0) {
                            const dummyExpenses = generateDummyExpenses();
                            console.log('🎯 Creando datos dummy en el backend...');
                            const savedExpenses = [];
                            for (const dummyExpense of dummyExpenses) {
                                try {
                                    const createResponse = await fetch('/expenses', {
                                        method: 'POST',
                                        headers: {
                                            'Content-Type': 'application/json',
                                        },
                                        body: JSON.stringify({ ...dummyExpense, company_id: resolvedCompanyId })
                                    });

                                    if (createResponse.ok) {
                                        const savedExpense = await createResponse.json();
                                        savedExpenses.push(savedExpense);
                                    }
                                } catch (error) {
                                    console.error('Error creando gasto dummy:', error);
                                }
                            }

                            const normalizedDummy = savedExpenses.map(normalizeExpense);
                            setExpensesData(normalizedDummy);
                            saveLocalExpenses(normalizedDummy);
                            syncDemoMode(true);
                            console.log('🎯 Datos dummy creados en backend:', normalizedDummy.length);
                        } else {
                            const normalizedExpenses = backendExpenses.map(normalizeExpense);
                            setExpensesData(normalizedExpenses);
                            saveLocalExpenses(normalizedExpenses);
                            const hasDemo = normalizedExpenses.some((expense) => {
                                const metadata = expense?.metadata || {};
                                return metadata.demo === true || metadata.scenario === 'onboarding';
                            });
                            syncDemoMode(hasDemo);
                            console.log('📋 Gastos cargados desde backend:', normalizedExpenses.length);
                        }
                    } else {
                        console.error('Error cargando gastos del backend:', response.status);
                        const savedExpenses = loadLocalExpenses();
                        const normalizedExpenses = savedExpenses.map(normalizeExpense);
                        const scopedExpenses = normalizedExpenses.filter(exp => exp.company_id === resolvedCompanyId);
                        setExpensesData(scopedExpenses);
                        const hasDemo = scopedExpenses.some((expense) => {
                            const metadata = expense?.metadata || {};
                            return metadata.demo === true || metadata.scenario === 'onboarding';
                        });
                        syncDemoMode(hasDemo);
                        console.log('📋 Gastos cargados desde localStorage (fallback):', scopedExpenses.length);
                    }
                } catch (error) {
                    console.error('Error conectando al backend:', error);
                    const savedExpenses = loadLocalExpenses();
                    const normalizedExpenses = savedExpenses.map(normalizeExpense);
                    const scopedExpenses = normalizedExpenses.filter(exp => exp.company_id === resolvedCompanyId);
                    setExpensesData(scopedExpenses);
                    const hasDemo = scopedExpenses.some((expense) => {
                        const metadata = expense?.metadata || {};
                        return metadata.demo === true || metadata.scenario === 'onboarding';
                    });
                    syncDemoMode(hasDemo);
                    console.log('📋 Gastos cargados desde localStorage (fallback):', scopedExpenses.length);
                }
            }, [loadLocalExpenses, normalizeExpense, resolvedCompanyId, saveLocalExpenses, syncDemoMode]);

            useEffect(() => {
                loadExpenses();
            }, [loadExpenses]);

            // Función para predecir categoría automáticamente
            const predictCategory = async (description, amount = null, providerName = null) => {
                if (!description || description.length < 3) {
                    return null;
                }

                setIsPredictingCategory(true);
                try {
                    const response = await fetch('/expenses/predict-category', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            description: description,
                            amount: amount,
                            provider_name: providerName,
                            include_history: true,
                            company_id: resolvedCompanyId,
                        })
                    });

                    if (response.ok) {
                        const result = await response.json();
                        console.log('🤖 Category prediction result:', result);
                        setCategoryPrediction(result);

                        // Auto-aplicar si la confianza es alta
                        if (result.confianza >= 0.8 && !getFieldValue('categoria')) {
                            handleFieldChange('categoria', result.categoria_sugerida);
                            console.log(`✅ Auto-aplicada categoría: ${result.categoria_sugerida} (confianza: ${result.confianza})`);
                        }

                        return result;
                    } else {
                        console.warn('Error predicting category:', response.status);
                        return null;
                    }
                } catch (error) {
                    console.error('Error predicting category:', error);
                    return null;
                } finally {
                    setIsPredictingCategory(false);
                }
            };

            // Auto-predicción cuando cambian los campos relevantes
            useEffect(() => {
                const description = getFieldValue('descripcion');
                const amount = getFieldValue('monto_total');
                const providerName = getFieldValue('proveedor.nombre');

                // Solo predecir si tenemos descripción y no hay categoría ya seleccionada
                if (description && description.length >= 3 && !getFieldValue('categoria')) {
                    const timeoutId = setTimeout(() => {
                        predictCategory(description, amount, providerName);
                    }, 1500); // Esperar 1.5 segundos después del último cambio

                    return () => clearTimeout(timeoutId);
                }
            }, [formData.descripcion, formData.monto_total, formData['proveedor.nombre']]);

            // Función para verificar duplicados antes de guardar
            const checkForDuplicates = async (expenseData) => {
                setIsCheckingDuplicates(true);
                try {
                    const duplicateCheckData = {
                        new_expense: {
                            descripcion: expenseData.descripcion || 'Gasto sin descripción',
                            monto_total: expenseData.monto_total || 0,
                            fecha_gasto: expenseData.fecha_gasto,
                            categoria: expenseData.categoria,
                            proveedor: expenseData.proveedor ? { nombre: expenseData.proveedor } : null,
                            rfc: expenseData.rfc,
                            workflow_status: 'draft',
                            estado_factura: 'pendiente',
                            estado_conciliacion: 'pendiente',
                            forma_pago: expenseData.forma_pago,
                            paid_by: expenseData.paid_by || 'company_account',
                            will_have_cfdi: expenseData.will_have_cfdi !== false,
                            company_id: expenseData.company_id || resolvedCompanyId,
                        },
                        check_existing: true,
                        company_id: expenseData.company_id || resolvedCompanyId,
                    };

                    const response = await fetch('/expenses/check-duplicates', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(duplicateCheckData)
                    });

                    if (response.ok) {
                        const result = await response.json();
                        console.log('🔍 Duplicate check result:', result);
                        return result;
                    } else {
                        console.warn('Error checking duplicates:', response.status);
                        return { has_duplicates: false, recommendation: 'proceed' };
                    }
                } catch (error) {
                    console.error('Error checking duplicates:', error);
                    return { has_duplicates: false, recommendation: 'proceed' };
                } finally {
                    setIsCheckingDuplicates(false);
                }
            };

            // Función para mostrar alerta de duplicado
            const showDuplicateAlert = (duplicateResult, newExpenseData) => {
                return new Promise((resolve) => {
                    if (!duplicateResult.has_duplicates) {
                        resolve(true);
                        return;
                    }

                    const topMatch = duplicateResult.duplicates[0];
                    const existing = topMatch.existing_expense;

                    let message = `⚠️ POSIBLE GASTO DUPLICADO DETECTADO\n\n`;
                    message += `🔍 Confianza: ${topMatch.confidence_level.toUpperCase()}\n`;
                    message += `📊 Similitud: ${(topMatch.similarity_score * 100).toFixed(1)}%\n\n`;

                    message += `📝 GASTO NUEVO:\n`;
                    message += `• ${newExpenseData.descripcion || 'N/A'}\n`;
                    message += `• $${newExpenseData.monto_total || 0}\n`;
                    message += `• ${newExpenseData.fecha_gasto || 'N/A'}\n`;
                    if (newExpenseData.proveedor) {
                        message += `• Proveedor: ${newExpenseData.proveedor}\n`;
                    }
                    message += `\n`;

                    message += `📋 GASTO EXISTENTE:\n`;
                    message += `• ${existing.descripcion}\n`;
                    message += `• $${existing.monto_total}\n`;
                    message += `• ${existing.fecha_gasto || 'N/A'}\n\n`;

                    message += `🎯 RAZONES:\n`;
                    topMatch.match_reasons.forEach(reason => {
                        message += `• ${reason}\n`;
                    });

                    message += `\n¿Deseas continuar de todos modos?`;

                    if (duplicateResult.risk_level === 'high') {
                        message += `\n\n🚫 RECOMENDACIÓN: NO continuar (muy probable duplicado)`;
                    } else if (duplicateResult.risk_level === 'medium') {
                        message += `\n\n⚠️ RECOMENDACIÓN: Revisar cuidadosamente`;
                    }

                    const userChoice = confirm(message);
                    resolve(userChoice);
                });
            };

            // Función para guardar gasto en nuestra base de datos
            const saveExpenseToDatabase = async (expenseData, skipDuplicateCheck = false) => {
                try {
                    // Verificar duplicados a menos que se haya hecho antes
                    if (!skipDuplicateCheck) {
                        console.log('🔍 Verificando duplicados antes de guardar...');
                        const duplicateResult = await checkForDuplicates(expenseData);

                        if (duplicateResult.has_duplicates) {
                            const userWantsToContinue = await showDuplicateAlert(duplicateResult, expenseData);
                            if (!userWantsToContinue) {
                                console.log('🚫 Usuario canceló por duplicado detectado');
                                return null; // Cancelar el guardado
                            }
                            console.log('✅ Usuario decidió continuar a pesar del duplicado');
                        }
                    }
                    const hasInvoice = !!expenseData.factura_id;
                    const estadoFactura = hasInvoice
                        ? 'facturado'
                        : expenseData.will_have_cfdi ? 'pendiente' : 'no_requiere';

                    const estadoConciliacion = hasInvoice
                        ? 'pendiente_bancaria'
                        : expenseData.will_have_cfdi ? 'pendiente_factura' : 'sin_factura';

                    // Preparar datos para el backend
                    const backendExpense = {
                        descripcion: expenseData.descripcion || expenseData.name || 'Gasto sin descripción',
                        monto_total: expenseData.monto_total || expenseData.total_amount || 0,
                        fecha_gasto: expenseData.fecha_gasto || expenseData.date,
                        categoria: expenseData.categoria || expenseData.category,
                        proveedor: expenseData.proveedor,
                        rfc: expenseData.rfc,
                        tax_info: expenseData.tax_info,
                        asientos_contables: expenseData.asientos_contables,
                        workflow_status: expenseData.workflow_status || 'draft',
                        estado_factura: estadoFactura,
                        estado_conciliacion: estadoConciliacion,
                        forma_pago: expenseData.forma_pago || expenseData.payment_mode,
                        paid_by: expenseData.paid_by || 'company_account',
                        will_have_cfdi: expenseData.will_have_cfdi !== false,
                        movimientos_bancarios: expenseData.movimientos_bancarios,
                        company_id: expenseData.company_id || resolvedCompanyId,
                        metadata: {
                            factura_id: expenseData.factura_id,
                            factura_url: hasInvoice ? (expenseData.factura_url || `https://erp.tuempresa.com/facturas/${expenseData.factura_id}`) : null,
                            movimiento_bancario: hasInvoice ? expenseData.movimiento_bancario || null : null,
                            fecha_creacion: new Date().toISOString(),
                            ...expenseData.metadata
                        }
                    };

                    // Enviar al backend
                    const response = await fetch('/expenses', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(backendExpense)
                    });

                    if (response.ok) {
                        const savedExpense = await response.json();
                        const normalizedExpense = normalizeExpense(savedExpense);

                        // Actualizar estado local
                        setExpensesData(prevExpenses => {
                            const updatedExpenses = [...prevExpenses, normalizedExpense];
                            // Mantener sync con localStorage como backup
                            saveLocalExpenses(updatedExpenses);
                            return updatedExpenses;
                        });

                        console.log('✅ Gasto guardado en backend:', normalizedExpense);
                        return normalizedExpense;
                    } else {
                        const errorData = await response.json();
                        throw new Error(`Error del servidor: ${errorData.detail || response.statusText}`);
                    }

                } catch (error) {
                    console.error('Error guardando gasto en backend:', error);

                    // Fallback a localStorage
                    const normalizedExpense = normalizeExpense({
                        id: Date.now().toString(),
                        fecha_creacion: new Date().toISOString(),
                        company_id: expenseData.company_id || resolvedCompanyId,
                        ...expenseData,
                        estado_factura: estadoFactura,
                        estado_conciliacion: estadoConciliacion,
                        factura_url: hasInvoice ? (expenseData.factura_url || `https://erp.tuempresa.com/facturas/${expenseData.factura_id}`) : null,
                        movimiento_bancario: hasInvoice ? expenseData.movimiento_bancario || null : null
                    });

                    const currentExpenses = loadLocalExpenses();
                    const updatedExpenses = [...currentExpenses.map(normalizeExpense), normalizedExpense];
                    saveLocalExpenses(updatedExpenses);
                    setExpensesData(updatedExpenses);

                    console.warn('⚠️ Gasto guardado en localStorage (fallback):', normalizedExpense);
                    return normalizedExpense;
                }
            };

            // Función para limpiar datos y regenerar dummy data
            const handleRegenerateDummyData = async () => {
                if (confirm('¿Estás seguro de que quieres limpiar todos los datos y generar nuevos datos de prueba?')) {
                    try {
                        // TODO: Agregar endpoint DELETE /expenses para limpiar datos del backend
                        clearLocalExpenses();

                        const newDummyData = generateDummyExpenses();
                        console.log('🎯 Recreando datos dummy en el backend...');

                        // Crear cada gasto dummy en el backend
                        const savedExpenses = [];
                        for (const dummyExpense of newDummyData) {
                            try {
                                const createResponse = await fetch('/expenses', {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/json',
                                    },
                                    body: JSON.stringify({ ...dummyExpense, company_id: resolvedCompanyId })
                                });

                                if (createResponse.ok) {
                                    const savedExpense = await createResponse.json();
                                    savedExpenses.push(savedExpense);
                                }
                            } catch (error) {
                                console.error('Error creando gasto dummy:', error);
                            }
                        }

                        const normalizedData = savedExpenses.map(normalizeExpense);
                        saveLocalExpenses(normalizedData);
                        setExpensesData(normalizedData);
                        alert(`✅ Se generaron ${savedExpenses.length} gastos de prueba en el backend`);

                    } catch (error) {
                        console.error('Error regenerando datos dummy:', error);
                        // Fallback a localStorage
                        const newDummyData = generateDummyExpenses();
                        const normalizedData = newDummyData.map(normalizeExpense);
                        saveLocalExpenses(normalizedData);
                        setExpensesData(normalizedData);
                        alert(`⚠️ Se generaron ${newDummyData.length} gastos de prueba en localStorage (fallback)`);
                    }
                }
            };

            // Función para generar gastos dummy para demostración
            const generateDummyExpenses = () => {
                const proveedores = [
                    { nombre: 'Pemex', categoria: 'combustible', rfc: 'PEP970814KS3', tiene_rfc: true },
                    { nombre: 'Walmart', categoria: 'oficina', rfc: 'WAL9704132P6', tiene_rfc: true },
                    { nombre: 'Restaurante La Europea', categoria: 'alimentos', rfc: null, tiene_rfc: false },
                    { nombre: 'Home Depot México', categoria: 'oficina', rfc: 'HDM050101RK3', tiene_rfc: true },
                    { nombre: 'Uber', categoria: 'transporte', rfc: null, tiene_rfc: false },
                    { nombre: 'Microsoft México', categoria: 'tecnologia', rfc: 'MIC030201RG7', tiene_rfc: true },
                    { nombre: 'Hotel City Express', categoria: 'hospedaje', rfc: 'HCE060301DH8', tiene_rfc: true },
                    { nombre: 'Farmacias del Ahorro', categoria: 'salud', rfc: 'FDA970503JH1', tiene_rfc: true },
                    { nombre: 'Taxi Local', categoria: 'transporte', rfc: null, tiene_rfc: false },
                    { nombre: 'Starbucks', categoria: 'alimentos', rfc: 'STA950415KN2', tiene_rfc: true }
                ];

                const dummyExpenses = [];
                const today = new Date();

                for (let i = 0; i < 15; i++) {
                    const proveedor = proveedores[Math.floor(Math.random() * proveedores.length)];
                    const fechaGasto = new Date(today);
                    fechaGasto.setDate(today.getDate() - Math.floor(Math.random() * 60)); // Últimos 2 meses

                    // Determinar si va a tener CFDI basado en el monto y proveedor
                    const monto = Math.floor(Math.random() * 5000) + 100;
                    const willHaveCfdi = proveedor.tiene_rfc && (monto > 500 || Math.random() > 0.3);

                    // Determinar estado de factura
                    let estadoFactura = 'no_requiere';
                    if (willHaveCfdi) {
                        estadoFactura = Math.random() > 0.4 ? 'pendiente' : 'facturado';
                    }

                    const facturaId = estadoFactura === 'facturado' ? `FAC-${Math.floor(Math.random() * 10000)}` : null;
                    const facturaUrl = facturaId ? `https://erp.tuempresa.com/facturas/${facturaId}` : null;

                    let movimientoBancario = null;
                    let movimientosBancarios = [];
                    let estadoConciliacion = 'sin_factura';
                    let fechaConciliacionBancaria = null;

                    const taxInfo = (() => {
                        if (!willHaveCfdi) return null;
                        const ivaAmount = round2(monto * 0.16);
                        const subtotalCalc = round2(monto - ivaAmount);
                        return {
                            subtotal: subtotalCalc,
                            total: monto,
                            currency: 'MXN',
                            taxes: [
                                {
                                    type: 'IVA',
                                    code: '002',
                                    kind: 'traslado',
                                    rate: 0.16,
                                    amount: ivaAmount,
                                }
                            ],
                            iva_amount: ivaAmount,
                            other_taxes: 0,
                        };
                    })();

                    if (estadoFactura === 'facturado') {
                        if (Math.random() > 0.55) {
                            const sampleMovement = SAMPLE_BANK_MOVEMENTS[Math.floor(Math.random() * SAMPLE_BANK_MOVEMENTS.length)];
                            const movement = { ...sampleMovement };
                            movimientoBancario = movement;
                            movimientosBancarios = [movement];
                            estadoConciliacion = 'conciliado_banco';
                            fechaConciliacionBancaria = new Date().toISOString();
                        } else {
                            estadoConciliacion = 'pendiente_bancaria';
                        }
                    } else if (estadoFactura === 'pendiente') {
                        estadoConciliacion = facturaId ? 'pendiente_bancaria' : 'pendiente_factura';
                    }

                    const baseExpense = {
                        id: `exp_${Date.now()}_${i}`,
                        descripcion: `Gasto en ${proveedor.nombre} - ${getCategoryLabel(proveedor.categoria)}`,
                        monto_total: monto,
                        fecha_gasto: fechaGasto.toISOString().split('T')[0],
                        company_id: resolvedCompanyId,
                        'proveedor.nombre': proveedor.nombre,
                        categoria: proveedor.categoria,
                        forma_pago: Math.random() > 0.5 ? 'tarjeta_empresa' : 'efectivo',
                        will_have_cfdi: willHaveCfdi,
                        paid_by: Math.random() > 0.6 ? 'company_account' : 'own_account',
                        rfc: proveedor.rfc,
                        estado_factura: estadoFactura,
                        estado_conciliacion: estadoConciliacion,
                        fecha_creacion: new Date().toISOString(),
                        tax_info: taxInfo,
                        factura_id: facturaId,
                        factura_url: facturaUrl,
                        movimiento_bancario: movimientoBancario,
                        movimientos_bancarios: movimientosBancarios,
                        fecha_conciliacion_bancaria: fechaConciliacionBancaria,
                        completitud: calculateCompleteness(willHaveCfdi, estadoFactura, proveedor.rfc)
                    };

                    const expense = {
                        ...baseExpense,
                        asientos_contables: generateAccountingEntries({ ...baseExpense }),
                    };

                    dummyExpenses.push(expense);
                }

                return dummyExpenses;
            };

            // Función para obtener label de categoría
            const getCategoryLabel = (categoryValue) => {
                const category = CATEGORIAS_DISPONIBLES.find(cat => cat.value === categoryValue);
                return category ? category.label.substring(2) : 'Otros';
            };

            const EXPENSE_ACCOUNT_MAP = {
                combustible: { cuenta: '6140', nombre: 'Combustibles y lubricantes', descripcion: 'Consumo de combustible para operaciones' },
                alimentos: { cuenta: '6150', nombre: 'Viáticos y viajes', descripcion: 'Gastos de alimentación en viaje' },
                transporte: { cuenta: '6130', nombre: 'Servicios de transporte', descripcion: 'Traslados y logística' },
                hospedaje: { cuenta: '6150', nombre: 'Viáticos y viajes', descripcion: 'Alojamiento del personal' },
                oficina: { cuenta: '6180', nombre: 'Papelería y misceláneos', descripcion: 'Insumos y servicios de oficina' },
                tecnologia: { cuenta: '6170', nombre: 'Servicios tecnológicos', descripcion: 'Software, hosting y herramientas digitales' },
                marketing: { cuenta: '6160', nombre: 'Publicidad y promoción', descripcion: 'Campañas y materiales de marketing' },
                capacitacion: { cuenta: '6155', nombre: 'Capacitación y desarrollo', descripcion: 'Cursos y certificaciones del personal' },
                salud: { cuenta: '6195', nombre: 'Gastos médicos y bienestar', descripcion: 'Consultas, seguros o programas de salud' },
                otros: { cuenta: '6190', nombre: 'Gastos generales', descripcion: 'Otros gastos operativos' }
            };

            const TAX_ACCOUNT_MAP = {
                IVA: {
                    traslado: { cuenta: '1190', nombre: 'IVA acreditable pendiente', tipo: 'iva_acreditable' },
                    retencion: { cuenta: '2130', nombre: 'IVA retenido por pagar', tipo: 'pasivo' }
                },
                ISR: {
                    retencion: { cuenta: '2110', nombre: 'ISR retenido por pagar', tipo: 'pasivo' }
                },
                IEPS: {
                    traslado: { cuenta: '1195', nombre: 'IEPS acreditable pagado', tipo: 'impuesto_acreditable' }
                },
                OTRO: {
                    traslado: { cuenta: '1180', nombre: 'Impuestos acreditables diversos', tipo: 'impuesto' },
                    retencion: { cuenta: '2190', nombre: 'Retenciones diversas por pagar', tipo: 'pasivo' }
                }
            };

            const PAYMENT_ACCOUNT_MAP = {
                company_account: { cuenta: '1110', nombre: 'Bancos', tipo: 'activo', descripcion: 'Pago con cuenta bancaria corporativa' },
                own_account: { cuenta: '2180', nombre: 'Gastos por comprobar', tipo: 'pasivo', descripcion: 'Pago con recursos del empleado o caja chica' },
                tarjeta_empresa: { cuenta: '1120', nombre: 'Tarjetas corporativas', tipo: 'activo', descripcion: 'Pago con tarjeta corporativa' }
            };

            const invoiceCounts = useMemo(() => {
                return expensesData.reduce((acc, expense) => {
                    const status = (expense.estado_factura || 'pendiente').toLowerCase();
                    acc[status] = (acc[status] || 0) + 1;
                    return acc;
                }, {});
            }, [expensesData]);

            const bankCounts = useMemo(() => {
                const pending = expensesData.filter((expense) => (expense.estado_conciliacion || '').toLowerCase() !== 'conciliado_banco');
                const reconciled = expensesData.length - pending.length;
                return {
                    pending: pending.length,
                    reconciled: reconciled,
                };
            }, [expensesData]);

            const round2 = (value) => Math.round((Number(value) || 0) * 100) / 100;
            const toAmount = (value) => round2(value).toFixed(2);

            const resolveTaxAccount = (tax) => {
                const taxType = (tax.type || 'OTRO').toUpperCase();
                const mapping = TAX_ACCOUNT_MAP[taxType] || TAX_ACCOUNT_MAP.OTRO;
                const base = tax.kind === 'retencion' ? mapping.retencion : mapping.traslado;
                const fallback = tax.kind === 'retencion' ? TAX_ACCOUNT_MAP.OTRO.retencion : TAX_ACCOUNT_MAP.OTRO.traslado;
                const config = base || fallback;
                if (!config) return null;
                return {
                    ...config,
                    descripcion: tax.kind === 'retencion'
                        ? `Retención fiscal aplicada (${taxType})`
                        : `Impuesto trasladado acreditable (${taxType})`
                };
            };

            const generateAccountingEntries = (expense) => {
                const categoria = expense.categoria || 'otros';
                const cuentaGasto = EXPENSE_ACCOUNT_MAP[categoria] || EXPENSE_ACCOUNT_MAP.otros;
                const total = round2(expense.monto_total || expense.total || 0);
                const taxInfo = expense.tax_info || expense.tax_breakdown || null;
                const taxes = Array.isArray(taxInfo?.taxes) ? taxInfo.taxes : [];
                const traslados = taxes.filter(tax => tax.kind === 'traslado');
                const retenciones = taxes.filter(tax => tax.kind === 'retencion');
                const trasladosSum = round2(traslados.reduce((sum, tax) => sum + (tax.amount || 0), 0));
                const retencionesSum = round2(retenciones.reduce((sum, tax) => sum + (tax.amount || 0), 0));

                let subtotal = round2(taxInfo?.subtotal);
                if (!(subtotal > 0)) {
                    subtotal = round2(total + retencionesSum - trasladosSum);
                }
                if (subtotal < 0) subtotal = 0;

                const willHaveCfdi = !!expense.will_have_cfdi;
                const estadoFactura = expense.estado_factura || (willHaveCfdi ? 'pendiente' : 'no_requiere');
                const paidBy = expense.paid_by || 'company_account';

                const estadoConciliacion = (expense.estado_conciliacion || '').toLowerCase();
                const isPaid = estadoConciliacion === 'conciliado_banco';

                const movimientos = [];
                const pushEntry = (cuenta, nombre, debe, haber, tipo, descripcion) => {
                    movimientos.push({
                        cuenta,
                        nombre_cuenta: nombre,
                        descripcion,
                        debe: toAmount(debe),
                        haber: toAmount(haber),
                        tipo,
                    });
                };

                if (subtotal > 0) {
                    pushEntry(
                        cuentaGasto.cuenta,
                        cuentaGasto.nombre,
                        subtotal,
                        0,
                        'gasto',
                        cuentaGasto.descripcion || 'Registro del gasto operativo'
                    );
                }

                traslados.forEach((tax) => {
                    const config = resolveTaxAccount(tax);
                    if (!config) return;
                    const amount = round2(tax.amount || 0);
                    if (amount <= 0) return;
                    pushEntry(config.cuenta, config.nombre, amount, 0, config.tipo, config.descripcion);
                });

                let totalDebits = round2(movimientos.reduce((sum, mov) => sum + parseFloat(mov.debe), 0));
                if (totalDebits <= 0 && total > 0) {
                    totalDebits = total;
                    pushEntry(
                        cuentaGasto.cuenta,
                        cuentaGasto.nombre,
                        total,
                        0,
                        'gasto',
                        cuentaGasto.descripcion || 'Registro del gasto operativo'
                    );
                }

                const resolvePaymentAccount = () => {
                    const key = paidBy in PAYMENT_ACCOUNT_MAP ? paidBy : 'company_account';
                    const base = PAYMENT_ACCOUNT_MAP[key] || PAYMENT_ACCOUNT_MAP.company_account;
                    let descripcion = base.descripcion;

                    if (isPaid) {
                        descripcion = 'Pago conciliado contra banco';
                    } else if (estadoFactura === 'facturado') {
                        descripcion = 'Factura registrada: pendiente de pago al proveedor';
                    } else if (willHaveCfdi) {
                        descripcion = 'Gasto por comprobar en espera de CFDI';
                    } else {
                        descripcion = base.descripcion;
                    }

                    return { ...base, descripcion };
                };

                const paymentAccount = resolvePaymentAccount();
                const providerAccount = {
                    cuenta: '2100',
                    nombre: 'Proveedores',
                    tipo: 'pasivo',
                    descripcion: 'Cuenta por pagar al proveedor'
                };
                const bankAccount = PAYMENT_ACCOUNT_MAP.company_account;

                if (estadoFactura === 'facturado') {
                    const providerCredit = round2(totalDebits - retencionesSum);

                    if (isPaid) {
                        if (providerCredit > 0) {
                            pushEntry(
                                bankAccount.cuenta,
                                bankAccount.nombre,
                                0,
                                providerCredit,
                                bankAccount.tipo,
                                'Pago bancario conciliado al proveedor'
                            );
                        }
                    } else {
                        if (providerCredit > 0) {
                            pushEntry(
                                providerAccount.cuenta,
                                providerAccount.nombre,
                                0,
                                providerCredit,
                                providerAccount.tipo,
                                'Factura registrada: obligación con el proveedor'
                            );
                        }
                    }

                    retenciones.forEach((tax) => {
                        const config = resolveTaxAccount(tax);
                        if (!config) return;
                        const amount = round2(tax.amount || 0);
                        if (amount <= 0) return;
                        pushEntry(config.cuenta, config.nombre, 0, amount, config.tipo || 'pasivo', config.descripcion);
                    });
                } else {
                    const paymentCredit = round2(totalDebits - retencionesSum);
                    if (paymentCredit > 0) {
                        pushEntry(
                            paymentAccount.cuenta,
                            paymentAccount.nombre,
                            0,
                            paymentCredit,
                            paymentAccount.tipo || 'pasivo',
                            paymentAccount.descripcion
                        );
                    }
                    retenciones.forEach((tax) => {
                        const config = resolveTaxAccount(tax);
                        if (!config) return;
                        const amount = round2(tax.amount || 0);
                        if (amount <= 0) return;
                        pushEntry(config.cuenta, config.nombre, 0, amount, config.tipo || 'pasivo', config.descripcion);
                    });
                }

                let totalDebe = round2(movimientos.reduce((sum, mov) => sum + parseFloat(mov.debe), 0));
                let totalHaber = round2(movimientos.reduce((sum, mov) => sum + parseFloat(mov.haber), 0));
                let diff = round2(totalDebe - totalHaber);

                if (Math.abs(diff) >= 0.01 && movimientos.length > 0) {
                    const adjustIndex = movimientos.findIndex(mov => parseFloat(mov.haber) > 0) !== -1
                        ? movimientos.findIndex(mov => parseFloat(mov.haber) > 0)
                        : movimientos.findIndex(mov => parseFloat(mov.debe) > 0);
                    if (adjustIndex !== -1) {
                        const target = movimientos[adjustIndex];
                        if (diff > 0) {
                            target.haber = toAmount(parseFloat(target.haber) + diff);
                        } else {
                            target.debe = toAmount(parseFloat(target.debe) + (diff * -1));
                        }
                    }
                    totalDebe = round2(movimientos.reduce((sum, mov) => sum + parseFloat(mov.debe), 0));
                    totalHaber = round2(movimientos.reduce((sum, mov) => sum + parseFloat(mov.haber), 0));
                    diff = round2(totalDebe - totalHaber);
                }

                return {
                    fecha_asiento: new Date().toISOString().split('T')[0],
                    numero_poliza: `POL-${Math.floor(Math.random() * 10000)}`,
                    tipo_poliza: willHaveCfdi ? 'Egresos con IVA' : 'Egresos sin factura',
                    concepto: `Registro de gasto - ${cuentaGasto.nombre}`,
                    movimientos,
                    total_debe: toAmount(totalDebe),
                    total_haber: toAmount(totalHaber),
                    balanceado: Math.abs(diff) < 0.01
                };
            };

            // Función para calcular completitud
            const calculateCompleteness = (willHaveCfdi, estadoFactura, rfc) => {
                const criterios = {
                    datos_basicos: true, // Siempre completo para datos dummy
                    facturacion_requerida: willHaveCfdi,
                    factura_recibida: estadoFactura === 'facturado',
                    rfc_proveedor: !!rfc,
                    asientos_generados: true,
                    conciliado: estadoFactura === 'facturado' || !willHaveCfdi
                };

                let score = 0;
                let total = 0;

                // Datos básicos (peso: 2)
                total += 2;
                if (criterios.datos_basicos) score += 2;

                // Asientos contables (peso: 2)
                total += 2;
                if (criterios.asientos_generados) score += 2;

                // Facturación (peso: 3 si se requiere)
                if (criterios.facturacion_requerida) {
                    total += 3;
                    if (criterios.factura_recibida) score += 3;

                    // RFC (peso: 1 si se requiere factura)
                    total += 1;
                    if (criterios.rfc_proveedor) score += 1;
                }

                // Conciliación (peso: 2)
                total += 2;
                if (criterios.conciliado) score += 2;

                const porcentaje = Math.round((score / total) * 100);

                return {
                    porcentaje,
                    criterios,
                    estado: porcentaje === 100 ? 'completo' :
                           porcentaje >= 70 ? 'parcial' : 'incompleto',
                    detalles: {
                        score,
                        total,
                        faltan: total - score
                    }
                };
            };


            const progress = calculateCompleteness(
                formData.will_have_cfdi || false,
                formData.invoice_status || 'no_invoice',
                formData.proveedor?.rfc || null
            );
            const missingRequiredFields = ['descripcion', 'monto_total', 'fecha_gasto', 'proveedor.nombre', 'forma_pago', 'will_have_cfdi', 'paid_by'].filter(field => {
                const value = getFieldValue(field);
                return !value;
            });

            const currentPath = typeof window !== 'undefined' ? window.location.pathname : '';

            return (
                <div className="min-h-screen bg-slate-100 text-slate-900">
                    <header className="bg-white border-b shadow-sm sticky top-0 z-50">
                        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                            <div className="flex items-center justify-between h-16 gap-6">
                                <div className="flex items-center gap-6">
                                    <a href="/dashboard" className="flex items-center gap-2">
                                        <img src="/static/img/ContaFlow.png" alt="ContaFlow" className="h-9 w-auto" />
                                    </a>
                                    <nav className="hidden xl:flex items-center gap-4 text-sm font-semibold text-slate-600">
                                        {navItems.map((item) => {
                                            const isActive = item.matches.some((path) => currentPath.startsWith(path));
                                            return (
                                                <a
                                                    key={item.href}
                                                    href={item.href}
                                                    className={`inline-flex items-center gap-2 border-b-2 pb-1 transition-colors ${isActive ? 'text-blue-600 border-blue-600' : 'border-transparent hover:text-blue-600 hover:border-blue-200'}`}
                                                >
                                                    <i className={`fas ${item.icon}`}></i>
                                                    {item.label}
                                                </a>
                                            );
                                        })}
                                    </nav>
                                </div>
                                <div className="flex items-center gap-4 text-sm">
                                    <div className="hidden lg:flex items-center gap-2 text-slate-600">
                                        <i className="fas fa-building text-blue-600"></i>
                                        <span className="font-semibold text-slate-900">{headerCompany}</span>
                                    </div>
                                    <div className="hidden lg:flex items-center gap-2 text-slate-500">
                                        <i className="fas fa-user-circle text-slate-400 text-lg"></i>
                                        <span>{headerUser}</span>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => setShowNavigationDrawer(true)}
                                        className="inline-flex lg:hidden items-center justify-center h-10 w-10 rounded-full border border-slate-200 text-slate-600 hover:bg-slate-100"
                                        aria-label="Abrir menú"
                                    >
                                        <i className="fas fa-bars"></i>
                                    </button>
                                    <a
                                        href="/auth/logout"
                                        className="inline-flex items-center gap-2 rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-red-50 hover:text-red-600 transition-colors"
                                    >
                                        <i className="fas fa-sign-out-alt"></i>
                                        Cerrar sesión
                                    </a>
                                </div>
                            </div>
                        </div>
                        <div className="xl:hidden px-4 pb-3">
                            <nav className="flex flex-wrap items-center gap-3 text-xs font-semibold text-slate-600">
                                {navItems.map((item) => {
                                    const isActive = item.matches.some((path) => currentPath.startsWith(path));
                                    return (
                                        <a
                                            key={`mobile-${item.href}`}
                                            href={item.href}
                                            className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 ${isActive ? 'border-blue-600 text-blue-600 bg-blue-50' : 'border-slate-200 hover:border-blue-300 hover:text-blue-600'}`}
                                        >
                                            <i className={`fas ${item.icon}`}></i>
                                            {item.label}
                                        </a>
                                    );
                                })}
                            </nav>
                        </div>
                    </header>
                    <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                        <header className="page-header">
                            <div className="page-header__content">
                                <div className="page-header__meta">
                                    <h1 className="page-header__title"><span aria-hidden="true">🎤</span> Centro de Gastos por Voz</h1>
                                    <p className="page-header__subtitle">Captura gastos por voz, ticket u OCR, vincula CFDI demo y concilia con tus cuentas bancarias.</p>
                                </div>
                                <div className="page-header__actions">
                                    <span className="badge-secondary">Gasto → Factura → Banco</span>
                                </div>
                            </div>
                        </header>
                    </section>

                    <div className="sticky top-[6.5rem] xl:top-[4.5rem] z-30 border-b bg-white/90 backdrop-blur">
                        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 space-y-4">
                            <div className="flex flex-wrap items-center gap-4">
                                <div>
                                    <span className="block text-xs font-semibold uppercase text-slate-500 mb-1">Empresa activa</span>
                                    <div className="inline-flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
                                        <i className="fas fa-building text-slate-500"></i>
                                        <select
                                            value={companyId}
                                            onChange={(event) => handleCompanyChange(event.target.value)}
                                            className="bg-transparent focus:outline-none"
                                        >
                                            {knownCompanies.map((company) => (
                                                <option key={company} value={company}>{company}</option>
                                            ))}
                                            {!knownCompanies.includes('default') && (
                                                <option value="default">default</option>
                                            )}
                                            <option value="__new__">➕ Registrar empresa…</option>
                                        </select>
                                    </div>
                                </div>
                                <span className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold ${demoMode ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                                    <i className={`fas ${demoMode ? 'fa-rocket' : 'fa-plug'}`}></i>
                                    {demoMode ? 'Demo activa' : 'Empresa real'}
                                </span>
                                <button
                                    type="button"
                                    onClick={() => setShowNavigationDrawer(true)}
                                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100 md:hidden"
                                >
                                    <i className="fas fa-bars"></i>
                                    Accesos rápidos
                                </button>
                                <div className="flex-1 hidden md:block">
                                    <div className="text-xs uppercase text-slate-500">Avance del flujo</div>
                                    <div className="flex items-center gap-3 text-sm">
                                        <strong>{progress.porcentaje}% completado</strong>
                                        <span className="text-slate-500">Faltan {progress.detalles.faltan} pasos</span>
                                    </div>
                                </div>
                            </div>

                            <div className="flex flex-wrap items-center gap-3">
                                <button
                                    onClick={() => {
                                        document.getElementById('capture-mode-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                    }}
                                    className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-slate-800"
                                >
                                    <i className="fas fa-microphone"></i>
                                    Registrar gasto
                                </button>
                                <button
                                    onClick={() => setShowPendingInvoices(true)}
                                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                                >
                                    <i className="fas fa-file-invoice"></i>
                                    Facturas pendientes
                                </button>
                                <button
                                    onClick={() => {
                                        setShowBankReconciliation(true);
                                        markMissionComplete('3');
                                    }}
                                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                                >
                                    <i className="fas fa-wallet"></i>
                                    Cuentas de Banco y Efectivo
                                </button>
                                <div className="relative">
                                    <button
                                        onClick={() => setMoreActionsOpen((open) => !open)}
                                        aria-haspopup="true"
                                        aria-expanded={moreActionsOpen}
                                        className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                                    >
                                        <i className="fas fa-ellipsis-h"></i>
                                        Más opciones
                                    </button>
                                    {moreActionsOpen && (
                                        <div className="absolute left-0 mt-2 w-60 rounded-2xl border border-slate-200 bg-white text-slate-700 shadow-xl z-20">
                                            <ul className="py-2 text-sm">
                                                <li>
                                                    <button
                                                        onClick={() => {
                                                            setShowInvoiceUpload(true);
                                                            setMoreActionsOpen(false);
                                                        }}
                                                        className="flex w-full items-center gap-3 px-4 py-2 hover:bg-slate-100"
                                                    >
                                                        <i className="fas fa-upload text-emerald-500"></i>
                                                        Cargar facturas demo
                                                    </button>
                                                </li>
                                                <li>
                                                    <button
                                                        onClick={() => {
                                                            setShowReconciliation(true);
                                                            setMoreActionsOpen(false);
                                                        }}
                                                        className="flex w-full items-center gap-3 px-4 py-2 hover:bg-slate-100"
                                                    >
                                                        <i className="fas fa-balance-scale text-purple-500"></i>
                                                        Conciliar gastos
                                                    </button>
                                                </li>
                                                <li>
                                                    <button
                                                        onClick={() => {
                                                            setShowCompletenessView(true);
                                                            setMoreActionsOpen(false);
                                                        }}
                                                        className="flex w-full items-center gap-3 px-4 py-2 hover:bg-slate-100"
                                                    >
                                                        <i className="fas fa-clipboard-check text-indigo-500"></i>
                                                        Vista contable
                                                    </button>
                                                </li>
                                                <li>
                                                    <button
                                                        onClick={() => {
                                                            setShowConversationalAssistant(true);
                                                            setMoreActionsOpen(false);
                                                        }}
                                                        className="flex w-full items-center gap-3 px-4 py-2 hover:bg-slate-100"
                                                    >
                                                        <i className="fas fa-robot text-pink-500"></i>
                                                        Asistente IA
                                                    </button>
                                                </li>
                                            </ul>
                                        </div>
                                    )}
                                </div>
                                <button
                                    onClick={() => setShowExpensesDashboard(true)}
                                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                                >
                                    <i className="fas fa-chart-line"></i>
                                    Abrir tablero demo
                                </button>
                            </div>
                        </div>
                    </div>

                    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
                        <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
                            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-lg font-semibold text-slate-900">Gastos</h3>
                                    <span className="text-sm font-semibold text-blue-600">{expensesData.length}</span>
                                </div>
                                <p className="mt-3 text-sm text-slate-600">Centraliza los gastos que dictas, subes por ticket o capturas manualmente.</p>
                                <button
                                    onClick={() => document.getElementById('capture-mode-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                                    className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-[#11446e] hover:text-[#0b3050]"
                                >
                                    <i className="fas fa-arrow-right"></i>
                                    Abrir captura
                                </button>
                            </div>
                            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-lg font-semibold text-slate-900">Facturas</h3>
                                    <span className="text-sm font-semibold text-emerald-600">{invoiceCounts.facturado || 0}</span>
                                </div>
                                <p className="mt-3 text-sm text-slate-600">Adjunta CFDI demo o revisa las pendientes antes de conciliar en bancos.</p>
                                <button
                                    onClick={() => setShowPendingInvoices(true)}
                                    className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-emerald-600 hover:text-emerald-700"
                                >
                                    <i className="fas fa-file-invoice"></i>
                                    Ver pendientes
                                </button>
                            </div>
                            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-lg font-semibold text-slate-900">Cuentas de Banco y Efectivo</h3>
                                    <span className="text-sm font-semibold text-purple-600">{bankCounts.reconciled}/{expensesData.length}</span>
                                </div>
                                <p className="mt-3 text-sm text-slate-600">Conciliación demo lista para ilustrar cómo se relacionan pagos y gastos.</p>
                                <button
                                    onClick={() => setShowBankReconciliation(true)}
                                    className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-purple-600 hover:text-purple-700"
                                >
                                    <i className="fas fa-university"></i>
                                    Revisar conciliación
                                </button>
                            </div>
                        </section>

                    {demoMode && activeMission && missionDetails[activeMission] && (
                        (() => {
                            const mission = missionDetails[activeMission];
                            const missionCompleted = completedMissions.includes(activeMission);
                            return (
                                <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 text-left space-y-4">
                                    <div className="flex items-start justify-between gap-3">
                                        <div>
                                            <p className="text-sm font-semibold text-blue-700">Guía del demo</p>
                                            <h3 className="text-lg font-bold text-slate-900">🎯 {mission.title}</h3>
                                            <p className="text-sm text-slate-600">{mission.description}</p>
                                        </div>
                                        <button
                                            type="button"
                                            className="text-slate-400 hover:text-slate-600"
                                            aria-label="Ocultar guía de misión"
                                            onClick={() => goToMission(null)}
                                        >
                                            <i className="fas fa-times"></i>
                                        </button>
                                    </div>
                                    <ul className="space-y-1 text-sm text-slate-600 list-disc list-inside">
                                        {mission.steps.map((step, index) => (
                                            <li key={index}>{step}</li>
                                        ))}
                                    </ul>
                                    <div className="flex flex-wrap items-center gap-3">
                                        {mission.action && (
                                            <button
                                                type="button"
                                                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700"
                                                onClick={() => handleMissionAction(activeMission)}
                                            >
                                                <i className="fas fa-location-arrow"></i>
                                                {mission.ctaLabel}
                                            </button>
                                        )}
                                        <button
                                            type="button"
                                            className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold ${missionCompleted ? 'bg-emerald-100 text-emerald-700 cursor-default' : 'bg-emerald-500 text-white hover:bg-emerald-600'}`}
                                            onClick={() => markMissionComplete(activeMission)}
                                            disabled={missionCompleted}
                                        >
                                            <i className={`fas ${missionCompleted ? 'fa-check' : 'fa-flag-checkered'}`}></i>
                                            {missionCompleted ? 'Misión completada' : 'Marcar misión como completada'}
                                        </button>
                                        {mission.next && (
                                            <button
                                                type="button"
                                                className="inline-flex items-center gap-2 px-4 py-2 bg-slate-200 text-slate-700 rounded-lg text-sm font-semibold hover:bg-slate-300"
                                                onClick={() => goToMission(mission.next)}
                                            >
                                                <i className="fas fa-arrow-right"></i>
                                                Ir a misión {mission.next}
                                            </button>
                                        )}
                                        <button
                                            type="button"
                                            className="inline-flex items-center gap-2 text-sm text-blue-600 hover:underline"
                                            onClick={() => { window.location.href = '/onboarding'; }}
                                        >
                                            <i className="fas fa-arrow-left"></i>
                                            Volver al onboarding
                                        </button>
                                    </div>
                                    {missionCompleted && (
                                        <p className="text-xs text-emerald-600">¡Excelente! Marca la misión como completada en el onboarding o continúa con la siguiente misión.</p>
                                    )}
                                </div>
                            );
                        })()
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        <div className="bg-white border border-gray-200 rounded-lg p-4 text-left">
                            <p className="text-xs text-gray-500 uppercase tracking-wide">Gastos demo</p>
                            <p className="text-2xl font-bold text-gray-900">{expensesData.length}</p>
                        </div>
                        <div className="bg-white border border-gray-200 rounded-lg p-4 text-left">
                            <p className="text-xs text-gray-500 uppercase tracking-wide">Facturados</p>
                            <p className="text-lg font-semibold text-emerald-600">{invoiceCounts.facturado || 0}</p>
                            <p className="text-xs text-emerald-700">Pendientes: {invoiceCounts.pendiente || 0}</p>
                        </div>
                        <div className="bg-white border border-gray-200 rounded-lg p-4 text-left">
                            <p className="text-xs text-gray-500 uppercase tracking-wide">Sin factura</p>
                            <p className="text-lg font-semibold text-amber-600">{invoiceCounts['sin_factura'] || 0}</p>
                            <p className="text-xs text-amber-700">Idea: completa misión 2</p>
                        </div>
                        <div className="bg-white border border-gray-200 rounded-lg p-4 text-left">
                            <p className="text-xs text-gray-500 uppercase tracking-wide">Conciliación bancaria</p>
                            <p className="text-lg font-semibold text-blue-700">{bankCounts.reconciled} conciliados</p>
                            <p className="text-xs text-slate-600">Pendientes: {bankCounts.pending}</p>
                        </div>
                    </div>

                    {/* Selección de método de entrada */}
                    <div id="capture-mode-section" className="bg-white rounded-lg shadow-md p-6 sm:p-8">
                        <div className="text-center space-y-6">
                            <h3 className="text-xl font-semibold text-gray-800">Elige cómo quieres registrar el gasto</h3>

                            {/* Botones de selección de modo */}
                            <div className="flex flex-col sm:flex-row sm:justify-center gap-3 sm:gap-4">
                                <button
                                    onClick={() => setInputMode('voice')}
                                    className={`flex flex-col items-center w-full sm:w-auto sm:min-w-[180px] px-5 py-5 sm:px-6 sm:py-6 rounded-lg border-2 transition-all ${
                                        inputMode === 'voice'
                                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                                        : 'border-gray-300 bg-white text-gray-600 hover:border-blue-300'
                                    }`}
                                >
                                    <i className="fas fa-microphone text-3xl mb-2"></i>
                                    <span className="font-medium">Voz (dictado)</span>
                                    <span className="text-xs text-center">Habla y nosotros llenamos el gasto</span>
                                </button>

                                <button
                                    onClick={() => setInputMode('ocr')}
                                    className={`flex flex-col items-center w-full sm:w-auto sm:min-w-[180px] px-5 py-5 sm:px-6 sm:py-6 rounded-lg border-2 transition-all ${
                                        inputMode === 'ocr'
                                        ? 'border-green-500 bg-green-50 text-green-700'
                                        : 'border-gray-300 bg-white text-gray-600 hover:border-green-300'
                                    }`}
                                >
                                    <i className="fas fa-camera text-3xl mb-2"></i>
                                    <span className="font-medium">Subir ticket (OCR)</span>
                                    <span className="text-xs text-center">Leemos tickets y facturas automáticamente</span>
                                </button>

                                <button
                                    onClick={() => setInputMode('text')}
                                    className={`flex flex-col items-center w-full sm:w-auto sm:min-w-[180px] px-5 py-5 sm:px-6 sm:py-6 rounded-lg border-2 transition-all ${
                                        inputMode === 'text'
                                        ? 'border-purple-500 bg-purple-50 text-purple-700'
                                        : 'border-gray-300 bg-white text-gray-600 hover:border-purple-300'
                                    }`}
                                >
                                    <i className="fas fa-keyboard text-3xl mb-2"></i>
                                    <span className="font-medium">Texto (manual)</span>
                                    <span className="text-xs text-center">Escribe los datos directamente</span>
                                </button>
                            </div>

                            {/* Área específica según el modo */}
                            <div className="mt-8">
                                {inputMode === 'voice' && (
                                    <div className="space-y-4">
                                        <div className="relative flex justify-center">
                                            <button
                                                onClick={handleToggleRecording}
                                                className={`w-20 h-20 rounded-full flex items-center justify-center text-white text-2xl transition-all duration-200 ${
                                                    isRecording
                                                        ? 'bg-red-500 recording-ring'
                                                        : 'bg-blue-500 hover:bg-blue-600'
                                                }`}
                                            >
                                                <i className={isRecording ? "fas fa-stop" : "fas fa-microphone"}></i>
                                            </button>

                                            {isRecording && (
                                                <div className="absolute inset-0 border-4 border-red-300 rounded-full animate-ping"></div>
                                            )}
                                        </div>
                                        <div className="space-y-2">
                                            <p className={`text-lg font-medium ${
                                                isRecording ? 'text-red-600' : 'text-gray-700'
                                            }`}>
                                                {isRecording ? '🎤 Escuchando...' : '🎤 Haz clic para grabar'}
                                            </p>
                                            <p className="text-sm text-gray-500">
                                                {isRecording
                                                    ? 'Describe tu gasto de manera natural'
                                                    : 'Ejemplo: "Gasto de gasolina de 500 pesos en Pemex"'
                                                }
                                            </p>
                                        </div>
                                    </div>
                                )}

                                {inputMode === 'ocr' && (
                                    <div className="space-y-4">
                                        <div className="border-2 border-dashed border-green-300 rounded-lg p-5 sm:p-8 bg-green-50">
                                            <input
                                                type="file"
                                                id="ocr-file-upload"
                                                accept="image/*,.pdf,.heic,.heif"
                                                className="hidden"
                                                onChange={(e) => {
                                                    const file = e.target.files[0];
                                                    if (file) handleOcrUpload(file);
                                                }}
                                            />
                                            <label htmlFor="ocr-file-upload" className="cursor-pointer block text-center">
                                                {isUploading ? (
                                                    <div>
                                                        <i className="fas fa-spinner fa-spin text-4xl text-green-500 mb-4"></i>
                                                        <p className="text-lg font-medium text-green-700">Procesando con OCR...</p>
                                                        <p className="text-sm text-green-600">Extrayendo campos del documento</p>
                                                    </div>
                                                ) : (
                                                    <div>
                                                        <i className="fas fa-cloud-upload-alt text-4xl text-green-500 mb-4"></i>
                                                        <p className="text-lg font-medium text-green-700">Subir Ticket o Factura</p>
                                                        <p className="text-sm text-green-600">Soporta JPG, PNG, HEIC, PDF hasta 10MB</p>
                                                        <p className="text-xs text-gray-500 mt-2">OCR detectará automáticamente proveedor, RFC, fecha y montos</p>
                                                    </div>
                                                )}
                                            </label>
                                        </div>
                                        {ocrResult && (
                                            <div className="space-y-3">
                                                <div className="bg-green-100 border border-green-300 rounded-lg p-4">
                                                    <div className="flex items-center gap-2 mb-2">
                                                        <i className="fas fa-check-circle text-green-600"></i>
                                                        <span className="font-medium text-green-800">OCR Completado</span>
                                                        <span className="text-sm text-green-600">
                                                            Confianza: {Math.round((ocrResult.ocr_confidence || 0) * 100)}%
                                                        </span>
                                                    </div>
                                                    <p className="text-sm text-green-700">{ocrResult.message}</p>
                                                </div>

                                                {/* ✅ NUEVO PANEL DE INTELIGENCIA */}
                                                {ocrResult.fields && (
                                                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                                                        <div className="flex items-center gap-2 mb-3">
                                                            <i className="fas fa-brain text-blue-600"></i>
                                                            <span className="font-medium text-blue-800">Inteligencia Aplicada</span>
                                                        </div>

                                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                                                            {ocrResult.fields.categoria && (
                                                                <div className="flex items-center gap-2">
                                                                    <i className="fas fa-tag text-blue-500"></i>
                                                                    <span className="text-gray-600">Categoría:</span>
                                                                    <span className="font-medium text-blue-700">{ocrResult.fields.categoria}</span>
                                                                    {ocrResult.fields.confianza_categoria && (
                                                                        <span className="text-xs bg-blue-200 text-blue-800 px-2 py-1 rounded">
                                                                            {Math.round(ocrResult.fields.confianza_categoria * 100)}%
                                                                        </span>
                                                                    )}
                                                                </div>
                                                            )}

                                                            {ocrResult.fields.forma_pago && (
                                                                <div className="flex items-center gap-2">
                                                                    <i className="fas fa-credit-card text-blue-500"></i>
                                                                    <span className="text-gray-600">Forma de pago:</span>
                                                                    <span className="font-medium text-blue-700">{ocrResult.fields.forma_pago}</span>
                                                                </div>
                                                            )}

                                                            {ocrResult.fields.validacion_rfc && (
                                                                <div className="flex items-center gap-2">
                                                                    <i className={`fas ${ocrResult.fields.validacion_rfc.valido ? 'fa-check-circle text-green-500' : 'fa-exclamation-circle text-yellow-500'}`}></i>
                                                                    <span className="text-gray-600">RFC:</span>
                                                                    <span className={`font-medium ${ocrResult.fields.validacion_rfc.valido ? 'text-green-700' : 'text-yellow-700'}`}>
                                                                        {ocrResult.fields.validacion_rfc.mensaje}
                                                                    </span>
                                                                </div>
                                                            )}

                                                            {ocrResult.fields.iva_desglosado && (
                                                                <div className="flex items-center gap-2">
                                                                    <i className="fas fa-calculator text-blue-500"></i>
                                                                    <span className="text-gray-600">IVA:</span>
                                                                    <span className="font-medium text-blue-700">
                                                                        ${ocrResult.fields.iva_desglosado.subtotal} + ${ocrResult.fields.iva_desglosado.iva} ({ocrResult.fields.iva_desglosado.tasa_iva}%)
                                                                    </span>
                                                                </div>
                                                            )}
                                                        </div>

                                                        {ocrResult.fields.descripcion_inteligente && (
                                                            <div className="mt-3 pt-3 border-t border-blue-200">
                                                                <div className="flex items-start gap-2">
                                                                    <i className="fas fa-lightbulb text-blue-500 mt-1"></i>
                                                                    <div>
                                                                        <span className="text-gray-600 text-sm">Descripción inteligente:</span>
                                                                        <p className="font-medium text-blue-700">{ocrResult.fields.descripcion_inteligente}</p>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                )}

                                {inputMode === 'text' && (
                                    <div className="space-y-4">
                                        <div className="bg-purple-50 rounded-lg p-6">
                                            <textarea
                                                placeholder="Escribe la información del gasto...
Ejemplo: 'Compra de gasolina por 500 pesos en Pemex, pagado con tarjeta de empresa'"
                                                className="w-full h-32 p-4 border border-purple-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-purple-500"
                                                onChange={(e) => {
                                                    if (e.target.value.trim()) {
                                                        handleTextInput(e.target.value);
                                                    }
                                                }}
                                            />
                                            <div className="mt-3 text-center">
                                                <button
                                                    onClick={() => {
                                                        const textarea = document.querySelector('textarea');
                                                        if (textarea.value.trim()) {
                                                            handleTextInput(textarea.value);
                                                        }
                                                    }}
                                                    className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                                                >
                                                    <i className="fas fa-magic mr-2"></i>
                                                    Procesar Texto
                                                </button>
                                            </div>
                                        </div>
                                        <div className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3">
                                            <p className="font-medium mb-1">💡 Consejos:</p>
                                            <ul className="text-xs space-y-1">
                                                <li>• Incluye el monto: "500 pesos", "$1,200"</li>
                                                <li>• Menciona el proveedor: "Pemex", "Oxxo", "Liverpool"</li>
                                                <li>• Indica el método de pago: "tarjeta empresa", "efectivo"</li>
                                            </ul>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Layout principal */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Columna izquierda: Transcripción */}
                        <div className="lg:col-span-1 space-y-6">
                            {/* Transcripción en vivo */}
                            <div className="bg-white rounded-lg shadow-md p-4">
                                <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center gap-2">
                                    <i className="fas fa-microphone text-gray-500"></i>
                                    Transcripción en Vivo
                                </h3>

                                <div className="h-32 overflow-y-auto bg-gray-50 p-3 rounded border">
                                    {transcript ? (
                                        <p className="text-gray-700">{transcript}</p>
                                    ) : (
                                        <p className="text-gray-400 text-center">
                                            {isRecording ? 'Comienza a hablar...' : 'Esperando transcripción...'}
                                        </p>
                                    )}
                                </div>
                            </div>

                            {/* Resumen detectado */}
                            {currentSummary && (
                                <div className="bg-white rounded-lg shadow-md p-4 border-l-4 border-blue-400">
                                    <h3 className="text-lg font-medium text-gray-900 mb-2">
                                        Resumen Detectado
                                    </h3>
                                    <p className="text-gray-700 mb-3">{currentSummary}</p>
                                    <div className="flex items-center gap-2">
                                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                            summaryConfidence >= 0.8 ? 'bg-green-100 text-green-800' :
                                            summaryConfidence >= 0.5 ? 'bg-yellow-100 text-yellow-800' :
                                            'bg-red-100 text-red-800'
                                        }`}>
                                            {summaryConfidence >= 0.8 ? 'Alta confianza' :
                                             summaryConfidence >= 0.5 ? 'Confianza media' : 'Baja confianza'}
                                        </span>
                                        <span className="text-xs text-gray-500">
                                            {Math.round(summaryConfidence * 100)}%
                                        </span>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Columna derecha: Progreso y campos */}
                        <div className="lg:col-span-2 space-y-6">
                            {/* Barra de progreso */}
                            <div className="bg-white rounded-lg shadow-md p-4">
                                <div className="flex items-center justify-between mb-3">
                                    <h3 className="text-lg font-medium text-gray-900">Progreso de Completitud</h3>
                                    <div className="text-right">
                                        <div className="text-2xl font-bold text-gray-900">{progress.porcentaje}%</div>
                                        <div className="text-sm text-gray-500">
                                            {progress.detalles.score}/{progress.detalles.total} campos
                                        </div>
                                    </div>
                                </div>

                                <div className="mb-4">
                                    <div className={`w-full h-3 rounded-full ${
                                        progress.porcentaje >= 80 ? 'bg-green-50' : progress.porcentaje >= 50 ? 'bg-yellow-50' : 'bg-red-50'
                                    }`}>
                                        <div
                                            className={`h-3 rounded-full transition-all duration-500 ${
                                                progress.porcentaje >= 80 ? 'bg-green-500' : progress.porcentaje >= 50 ? 'bg-yellow-500' : 'bg-red-500'
                                            }`}
                                            style={{ width: `${progress.porcentaje}%` }}
                                        />
                                    </div>
                                </div>

                                <div className="text-center text-sm text-gray-600">
                                    {progress.porcentaje >= 80 ? 'Listo para enviar' :
                                     progress.porcentaje >= 50 ? 'En progreso' : 'Necesita más información'}
                                </div>
                            </div>

                            {/* Campos del formulario */}
                            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                                {/* Campos capturados */}
                                <div className="bg-white rounded-lg shadow-md p-4">
                                    <div className="flex items-center justify-between mb-4">
                                        <h3 className="text-lg font-medium text-gray-900 flex items-center gap-2">
                                            <i className="fas fa-check-circle text-green-500"></i>
                                            Campos Capturados
                                        </h3>
                                        {/* Indicador del sistema interno */}
                                        <div className="bg-blue-50 border border-blue-200 rounded-lg px-2 py-1">
                                            <div className="flex items-center gap-2">
                                                <i className="fas fa-database text-blue-600 text-xs"></i>
                                                <span className="text-xs text-blue-700 font-medium">
                                                    {expensesData.length} gastos registrados
                                                </span>
                                                <button
                                                    onClick={handleRegenerateDummyData}
                                                    className="text-xs text-blue-600 hover:text-blue-800 ml-2"
                                                    title="Regenerar datos de prueba"
                                                >
                                                    🔄
                                                </button>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="space-y-3">
                                        {Object.entries(EXPENSE_FIELDS).map(([fieldKey, fieldConfig]) => {
                                            const value = getFieldValue(fieldKey);
                                            const confidence = getFieldConfidence(fieldKey);

                                            if (!value) return null;

                                            // Formatear el valor para mostrar de manera más legible
                                            let displayValue = value;
                                            if (fieldKey === 'monto_total' && typeof value === 'number') {
                                                displayValue = `$${value.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                                            } else if (fieldKey === 'fecha_gasto' && value) {
                                                const date = new Date(value);
                                                displayValue = date.toLocaleDateString('es-MX', {
                                                    year: 'numeric', month: 'long', day: 'numeric'
                                                });
                                            } else if (fieldKey === 'will_have_cfdi') {
                                                displayValue = value ? 'Sí, habrá factura (CFDI)' : 'No, sin factura';
                                            } else if (fieldKey === 'paid_by') {
                                                displayValue = value === 'company_account' ? 'Empresa (tarjeta corporativa)' : 'Empleado (reembolso)';
                                            } else if (typeof value === 'object') {
                                                displayValue = JSON.stringify(value);
                                            } else {
                                                displayValue = String(value);
                                            }

                                            return (
                                                <div key={fieldKey} className="border rounded-lg p-3 bg-green-50 border-green-200">
                                                    <div className="flex items-start justify-between">
                                                        <div className="flex-1">
                                                            <div className="flex items-center gap-2 mb-1">
                                                                <span className="text-sm font-medium text-gray-900">
                                                                    {fieldConfig.name}
                                                                </span>
                                                                {fieldConfig.required && (
                                                                    <span className="text-red-500 text-xs">*</span>
                                                                )}
                                                                {formData._ocrIntakeId && (
                                                                    <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">
                                                                        OCR
                                                                    </span>
                                                                )}
                                                            </div>
                                                            <div className="text-base font-medium text-green-700">
                                                                {displayValue}
                                                            </div>
                                                            {confidence > 0 && (
                                                                <div className="text-xs text-gray-500 mt-1 flex items-center gap-1">
                                                                    <div className={`w-2 h-2 rounded-full ${
                                                                        confidence >= 0.8 ? 'bg-green-500' :
                                                                        confidence >= 0.6 ? 'bg-yellow-500' : 'bg-red-500'
                                                                    }`}></div>
                                                                    {Math.round(confidence * 100)}% confianza
                                                                </div>
                                                            )}
                                                        </div>
                                                        <button
                                                            onClick={() => {
                                                                let currentValue = value;
                                                                if (fieldKey === 'will_have_cfdi') {
                                                                    currentValue = value ? 'true' : 'false';
                                                                } else if (fieldKey === 'paid_by') {
                                                                    currentValue = value;
                                                                }

                                                                const newValue = prompt(`Editar ${fieldConfig.name}:`, String(currentValue));
                                                                if (newValue !== null && newValue !== String(currentValue)) {
                                                                    let processedValue = newValue;
                                                                    if (fieldKey === 'monto_total') {
                                                                        processedValue = parseFloat(newValue.replace(/[$,]/g, '')) || 0;
                                                                    } else if (fieldKey === 'will_have_cfdi') {
                                                                        processedValue = newValue.toLowerCase() === 'true';
                                                                    }
                                                                    handleFieldChange(fieldKey, processedValue);
                                                                }
                                                            }}
                                                            className="px-2 py-1 text-xs text-blue-600 bg-blue-50 border border-blue-200 rounded hover:bg-blue-100 transition-colors"
                                                        >
                                                            <i className="fas fa-edit mr-1"></i>
                                                            Editar
                                                        </button>
                                                    </div>
                                                </div>
                                            );
                                        })}

                                        {Object.keys(formData).filter(k => !k.startsWith('_')).length === 0 && (
                                            <div className="text-center py-8">
                                                <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
                                                    <i className="fas fa-microphone text-gray-400 text-2xl"></i>
                                                </div>
                                                <p className="text-gray-500 text-sm">
                                                    Aún no se han capturado campos del gasto
                                                </p>
                                                <p className="text-gray-400 text-xs mt-1">
                                                    Usa el micrófono para dictar la información
                                                </p>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* Campos faltantes */}
                                <div className="bg-white rounded-lg shadow-md p-4">
                                    <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center gap-2">
                                        <i className="fas fa-list text-orange-500"></i>
                                        Campos Pendientes
                                    </h3>

                                    <div className="space-y-4">
                                        {Object.entries(EXPENSE_FIELDS).map(([fieldKey, fieldConfig]) => {
                                            const value = getFieldValue(fieldKey);

                                            if (value) return null;

                                            return (
                                                <div key={fieldKey} className={`border rounded-lg p-3 ${
                                                    fieldConfig.required ? 'border-orange-200 bg-orange-50' : 'border-gray-200 bg-gray-50'
                                                }`}>
                                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                                        {fieldConfig.name}
                                                        {fieldConfig.required && <span className="text-red-500 ml-1">*</span>}
                                                    </label>

                                                    {fieldConfig.type === 'select' ? (
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
                                                            {fieldKey === 'categoria' && (
                                                                <div className="mt-2 space-y-2">
                                                                    {isPredictingCategory && (
                                                                        <div className="flex items-center text-xs text-blue-600">
                                                                            <i className="fas fa-robot fa-spin mr-2"></i>
                                                                            Prediciendo categoría con IA...
                                                                        </div>
                                                                    )}

                                                                    {categoryPrediction && !value && categoryPrediction.confianza < 0.8 && (
                                                                        <div className="p-2 bg-blue-50 rounded-md border border-blue-200">
                                                                            <div className="text-xs font-medium text-blue-800 mb-1">
                                                                                🤖 IA sugiere: {categoryPrediction.categoria_sugerida}
                                                                                <span className="ml-1 text-blue-600">
                                                                                    ({Math.round(categoryPrediction.confianza * 100)}% confianza)
                                                                                </span>
                                                                            </div>
                                                                            <div className="text-xs text-blue-700 mb-2">
                                                                                {categoryPrediction.razonamiento}
                                                                            </div>
                                                                            <button
                                                                                onClick={() => {
                                                                                    handleFieldChange('categoria', categoryPrediction.categoria_sugerida);
                                                                                    setCategoryPrediction(null);
                                                                                }}
                                                                                className="px-2 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 mr-2"
                                                                            >
                                                                                ✅ Aplicar
                                                                            </button>
                                                                            <button
                                                                                onClick={() => setCategoryPrediction(null)}
                                                                                className="px-2 py-1 bg-gray-400 text-white text-xs rounded hover:bg-gray-500"
                                                                            >
                                                                                ❌ Rechazar
                                                                            </button>

                                                                            {categoryPrediction.alternativas && categoryPrediction.alternativas.length > 0 && (
                                                                                <div className="mt-2">
                                                                                    <div className="text-xs text-blue-700 mb-1">Alternativas:</div>
                                                                                    <div className="flex flex-wrap gap-1">
                                                                                        {categoryPrediction.alternativas.map((alt, idx) => (
                                                                                            <button
                                                                                                key={idx}
                                                                                                onClick={() => {
                                                                                                    handleFieldChange('categoria', alt.categoria);
                                                                                                    setCategoryPrediction(null);
                                                                                                }}
                                                                                                className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded hover:bg-blue-200"
                                                                                                title={alt.razon}
                                                                                            >
                                                                                                {alt.categoria} ({Math.round(alt.confianza * 100)}%)
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
                                                            )}
                                                        </div>
                                                    ) : fieldConfig.type === 'number' ? (
                                                        <input
                                                            type="number"
                                                            value={value || ''}
                                                            onChange={(e) => handleFieldChange(fieldKey, parseFloat(e.target.value) || 0)}
                                                            placeholder={fieldConfig.placeholder}
                                                            className="w-full p-2 border border-gray-300 rounded-md text-sm"
                                                            step="0.01"
                                                            min="0"
                                                        />
                                                    ) : fieldConfig.type === 'date' ? (
                                                        <input
                                                            type="date"
                                                            value={value || ''}
                                                            onChange={(e) => handleFieldChange(fieldKey, e.target.value)}
                                                            className="w-full p-2 border border-gray-300 rounded-md text-sm"
                                                            max={new Date().toISOString().split('T')[0]}
                                                        />
                                                    ) : fieldConfig.type === 'textarea' ? (
                                                        <textarea
                                                            value={value || ''}
                                                            onChange={(e) => handleFieldChange(fieldKey, e.target.value)}
                                                            placeholder={fieldConfig.placeholder}
                                                            className="w-full p-2 border border-gray-300 rounded-md text-sm"
                                                            rows="3"
                                                        />
                                                    ) : (
                                                        <input
                                                            type="text"
                                                            value={value || ''}
                                                            onChange={(e) => handleFieldChange(fieldKey, e.target.value)}
                                                            placeholder={fieldConfig.placeholder}
                                                            className="w-full p-2 border border-gray-300 rounded-md text-sm"
                                                        />
                                                    )}

                                                    {fieldConfig.help && (
                                                        <p className="text-xs text-gray-500 mt-1">{fieldConfig.help}</p>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Sección de adjuntar archivos */}
                    <div className="bg-white border border-gray-200 rounded-lg shadow-md p-6">
                        <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center gap-2">
                            <i className="fas fa-paperclip text-blue-500"></i>
                            Adjuntar Comprobantes
                        </h3>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {/* Adjuntar Ticket/Foto */}
                            <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-blue-400 transition-colors">
                                <input
                                    type="file"
                                    id="ticket-upload"
                                    accept="image/*,.pdf,.heic,.heif"
                                    className="hidden"
                                    onChange={(e) => {
                                        const file = e.target.files[0];
                                        if (file) {
                                            handleFieldChange('ticket_file', file.name);
                                            // Aquí iría la lógica para subir el archivo
                                        }
                                    }}
                                />
                                <label htmlFor="ticket-upload" className="cursor-pointer block">
                                    <i className="fas fa-camera text-3xl text-gray-400 mb-2"></i>
                                    <p className="text-sm font-medium text-gray-700">Foto del Ticket</p>
                                    <p className="text-xs text-gray-500 mt-1">JPG, PNG, HEIC, PDF hasta 10MB</p>
                                </label>
                                {getFieldValue('ticket_file') && (
                                    <div className="mt-2 text-xs text-green-600">
                                        <i className="fas fa-check mr-1"></i>
                                        {getFieldValue('ticket_file')}
                                    </div>
                                )}
                            </div>

                            {/* Adjuntar XML */}
                            <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-green-400 transition-colors">
                                <input
                                    type="file"
                                    id="xml-upload"
                                    accept=".xml"
                                    className="hidden"
                                    onChange={(e) => {
                                        const file = e.target.files[0];
                                        if (file) {
                                            handleXmlUpload(file);
                                        }
                                    }}
                                />
                                <label htmlFor="xml-upload" className="cursor-pointer block">
                                    <i className="fas fa-file-code text-3xl text-gray-400 mb-2"></i>
                                    <p className="text-sm font-medium text-gray-700">XML Factura</p>
                                    <p className="text-xs text-gray-500 mt-1">Archivo XML CFDI</p>
                                </label>
                                {getFieldValue('xml_file') && (
                                    <div className="mt-2 text-xs text-green-600">
                                        <i className="fas fa-check mr-1"></i>
                                        {getFieldValue('xml_file')}
                                    </div>
                                )}
                            </div>

                            {/* Adjuntar PDF */}
                            <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-red-400 transition-colors">
                                <input
                                    type="file"
                                    id="pdf-upload"
                                    accept=".pdf"
                                    className="hidden"
                                    onChange={(e) => {
                                        const file = e.target.files[0];
                                        if (file) {
                                            handleFieldChange('pdf_file', file.name);
                                            // Aquí iría la lógica para subir el PDF
                                        }
                                    }}
                                />
                                <label htmlFor="pdf-upload" className="cursor-pointer block">
                                    <i className="fas fa-file-pdf text-3xl text-gray-400 mb-2"></i>
                                    <p className="text-sm font-medium text-gray-700">PDF Factura</p>
                                    <p className="text-xs text-gray-500 mt-1">Representación impresa</p>
                                </label>
                                {getFieldValue('pdf_file') && (
                                    <div className="mt-2 text-xs text-green-600">
                                        <i className="fas fa-check mr-1"></i>
                                        {getFieldValue('pdf_file')}
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="mt-4 bg-blue-50 border border-blue-200 rounded-lg p-3">
                            <div className="flex items-start gap-2">
                                <i className="fas fa-info-circle text-blue-500 mt-0.5"></i>
                                <div className="text-sm text-blue-700">
                                    <p className="font-medium">Tipos de comprobantes:</p>
                                    <ul className="mt-1 text-xs space-y-1">
                                        <li>• <strong>Ticket:</strong> Foto del comprobante o nota de venta</li>
                                        <li>• <strong>XML:</strong> Archivo CFDI para gastos con factura</li>
                                        <li>• <strong>PDF:</strong> Representación impresa de la factura</li>
                                    </ul>
                                </div>
                            </div>
                        </div>

                        {invoiceParsing.status === 'loading' && (
                            <div className="mt-4 bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm text-yellow-800 flex items-center gap-2">
                                <i className="fas fa-spinner fa-spin"></i>
                                Analizando CFDI {invoiceParsing.filename || ''}...
                            </div>
                        )}

                        {invoiceParsing.status === 'error' && (
                            <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 flex items-center gap-2">
                                <i className="fas fa-triangle-exclamation"></i>
                                {invoiceParsing.message || 'No se pudo interpretar el CFDI. Intenta nuevamente.'}
                            </div>
                        )}

                        {formData.tax_info && (
                            <div className="mt-4 bg-green-50 border border-green-200 rounded-lg p-4 text-sm text-green-800">
                                <div className="flex items-center justify-between mb-2">
                                    <h4 className="font-medium">IVA e impuestos detectados del CFDI</h4>
                                    {formData.tax_info.uuid && (
                                        <span className="text-xs text-green-600">UUID: {formData.tax_info.uuid}</span>
                                    )}
                                </div>
                                <div className="grid grid-cols-2 gap-2 text-xs text-green-700">
                                    <span>Subtotal: <strong>${(formData.tax_info.subtotal || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}</strong></span>
                                    <span>Total: <strong>${(formData.tax_info.total || formData.monto_total || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}</strong></span>
                                    <span>IVA acreditable: <strong>${(formData.tax_info.iva_amount || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}</strong></span>
                                    <span>Otros impuestos: <strong>${(formData.tax_info.other_taxes || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}</strong></span>
                                </div>
                                {Array.isArray(formData.tax_info.taxes) && formData.tax_info.taxes.length > 0 && (
                                    <div className="mt-2 text-xs text-green-700 space-y-1">
                                        {formData.tax_info.taxes.map((tax, idx) => (
                                            <div key={idx} className="flex items-center gap-2">
                                                <i className="fas fa-check text-green-500"></i>
                                                <span>{tax.kind === 'retencion' ? 'Retención' : 'Impuesto'} {tax.type} • {tax.rate ? `${(tax.rate * 100).toFixed(2)}%` : ''} • ${Number(tax.amount || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Footer con acciones */}
                    <div className="bg-white border-t border-gray-200 px-6 py-4 rounded-lg shadow-md">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className="flex items-center gap-2">
                                    <div className={`w-3 h-3 rounded-full ${
                                        missingRequiredFields.length === 0 ? 'bg-green-500' :
                                        progress.porcentaje >= 50 ? 'bg-yellow-500' : 'bg-red-500'
                                    }`} />
                                    <span className="text-sm text-gray-600">
                                        {missingRequiredFields.length === 0 ? 'Listo para enviar' :
                                         progress.porcentaje >= 50 ? 'En progreso' : 'Necesita más información'}
                                    </span>
                                </div>
                                <div className="text-sm text-gray-500">{progress.porcentaje}% completo</div>
                                {missingRequiredFields.length > 0 && (
                                    <div className="text-sm text-red-600">
                                        {missingRequiredFields.length} campos requeridos faltantes
                                    </div>
                                )}
                            </div>

                            <div className="flex items-center gap-3">
                                <button
                                    onClick={handleSaveDraft}
                                    disabled={Object.keys(formData).filter(k => !k.startsWith('_')).length === 0 || isSaving || isSending}
                                    className={`px-4 py-2 text-sm font-medium rounded-md border transition-colors ${
                                        Object.keys(formData).filter(k => !k.startsWith('_')).length > 0 && !isSaving && !isSending
                                            ? 'text-gray-700 bg-white border-gray-300 hover:bg-gray-50'
                                            : 'text-gray-400 bg-gray-100 border-gray-200 cursor-not-allowed'
                                    }`}
                                >
                                    {isSaving ? (
                                        <>
                                            <i className="fas fa-spinner fa-spin mr-2"></i>
                                            Guardando...
                                        </>
                                    ) : (
                                        <>
                                            <i className="fas fa-save mr-2"></i>
                                            Guardar Borrador
                                        </>
                                    )}
                                </button>

                                {demoMode && (
                                    <button
                                        onClick={handleSaveDemoExpense}
                                        className="px-6 py-2 text-sm font-medium text-white bg-emerald-600 rounded-md hover:bg-emerald-700 transition-colors"
                                    >
                                        <i className="fas fa-floppy-disk mr-2"></i>
                                        Guardar gasto demo
                                    </button>
                                )}

                                {!demoMode && (
                                    <button
                                        onClick={handleSendToOdoo}
                                        disabled={missingRequiredFields.length > 0 || isSaving || isSending || isCheckingDuplicates}
                                        className={`px-6 py-2 text-sm font-medium rounded-md transition-colors ${
                                            missingRequiredFields.length === 0 && !isSaving && !isSending && !isCheckingDuplicates
                                                ? 'text-white bg-blue-600 hover:bg-blue-700'
                                                : 'text-gray-400 bg-gray-200 cursor-not-allowed'
                                        }`}
                                    >
                                        {isCheckingDuplicates ? (
                                            <>
                                                <i className="fas fa-search fa-spin mr-2"></i>
                                                Verificando duplicados...
                                            </>
                                        ) : isSending ? (
                                            <>
                                                <i className="fas fa-spinner fa-spin mr-2"></i>
                                                Enviando a Odoo...
                                            </>
                                        ) : (
                                            <>
                                                <i className="fas fa-paper-plane mr-2"></i>
                                                Guardar gasto
                                            </>
                                        )}
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Indicador de guardado */}
                    {lastSaveTime && (
                        <div className="fixed bottom-4 right-4 bg-green-100 border border-green-400 text-green-700 px-4 py-2 rounded-lg shadow-lg slide-in">
                            <div className="flex items-center gap-2">
                                <i className="fas fa-check"></i>
                                <span className="text-sm">
                                    Borrador guardado a las {lastSaveTime.toLocaleTimeString()}
                                </span>
                            </div>
                        </div>
                    )}

                    {/* Modal de Dashboard de Gastos */}
                    {showExpensesDashboard && (
                        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                            <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
                                <div className="p-6 border-b border-gray-200">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <h2 className="text-xl font-bold text-gray-900">Dashboard de Gastos</h2>
                                            <p className="text-gray-600 mt-1">Análisis y resumen de tus gastos empresariales</p>
                                        </div>
                                        <button
                                            onClick={() => setShowExpensesDashboard(false)}
                                            className="text-gray-400 hover:text-gray-600"
                                            aria-label="Cerrar modal de dashboard"
                                        >
                                            <i className="fas fa-times text-xl"></i>
                                        </button>
                                    </div>
                                </div>

                                <DashboardContent
                                    expensesData={expensesData}
                                    selectedMonth={selectedMonth}
                                    setSelectedMonth={setSelectedMonth}
                                    selectedCategoryFilter={selectedCategoryFilter}
                                    setSelectedCategoryFilter={setSelectedCategoryFilter}
                                    categorias={CATEGORIAS_DISPONIBLES}
                                    getCategoryInfo={getCategoryInfo}
                                    onOpenQuickView={setQuickViewExpense}
                                />
                            </div>
                        </div>
                    )}

                    {/* Modal de Facturas Pendientes */}
                    {showPendingInvoices && (
                        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                            <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
                                <div className="p-6 border-b border-gray-200">
                                    <div className="flex items-center justify-between">
                                        <h2 className="text-xl font-bold text-gray-900">Facturas Pendientes</h2>
                                        <button
                                            onClick={() => setShowPendingInvoices(false)}
                                            className="text-gray-400 hover:text-gray-600"
                                            aria-label="Cerrar facturas pendientes"
                                        >
                                            <i className="fas fa-times text-xl"></i>
                                        </button>
                                    </div>
                                </div>

                                <PendingInvoicesContent
                                    expensesData={expensesData}
                                    onRegisterInvoice={registerInvoiceForExpense}
                                    onMarkInvoiced={markExpenseAsInvoiced}
                                    onCloseNoInvoice={closeExpenseWithoutInvoice}
                                    onOpenNonReconciliation={(expense) => {
                                        setSelectedExpenseForNonReconciliation(expense);
                                        setShowNonReconciliationModal(true);
                                    }}
                                />
                            </div>
                        </div>
                    )}

                    {/* Modal de Carga de Facturas */}
                    {showInvoiceUpload && (
                        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                            <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
                                <div className="p-6 border-b border-gray-200">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <h2 className="text-xl font-bold text-gray-900">Carga Masiva de Facturas</h2>
                                            <p className="text-gray-600 mt-1">Sube múltiples facturas para procesamiento automático</p>
                                        </div>
                                        <button
                                            onClick={() => setShowInvoiceUpload(false)}
                                            className="text-gray-400 hover:text-gray-600"
                                            aria-label="Cerrar carga de facturas"
                                        >
                                            <i className="fas fa-times text-xl"></i>
                                        </button>
                                    </div>
                                </div>

                                <InvoiceUploadContent
                                    expensesData={expensesData}
                                    setExpensesData={setExpensesData}
                                    normalizeExpenseFn={normalizeExpense}
                                    companyId={resolvedCompanyId}
                                />
                            </div>
                        </div>
                    )}

                    <p className="mt-10 text-center text-xs text-gray-500">
                        Cuando quieras, cambia de la empresa demo a tu empresa real para registrar gastos auténticos.
                    </p>
                </div>

                {/* Modal de Conciliación */}
                    {showReconciliation && (
                        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                            <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
                                <div className="p-6 border-b border-gray-200">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <h2 className="text-xl font-bold text-gray-900">Conciliador de Gastos</h2>
                                            <p className="text-gray-600 mt-1">Concilia gastos registrados con facturas recibidas</p>
                                        </div>
                                        <button
                                            onClick={() => setShowReconciliation(false)}
                                            className="text-gray-400 hover:text-gray-600"
                                            aria-label="Cerrar conciliación"
                                        >
                                            <i className="fas fa-times text-xl"></i>
                                        </button>
                                    </div>
                                </div>

                                <ReconciliationContent
                                    expensesData={expensesData}
                                    onOpenBulkUpload={() => {
                                        setShowInvoiceUpload(true);
                                    }}
                                />
                            </div>
                        </div>
                    )}

                    {/* Modal de Conciliación Bancaria */}
                    {showBankReconciliation && (
                        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                            <div className="bg-white rounded-lg shadow-xl max-w-5xl w-full max-h-[95vh] overflow-y-auto">
                                <div className="p-6 border-b border-gray-200">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <h2 className="text-xl font-bold text-gray-900">Conciliación bancaria</h2>
                                            <p className="text-gray-600 mt-1">Asocia los gastos conciliados con sus movimientos bancarios.
                                            </p>
                                        </div>
                                        <button
                                            onClick={() => setShowBankReconciliation(false)}
                                            className="text-gray-400 hover:text-gray-600"
                                            aria-label="Cerrar conciliación bancaria"
                                        >
                                            <i className="fas fa-times text-xl"></i>
                                        </button>
                                    </div>
                                </div>

                                <BankReconciliationContent
                                    expensesData={expensesData}
                                    onUpdateExpense={updateExpense}
                                    companyId={resolvedCompanyId}
                                    onMissionComplete={() => {
                                        if (demoMode) {
                                            markMissionComplete('3');
                                            if (activeMission === '3') {
                                                goToMission('4');
                                            }
                                        }
                                    }}
                                />
                            </div>
                        </div>
                    )}

                    {/* Modal de Vista de Completitud y Asientos Contables */}
                    {showCompletenessView && (
                        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                            <div className="bg-white rounded-lg shadow-xl max-w-7xl w-full max-h-[95vh] overflow-y-auto">
                                <div className="p-6 border-b border-gray-200">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <h2 className="text-xl font-bold text-gray-900">Vista Contable y Completitud</h2>
                                            <p className="text-gray-600 mt-1">Revisa el estado contable, asientos y completitud de cada transacción</p>
                                        </div>
                                        <button
                                            onClick={() => setShowCompletenessView(false)}
                                            className="text-gray-400 hover:text-gray-600"
                                            aria-label="Cerrar vista contable"
                                        >
                                            <i className="fas fa-times text-xl"></i>
                                        </button>
                                    </div>
                                </div>

                                <CompletenessView
                                    expensesData={expensesData}
                                    getCategoryInfo={getCategoryInfo}
                                />
                            </div>
                        </div>
                    )}

                    {/* Modal del Asistente Conversacional */}
                    {showConversationalAssistant && (
                        <ConversationalAssistantModal
                            onClose={() => setShowConversationalAssistant(false)}
                        />
                    )}

                    {/* Modal de No Conciliación */}
                    <NonReconciliationModal
                        isOpen={showNonReconciliationModal}
                        onClose={() => setShowNonReconciliationModal(false)}
                        expense={selectedExpenseForNonReconciliation}
                        onSubmit={(result) => {
                            console.log('Non-reconciliation marked:', result);
                            // Aquí podrías actualizar el estado local del gasto
                        }}
                        companyId={resolvedCompanyId}
                    />

                    {quickViewExpense && (
                        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black bg-opacity-50 p-4">
                            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto">
                                <div className="flex items-start justify-between gap-4 border-b border-slate-200 p-6">
                                    <div>
                                        <p className="text-xs uppercase tracking-wide text-slate-500">Estado del gasto</p>
                                        <h2 className="text-2xl font-semibold text-slate-900">{quickViewExpense.descripcion}</h2>
                                        <p className="text-sm text-slate-500">{formatCurrency(quickViewExpense.monto_total)} · {quickViewExpense.fecha_gasto || 'Sin fecha'}</p>
                                    </div>
                                    <button
                                        onClick={() => setQuickViewExpense(null)}
                                        className="text-slate-400 hover:text-slate-600"
                                        aria-label="Cerrar visualizador"
                                    >
                                        <i className="fas fa-times text-xl"></i>
                                    </button>
                                </div>

                                <div className="p-6 space-y-6">
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                        <div className="border border-blue-100 rounded-xl p-3 bg-blue-50">
                                            <p className="text-xs uppercase font-semibold text-blue-600">Factura</p>
                                            <p className="text-sm font-semibold text-blue-800 mt-1 capitalize">{(quickViewExpense.estado_factura || 'pendiente').replace(/_/g, ' ')}</p>
                                            <p className="text-xs text-blue-600 mt-1">
                                                {quickViewExpense.estado_factura === 'facturado'
                                                    ? 'Factura registrada correctamente'
                                                    : quickViewExpense.estado_factura === 'sin_factura'
                                                        ? 'Marcado como sin factura'
                                                        : 'Aún falta vincular CFDI'}
                                            </p>
                                        </div>
                                        <div className="border border-emerald-100 rounded-xl p-3 bg-emerald-50">
                                            <p className="text-xs uppercase font-semibold text-emerald-600">Banco</p>
                                            <p className="text-sm font-semibold text-emerald-800 mt-1 capitalize">{(quickViewExpense.estado_conciliacion || 'pendiente').replace(/_/g, ' ')}</p>
                                            <p className="text-xs text-emerald-600 mt-1">
                                                {quickViewExpense.estado_conciliacion === 'conciliado_banco'
                                                    ? 'Ya vinculado a un movimiento bancario'
                                                    : 'Pendiente de conciliación bancaria'}
                                            </p>
                                        </div>
                                        <div className="border border-purple-100 rounded-xl p-3 bg-purple-50 sm:col-span-2">
                                            <p className="text-xs uppercase font-semibold text-purple-600">Flujo contable</p>
                                            <div className="flex items-center gap-2 text-sm text-purple-700 mt-2">
                                                <i className="fas fa-route"></i>
                                                <span>{(quickViewExpense.workflow_status || 'capturado').replace(/_/g, ' ')}</span>
                                            </div>
                                            {quickViewExpense.categoria && (
                                                <p className="text-xs text-purple-600 mt-1">Categoría: {quickViewExpense.categoria}</p>
                                            )}
                                        </div>
                                    </div>

                                    <div className="space-y-3">
                                        <p className="text-xs uppercase font-semibold text-slate-500">Avance del flujo</p>
                                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
                                            {[
                                                {
                                                    label: 'Captura',
                                                    icon: 'fa-flag-checkered',
                                                    color: 'text-blue-500',
                                                    progress: 100,
                                                },
                                                {
                                                    label: 'Factura',
                                                    icon: quickViewExpense.estado_factura === 'facturado' ? 'fa-check-circle' : 'fa-file-invoice',
                                                    color: quickViewExpense.estado_factura === 'facturado' ? 'text-green-500' : 'text-yellow-500',
                                                    progress: quickViewExpense.estado_factura === 'facturado' ? 100 : quickViewExpense.estado_factura === 'pendiente' ? 45 : 70,
                                                },
                                                {
                                                    label: 'Banco',
                                                    icon: quickViewExpense.estado_conciliacion === 'conciliado_banco' ? 'fa-coins' : 'fa-university',
                                                    color: quickViewExpense.estado_conciliacion === 'conciliado_banco' ? 'text-emerald-500' : 'text-emerald-400',
                                                    progress: quickViewExpense.estado_conciliacion === 'conciliado_banco' ? 100 : quickViewExpense.estado_factura === 'facturado' ? 40 : 10,
                                                }
                                            ].map((step) => (
                                                <div key={step.label} className="flex-1">
                                                    <div className="flex items-center gap-2 text-sm font-medium text-slate-600">
                                                        <i className={`fas ${step.icon} ${step.color}`}></i>
                                                        <span>{step.label}</span>
                                                    </div>
                                                    <div className="h-2 bg-slate-100 rounded-full mt-2">
                                                        <div className="h-full rounded-full bg-gradient-to-r from-blue-400 to-blue-600" style={{ width: `${step.progress}%` }}></div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                        <button
                                            onClick={() => {
                                                setQuickViewExpense(null);
                                                setShowInvoiceUpload(true);
                                            }}
                                            className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium bg-blue-50 text-blue-700 rounded-lg border border-blue-200 hover:bg-blue-100"
                                        >
                                            <i className="fas fa-file-upload"></i>
                                            Vincular factura
                                        </button>
                                        <button
                                            onClick={() => {
                                                setQuickViewExpense(null);
                                                setShowReconciliation(true);
                                            }}
                                            className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium bg-emerald-50 text-emerald-700 rounded-lg border border-emerald-200 hover:bg-emerald-100"
                                        >
                                            <i className="fas fa-scale-balanced"></i>
                                            Resolver en conciliación
                                        </button>
                                    </div>

                                    <div className="border border-slate-200 rounded-lg p-3 bg-slate-50 text-xs text-slate-600 space-y-1">
                                        <p><strong>Proveedor:</strong> {quickViewExpense.proveedor?.nombre || 'Sin proveedor'}</p>
                                        <p><strong>RFC:</strong> {quickViewExpense.rfc || '—'}</p>
                                        <p><strong>Forma de pago:</strong> {quickViewExpense.forma_pago || '—'}</p>
                                        <p><strong>Pagado por:</strong> {quickViewExpense.paid_by || '—'}</p>
                                        {Array.isArray(quickViewExpense.movimientos_bancarios) && quickViewExpense.movimientos_bancarios.length > 0 && (
                                            <p><strong>Movimientos vinculados:</strong> {quickViewExpense.movimientos_bancarios.length}</p>
                                        )}
                                    </div>

                                    {quickViewExpense.asientos_contables && (
                                        <div className="space-y-3">
                                            <div className="flex items-center justify-between">
                                                <div>
                                                    <p className="text-xs uppercase font-semibold text-slate-500">Asiento contable</p>
                                                    <p className="text-sm font-semibold text-slate-800">
                                                        {quickViewExpense.asientos_contables.numero_poliza || 'Póliza sin folio'}
                                                    </p>
                                                    <p className="text-xs text-slate-500">
                                                        {quickViewExpense.asientos_contables.fecha_asiento || 'Fecha no definida'} · {quickViewExpense.asientos_contables.tipo_poliza || 'Sin tipo'}
                                                    </p>
                                                </div>
                                                <span className={`inline-flex items-center gap-2 px-2 py-1 text-xs font-semibold rounded-full ${quickViewExpense.asientos_contables.balanceado ? 'bg-emerald-100 text-emerald-700 border border-emerald-200' : 'bg-red-100 text-red-700 border border-red-200'}`}>
                                                    <i className={`fas ${quickViewExpense.asientos_contables.balanceado ? 'fa-check' : 'fa-triangle-exclamation'}`}></i>
                                                    {quickViewExpense.asientos_contables.balanceado ? 'Balanceado' : 'Revisar diferencias'}
                                                </span>
                                            </div>

                                            <div className="border border-slate-200 rounded-lg overflow-hidden">
                                                <table className="min-w-full text-xs">
                                                    <thead className="bg-slate-100 text-slate-600 uppercase">
                                                        <tr>
                                                            <th className="px-3 py-2 text-left font-semibold">Cuenta</th>
                                                            <th className="px-3 py-2 text-left font-semibold">Descripción</th>
                                                            <th className="px-3 py-2 text-right font-semibold">Debe</th>
                                                            <th className="px-3 py-2 text-right font-semibold">Haber</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody className="divide-y divide-slate-200 bg-white">
                                                        {quickViewExpense.asientos_contables.movimientos.slice(0, 4).map((mov, idx) => (
                                                            <tr key={`${mov.cuenta}-${idx}`}>
                                                                <td className="px-3 py-2 text-slate-700 font-mono text-[11px]">{mov.cuenta}</td>
                                                            <td className="px-3 py-2 text-slate-600">{mov.descripcion || mov.nombre_cuenta}</td>
                                                                <td className="px-3 py-2 text-right text-slate-700">${Number(mov.debe || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}</td>
                                                                <td className="px-3 py-2 text-right text-slate-700">${Number(mov.haber || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}</td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                    <tfoot className="bg-slate-50 text-slate-600">
                                                        <tr>
                                                            <td colSpan={2} className="px-3 py-2 text-right font-semibold">Totales</td>
                                                            <td className="px-3 py-2 text-right font-semibold text-slate-800">${Number(quickViewExpense.asientos_contables.total_debe || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}</td>
                                                            <td className="px-3 py-2 text-right font-semibold text-slate-800">${Number(quickViewExpense.asientos_contables.total_haber || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}</td>
                                                        </tr>
                                                    </tfoot>
                                                </table>
                                            </div>

                                            <button
                                                onClick={() => {
                                                    setQuickViewExpense(null);
                                                    setShowCompletenessView(true);
                                                }}
                                                className="inline-flex items-center gap-2 text-xs font-semibold text-purple-600 hover:text-purple-700"
                                            >
                                                <i className="fas fa-book-open"></i>
                                                Ver asiento completo
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}

                    {showNavigationDrawer && (
                        <div className="fixed inset-0 z-50 md:hidden">
                            <div
                                className="absolute inset-0 bg-black/40"
                                onClick={() => setShowNavigationDrawer(false)}
                            ></div>
                            <div className="absolute left-0 top-0 bottom-0 w-80 max-w-[85%] bg-white shadow-2xl p-6 space-y-6 overflow-y-auto">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 text-white font-semibold">
                                            MCP
                                        </div>
                                        <div className="text-sm leading-tight">
                                            <p className="font-semibold text-slate-900">MCP Expenses</p>
                                            <p className="text-xs text-slate-500">Control total de gastos</p>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => setShowNavigationDrawer(false)}
                                        className="h-9 w-9 inline-flex items-center justify-center rounded-full bg-slate-100 text-slate-600"
                                        aria-label="Cerrar menú"
                                    >
                                        <i className="fas fa-times"></i>
                                    </button>
                                </div>

                                <div className="space-y-4">
                                    <div>
                                        <p className="text-xs font-semibold text-slate-500 uppercase mb-2">Empresa</p>
                                        <div className="flex items-center gap-2 border border-slate-200 rounded-lg px-3 py-2">
                                            <i className="fas fa-building text-slate-500"></i>
                                            <select
                                                value={companyId}
                                                onChange={(event) => handleCompanyChange(event.target.value, { closeDrawer: true })}
                                                className="flex-1 bg-transparent text-sm focus:outline-none"
                                            >
                                                {knownCompanies.map((company) => (
                                                    <option key={company} value={company}>{company}</option>
                                                ))}
                                                {!knownCompanies.includes('default') && (
                                                    <option value="default">default</option>
                                                )}
                                                <option value="__new__">➕ Registrar empresa…</option>
                                            </select>
                                        </div>
                                    </div>

                                    <div className="space-y-2">
                                        <p className="text-xs font-semibold text-slate-500 uppercase">Acciones rápidas</p>
                                        <button
                                            onClick={() => {
                                                setShowExpensesDashboard(true);
                                                setShowNavigationDrawer(false);
                                            }}
                                            className="flex w-full items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                                        >
                                            <i className="fas fa-chart-bar text-blue-500"></i>
                                            Dashboard de gastos
                                        </button>
                                        <button
                                            onClick={() => {
                                                setShowInvoiceUpload(true);
                                                setShowNavigationDrawer(false);
                                            }}
                                            className="flex w-full items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                                        >
                                            <i className="fas fa-file-upload text-green-500"></i>
                                            Cargar facturas
                                        </button>
                                        <button
                                            onClick={() => {
                                                setShowReconciliation(true);
                                                setShowNavigationDrawer(false);
                                            }}
                                            className="flex w-full items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                                        >
                                            <i className="fas fa-balance-scale text-purple-500"></i>
                                            Conciliar gastos
                                        </button>
                                        <button
                                            onClick={() => {
                                                setShowBankReconciliation(true);
                                                setShowNavigationDrawer(false);
                                            }}
                                            className="flex w-full items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                                        >
                                            <i className="fas fa-university text-teal-500"></i>
                                            Conciliación bancaria
                                        </button>
                                    </div>

                                    <div className="space-y-2">
                                        <p className="text-xs font-semibold text-slate-500 uppercase">Cuenta</p>
                                        <button
                                            onClick={() => {
                                                handleCompanyChange('__new__', { closeDrawer: true });
                                            }}
                                            className="flex w-full items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                                        >
                                            <i className="fas fa-building text-slate-500"></i>
                                            Registrar nueva empresa
                                        </button>
                                        <button
                                            onClick={() => {
                                                alert('Cerrar sesión no está disponible en la demo.');
                                                setShowNavigationDrawer(false);
                                            }}
                                            className="flex w-full items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                                        >
                                            <i className="fas fa-sign-out-alt text-slate-500"></i>
                                            Cerrar sesión
                                        </button>
                                    </div>

                                    <div className="space-y-1 text-xs text-slate-500">
                                        <p>Empresa activa: <span className="font-semibold text-slate-700">{resolvedCompanyId}</span></p>
                                        {demoMode
                                            ? <p>Modo demo activo. Completa las misiones para conocer el flujo.</p>
                                            : <p>Modo real: cualquier cambio se refleja en tu instancia.</p>}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            );
        };

        // Renderizar la aplicación
        const root = ReactDOM.createRoot(document.getElementById('app-root'));
        root.render(<ExpenseRegistration />);

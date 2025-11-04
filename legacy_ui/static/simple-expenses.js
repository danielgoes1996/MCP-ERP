// Simple React component for testing
const SimpleExpenses = () => {
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
            }, 'Captura por voz o ticket, vincula facturas y concilia con el banco en un solo flujo.')
        ]),
        React.createElement('div', {
            key: 'success',
            className: 'bg-green-50 border border-green-200 rounded-lg p-6 text-center'
        }, [
            React.createElement('div', {
                key: 'icon',
                className: 'text-6xl mb-4'
            }, '✅'),
            React.createElement('h3', {
                key: 'title',
                className: 'text-xl font-semibold text-green-800 mb-2'
            }, '¡Badges eliminados exitosamente!'),
            React.createElement('p', {
                key: 'message',
                className: 'text-green-600'
            }, 'Los badges de empresa y modo demo han sido removidos completamente de la interfaz.')
        ])
    ]);
};

console.log('Simple expenses component loaded');

// Renderizar la aplicación
const root = ReactDOM.createRoot(document.getElementById('app-root'));
root.render(React.createElement(SimpleExpenses, null));
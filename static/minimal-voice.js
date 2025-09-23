// Minimal version to test
console.log('Minimal voice loading...');

try {
    const MinimalApp = () => {
        console.log('MinimalApp rendering...');
        return React.createElement('div', {
            className: 'p-8'
        }, [
            React.createElement('h1', {
                key: 'title',
                className: 'text-3xl font-bold text-blue-600 mb-4'
            }, '🎤 Sistema de Gastos por Voz'),

            React.createElement('div', {
                key: 'status',
                className: 'bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-4'
            }, '✅ React está funcionando correctamente'),

            React.createElement('button', {
                key: 'test-btn',
                onClick: () => alert('¡Botón funciona!'),
                className: 'bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded'
            }, 'Test Button'),

            React.createElement('div', {
                key: 'company-info',
                className: 'mt-4 p-4 bg-gray-100 rounded'
            }, [
                React.createElement('p', {
                    key: 'company-text',
                    className: 'text-sm text-gray-600'
                }, 'Empresa: cmp_231448bc'),
                React.createElement('p', {
                    key: 'mode-text',
                    className: 'text-sm text-blue-600'
                }, '🚀 Modo Demo Activo')
            ])
        ]);
    };

    console.log('Creating React root...');
    const appRoot = document.getElementById('app-root');
    if (appRoot) {
        const root = ReactDOM.createRoot(appRoot);
        root.render(React.createElement(MinimalApp, null));
        console.log('✅ App rendered successfully');
    } else {
        console.error('❌ app-root element not found');
    }
} catch (error) {
    console.error('❌ Error in minimal app:', error);
}
// Test React component
const TestComponent = () => {
    return React.createElement('div', {
        className: 'text-center py-12'
    },
        React.createElement('h1', {
            className: 'text-2xl font-bold text-green-600'
        }, '✅ React funciona correctamente!'),
        React.createElement('p', {
            className: 'text-gray-600 mt-4'
        }, 'Los badges de empresa han sido eliminados exitosamente.')
    );
};

// Renderizar la aplicación
const root = ReactDOM.createRoot(document.getElementById('app-root'));
root.render(React.createElement(TestComponent, null));
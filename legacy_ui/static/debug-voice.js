// Debug version simple
console.log('Loading debug voice...');

const DebugVoiceApp = () => {
    const [currentView, setCurrentView] = React.useState('main');

    console.log('Debug: currentView =', currentView);

    // Simple test function
    const testClick = () => {
        console.log('Debug: Button clicked!');
        alert('Button works!');
        setCurrentView('expense-form');
    };

    if (currentView === 'expense-form') {
        return React.createElement('div', {
            className: 'max-w-4xl mx-auto px-4 py-6'
        }, [
            React.createElement('h2', {
                key: 'title',
                className: 'text-2xl font-bold mb-4'
            }, '🎤 Voice Test'),
            React.createElement('button', {
                key: 'back',
                onClick: () => setCurrentView('main'),
                className: 'px-4 py-2 bg-gray-500 text-white rounded'
            }, 'Back')
        ]);
    }

    return React.createElement('div', {
        className: 'max-w-6xl mx-auto px-4 py-6'
    }, [
        React.createElement('h1', {
            key: 'title',
            className: 'text-3xl font-bold mb-6'
        }, 'Debug Voice Interface'),

        React.createElement('button', {
            key: 'test-btn',
            onClick: testClick,
            className: 'px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700'
        }, 'Test Voice Button'),

        React.createElement('p', {
            key: 'status',
            className: 'mt-4 text-gray-600'
        }, `Current view: ${currentView}`)
    ]);
};

console.log('Debug: Creating React root...');
const root = ReactDOM.createRoot(document.getElementById('app-root'));
root.render(React.createElement(DebugVoiceApp, null));
console.log('Debug: App rendered!');
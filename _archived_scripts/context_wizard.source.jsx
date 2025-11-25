const { useState } = React;

const ContextWizard = () => {
  const [step, setStep] = useState(0);
  return (
    <div className="bg-white rounded-2xl shadow p-6 space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">Context Wizard Placeholder</h1>
      <p className="text-slate-600">Step {step + 1} of 4</p>
      <button
        className="px-4 py-2 bg-slate-900 text-white rounded-lg"
        onClick={() => setStep((prev) => (prev + 1) % 4)}
      >
        Next
      </button>
    </div>
  );
};

const rootElement = document.getElementById('context-wizard-root');
if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(<ContextWizard />);
}

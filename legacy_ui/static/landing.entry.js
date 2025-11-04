const bundleCandidates = [
  './landing.bundle.js?v=1760933195198'
];

(async () => {
  for (const bundlePath of bundleCandidates) {
    try {
      await import(bundlePath);
      if (window.ContaFlowLanding) {
        const root = document.getElementById('landing-root');
        if (root) {
          const element = React.createElement(window.ContaFlowLanding);
          ReactDOM.createRoot(root).render(element);
        }
      }
      return;
    } catch (error) {
      console.warn(`No se pudo cargar ${bundlePath}`, error);
    }
  }

  console.error('⚠️ No se pudo cargar la landing de ContaFlow con los bundles disponibles');
})();

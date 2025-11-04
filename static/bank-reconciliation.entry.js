const bundleCandidates = [
  '/static/bank-reconciliation.bundle.js?v=1760647185740'
];

(async () => {
  for (const bundlePath of bundleCandidates) {
    try {
      await import(bundlePath);
      return;
    } catch (error) {
      console.warn(`No se pudo cargar ${bundlePath}`, error);
    }
  }

  console.error('⚠️ No se pudo cargar la app de conciliación bancaria');
})();

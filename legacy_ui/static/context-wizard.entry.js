const bundleCandidates = [
  '/static/context-wizard.bundle.js'
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

  console.error('⚠️ No se pudo cargar el Context Wizard');
})();

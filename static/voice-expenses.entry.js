try {
  const params = new URLSearchParams(window.location.search);
  const companyFromQuery = params.get('company_id');
  const missionFromQuery = params.get('mission');
  if (companyFromQuery) {
    localStorage.setItem('mcp_company_id', companyFromQuery);
    window.dispatchEvent(new CustomEvent('mcp-company-change', { detail: { companyId: companyFromQuery } }));
  }
  if (missionFromQuery) {
    localStorage.setItem('mcp_active_mission', missionFromQuery);
    localStorage.setItem('mcp_demo_mode', 'true');
  }
} catch (error) {
  console.warn('No se pudo procesar company_id desde la URL:', error);
}

import('/static/voice-expenses.bundle.js').catch((error) => {
  console.error('⚠️ No se pudo cargar la interfaz de voz', error);
});

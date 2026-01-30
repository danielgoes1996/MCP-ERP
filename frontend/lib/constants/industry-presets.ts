/**
 * Industry-specific presets for AI classification context
 *
 * Auto-fills COGS, Operating Expenses, and Sales Expenses definitions
 * when user selects an industry during onboarding
 */

export interface IndustryPreset {
  industry: string;
  label: string;
  business_models: string[];
  capitalization_threshold_mxn: number;
  cogs_definition: string;
  operating_expenses_definition: string;
  sales_expenses_definition: string;
  typical_expenses: string[];
}

export const INDUSTRY_PRESETS: Record<string, IndustryPreset> = {
  // ===== TECH / SAAS =====
  tech: {
    industry: 'tech',  // Código que coincide con INDUSTRY_DESCRIPTIONS
    label: 'Tecnología / SaaS',
    business_models: ['subscription'],  // Códigos que coinciden con BUSINESS_MODEL_DESCRIPTIONS
    capitalization_threshold_mxn: 10000,
    cogs_definition: 'Servidores cloud (AWS/Azure/GCP), Licencias de software embebidas en el producto, Salarios de desarrolladores de producto, APIs y servicios de terceros integrados al producto, Costos de infraestructura de producción.',
    operating_expenses_definition: 'Renta de oficina, Software administrativo (Slack/Jira/Notion), Servicios públicos (internet, electricidad), Mantenimiento y soporte técnico interno, Seguridad informática.',
    sales_expenses_definition: 'Comisiones a vendedores, Marketing digital (Google Ads, Facebook Ads), CRM y herramientas de ventas (Salesforce, HubSpot), Eventos y conferencias, Publicidad y branding.',
    typical_expenses: ['cloud_services', 'administrative_services', 'marketing', 'digital_marketing', 'utilities']
  },

  // ===== COMERCIALIZADORA =====
  retail: {
    industry: 'retail',
    label: 'Comercializadora / Retail',
    business_models: ['b2c_retail', 'b2c_online', 'distribution'],
    capitalization_threshold_mxn: 5000,
    cogs_definition: 'Compra de mercancía para reventa, Fletes de entrada de mercancía desde proveedores, Seguros de traslado de inventario, Gastos de importación (si aplica), Mermas y devoluciones de productos.',
    operating_expenses_definition: 'Sueldos administrativos y de tienda, Luz, agua, teléfono de sucursales, Renta de locales comerciales, Papelería y suministros de oficina, Limpieza y mantenimiento de locales.',
    sales_expenses_definition: 'Publicidad en medios (radio, TV, redes sociales), Comisiones a vendedores, Promociones y descuentos, Envíos a clientes finales (logística de última milla), Empaques y bolsas de marca.',
    typical_expenses: ['rent', 'utilities', 'marketing', 'logistics', 'sales_salaries']
  },

  // ===== CONSTRUCTORA =====
  construction: {
    industry: 'construction',
    label: 'Constructora / Infraestructura',
    business_models: ['b2b_services', 'production'],
    capitalization_threshold_mxn: 20000,
    cogs_definition: 'Materiales de construcción (cemento, acero, varilla), Terrenos por desarrollar (inventario), Mano de obra directa (albañiles, electricistas), Renta de maquinaria pesada (grúas, excavadoras), Subcontratos de obra (plomería, acabados).',
    operating_expenses_definition: 'Sueldos de ingenieros de oficina central, Renta de oficinas administrativas, Software de diseño (AutoCAD, Revit), Seguros de responsabilidad civil, Servicios legales y notariales.',
    sales_expenses_definition: 'Ventas de casas muestra, Comisiones a corredores inmobiliarios, Publicidad de desarrollos (vallas, revistas), Eventos de preventa, Marketing digital inmobiliario.',
    typical_expenses: ['raw_materials', 'production_salaries', 'services', 'legal_fees', 'insurance']
  },

  // ===== FINTECH =====
  financial_services: {
    industry: 'financial_services',
    label: 'Fintech / Servicios Financieros',
    business_models: ['subscription', 'b2c_online', 'marketplace'],
    capitalization_threshold_mxn: 15000,
    cogs_definition: 'Intereses pagados por fondeo (costo de capital), Comisiones transaccionales (SPEI, tarjetas), Costos de verificación de identidad (KYC/AML), Comisiones a procesadores de pago (Stripe, Conekta), Pérdidas por fraude (chargebacks).',
    operating_expenses_definition: 'Desarrollo y mantenimiento de App (si no se capitaliza), Nómina corporativa (legal, finanzas, soporte), Renta de servidores admin y bases de datos, Auditorías y compliance regulatorio, Seguros y fianzas.',
    sales_expenses_definition: 'Marketing de adquisición de usuarios (CAC), Comisiones a afiliados o referidos, Publicidad digital (Facebook, Google), Eventos fintech y networking, Promociones de onboarding (cashback, bonos).',
    typical_expenses: ['cloud_services', 'administrative_services', 'legal_fees', 'marketing', 'digital_marketing']
  },

  // ===== MANUFACTURA / PRODUCCIÓN =====
  manufacturing: {
    industry: 'manufacturing',
    label: 'Manufactura / Producción Industrial',
    business_models: ['production', 'b2b_wholesale'],
    capitalization_threshold_mxn: 10000,
    cogs_definition: 'Materia prima consumida en producción, Insumos de empaque (cajas, etiquetas, envases), Mano de obra directa de planta, Energía eléctrica de maquinaria de producción, Mantenimiento de maquinaria productiva.',
    operating_expenses_definition: 'Sueldos administrativos, Renta de oficinas y bodegas de almacenamiento, Luz y agua de áreas administrativas, Seguros de planta, Mantenimiento de instalaciones no productivas.',
    sales_expenses_definition: 'Comisiones a distribuidores, Publicidad de productos, Ferias y exposiciones industriales, Muestras de producto, Fletes de distribución a clientes.',
    typical_expenses: ['raw_materials', 'production_salaries', 'utilities', 'logistics', 'insurance']
  },

  // ===== PRODUCCIÓN DE ALIMENTOS =====
  food_production: {
    industry: 'food_production',
    label: 'Producción de Alimentos',
    business_models: ['production', 'b2b_wholesale', 'b2c_retail'],
    capitalization_threshold_mxn: 5000,
    cogs_definition: 'Materias primas alimenticias (ingredientes), Insumos de empaque (frascos, etiquetas, cajas), Mano de obra de planta de producción, Gas y energía de cocción/refrigeración, Certificaciones sanitarias y análisis de laboratorio.',
    operating_expenses_definition: 'Sueldos administrativos, Renta de planta y bodegas refrigeradas, Luz y agua de áreas no productivas, Seguros de alimentos y responsabilidad, Mantenimiento de refrigeradores y cámaras.',
    sales_expenses_definition: 'Comisiones a distribuidores y autoservicios, Publicidad de marca (empaques, redes sociales), Degustaciones y promociones en tiendas, Fletes de distribución refrigerada, Participación en ferias de alimentos.',
    typical_expenses: ['raw_materials', 'production_salaries', 'utilities', 'logistics', 'insurance']
  },

  // ===== SERVICIOS PROFESIONALES =====
  services: {
    industry: 'services',
    label: 'Servicios Profesionales (Consultoría, Legal, Contable)',
    business_models: ['b2b_services'],
    capitalization_threshold_mxn: 3000,
    cogs_definition: 'Honorarios a consultores externos (subcontratación), Software especializado para prestación de servicio, Viáticos de proyectos facturables a cliente, Materiales consumibles directamente ligados al proyecto, Estudios y análisis técnicos para el cliente.',
    operating_expenses_definition: 'Sueldos de personal de soporte y administrativo, Renta de oficinas, Servicios públicos (internet, teléfono, luz), Software administrativo (CRM, contabilidad), Seguros de responsabilidad profesional.',
    sales_expenses_definition: 'Comisiones a socios por traer clientes, Marketing (LinkedIn Ads, networking), Eventos de prospección y conferencias, Regalos corporativos, Publicidad en medios especializados.',
    typical_expenses: ['administrative_services', 'rent', 'utilities', 'marketing', 'services']
  },

  // ===== LOGÍSTICA Y TRANSPORTE =====
  logistics: {
    industry: 'logistics',
    label: 'Logística y Transporte',
    business_models: ['b2b_services'],
    capitalization_threshold_mxn: 50000,
    cogs_definition: 'Combustible de unidades de reparto, Salarios de choferes y operadores, Mantenimiento de flotilla (llantas, refacciones), Peajes y casetas de autopistas, Seguros de carga y unidades.',
    operating_expenses_definition: 'Sueldos administrativos (despacho, logística), Renta de oficinas y patios de maniobras, Servicios públicos de oficinas, Software de rastreo GPS y logística, Seguros de responsabilidad civil.',
    sales_expenses_definition: 'Comisiones a vendedores de servicios logísticos, Publicidad de servicios de transporte, Participación en expo transporte, CRM y herramientas de cotización, Marketing digital B2B.',
    typical_expenses: ['logistics', 'administrative_salaries', 'utilities', 'maintenance', 'insurance']
  },
};

/**
 * Get preset for a given industry
 */
export function getIndustryPreset(industry: string): IndustryPreset | null {
  return INDUSTRY_PRESETS[industry] || null;
}

/**
 * Get all available industries for dropdown
 */
export function getAvailableIndustries(): Array<{ value: string; label: string }> {
  return Object.values(INDUSTRY_PRESETS).map(preset => ({
    value: preset.industry,
    label: preset.label
  }));
}

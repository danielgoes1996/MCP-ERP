-- ===============================================================
-- SEED: Catálogo de Merchants Mexicanos Comunes
-- ===============================================================

-- Obtener el tenant_id por defecto (asumimos tenant_id = 1 o el primero disponible)
DO $$
DECLARE
    default_tenant_id INTEGER;
BEGIN
    SELECT id INTO default_tenant_id FROM tenants LIMIT 1;

    -- ===============================================================
    -- GASOLINERAS
    -- ===============================================================

    -- PEMEX
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'PEMEX',
        'PEP970814SF3',
        'portal',
        'https://factura.pemex.com',
        '["PEMEX", "GASOLINERA.*PEMEX", "PEMEX.*GASOLINERA", "P\\.E\\.M\\.E\\.X"]'::jsonb,
        '["pemex", "gasolinera", "combustible", "gas"]'::jsonb,
        '{"category": "gasolinera", "accepts_card": true, "cfdi_portal": "factura.pemex.com"}'::jsonb,
        true
    );

    -- G500
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'G500',
        'GSE0810156V8',
        'portal',
        'https://facturacion.g500.com.mx',
        '["G500", "G-500", "GASOLINERA.*G500"]'::jsonb,
        '["g500", "gasolinera", "combustible"]'::jsonb,
        '{"category": "gasolinera", "accepts_card": true}'::jsonb,
        true
    );

    -- BP (British Petroleum)
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'BP',
        'CSE970508SJ3',
        'portal',
        'https://facturacion.bp.com.mx',
        '["BP", "BRITISH.*PETROLEUM", "GASOLINERA.*BP"]'::jsonb,
        '["bp", "british petroleum", "gasolinera"]'::jsonb,
        '{"category": "gasolinera", "accepts_card": true}'::jsonb,
        true
    );

    -- ===============================================================
    -- TIENDAS DE CONVENIENCIA
    -- ===============================================================

    -- OXXO
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'OXXO',
        'OCO850101XXX',
        'portal',
        'https://www.oxxo.com/facturacion',
        '["OXXO", "O.*X.*X.*O"]'::jsonb,
        '["oxxo", "tienda", "conveniencia"]'::jsonb,
        '{"category": "conveniencia", "accepts_card": true, "cfdi_requires_ticket": true}'::jsonb,
        true
    );

    -- 7-Eleven
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        '7-Eleven',
        'SEV710101ABC',
        'portal',
        'https://www.7-eleven.com.mx/facturacion',
        '["7-ELEVEN", "SEVEN.*ELEVEN", "7 ELEVEN"]'::jsonb,
        '["7-eleven", "seven eleven", "tienda"]'::jsonb,
        '{"category": "conveniencia", "accepts_card": true}'::jsonb,
        true
    );

    -- ===============================================================
    -- SUPERMERCADOS
    -- ===============================================================

    -- Walmart
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'Walmart',
        'WMT800101XX1',
        'portal',
        'https://www.walmart.com.mx/facturacion',
        '["WALMART", "WAL.*MART"]'::jsonb,
        '["walmart", "supermercado", "super"]'::jsonb,
        '{"category": "supermercado", "accepts_card": true, "cfdi_requires_ticket": true}'::jsonb,
        true
    );

    -- Superama
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'Superama',
        'SMA820515XX2',
        'portal',
        'https://www.superama.com.mx/facturacion',
        '["SUPERAMA", "SUPER.*AMA"]'::jsonb,
        '["superama", "supermercado"]'::jsonb,
        '{"category": "supermercado", "accepts_card": true}'::jsonb,
        true
    );

    -- Soriana
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'Soriana',
        'OSO931229XX3',
        'portal',
        'https://www.soriana.com/facturacion',
        '["SORIANA", "TIENDA.*SORIANA"]'::jsonb,
        '["soriana", "supermercado", "super"]'::jsonb,
        '{"category": "supermercado", "accepts_card": true, "cfdi_requires_ticket": true}'::jsonb,
        true
    );

    -- Chedraui
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'Chedraui',
        'CHE650722XX4',
        'portal',
        'https://www.chedraui.com.mx/facturacion',
        '["CHEDRAUI", "TIENDA.*CHEDRAUI"]'::jsonb,
        '["chedraui", "supermercado"]'::jsonb,
        '{"category": "supermercado", "accepts_card": true}'::jsonb,
        true
    );

    -- La Comer
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'La Comer',
        'LCO910815XX5',
        'portal',
        'https://www.lacomer.com.mx/facturacion',
        '["LA COMER", "COMER"]'::jsonb,
        '["la comer", "comer", "supermercado"]'::jsonb,
        '{"category": "supermercado", "accepts_card": true}'::jsonb,
        true
    );

    -- ===============================================================
    -- DEPARTAMENTALES
    -- ===============================================================

    -- Liverpool
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'Liverpool',
        'PLI931004XX6',
        'portal',
        'https://www.liverpool.com.mx/tienda/facturacion',
        '["LIVERPOOL", "EL PUERTO DE LIVERPOOL"]'::jsonb,
        '["liverpool", "departamental"]'::jsonb,
        '{"category": "departamental", "accepts_card": true, "cfdi_requires_ticket": true}'::jsonb,
        true
    );

    -- Palacio de Hierro
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'Palacio de Hierro',
        'PHI380912XX7',
        'portal',
        'https://www.elpalaciodehierro.com/facturacion',
        '["PALACIO.*HIERRO", "EL PALACIO DE HIERRO"]'::jsonb,
        '["palacio", "hierro", "departamental"]'::jsonb,
        '{"category": "departamental", "accepts_card": true}'::jsonb,
        true
    );

    -- Sears
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'Sears',
        'SRS471116XX8',
        'portal',
        'https://www.sears.com.mx/facturacion',
        '["SEARS"]'::jsonb,
        '["sears", "departamental"]'::jsonb,
        '{"category": "departamental", "accepts_card": true}'::jsonb,
        true
    );

    -- ===============================================================
    -- RESTAURANTES
    -- ===============================================================

    -- Sanborns
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'Sanborns',
        'SAN470814XX9',
        'portal',
        'https://www.sanborns.com.mx/facturacion',
        '["SANBORNS", "SANBORN"]'::jsonb,
        '["sanborns", "restaurante", "tienda"]'::jsonb,
        '{"category": "restaurante", "accepts_card": true}'::jsonb,
        true
    );

    -- Starbucks
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'Starbucks',
        'STA020925XX0',
        'portal',
        'https://facturacion.starbucks.com.mx',
        '["STARBUCKS", "STAR.*BUCKS"]'::jsonb,
        '["starbucks", "cafe", "coffee"]'::jsonb,
        '{"category": "cafe", "accepts_card": true}'::jsonb,
        true
    );

    -- McDonald''s
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'McDonald''s',
        'MCD590701XX1',
        'portal',
        'https://facturacion.mcdonalds.com.mx',
        '["MCDONALD", "MC.*DONALD", "MC DONALD''S"]'::jsonb,
        '["mcdonalds", "restaurante", "comida rapida"]'::jsonb,
        '{"category": "restaurante", "accepts_card": true}'::jsonb,
        true
    );

    -- ===============================================================
    -- TIENDAS ESPECIALIZADAS
    -- ===============================================================

    -- Home Depot
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'Home Depot',
        'HMD000203XX2',
        'portal',
        'https://www.homedepot.com.mx/facturacion',
        '["HOME.*DEPOT", "THE HOME DEPOT"]'::jsonb,
        '["home depot", "ferreteria", "construccion"]'::jsonb,
        '{"category": "ferreteria", "accepts_card": true, "cfdi_requires_ticket": true}'::jsonb,
        true
    );

    -- Office Depot
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'Office Depot',
        'OFD950620XX3',
        'portal',
        'https://www.officedepot.com.mx/facturacion',
        '["OFFICE.*DEPOT"]'::jsonb,
        '["office depot", "papeleria", "oficina"]'::jsonb,
        '{"category": "papeleria", "accepts_card": true}'::jsonb,
        true
    );

    -- Costco
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'Costco',
        'CMM920427XX4',
        'portal',
        'https://www.costco.com.mx/facturacion',
        '["COSTCO"]'::jsonb,
        '["costco", "mayoreo", "club"]'::jsonb,
        '{"category": "club_precios", "accepts_card": true, "cfdi_requires_ticket": true, "requires_membership": true}'::jsonb,
        true
    );

    -- Sam''s Club
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'Sam''s Club',
        'NSC970619XX5',
        'portal',
        'https://www.sams.com.mx/facturacion',
        '["SAM''S.*CLUB", "SAMS.*CLUB", "SAM CLUB"]'::jsonb,
        '["sams", "club", "mayoreo"]'::jsonb,
        '{"category": "club_precios", "accepts_card": true, "requires_membership": true}'::jsonb,
        true
    );

    -- ===============================================================
    -- E-COMMERCE
    -- ===============================================================

    -- Amazon México
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'Amazon México',
        'AMZ101220XX6',
        'email',
        'https://www.amazon.com.mx/facturacion',
        '["AMAZON", "AMZ"]'::jsonb,
        '["amazon", "ecommerce", "online"]'::jsonb,
        '{"category": "ecommerce", "accepts_card": true, "auto_invoice_email": true}'::jsonb,
        true
    );

    -- Mercado Libre
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'Mercado Libre',
        'MLM990512XX7',
        'portal',
        'https://www.mercadolibre.com.mx/facturacion',
        '["MERCADO.*LIBRE", "ML", "MELI"]'::jsonb,
        '["mercadolibre", "mercado libre", "ecommerce"]'::jsonb,
        '{"category": "ecommerce", "accepts_card": true}'::jsonb,
        true
    );

    -- ===============================================================
    -- SERVICIOS
    -- ===============================================================

    -- Uber
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'Uber',
        'UTM1309234X8',
        'portal',
        'https://riders.uber.com/trips',
        '["UBER"]'::jsonb,
        '["uber", "transporte", "taxi"]'::jsonb,
        '{"category": "transporte", "accepts_card": true, "auto_invoice_app": true}'::jsonb,
        true
    );

    -- DiDi
    INSERT INTO merchants (
        tenant_id, name, rfc, invoicing_method, portal_url,
        regex_patterns, keywords, metadata, is_active
    ) VALUES (
        default_tenant_id,
        'DiDi',
        'DFM180815XX9',
        'portal',
        'https://web.didiglobal.com/mx/invoice',
        '["DIDI", "DI.*DI"]'::jsonb,
        '["didi", "transporte", "taxi"]'::jsonb,
        '{"category": "transporte", "accepts_card": true}'::jsonb,
        true
    );

    RAISE NOTICE 'Catálogo de merchants creado exitosamente';
END $$;

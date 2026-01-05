-- =====================================================
-- CPG RETAIL VERTICAL: Field Sales Complete System
-- Migration 004
-- =====================================================
-- Adds: Products, Routes, Visits, Delivery tracking
-- Extends: POS and Consignment tables
-- =====================================================

-- =====================================================
-- 1. PRODUCT CATALOG
-- =====================================================

CREATE TABLE IF NOT EXISTS cpg_productos (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50) NOT NULL,
    tenant_id INTEGER,

    -- Identification
    sku VARCHAR(100) NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    descripcion TEXT,
    categoria VARCHAR(50),  -- miel, polen, propoleo, jalea_real

    -- Pricing
    precio_base DECIMAL(10,2) NOT NULL,
    precio_sugerido DECIMAL(10,2),  -- Precio sugerido de venta al público
    comision_vendedor DECIMAL(5,2) DEFAULT 0.0,  -- Porcentaje de comisión

    -- Product specifications (específico de productos naturales)
    gramaje INTEGER,  -- Peso en gramos
    unidad_medida VARCHAR(20) DEFAULT 'gramos',  -- gramos, kg, ml, litros
    tipo_producto VARCHAR(50),  -- organica, convencional, cruda, procesada
    origen VARCHAR(100),  -- Región de origen

    -- Multimedia
    media_urls JSONB,  -- {"foto_principal": "url", "galeria": ["url1", "url2"]}

    -- Inventory
    disponible BOOLEAN DEFAULT true,
    stock_minimo INTEGER DEFAULT 0,
    requiere_refrigeracion BOOLEAN DEFAULT false,

    -- Metadata
    metadata JSONB,

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    UNIQUE(company_id, sku),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- Indexes for cpg_productos
CREATE INDEX idx_cpg_productos_company ON cpg_productos(company_id);
CREATE INDEX idx_cpg_productos_tenant ON cpg_productos(tenant_id);
CREATE INDEX idx_cpg_productos_sku ON cpg_productos(sku);
CREATE INDEX idx_cpg_productos_categoria ON cpg_productos(categoria);
CREATE INDEX idx_cpg_productos_disponible ON cpg_productos(disponible) WHERE disponible = true;
CREATE INDEX idx_cpg_productos_media ON cpg_productos USING GIN(media_urls);

COMMENT ON TABLE cpg_productos IS 'Product catalog for CPG retail (honey, natural products)';
COMMENT ON COLUMN cpg_productos.gramaje IS 'Product weight in grams';
COMMENT ON COLUMN cpg_productos.comision_vendedor IS 'Sales commission percentage for field reps';

-- =====================================================
-- 2. SALES ROUTES
-- =====================================================

CREATE TABLE IF NOT EXISTS cpg_routes (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50) NOT NULL,
    tenant_id INTEGER,

    -- Route identification
    codigo_ruta VARCHAR(50) NOT NULL,
    nombre_ruta VARCHAR(255) NOT NULL,

    -- Assignment
    vendedor_id INTEGER,  -- User assigned to route

    -- Route configuration
    frecuencia VARCHAR(20) DEFAULT 'weekly',  -- daily, weekly, biweekly, monthly
    dias_semana INTEGER[],  -- [1,3,5] = Monday, Wednesday, Friday (1=Monday, 7=Sunday)

    -- Route details
    descripcion TEXT,
    zona_geografica VARCHAR(100),

    -- Status
    status VARCHAR(20) DEFAULT 'active',  -- active, inactive, suspended

    -- Metadata
    metadata JSONB,

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    UNIQUE(company_id, codigo_ruta),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (vendedor_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Indexes for cpg_routes
CREATE INDEX idx_cpg_routes_company ON cpg_routes(company_id);
CREATE INDEX idx_cpg_routes_tenant ON cpg_routes(tenant_id);
CREATE INDEX idx_cpg_routes_vendedor ON cpg_routes(vendedor_id);
CREATE INDEX idx_cpg_routes_status ON cpg_routes(status);
CREATE INDEX idx_cpg_routes_codigo ON cpg_routes(codigo_ruta);

COMMENT ON TABLE cpg_routes IS 'Sales routes for field representatives';
COMMENT ON COLUMN cpg_routes.dias_semana IS 'Array of weekday numbers (1=Monday, 7=Sunday)';

-- =====================================================
-- 3. FIELD VISITS
-- =====================================================

CREATE TABLE IF NOT EXISTS cpg_visits (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50) NOT NULL,
    tenant_id INTEGER,

    -- Visit assignment
    pos_id INTEGER NOT NULL,
    route_id INTEGER,
    vendedor_id INTEGER NOT NULL,

    -- Schedule
    fecha_programada TIMESTAMP NOT NULL,
    fecha_visita_real TIMESTAMP,
    fecha_visita_anterior TIMESTAMP,

    -- Visit outcome
    status VARCHAR(20) DEFAULT 'scheduled',  -- scheduled, completed, cancelled, no_show, rescheduled
    tipo_visita VARCHAR(20) DEFAULT 'routine',  -- delivery, collection, audit, routine, emergency

    -- Delivery tracking
    productos_entregados JSONB,  -- [{"sku": "MIEL-ORG-250G", "qty": 10, "precio": 120}]
    monto_total_entregado DECIMAL(15,2) DEFAULT 0.0,

    -- Collection tracking
    monto_cobrado DECIMAL(15,2) DEFAULT 0.0,
    modalidad_pago VARCHAR(20),  -- efectivo, transferencia, cheque, tarjeta
    referencia_pago VARCHAR(255),

    -- Inventory audit
    inventario_contado JSONB,  -- {"MIEL-ORG-250G": 5, "MIEL-ORG-500G": 3}
    diferencia_inventario JSONB,  -- {"MIEL-ORG-250G": -2} (negative = faltante)

    -- Compliance & verification
    firma_digital TEXT,  -- Base64 encoded signature image
    firma_nombre VARCHAR(255),  -- Name of person who signed
    foto_firma_url VARCHAR(500),  -- Cloud storage URL

    -- GPS tracking
    gps_checkin JSONB,  -- {"lat": 19.4326, "lng": -99.1332, "timestamp": "2025-01-04T10:00:00Z", "accuracy": 10}
    gps_checkout JSONB,

    -- Visit notes
    observaciones TEXT,
    problemas_reportados TEXT,
    foto_evidencias JSONB,  -- ["url1", "url2", "url3"]

    -- Metadata
    metadata JSONB,

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,

    -- Constraints
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (pos_id) REFERENCES cpg_pos(id) ON DELETE CASCADE,
    FOREIGN KEY (route_id) REFERENCES cpg_routes(id) ON DELETE SET NULL,
    FOREIGN KEY (vendedor_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for cpg_visits
CREATE INDEX idx_cpg_visits_company ON cpg_visits(company_id);
CREATE INDEX idx_cpg_visits_tenant ON cpg_visits(tenant_id);
CREATE INDEX idx_cpg_visits_pos ON cpg_visits(pos_id);
CREATE INDEX idx_cpg_visits_route ON cpg_visits(route_id);
CREATE INDEX idx_cpg_visits_vendedor ON cpg_visits(vendedor_id);
CREATE INDEX idx_cpg_visits_status ON cpg_visits(status);
CREATE INDEX idx_cpg_visits_fecha_programada ON cpg_visits(fecha_programada);
CREATE INDEX idx_cpg_visits_fecha_real ON cpg_visits(fecha_visita_real);

-- Partial index for pending visits
CREATE INDEX idx_cpg_visits_pending ON cpg_visits(vendedor_id, fecha_programada)
WHERE status IN ('scheduled', 'rescheduled');

-- GIN indexes for JSONB
CREATE INDEX idx_cpg_visits_productos ON cpg_visits USING GIN(productos_entregados);
CREATE INDEX idx_cpg_visits_inventario ON cpg_visits USING GIN(inventario_contado);
CREATE INDEX idx_cpg_visits_gps_checkin ON cpg_visits USING GIN(gps_checkin);

COMMENT ON TABLE cpg_visits IS 'Field sales visits tracking with GPS, signature, and inventory audit';
COMMENT ON COLUMN cpg_visits.status IS 'Visit status: scheduled, completed, cancelled, no_show, rescheduled';
COMMENT ON COLUMN cpg_visits.gps_checkin IS 'GPS coordinates and timestamp when rep checked in at POS';
COMMENT ON COLUMN cpg_visits.firma_digital IS 'Base64 encoded signature image for proof of delivery';

-- =====================================================
-- 4. DELIVERY LINE ITEMS (Normalized)
-- =====================================================

CREATE TABLE IF NOT EXISTS cpg_delivery_items (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50) NOT NULL,
    tenant_id INTEGER,

    -- References
    visit_id INTEGER NOT NULL,
    producto_id INTEGER NOT NULL,

    -- Delivery details
    cantidad_entregada INTEGER NOT NULL,
    cantidad_vendida INTEGER DEFAULT 0,
    cantidad_devuelta INTEGER DEFAULT 0,

    -- Pricing
    precio_unitario DECIMAL(10,2) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,

    -- Status
    status VARCHAR(20) DEFAULT 'entregado',  -- entregado, vendido, devuelto, dañado

    -- Metadata
    notas TEXT,
    metadata JSONB,

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (visit_id) REFERENCES cpg_visits(id) ON DELETE CASCADE,
    FOREIGN KEY (producto_id) REFERENCES cpg_productos(id) ON DELETE CASCADE,

    CHECK (cantidad_entregada >= 0),
    CHECK (cantidad_vendida >= 0),
    CHECK (cantidad_devuelta >= 0),
    CHECK (cantidad_vendida + cantidad_devuelta <= cantidad_entregada)
);

-- Indexes for cpg_delivery_items
CREATE INDEX idx_cpg_delivery_items_company ON cpg_delivery_items(company_id);
CREATE INDEX idx_cpg_delivery_items_visit ON cpg_delivery_items(visit_id);
CREATE INDEX idx_cpg_delivery_items_producto ON cpg_delivery_items(producto_id);
CREATE INDEX idx_cpg_delivery_items_status ON cpg_delivery_items(status);

COMMENT ON TABLE cpg_delivery_items IS 'Normalized delivery line items per visit';
COMMENT ON COLUMN cpg_delivery_items.cantidad_vendida IS 'Quantity sold (updated when visit is completed or POS reports sales)';

-- =====================================================
-- 5. EXTEND EXISTING TABLES
-- =====================================================

-- Add fields to cpg_pos
ALTER TABLE cpg_pos ADD COLUMN IF NOT EXISTS media_urls JSONB;
ALTER TABLE cpg_pos ADD COLUMN IF NOT EXISTS route_id INTEGER;
ALTER TABLE cpg_pos ADD COLUMN IF NOT EXISTS ultima_visita TIMESTAMP;
ALTER TABLE cpg_pos ADD COLUMN IF NOT EXISTS proxima_visita TIMESTAMP;
ALTER TABLE cpg_pos ADD COLUMN IF NOT EXISTS frecuencia_visitas VARCHAR(20) DEFAULT 'weekly';

-- Add foreign key for route
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'cpg_pos_route_id_fkey'
    ) THEN
        ALTER TABLE cpg_pos ADD CONSTRAINT cpg_pos_route_id_fkey
        FOREIGN KEY (route_id) REFERENCES cpg_routes(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Add index
CREATE INDEX IF NOT EXISTS idx_cpg_pos_route ON cpg_pos(route_id);

COMMENT ON COLUMN cpg_pos.media_urls IS 'JSONB: {"fachada": "url", "logo": "url", "interior": ["url1", "url2"]}';
COMMENT ON COLUMN cpg_pos.ultima_visita IS 'Timestamp of last completed visit';
COMMENT ON COLUMN cpg_pos.proxima_visita IS 'Scheduled timestamp for next visit';

-- Add fields to cpg_consignment
ALTER TABLE cpg_consignment ADD COLUMN IF NOT EXISTS visit_id INTEGER;
ALTER TABLE cpg_consignment ADD COLUMN IF NOT EXISTS origen_visita BOOLEAN DEFAULT false;

-- Add foreign key for visit
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'cpg_consignment_visit_id_fkey'
    ) THEN
        ALTER TABLE cpg_consignment ADD CONSTRAINT cpg_consignment_visit_id_fkey
        FOREIGN KEY (visit_id) REFERENCES cpg_visits(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Add index
CREATE INDEX IF NOT EXISTS idx_cpg_consignment_visit ON cpg_consignment(visit_id);

COMMENT ON COLUMN cpg_consignment.visit_id IS 'Links consignment to the visit where products were delivered';
COMMENT ON COLUMN cpg_consignment.origen_visita IS 'TRUE if consignment was created from a field visit';

-- =====================================================
-- 6. REPORTING VIEWS
-- =====================================================

-- View: Route Performance
CREATE OR REPLACE VIEW cpg_route_performance AS
SELECT
    r.id as route_id,
    r.company_id,
    r.codigo_ruta,
    r.nombre_ruta,
    r.vendedor_id,
    u.name as vendedor_nombre,

    -- Visit metrics
    COUNT(DISTINCT v.id) as total_visitas,
    COUNT(DISTINCT v.id) FILTER (WHERE v.status = 'completed') as visitas_completadas,
    COUNT(DISTINCT v.id) FILTER (WHERE v.status = 'no_show') as visitas_no_show,
    COUNT(DISTINCT v.id) FILTER (WHERE v.status = 'cancelled') as visitas_canceladas,

    -- Financial metrics
    COALESCE(SUM(v.monto_total_entregado), 0) as total_entregado,
    COALESCE(SUM(v.monto_cobrado), 0) as total_cobrado,

    -- Efficiency metrics
    CASE
        WHEN COUNT(DISTINCT v.id) > 0
        THEN ROUND(COUNT(DISTINCT v.id) FILTER (WHERE v.status = 'completed')::NUMERIC / COUNT(DISTINCT v.id) * 100, 2)
        ELSE 0
    END as tasa_cumplimiento,

    -- POS count
    COUNT(DISTINCT p.id) as total_pos_en_ruta

FROM cpg_routes r
LEFT JOIN users u ON u.id = r.vendedor_id
LEFT JOIN cpg_visits v ON v.route_id = r.id
    AND v.fecha_visita_real >= NOW() - INTERVAL '30 days'
LEFT JOIN cpg_pos p ON p.route_id = r.id AND p.status = 'active'
WHERE r.status = 'active'
GROUP BY r.id, r.company_id, r.codigo_ruta, r.nombre_ruta, r.vendedor_id, u.name;

COMMENT ON VIEW cpg_route_performance IS 'Route performance metrics (last 30 days)';

-- View: Visit Compliance
CREATE OR REPLACE VIEW cpg_visit_compliance AS
SELECT
    v.id,
    v.company_id,
    v.pos_id,
    p.codigo as pos_codigo,
    p.nombre as pos_nombre,
    v.vendedor_id,
    u.name as vendedor_nombre,
    v.fecha_programada,
    v.fecha_visita_real,
    v.status,

    -- Compliance flags
    CASE
        WHEN v.status = 'completed' AND v.gps_checkin IS NOT NULL THEN true
        ELSE false
    END as tiene_gps,

    CASE
        WHEN v.status = 'completed' AND v.firma_digital IS NOT NULL THEN true
        ELSE false
    END as tiene_firma,

    CASE
        WHEN v.status = 'completed' AND v.inventario_contado IS NOT NULL THEN true
        ELSE false
    END as tiene_inventario,

    -- Timing
    CASE
        WHEN v.fecha_visita_real IS NOT NULL THEN
            EXTRACT(EPOCH FROM (v.fecha_visita_real - v.fecha_programada)) / 3600
        ELSE NULL
    END as horas_diferencia,

    -- Amounts
    v.monto_total_entregado,
    v.monto_cobrado

FROM cpg_visits v
LEFT JOIN cpg_pos p ON p.id = v.pos_id
LEFT JOIN users u ON u.id = v.vendedor_id
WHERE v.fecha_programada >= NOW() - INTERVAL '90 days'
ORDER BY v.fecha_programada DESC;

COMMENT ON VIEW cpg_visit_compliance IS 'Visit compliance tracking (GPS, signature, inventory)';

-- View: Product Performance
CREATE OR REPLACE VIEW cpg_product_performance AS
SELECT
    prod.id as producto_id,
    prod.company_id,
    prod.sku,
    prod.nombre,
    prod.categoria,
    prod.precio_base,

    -- Delivery metrics
    COUNT(DISTINCT di.visit_id) as total_entregas,
    COALESCE(SUM(di.cantidad_entregada), 0) as cantidad_total_entregada,
    COALESCE(SUM(di.cantidad_vendida), 0) as cantidad_total_vendida,
    COALESCE(SUM(di.cantidad_devuelta), 0) as cantidad_total_devuelta,

    -- Sales metrics
    COALESCE(SUM(di.subtotal), 0) as valor_total_entregado,

    -- Sell-through rate
    CASE
        WHEN SUM(di.cantidad_entregada) > 0 THEN
            ROUND(SUM(di.cantidad_vendida)::NUMERIC / SUM(di.cantidad_entregada) * 100, 2)
        ELSE 0
    END as tasa_venta,

    -- Return rate
    CASE
        WHEN SUM(di.cantidad_entregada) > 0 THEN
            ROUND(SUM(di.cantidad_devuelta)::NUMERIC / SUM(di.cantidad_entregada) * 100, 2)
        ELSE 0
    END as tasa_devolucion

FROM cpg_productos prod
LEFT JOIN cpg_delivery_items di ON di.producto_id = prod.id
    AND di.created_at >= NOW() - INTERVAL '30 days'
WHERE prod.disponible = true
GROUP BY prod.id, prod.company_id, prod.sku, prod.nombre, prod.categoria, prod.precio_base
ORDER BY cantidad_total_vendida DESC;

COMMENT ON VIEW cpg_product_performance IS 'Product performance metrics (last 30 days)';

-- View: Inventory Variance
CREATE OR REPLACE VIEW cpg_inventory_variance AS
SELECT
    v.id as visit_id,
    v.company_id,
    v.pos_id,
    p.codigo as pos_codigo,
    p.nombre as pos_nombre,
    v.fecha_visita_real,
    v.vendedor_id,

    -- Extract inventory data
    jsonb_object_keys(v.inventario_contado) as sku,
    (v.inventario_contado->>jsonb_object_keys(v.inventario_contado))::INTEGER as cantidad_contada,
    (v.diferencia_inventario->>jsonb_object_keys(v.inventario_contado))::INTEGER as diferencia,

    CASE
        WHEN (v.diferencia_inventario->>jsonb_object_keys(v.inventario_contado))::INTEGER < 0 THEN 'faltante'
        WHEN (v.diferencia_inventario->>jsonb_object_keys(v.inventario_contado))::INTEGER > 0 THEN 'sobrante'
        ELSE 'exacto'
    END as tipo_diferencia

FROM cpg_visits v
LEFT JOIN cpg_pos p ON p.id = v.pos_id
WHERE v.status = 'completed'
  AND v.inventario_contado IS NOT NULL
  AND v.fecha_visita_real >= NOW() - INTERVAL '30 days';

COMMENT ON VIEW cpg_inventory_variance IS 'Inventory count variances detected during visits';

-- =====================================================
-- MIGRATION COMPLETE
-- =====================================================

-- Summary of what was created
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 004 Complete: Field Sales System';
    RAISE NOTICE '   - cpg_productos: Product catalog';
    RAISE NOTICE '   - cpg_routes: Sales routes';
    RAISE NOTICE '   - cpg_visits: Field visits (GPS, signature, inventory)';
    RAISE NOTICE '   - cpg_delivery_items: Delivery line items';
    RAISE NOTICE '   - Extended: cpg_pos and cpg_consignment';
    RAISE NOTICE '   - 4 reporting views created';
END $$;

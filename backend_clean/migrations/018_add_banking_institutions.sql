-- Migración 018: Crear tabla de instituciones bancarias
-- Fecha: 2025-09-27
-- Descripción: Crear tabla para manejar dropdown de bancos

-- =====================================================
-- PASO 1: CREAR TABLA DE INSTITUCIONES BANCARIAS
-- =====================================================

CREATE TABLE IF NOT EXISTS banking_institutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    short_name TEXT,
    type TEXT NOT NULL DEFAULT 'bank',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER DEFAULT 100,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (type IN ('bank', 'credit_union', 'fintech', 'other'))
);

-- =====================================================
-- PASO 2: INSERTAR INSTITUCIONES BANCARIAS PRINCIPALES
-- =====================================================

INSERT INTO banking_institutions (name, short_name, type, sort_order) VALUES
-- Bancos principales (orden alfabético con prioridad)
('BBVA México', 'BBVA', 'bank', 1),
('Banco Santander', 'Santander', 'bank', 2),
('Banamex', 'Banamex', 'bank', 3),
('Banorte', 'Banorte', 'bank', 4),
('HSBC México', 'HSBC', 'bank', 5),
('Scotiabank', 'Scotia', 'bank', 6),
('Banco Azteca', 'Azteca', 'bank', 7),
('Inbursa', 'Inbursa', 'bank', 8),
('Banco del Bajío', 'BajÍo', 'bank', 9),
('Afirme', 'Afirme', 'bank', 10),

-- Bancos digitales y fintech
('Nu México', 'Nu', 'fintech', 11),
('Banco Dinn', 'Dinn', 'fintech', 12),
('Hey Banco', 'Hey', 'fintech', 13),
('Klar', 'Klar', 'fintech', 14),
('Stori', 'Stori', 'fintech', 15),
('Mercado Pago', 'MercadoPago', 'fintech', 16),

-- Bancos especializados
('Banco Invex', 'Invex', 'bank', 17),
('Banco Ve Por Más', 'Ve Por Más', 'bank', 18),
('Banco Multiva', 'Multiva', 'bank', 19),
('Banco Compartamos', 'Compartamos', 'bank', 20),
('ABC Capital', 'ABC Capital', 'bank', 21),
('Banco Famsa', 'Famsa', 'bank', 22),
('Banco Coppel', 'Coppel', 'bank', 23),
('Banco Autofin', 'Autofin', 'bank', 24),
('Banco Credit Suisse', 'Credit Suisse', 'bank', 25),
('JPMorgan', 'JPMorgan', 'bank', 26),

-- Cajas populares y cooperativas
('Caja Popular Mexicana', 'CPMX', 'credit_union', 27),
('Caja Libertad', 'Libertad', 'credit_union', 28),
('Caja Los Altos', 'Los Altos', 'credit_union', 29),

-- Otros
('Otro', 'Otro', 'other', 99);

-- =====================================================
-- PASO 3: CREAR ÍNDICES
-- =====================================================

CREATE INDEX idx_banking_institutions_active_sort
ON banking_institutions(active, sort_order);

CREATE INDEX idx_banking_institutions_type
ON banking_institutions(type);

CREATE INDEX idx_banking_institutions_name
ON banking_institutions(name) WHERE active = TRUE;

-- =====================================================
-- REGISTRAR MIGRACIÓN
-- =====================================================

INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)
VALUES ('018', 'Add banking institutions table for dropdown selection', CURRENT_TIMESTAMP);

-- =====================================================
-- EJEMPLOS DE CONSULTAS
-- =====================================================

/*
-- Obtener todos los bancos activos ordenados:
SELECT * FROM banking_institutions
WHERE active = TRUE
ORDER BY sort_order, name;

-- Obtener solo bancos principales:
SELECT * FROM banking_institutions
WHERE type = 'bank' AND active = TRUE
ORDER BY sort_order;

-- Buscar banco por nombre:
SELECT * FROM banking_institutions
WHERE name LIKE '%BBVA%' OR short_name LIKE '%BBVA%';
*/
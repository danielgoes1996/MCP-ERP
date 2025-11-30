# Sistema de Merchants - Documentación

## 📋 Descripción General

El sistema de merchants permite identificar y clasificar automáticamente comercios en tickets de compra, facilitando la facturación automática y el análisis de gastos.

---

## 🗄️ Estructura de Datos

### Tabla: `merchants`

```sql
CREATE TABLE merchants (
    id UUID PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    rfc VARCHAR(13),

    -- Facturación
    invoicing_method VARCHAR(50),  -- 'portal', 'email', 'api'
    portal_url VARCHAR(500),

    -- Clasificación
    regex_patterns JSONB DEFAULT '[]',
    keywords JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',

    -- Estado
    is_active BOOLEAN DEFAULT true,
    success_rate DECIMAL(5,2) DEFAULT 0.0,
    total_processed INTEGER DEFAULT 0,

    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

---

## 🏪 Catálogo de Merchants

### Merchants Disponibles (24 total)

#### Gasolineras
- **PEMEX** (RFC: PEP970814SF3)
  - Portal: https://factura.pemex.com
  - Patrones: `PEMEX`, `GASOLINERA.*PEMEX`
  - Keywords: pemex, gasolinera, combustible

- **G500** (RFC: GSE0810156V8)
- **BP** (RFC: CSE970508SJ3)

#### Conveniencia
- **OXXO** (RFC: OCO850101XXX)
  - Portal: https://www.oxxo.com/facturacion
  - Requiere ticket para CFDI
- **7-Eleven** (RFC: SEV710101ABC)

#### Supermercados
- **Walmart**, **Soriana**, **Chedraui**, **La Comer**

#### Departamentales
- **Liverpool**, **Palacio de Hierro**, **Sears**

#### Restaurantes
- **Sanborns**, **Starbucks**, **McDonald's**

#### Tiendas Especializadas
- **Home Depot**, **Office Depot**, **Costco**, **Sam's Club**

#### E-commerce
- **Amazon México** (email automation)
- **Mercado Libre**

#### Transporte
- **Uber**, **DiDi**

---

## 🔍 Sistema de Clasificación

### 1. Clasificación por Regex

Los merchants tienen patrones regex para identificación automática:

```python
{
    "regex_patterns": [
        "PEMEX",
        "GASOLINERA.*PEMEX",
        "P\\.E\\.M\\.E\\.X"
    ]
}
```

### 2. Clasificación por Keywords

Búsqueda por palabras clave:

```python
{
    "keywords": [
        "pemex",
        "gasolinera",
        "combustible",
        "gas"
    ]
}
```

### 3. Clasificación Semántica (Futuro)

Embeddings para búsqueda semántica avanzada.

---

## 💻 Uso del API

### Listar Merchants

```python
from modules.invoicing_agent.models import list_merchants

# Listar todos los merchants activos
merchants = list_merchants(tenant_id=3)

# Resultado:
# [
#   {
#     "id": "33085686-fc2b-496f-867c-eecef2b44b76",
#     "nombre": "PEMEX",
#     "rfc": "PEP970814SF3",
#     "metodo_facturacion": "portal",
#     "is_active": True
#   },
#   ...
# ]
```

### Buscar Merchant por Nombre

```python
from modules.invoicing_agent.models import find_merchant_by_name

# Búsqueda fuzzy (case insensitive, LIKE %nombre%)
merchant = find_merchant_by_name("pemex", tenant_id=3)

# Resultado:
# {
#   "id": "33085686-fc2b-496f-867c-eecef2b44b76",
#   "nombre": "PEMEX",
#   "rfc": "PEP970814SF3",
#   ...
# }
```

### Crear Merchant

```python
from modules.invoicing_agent.models import create_merchant

merchant_id = create_merchant(
    nombre="Nuevo Comercio",
    metodo_facturacion="portal",
    rfc="ABC123456DEF",
    portal_url="https://facturacion.comercio.com",
    metadata={
        "category": "retail",
        "auto_invoice": True
    },
    tenant_id=3
)

# Retorna UUID string
```

---

## 🔗 Integración con Tickets

### Relación Merchant → Ticket

```python
from modules.invoicing_agent.models import update_ticket

# Asignar merchant a ticket
ticket = update_ticket(
    ticket_id="d52a4530-b0b4-42d9-8dd8-fb97207e62b2",
    merchant_id="33085686-fc2b-496f-867c-eecef2b44b76",
    merchant_name="PEMEX",
    confidence=0.95
)
```

### Consultar Tickets por Merchant

```sql
SELECT t.*, m.name as merchant_name
FROM tickets t
LEFT JOIN merchants m ON t.merchant_id = m.id
WHERE m.name = 'PEMEX'
  AND t.tenant_id = 3
ORDER BY t.created_at DESC;
```

---

## 📊 Estadísticas de Merchants

### Merchant con Más Procesados

```sql
SELECT
    m.name,
    m.total_processed,
    m.success_rate
FROM merchants m
WHERE m.tenant_id = 3
  AND m.is_active = true
ORDER BY m.total_processed DESC
LIMIT 10;
```

### Tasa de Éxito por Merchant

```sql
SELECT
    m.name,
    ROUND(m.success_rate, 2) as success_rate,
    m.total_processed
FROM merchants m
WHERE m.tenant_id = 3
  AND m.total_processed > 10
ORDER BY m.success_rate DESC;
```

---

## 🎯 Casos de Uso

### 1. Clasificación Automática de Tickets

```python
# Al recibir un ticket de WhatsApp
ticket_id = create_ticket(
    raw_data="Compra en PEMEX por $500",
    tipo="texto",
    user_id=1
)

# Buscar merchant
merchant = find_merchant_by_name("PEMEX")

# Asignar merchant
update_ticket(
    ticket_id=ticket_id,
    merchant_id=merchant["id"],
    merchant_name=merchant["nombre"],
    confidence=0.95
)
```

### 2. Facturación Automática

```python
# Crear job de facturación
job_id = create_invoicing_job(
    ticket_id=ticket_id,
    merchant_id=merchant["id"],
    tenant_id=3
)
```

### 3. Dashboard por Merchant

```sql
SELECT
    m.name as merchant,
    COUNT(t.id) as total_tickets,
    SUM(t.total) as monto_total,
    AVG(t.total) as ticket_promedio
FROM tickets t
JOIN merchants m ON t.merchant_id = m.id
WHERE t.tenant_id = 3
  AND t.created_at >= '2024-01-01'
GROUP BY m.name
ORDER BY monto_total DESC;
```

---

## 🔧 Mantenimiento

### Agregar Nuevo Merchant

```sql
INSERT INTO merchants (
    tenant_id, name, rfc, invoicing_method, portal_url,
    regex_patterns, keywords, metadata
) VALUES (
    3,
    'Nuevo Comercio',
    'COM987654ABC',
    'portal',
    'https://facturacion.comercio.com',
    '["COMERCIO", "NUEVO.*COMERCIO"]'::jsonb,
    '["comercio", "tienda"]'::jsonb,
    '{"category": "retail"}'::jsonb
);
```

### Desactivar Merchant

```sql
UPDATE merchants
SET is_active = false
WHERE name = 'Merchant Obsoleto'
  AND tenant_id = 3;
```

### Actualizar Tasa de Éxito

```sql
UPDATE merchants
SET
    total_processed = total_processed + 1,
    success_rate = (
        SELECT COUNT(*)::DECIMAL / (total_processed + 1) * 100
        FROM tickets t
        WHERE t.merchant_id = merchants.id
          AND t.status = 'processed'
    )
WHERE id = '<merchant_uuid>';
```

---

## 🚀 Mejoras Futuras

1. **Clasificación Semántica**
   - Embeddings con vector similarity
   - Búsqueda por descripción de ticket

2. **Auto-aprendizaje**
   - Actualizar patrones basado en tickets correctamente clasificados
   - Sugerir nuevos merchants automáticamente

3. **Integración con RPA**
   - Configuración de bots por merchant
   - Credenciales encriptadas en metadata

4. **Analytics**
   - Dashboard de métricas por merchant
   - Alertas de cambios en patrones de gasto

---

## 📞 Soporte

Para agregar nuevos merchants o modificar los existentes, contactar al equipo de desarrollo.

**Ubicación del catálogo:** `migrations/003_seed_merchants_catalog.sql`

**API Functions:** `modules/invoicing_agent/models.py`

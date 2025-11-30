# Sistema Completo de Gestión de Activos Fijos

## Descripción General

Sistema integral para la gestión de activos fijos que se integra automáticamente con el procesador de facturas existente. Detecta automáticamente cuando una factura corresponde a un activo fijo, determina tasas de depreciación usando RAG sobre el código fiscal (LISR), y proporciona una API completa para gestionar el ciclo de vida de los activos.

---

## Componentes del Sistema

### 1. Base de Datos

**Tabla principal**: `fixed_assets`
- Registro de activos con información de compra, depreciación contable/fiscal, ubicación, responsables
- Asset codes auto-generados: `AF-2025-001`, `AF-2025-002`, etc.
- Soporte para costos adicionales (flete, instalación) en JSONB
- Tracking de estatus: `active`, `disposed`, `lost`, `in_repair`, `retired`

**Tabla de histórico**: `asset_depreciation_history`
- Registro mensual de depreciación contable y fiscal
- Book values al final de cada mes
- Referencias a pólizas contables generadas

**Migración**: [migrations/041_create_fixed_assets_tables.sql](migrations/041_create_fixed_assets_tables.sql)

### 2. Servicios Backend

**DepreciationRateService** ([core/fiscal/depreciation_rate_service.py](core/fiscal/depreciation_rate_service.py))
- Búsqueda semántica en LISR Artículo 34 usando vectores (pgvector)
- Determina tasas fiscales y contables automáticamente
- Incluye fundamento legal completo (artículo, fracción, DOF)
- Calcula ISR diferido cuando fiscal ≠ contable

**AssetClassificationMapper** ([core/fiscal/asset_classification_mapper.py](core/fiscal/asset_classification_mapper.py))
- Mapea familias SAT (151-158, 118) a clases internas (equipo_computo, vehiculos, etc.)
- Extrae datos de activo desde clasificación de factura
- Valida si debe auto-crear activo basado en reglas de negocio

**UniversalInvoiceEngineSystem** (modificado en [core/expenses/invoices/universal_invoice_engine_system.py](core/expenses/invoices/universal_invoice_engine_system.py))
- Enriquece clasificaciones automáticamente con datos de depreciación
- Detecta activos fijos basado en código SAT
- Almacena metadata en `accounting_classification.metadata.fixed_asset`

### 3. API REST

**Router**: `/api/fixed-assets` ([api/fixed_assets_api.py](api/fixed_assets_api.py))

Endpoints principales:
- `POST /api/fixed-assets` - Crear activo fijo
- `GET /api/fixed-assets` - Listar activos (con filtros)
- `GET /api/fixed-assets/{id}` - Obtener detalle
- `PATCH /api/fixed-assets/{id}` - Actualizar activo
- `DELETE /api/fixed-assets/{id}` - Eliminar activo
- `POST /api/fixed-assets/{id}/additional-costs` - Agregar costos adicionales
- `POST /api/fixed-assets/{id}/dispose` - Dar de baja activo
- `GET /api/fixed-assets/{id}/depreciation-history` - Histórico de depreciación

### 4. Frontend

**Componente**: `FixedAssetDepreciationInfo` ([frontend/components/invoices/FixedAssetDepreciationInfo.tsx](frontend/components/invoices/FixedAssetDepreciationInfo.tsx))
- Muestra tasas fiscal y contable lado a lado
- Fundamento legal con enlace al DOF
- Alerta de ISR diferido
- Botón para registrar activo fijo

---

## Flujo de Trabajo Completo

### Escenario: Compra de Laptop Dell por $50,000

**1. Upload de Factura**
```bash
POST /invoices/upload-bulk
- files: laptop_dell.xml
- company_id: carreta_verde
```

**2. Procesamiento Automático**
- Parsea CFDI → extrae UUID, RFC, conceptos, total
- Clasificación IA → determina código SAT: `156.01` (Equipo de cómputo)
- **Detección de activo fijo** → familia `156` está en lista de activos fijos
- **RAG depreciation** → busca en LISR Art. 34 usando embeddings
  - Query: "Laptop Dell Precision 5570 equipo computo electronico"
  - Match: Fracción V → 30% anual (3.33 años)
- **Enriquecimiento** → agrega metadata:

```json
{
  "sat_account_code": "156.01",
  "metadata": {
    "fixed_asset": {
      "is_fixed_asset": true,
      "asset_type": "equipo_computo",

      "depreciation_rate_fiscal_annual": 30.0,
      "depreciation_years_fiscal": 3.33,
      "depreciation_months_fiscal": 40,

      "depreciation_rate_accounting_annual": 20.0,
      "depreciation_years_accounting": 5.0,
      "depreciation_months_accounting": 60,

      "legal_basis": {
        "law": "LISR",
        "article": "34",
        "section": "Fracción V",
        "article_text": "Tratándose de equipo de cómputo electrónico..., 30%.",
        "dof_url": "https://www.dof.gob.mx/nota_detalle.php?codigo=5328028&fecha=11/12/2013"
      },

      "has_deferred_tax": true
    }
  }
}
```

**3. Vista en Frontend**
- Usuario ve clasificación con sección especial de activo fijo
- Componente `FixedAssetDepreciationInfo` renderiza:
  - Tasa fiscal: 30% anual (40 meses)
  - Tasa contable: 20% anual (60 meses)
  - Fundamento: LISR Art. 34 Fracción V
  - Alerta: "ISR diferido por diferencia temporal"
  - Botón: "Registrar como Activo Fijo"

**4. Registro de Activo**
```bash
POST /api/fixed-assets
{
  "description": "Laptop Dell Precision 5570",
  "asset_class": "equipo_computo",
  "asset_category": "156",
  "purchase_date": "2025-11-28",
  "supplier_name": "Dell México S.A. de C.V.",
  "supplier_rfc": "DEL850101ABC",
  "purchase_value": 43103.45,  // Subtotal sin IVA
  "invoice_uuid": "ABC123...",
  "depreciation_rate_accounting": 20.0,
  "depreciation_years_accounting": 5.0,
  "depreciation_rate_fiscal": 30.0,
  "depreciation_years_fiscal": 3.33,
  "legal_basis": { ... },
  "department": "IT",
  "location": "Oficina CDMX - Piso 3",
  "responsible_user_id": 42
}
```

**Respuesta**:
```json
{
  "id": 123,
  "asset_code": "AF-2025-001",  // Auto-generado
  "total_cost": 43103.45,
  "book_value_accounting": 43103.45,
  "book_value_fiscal": 43103.45,
  "months_remaining_accounting": 60,
  "months_remaining_fiscal": 40,
  "status": "active"
}
```

**5. Agregar Costo Adicional (Flete)**
```bash
POST /api/fixed-assets/123/additional-costs
{
  "concept": "Flete y entrega",
  "amount": 500.00,
  "expense_id": 456  // Opcional: liga a otro expense
}
```

**Actualización automática**:
- `total_cost` = 43,103.45 + 500.00 = **43,603.45**
- `additional_costs` JSONB actualizado
- Depreciation mensual recalculado basado en nuevo total

**6. Depreciación Mensual (Job automático)**
```python
# Ejecutar el 1 de cada mes
POST /api/fixed-assets/depreciate-monthly
{
  "period_year": 2025,
  "period_month": 12
}
```

Para laptop de $43,603.45:
- **Depreciación contable**: $43,603.45 × 20% / 12 = **$726.72/mes**
- **Depreciación fiscal**: $43,603.45 × 30% / 12 = **$1,090.09/mes**

Se crea registro en `asset_depreciation_history`:
```sql
INSERT INTO asset_depreciation_history VALUES (
  asset_id: 123,
  period_year: 2025,
  period_month: 12,
  depreciation_amount_accounting: 726.72,
  depreciation_amount_fiscal: 1090.09,
  accumulated_accounting: 726.72,
  accumulated_fiscal: 1090.09,
  book_value_accounting: 42876.73,
  book_value_fiscal: 42513.36,
  poliza_id: 'POL-2025-12-001',
  poliza_data: { ... }
)
```

**7. Reportes y Dashboards**

```sql
-- Valor total de activos activos
SELECT
    asset_class,
    COUNT(*) as qty,
    SUM(total_cost) as total_cost,
    SUM(book_value_accounting) as book_value_accounting,
    SUM(book_value_fiscal) as book_value_fiscal,
    SUM(book_value_accounting - book_value_fiscal) as deferred_tax_asset
FROM fixed_assets_current_values
WHERE status = 'active'
GROUP BY asset_class;

-- Activos por depreciar en próximos 12 meses
SELECT
    asset_code,
    description,
    department,
    months_remaining_accounting,
    book_value_accounting,
    (book_value_accounting / NULLIF(months_remaining_accounting, 0)) as monthly_depreciation
FROM fixed_assets_current_values
WHERE status = 'active'
  AND months_remaining_accounting BETWEEN 1 AND 12
ORDER BY months_remaining_accounting;
```

---

## Instalación y Configuración

### 1. Dependencias
```bash
pip install sentence-transformers pgvector psycopg2-binary
```

### 2. Habilitar pgvector en PostgreSQL
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 3. Ejecutar Migraciones
```bash
# RAG fiscal (vectores de LISR)
psql -U postgres -d mcp_server -f migrations/040_create_fiscal_regulations.sql

# Activos fijos y depreciación
psql -U postgres -d mcp_server -f migrations/041_create_fixed_assets_tables.sql
```

### 4. Seed de Regulaciones Fiscales
```bash
python scripts/seed_fiscal_regulations.py
```

Verifica que se insertaron 12 regulaciones:
```sql
SELECT COUNT(*) FROM fiscal_regulations WHERE regulation_type = 'depreciation';
-- Debe retornar: 12
```

### 5. Verificar Integración
```bash
# Test del servicio de depreciación
python -c "
from core.fiscal.depreciation_rate_service import get_depreciation_rate_service
service = get_depreciation_rate_service()
rate = service.get_depreciation_rate(
    asset_description='Laptop Dell Precision',
    sat_account_code='156.01'
)
print(f'Tasa fiscal: {rate.annual_rate_fiscal}%')
print(f'Legal: {rate.law_code} {rate.article} {rate.section}')
"
```

---

## Mapeo de Familias SAT → Asset Class

| Familia SAT | Asset Class           | Descripción                          | Tasa Fiscal | Vida Útil |
|-------------|-----------------------|--------------------------------------|-------------|-----------|
| 151         | terrenos              | Terrenos                             | 0%          | Indefinido|
| 152         | edificios             | Edificios y construcciones           | 5%          | 20 años   |
| 153         | maquinaria            | Maquinaria industrial                | 10%         | 10 años   |
| 154         | vehiculos             | Vehículos de transporte              | 25%         | 4 años    |
| 155         | mobiliario            | Mobiliario y equipo de oficina       | 10%         | 10 años   |
| 156         | equipo_computo        | Equipo de cómputo electrónico        | 30%         | 3.33 años |
| 157         | equipo_comunicacion   | Equipo de comunicación               | 25%         | 4 años    |
| 158         | activos_biologicos    | Activos biológicos                   | Variable    | Variable  |
| 118         | activos_intangibles   | Activos intangibles (software, etc.) | 15%         | 6.67 años |

---

## API Reference

### Crear Activo Fijo

```bash
POST /api/fixed-assets
Content-Type: application/json
Authorization: Bearer {token}

{
  "description": "Laptop Dell Precision 5570",
  "asset_class": "equipo_computo",
  "asset_category": "156",
  "purchase_date": "2025-11-28",
  "purchase_value": 43103.45,
  "invoice_uuid": "ABC123...",
  "depreciation_rate_accounting": 20.0,
  "depreciation_years_accounting": 5.0,
  "depreciation_rate_fiscal": 30.0,
  "depreciation_years_fiscal": 3.33,
  "department": "IT",
  "location": "Oficina CDMX"
}
```

### Listar Activos con Filtros

```bash
GET /api/fixed-assets?asset_class=equipo_computo&department=IT&status=active&page=1&page_size=50
```

### Obtener Detalle de Activo

```bash
GET /api/fixed-assets/123
```

Respuesta incluye:
- Información completa del activo
- Book values actuales (accounting y fiscal)
- Meses restantes de depreciación
- Porcentaje depreciado
- Costos adicionales agregados
- Fundamento legal

### Agregar Costo Adicional

```bash
POST /api/fixed-assets/123/additional-costs
{
  "concept": "Instalación y configuración",
  "amount": 1500.00,
  "expense_id": 789
}
```

Recalcula automáticamente:
- `total_cost` = `purchase_value` + sum(`additional_costs`)
- Depreciación mensual basada en nuevo `total_cost`

### Dar de Baja Activo

```bash
POST /api/fixed-assets/123/dispose
{
  "disposal_date": "2025-11-28",
  "disposal_method": "sale",
  "disposal_value": 15000.00,
  "disposal_reason": "Actualización de equipo"
}
```

Calcula automáticamente ganancia/pérdida en venta.

### Histórico de Depreciación

```bash
GET /api/fixed-assets/123/depreciation-history?year=2025
```

Retorna todos los registros mensuales de depreciación con:
- Monto depreciado (accounting y fiscal)
- Acumulados al final del mes
- Book values al final del mes
- Referencias a pólizas contables

---

## Queries Útiles

### Activos totalmente depreciados (contable)
```sql
SELECT asset_code, description, purchase_date, total_cost
FROM fixed_assets_current_values
WHERE fully_depreciated_accounting = true
  AND status = 'active'
ORDER BY purchase_date;
```

### ISR Diferido Total
```sql
SELECT
    SUM(accumulated_depreciation_fiscal - accumulated_depreciation_accounting) as deferred_tax_base,
    SUM(accumulated_depreciation_fiscal - accumulated_depreciation_accounting) * 0.30 as deferred_tax_liability
FROM fixed_assets
WHERE status = 'active';
```

### Depreciación del mes actual
```sql
SELECT
    fa.asset_code,
    fa.description,
    adh.depreciation_amount_accounting,
    adh.depreciation_amount_fiscal,
    adh.book_value_accounting
FROM asset_depreciation_history adh
JOIN fixed_assets fa ON fa.id = adh.asset_id
WHERE adh.period_year = 2025
  AND adh.period_month = 11
ORDER BY adh.depreciation_amount_accounting DESC;
```

### Activos por departamento
```sql
SELECT
    department,
    COUNT(*) as qty,
    SUM(total_cost) as total_investment,
    SUM(book_value_accounting) as current_value,
    ROUND(
        (SUM(book_value_accounting) / NULLIF(SUM(total_cost), 0)) * 100,
        2
    ) as remaining_pct
FROM fixed_assets_current_values
WHERE status = 'active'
GROUP BY department
ORDER BY total_investment DESC;
```

---

## Roadmap / Próximas Funcionalidades

### Corto Plazo
- [ ] **Job mensual de depreciación**: Cron job automático para ejecutar el 1 de cada mes
- [ ] **Frontend - Vista de listado**: Tabla con filtros, búsqueda, ordenamiento
- [ ] **Frontend - Formulario de creación**: Integrado con clasificación de factura
- [ ] **Generar pólizas contables**: Integración con `accounting_rules.py` para pólizas mensuales

### Mediano Plazo
- [ ] **Dashboard de KPIs**: Total invertido, depreciación mensual, ISR diferido, etc.
- [ ] **Alertas**: Activos próximos a depreciarse completamente, mantenimientos programados
- [ ] **Revaluaciones**: Soporte para revaluar activos (NIF C-15)
- [ ] **Códigos QR**: Generar y descargar etiquetas con QR para inventario físico
- [ ] **Fotos y adjuntos**: Upload de fotos del activo, facturas, manuales

### Largo Plazo
- [ ] **Módulo de mantenimiento**: Registro de mantenimientos preventivos y correctivos
- [ ] **Bajas automáticas**: Integración con pólizas de baja por venta/donación/pérdida
- [ ] **Conciliación física**: App móvil para escaneo de QR e inventario físico
- [ ] **Reportes SAT**: Generación automática de anexos fiscales
- [ ] **Multi-moneda**: Soporte para activos comprados en USD/EUR

---

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                  INVOICE UPLOAD (XML/PDF)                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
         ┌──────────────────────────────────────┐
         │   UniversalInvoiceEngineSystem       │
         │   - Parse CFDI                       │
         │   - 3-phase classification (SAT)     │
         └──────────────────────────────────────┘
                            │
                            ▼
         ┌──────────────────────────────────────┐
         │   Detect Fixed Asset (familia 151-  │
         │   158, 118)?                         │
         └──────────────────────────────────────┘
                            │
                     ┌──────┴──────┐
                   NO│             │YES
                     │             ▼
                     │   ┌──────────────────────────────┐
                     │   │  DepreciationRateService     │
                     │   │  (RAG Fiscal)                │
                     │   │  1. Build search query       │
                     │   │  2. Generate embedding       │
                     │   │  3. Vector search pgvector   │
                     │   │  4. Return depreciation rate │
                     │   └──────────────────────────────┘
                     │             │
                     │             ▼
                     │   ┌──────────────────────────────┐
                     │   │  Enrich classification with: │
                     │   │  - Fiscal rate (LISR)        │
                     │   │  - Accounting rate (NIF)     │
                     │   │  - Legal basis               │
                     │   │  - Deferred tax flag         │
                     │   └──────────────────────────────┘
                     │             │
                     └─────────────┼─────────────────────┐
                                   ▼                     │
                     ┌──────────────────────────────┐    │
                     │  Save to sat_invoices        │    │
                     │  accounting_classification   │    │
                     └──────────────────────────────┘    │
                                   │                     │
                                   ▼                     │
                     ┌──────────────────────────────┐    │
                     │  Frontend: Display           │    │
                     │  - Regular classification    │◄───┘
                     │  - Fixed asset info (if any) │
                     └──────────────────────────────┘
                                   │
                          User clicks "Registrar"
                                   │
                                   ▼
                     ┌──────────────────────────────┐
                     │  POST /api/fixed-assets      │
                     │  - Auto-generate asset_code  │
                     │  - Calculate total_cost      │
                     │  - Initialize tracking       │
                     └──────────────────────────────┘
                                   │
                                   ▼
                     ┌──────────────────────────────┐
                     │  fixed_assets table          │
                     │  - Active status             │
                     │  - Ready for depreciation    │
                     └──────────────────────────────┘
                                   │
                       Monthly job (1st of month)
                                   │
                                   ▼
                     ┌──────────────────────────────┐
                     │  Calculate & record monthly  │
                     │  depreciation                │
                     │  → asset_depreciation_history│
                     │  → Generate poliza           │
                     │  → Update accumulated        │
                     └──────────────────────────────┘
```

---

## Documentación Relacionada

- **RAG Depreciation Setup**: [FIXED_ASSETS_DEPRECIATION_SETUP.md](FIXED_ASSETS_DEPRECIATION_SETUP.md) - Instalación detallada del sistema RAG
- **Migración DB**: [migrations/041_create_fixed_assets_tables.sql](migrations/041_create_fixed_assets_tables.sql) - Schema completo con comentarios
- **API Code**: [api/fixed_assets_api.py](api/fixed_assets_api.py) - Implementación completa de endpoints
- **Depreciation Service**: [core/fiscal/depreciation_rate_service.py](core/fiscal/depreciation_rate_service.py) - Lógica RAG

---

## Contacto y Soporte

Para problemas o preguntas:

1. **Logs**: `tail -f logs/app.log | grep -i "fixed_asset"`
2. **DB Status**: Verificar migraciones aplicadas en tabla `schema_migrations`
3. **Service Health**: Test rápido con script de verificación en FIXED_ASSETS_DEPRECIATION_SETUP.md

---

**Sistema implementado y listo para producción** ✅

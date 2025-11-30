# Sistema de Tasas de Depreciación con RAG Fiscal

## 📋 Resumen

Este sistema detecta automáticamente activos fijos en facturas y determina tasas de depreciación fiscal y contable usando **RAG (Retrieval Augmented Generation)** sobre el Código Fiscal mexicano (LISR Artículo 34).

### ✨ Funcionalidades

- **Detección automática** de activos fijos en facturas (SAT familias 151-158, 118)
- **Búsqueda semántica** en regulaciones fiscales usando embeddings vectoriales
- **Tasas fiscales** (LISR) para declaraciones SAT
- **Tasas contables** (NIF) para estados financieros
- **Respaldo legal** con artículo, fracción y DOF
- **ISR diferido** automático cuando fiscal ≠ contable
- **UI dedicada** para mostrar información de depreciación

### 🎯 Ejemplo de Resultado

Cuando se sube una factura de una laptop Dell:

```json
{
  "sat_account_code": "156.01",
  "sat_account_name": "Equipo de cómputo electrónico",
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
        "article_text": "Tratándose de equipo de cómputo electrónico..., 30%."
      },

      "has_deferred_tax": true
    }
  }
}
```

---

## 🚀 Instalación

### Paso 1: Instalar Dependencias

```bash
cd /Users/danielgoes96/Desktop/mcp-server

# Instalar sentence-transformers para embeddings
pip install sentence-transformers

# Verificar que psycopg2 y pgvector estén instalados
pip install psycopg2-binary pgvector
```

### Paso 2: Habilitar pgvector en PostgreSQL

```bash
# Conectar a PostgreSQL
psql -U postgres -d mcp_server

# Habilitar extensión pgvector
CREATE EXTENSION IF NOT EXISTS vector;

# Verificar instalación
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### Paso 3: Ejecutar Migración

```bash
# Aplicar migración para crear tabla fiscal_regulations
psql -U postgres -d mcp_server -f migrations/040_create_fiscal_regulations.sql
```

Verifica que la tabla se creó:

```sql
\d fiscal_regulations
```

Deberías ver columnas como `content_embedding vector(384)`.

### Paso 4: Seed de Regulaciones Fiscales

```bash
# Ejecutar script de seed para insertar Artículo 34 LISR
python scripts/seed_fiscal_regulations.py
```

**Salida esperada**:

```
🚀 Starting fiscal regulations seed process...
Loading sentence-transformers model...
✅ Model loaded
Connecting to PostgreSQL at localhost...
✅ Connected to database
Clearing existing depreciation regulations...
✅ Deleted 0 existing regulations
Processing 12 Article 34 provisions...
  [1/12] Processing Fracción II...
  [2/12] Processing Fracción III...
  ...
✅ Successfully inserted 12 fiscal regulations
✅ Verification: 12 regulations in database

🧪 Testing semantic search...
  Query: 'laptop dell computadora'
  → Match: Art. 34 Fracción V - 30.0% (similarity: 95.23%)

  Query: 'escritorio silla muebles oficina'
  → Match: Art. 34 Fracción VI - 10.0% (similarity: 92.45%)

  Query: 'camioneta nissan vehículo'
  → Match: Art. 34 Fracción VIII - 25.0% (similarity: 93.87%)

✅ Fiscal regulations seed completed successfully!
```

### Paso 5: Verificar Servicio

```python
# Test rápido del servicio
python -c "
from core.fiscal.depreciation_rate_service import get_depreciation_rate_service

service = get_depreciation_rate_service()
rate = service.get_depreciation_rate(
    asset_description='Laptop Dell Precision 5570',
    sat_account_code='156.01',
    sat_product_code='43211500'
)

print(f'Tasa fiscal: {rate.annual_rate_fiscal}%')
print(f'Artículo: {rate.law_code} {rate.article} {rate.section}')
print(f'Confianza: {rate.confidence:.2%}')
"
```

**Salida esperada**:

```
Tasa fiscal: 30.0%
Artículo: LISR 34 Fracción V
Confianza: 95%
```

---

## 🔧 Configuración

### Ajustar Tasas Contables

Si quieres cambiar las políticas de depreciación contable (diferentes de las fiscales), edita:

**Archivo**: `core/fiscal/depreciation_rate_service.py`

**Método**: `_determine_accounting_rate()`

```python
def _determine_accounting_rate(self, ...):
    # Ejemplo: Depreciar equipo de cómputo en 4 años contablemente
    if asset_type == 'equipo_computo':
        accounting_years = 4.0  # En lugar de 5.0
        accounting_months = 48
        accounting_rate = 25.0

    return accounting_rate, accounting_years, accounting_months
```

### Agregar Nuevas Regulaciones

Para agregar más artículos fiscales (ej: LISR Art. 36 límites de deducción):

1. Edita `scripts/seed_fiscal_regulations.py`
2. Agrega nuevo objeto en `ARTICLE_34_PROVISIONS`
3. Re-ejecuta seed: `python scripts/seed_fiscal_regulations.py`

---

## 📊 Uso en Producción

### Flujo Automático

Cuando se sube una factura:

1. **Upload** → `/invoices/upload-bulk`
2. **Parseo CFDI** → Extrae UUID, RFC, conceptos
3. **Clasificación IA** → Determina cuenta SAT (ej: 156.01)
4. **Detección de activo** → Si familia 151-158 → Es activo fijo
5. **RAG fiscal** → Busca en LISR Art. 34 usando embeddings
6. **Enrichment** → Agrega tasas fiscal/contable con respaldo legal
7. **Guardar** → En `sat_invoices.accounting_classification.metadata.fixed_asset`

### Consultar Clasificaciones con Activos

```sql
-- Ver facturas clasificadas como activos fijos
SELECT
    id,
    parsed_data->>'uuid' as uuid,
    accounting_classification->>'sat_account_code' as sat_code,
    accounting_classification->'metadata'->'fixed_asset'->>'asset_type' as asset_type,
    accounting_classification->'metadata'->'fixed_asset'->>'depreciation_rate_fiscal_annual' as fiscal_rate,
    accounting_classification->'metadata'->'fixed_asset'->'legal_basis'->>'section' as lisr_section
FROM sat_invoices
WHERE accounting_classification->'metadata'->'fixed_asset'->>'is_fixed_asset' = 'true'
ORDER BY created_at DESC;
```

### API Endpoint (Ya Integrado)

```bash
# Obtener clasificación de factura con activo fijo
GET /api/invoice-classification/session/{session_id}
```

**Respuesta incluirá**:

```json
{
  "session_id": "abc123",
  "accounting_classification": {
    "sat_account_code": "156.01",
    "metadata": {
      "fixed_asset": {
        "is_fixed_asset": true,
        "depreciation_rate_fiscal_annual": 30.0,
        "legal_basis": { ... }
      }
    }
  }
}
```

---

## 🎨 Frontend

### Usar Componente React

```tsx
import { FixedAssetDepreciationInfo } from '@/components/invoices/FixedAssetDepreciationInfo';

function InvoiceClassificationView() {
  const classification = useClassification(sessionId);
  const fixedAssetData = classification?.metadata?.fixed_asset;

  return (
    <div>
      {/* ... otras secciones ... */}

      {fixedAssetData && (
        <FixedAssetDepreciationInfo
          data={fixedAssetData}
          onCreateAsset={() => {
            // Navegar a formulario de registro de activo fijo
            router.push(`/fixed-assets/new?session=${sessionId}`);
          }}
        />
      )}
    </div>
  );
}
```

El componente mostrará:

- ✅ Tasas fiscal y contable lado a lado
- ✅ Fundamento legal completo con enlace al DOF
- ✅ Alerta si hay ISR diferido
- ✅ Botón para registrar como activo fijo
- ✅ Confianza de la clasificación

---

## 🧪 Testing

### Test Unitario del Servicio

```python
# tests/test_depreciation_service.py

def test_laptop_depreciation():
    service = get_depreciation_rate_service()

    rate = service.get_depreciation_rate(
        asset_description="Laptop HP EliteBook 840 G9",
        sat_account_code="156.01"
    )

    assert rate.annual_rate_fiscal == 30.0
    assert rate.years_fiscal == 3.33
    assert rate.law_code == "LISR"
    assert rate.article == "34"
    assert rate.section == "Fracción V"
    assert rate.confidence > 0.9

def test_furniture_depreciation():
    service = get_depreciation_rate_service()

    rate = service.get_depreciation_rate(
        asset_description="Escritorio ejecutivo con cajonera",
        sat_account_code="155.01"
    )

    assert rate.annual_rate_fiscal == 10.0
    assert rate.years_fiscal == 10.0
    assert rate.section == "Fracción VI"
```

### Test End-to-End

```bash
# 1. Subir factura de activo fijo
curl -X POST http://localhost:8000/invoices/upload-bulk \
  -F "files=@laptop_dell.xml" \
  -F "company_id=carreta_verde"

# 2. Obtener batch_id de respuesta
# batch_id: "batch_abc123"

# 3. Procesar batch
curl -X POST http://localhost:8000/invoices/process-batch/batch_abc123

# 4. Verificar clasificación incluye fixed_asset
curl http://localhost:8000/api/invoice-classification/session/{session_id} | jq '.accounting_classification.metadata.fixed_asset'
```

---

## 📚 Arquitectura

```
┌──────────────────────────────────────────────────────────┐
│           INVOICE UPLOAD & CLASSIFICATION                │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────┐
         │  UniversalInvoiceEngineSystem  │
         │  - Parsea CFDI                 │
         │  - Clasifica con IA (SAT code) │
         └────────────────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────┐
         │  _enrich_with_depreciation_    │
         │  rates()                       │
         │  - Detecta familia 151-158     │
         │  - Llama DepreciationService   │
         └────────────────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────┐
         │  DepreciationRateService       │
         │  - Build search query          │
         │  - Generate embedding          │
         │  - Query fiscal_regulations    │
         │  - Vector similarity search    │
         └────────────────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────┐
         │  PostgreSQL + pgvector         │
         │  fiscal_regulations table      │
         │  - LISR Art. 34 vectorizado    │
         │  - Búsqueda <=> similarity     │
         └────────────────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────┐
         │  DepreciationRate (result)     │
         │  - Fiscal: 30% (3.33 años)     │
         │  - Accounting: 20% (5 años)    │
         │  - Legal: LISR 34-V            │
         │  - Confidence: 95%             │
         └────────────────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────┐
         │  Enrich classification_dict    │
         │  metadata.fixed_asset = {...}  │
         └────────────────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────┐
         │  Save to sat_invoices          │
         │  accounting_classification     │
         └────────────────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────┐
         │  Frontend: Display             │
         │  FixedAssetDepreciationInfo    │
         └────────────────────────────────┘
```

---

## 🔐 Mantenimiento

### Actualizar Tasas Fiscales

Cuando el SAT publique nuevas tasas en el DOF:

1. Editar `scripts/seed_fiscal_regulations.py`
2. Actualizar `effective_date` y `dof_publication_date`
3. Marcar regulaciones viejas como `superseded`:

```sql
UPDATE fiscal_regulations
SET status = 'superseded',
    superseded_date = '2026-01-01'
WHERE law_code = 'LISR'
  AND article_number = '34'
  AND section = 'Fracción V'
  AND effective_date = '2014-01-01';
```

4. Re-ejecutar seed con nuevas tasas

### Monitoreo

```sql
-- Ver regulaciones activas
SELECT law_code, article_number, section, title, effective_date
FROM fiscal_regulations
WHERE status = 'active'
ORDER BY law_code, article_number;

-- Ver tasas más usadas (logs de clasificación)
SELECT
    accounting_classification->'metadata'->'fixed_asset'->'legal_basis'->>'section' as lisr_section,
    COUNT(*) as usage_count
FROM sat_invoices
WHERE accounting_classification->'metadata'->'fixed_asset'->>'is_fixed_asset' = 'true'
GROUP BY lisr_section
ORDER BY usage_count DESC;
```

---

## ✅ Checklist de Instalación

- [ ] Instalar `sentence-transformers`
- [ ] Habilitar `pgvector` en PostgreSQL
- [ ] Ejecutar migración `040_create_fiscal_regulations.sql`
- [ ] Ejecutar seed `python scripts/seed_fiscal_regulations.py`
- [ ] Verificar 12 regulaciones insertadas
- [ ] Test del servicio con ejemplo de laptop
- [ ] Subir factura de prueba y verificar clasificación
- [ ] Componente React renderiza correctamente

---

## 📞 Soporte

Si tienes problemas:

1. **Verificar logs**: `tail -f logs/app.log | grep -i depreciation`
2. **Test de embeddings**: El modelo se descarga automáticamente la primera vez
3. **Conectividad PostgreSQL**: Verificar `core/shared/db_config.py`
4. **pgvector**: `SELECT * FROM pg_extension WHERE extname = 'vector';`

---

## 🎉 Resultado Final

Con este sistema, cada factura de activo fijo se clasifica automáticamente con:

✅ Tasa fiscal (LISR) para SAT
✅ Tasa contable (NIF) para estados financieros
✅ Respaldo legal completo con artículo del DOF
✅ ISR diferido calculado automáticamente
✅ UI clara para contadores y administradores
✅ RAG semántico para máxima precisión

**¡Todo automático! 🚀**

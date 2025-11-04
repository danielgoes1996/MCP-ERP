# Fiscal pipeline v1

La capa fiscal integra reglas deterministas, catálogos SAT y CFDI para
mantener trazabilidad completa desde la detección de datos hasta la
clasificación final.

## Orden de priorización

1. **Reglas de proveedor (`provider_rules`)**
   - Coincidencia exacta por `tenant_id` + nombre normalizado.
   - Aplica de forma determinista `category_slug`, códigos SAT e IVA
     predeterminados.
   - Actualiza `expense_records.tax_source = 'rule'` y
     `classification_source = 'provider_rule'` con explicaciones cortas
     y detalladas.

2. **Catálogo contable (`ACCOUNTING_CATEGORY_CATALOG`)**
   - Búsqueda por sinónimos en descripción/proveedor.
   - Mapea `category_slug` → códigos SAT desde `CATEGORY_SAT_MAPPING`.
   - Marca `tax_source = 'rule'`, `classification_source = 'catalog_keyword'`.

3. **LLM (Claude/GPT)**
   - Se ejecuta solo si no hay regla ni coincidencia de catálogo.
   - El callback LLM debe regresar `category_slug`, códigos SAT,
     explicación y confianza.
   - Actualiza `tax_source = 'llm'`, `classification_source = 'llm_claude'`
     (o el valor indicado por el callback) y persiste la sugerencia en
     `category_prediction_history`.

4. **CFDI**
   - `on_cfdi_received` busca gastos por monto, proveedor y fecha ±3 días.
   - Prioriza campos del XML: `ClaveProdServ`, tasa de IVA y totales.
   - Marca `tax_source = 'cfdi'`, `classification_source = 'cfdi_xml'` y
     deja el rastro `"Revalidado con CFDI XML"`.

## Campos nuevos en `expense_records`

- `tax_source` (enum: `llm`, `rule`, `cfdi`, `manual`).
- `explanation_short`, `explanation_detail` para trazabilidad rápida y
  completa.
- `catalog_version` (default `v1`) asegura saber qué catálogo SAT se usó.
- `classification_source` identifica el motor exacto (ej. `provider_rule`,
  `catalog_keyword`, `llm_claude`, `cfdi_xml`).

## Tabla `provider_rules`

Tabla ligera que almacena reglas confirmadas por proveedor:

```
id INTEGER PRIMARY KEY AUTOINCREMENT
tenant_id INTEGER REFERENCES tenants(id)
provider_name_normalized TEXT
category_slug TEXT
sat_account_code TEXT
sat_product_service_code TEXT
default_iva_rate REAL DEFAULT 0
iva_tipo TEXT DEFAULT 'tasa_0'
confidence REAL DEFAULT 0.9
last_confirmed_by INTEGER
last_confirmed_at TIMESTAMP
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

Se recomienda almacenar el nombre en minúsculas sin espacios dobles para
maximizar coincidencias.

## Funciones principales

### `lookup_provider_rule(conn, tenant_id, provider_name)`
Devuelve la regla de mayor confianza para el proveedor. Usa el helper
interno `_normalize_provider_name`.

### `classify_expense_fiscal(conn, expense_id, tenant_id, descripcion, proveedor, monto, llm_classifier=None)`
1. Busca reglas de proveedor.
2. Revisa catálogos por sinónimos.
3. Invoca el LLM si no hubo coincidencias.
4. Actualiza `expense_records` y escribe en
   `category_prediction_history` con `prediction_method = tax_source`.

### `on_cfdi_received(conn, tenant_id, cfdi_data)`
1. Normaliza proveedor y acota la fecha ±3 días.
2. Actualiza sat codes, IVA y estado CFDI.
3. Inserta entrada en `category_prediction_history` con método `cfdi`.

Ambas funciones realizan `commit()` y retornan información mínima para
UI/servicios superiores.

## Flujo resumido

```
voice/OCR → parseo → classify_expense_fiscal → expense_records
                                ↑
                            provider_rules
                                ↑
             correcciones usuario → nuevas reglas persistentes

CFDI XML → on_cfdi_received → revalida SAT + IVA
```

La trazabilidad queda accesible mediante los campos nuevos y los
registros en `category_prediction_history`, listos para auditorías y
explicabilidad ante contadores o SAT.

## UI fiscal v1

- **Tabla principal de gastos**: muestra un badge de fuente (`tax_source`),
  la confianza detectada y tooltip con `explanation_short` y
  `classification_source`. El catálogo utilizado (`catalog_version`) se
  ve como subetiqueta.
- **Acción “Ver trazabilidad”**: abre un panel con CFDI, póliza contable y
  estatus bancario vinculados al gasto, utilizando `explanation_detail` y
  los campos SAT.
- **Dashboard fiscal**: incluye filtros por fuente fiscal (CFDI, reglas,
  IA, manual) y contadores que resumen cuántos gastos provienen de cada
  origen.

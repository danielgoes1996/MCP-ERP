# Endpoint: `/sessions/viewer-pro/{tenant_id}` - Documentación Completa

## Descripción General

Endpoint optimizado para el visualizador Pro de CFDIs. Devuelve datos en formato flat (camelCase) con todos los campos pre-calculados, incluido el contenido XML completo.

## URL

```
GET /universal-invoice/sessions/viewer-pro/{tenant_id}
```

## Parámetros

### Path Parameters

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `tenant_id` | string | Sí | ID del tenant/empresa (ej: "carreta_verde", "default") |

### Query Parameters

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `year` | int | No | - | Filtro por año (ej: 2025) |
| `month` | int | No | - | Filtro por mes (1-12) |
| `tipo` | string | No | - | Filtro por tipo de comprobante: I/E/T/N/P |
| `estatus` | string | No | - | Filtro por estatus SAT: vigente/cancelado/sustituido |
| `search` | string | No | - | Búsqueda por UUID, RFC, nombre, serie/folio |
| `limit` | int | No | 500 | Número máximo de registros a devolver |
| `offset` | int | No | 0 | Offset para paginación |

## Respuesta

### Formato de Respuesta

```json
{
  "success": true,
  "documents": [...],
  "total_count": 100,
  "limit": 500,
  "offset": 0,
  "has_more": false
}
```

### Estructura de Documento (Formato Flat)

Cada documento en el array `documents` tiene la siguiente estructura:

```typescript
interface DocumentoViewer {
  // Identificadores
  id: string;              // ID de sesión
  uuid: string | null;     // UUID del CFDI

  // Serie y Folio
  serie: string | null;
  folio: string | null;

  // Fechas
  fechaEmision: string | null;    // ISO 8601
  fechaTimbrado: string | null;   // ISO 8601

  // Información básica
  tipo: string | null;             // I/E/T/N/P
  moneda: string;                  // Default: "MXN"
  tipoCambio: number | null;

  // Montos
  subtotal: number;                // Default: 0
  descuento: number | null;
  total: number;                   // Default: 0

  // Pago
  formaPago: string | null;        // "01", "02", etc.
  metodoPago: string | null;       // "PUE", "PPD"
  usoCFDI: string | null;          // "G01", "G03", etc.

  // Estatus
  estatusSAT: string;              // "vigente" | "cancelado" | "sustituido" | "desconocido"

  // Emisor
  emisorNombre: string | null;
  emisorRFC: string | null;
  emisorRegimenFiscal: string | null;

  // Receptor
  receptorNombre: string | null;
  receptorRFC: string | null;
  receptorUsoCFDI: string | null;
  receptorDomicilioFiscal: string | null;

  // Impuestos pre-calculados
  impuestosTrasladados: number;    // Suma total de trasladados
  impuestosRetenidos: number;      // Suma total de retenidos

  // Impuestos detallados
  impuestos: {
    trasladados: Array<{
      base: number;
      tipo: string;        // "IVA", "IEPS"
      tasa: number;
      importe: number;
    }>;
    retenidos: Array<{
      base: number;
      tipo: string;        // "ISR", "IVA"
      tasa: number;
      importe: number;
    }>;
  };

  // Conceptos
  conceptos: Array<any>;

  // Tax badges (para UI)
  taxBadges: Array<string>;

  // Complementos
  complementos: Array<{
    tipo: string;
    datos: any;
  }>;

  // Verificación
  selloVerificado: boolean;

  // Relacionados
  relacionados: Array<{
    tipo: string;
    uuid: string;
  }>;

  // XML completo
  xml: string;                     // Contenido XML completo del archivo

  // Notas
  notas: string;

  // Pagos (para complemento de pagos)
  pagos: any;
}
```

## Ejemplos de Uso

### 1. Obtener todas las facturas de un tenant

```bash
curl "http://localhost:8001/universal-invoice/sessions/viewer-pro/carreta_verde?limit=100"
```

### 2. Filtrar por año y mes

```bash
curl "http://localhost:8001/universal-invoice/sessions/viewer-pro/carreta_verde?year=2025&month=9"
```

### 3. Filtrar por tipo de comprobante (Ingresos)

```bash
curl "http://localhost:8001/universal-invoice/sessions/viewer-pro/carreta_verde?tipo=I"
```

### 4. Buscar por UUID

```bash
curl "http://localhost:8001/universal-invoice/sessions/viewer-pro/carreta_verde?search=522A1F68-90C3-11F0-AB6E-5715480B719A"
```

### 5. Buscar por RFC del emisor

```bash
curl "http://localhost:8001/universal-invoice/sessions/viewer-pro/carreta_verde?search=ANE140618P37"
```

### 6. Paginación

```bash
# Primera página
curl "http://localhost:8001/universal-invoice/sessions/viewer-pro/carreta_verde?limit=50&offset=0"

# Segunda página
curl "http://localhost:8001/universal-invoice/sessions/viewer-pro/carreta_verde?limit=50&offset=50"
```

### 7. Combinar filtros

```bash
curl "http://localhost:8001/universal-invoice/sessions/viewer-pro/carreta_verde?year=2025&month=9&tipo=I&estatus=vigente&limit=100"
```

## Ejemplo de Respuesta Completa

```json
{
  "success": true,
  "documents": [
    {
      "id": "uis_010ca556ba95c4cf",
      "uuid": "522A1F68-90C3-11F0-AB6E-5715480B719A",
      "serie": "SellerDebit",
      "folio": "16808751",
      "fechaEmision": "2025-09-13T11:01:42",
      "fechaTimbrado": "2025-09-13T11:01:44",
      "tipo": "I",
      "moneda": "MXN",
      "tipoCambio": null,
      "subtotal": 2.35,
      "descuento": null,
      "total": 2.73,
      "formaPago": "99",
      "metodoPago": "PPD",
      "usoCFDI": "G03",
      "estatusSAT": "vigente",
      "emisorNombre": "SERVICIOS COMERCIALES AMAZON MEXICO",
      "emisorRFC": "ANE140618P37",
      "emisorRegimenFiscal": "601",
      "receptorNombre": "POLLENBEEMX",
      "receptorRFC": "POL210218264",
      "receptorUsoCFDI": "G03",
      "receptorDomicilioFiscal": "76902",
      "impuestosTrasladados": 0.38,
      "impuestosRetenidos": 0,
      "impuestos": {
        "trasladados": [
          {
            "base": 2.35,
            "tipo": "IVA",
            "tasa": 0.16,
            "importe": 0.38
          }
        ],
        "retenidos": []
      },
      "conceptos": [
        {
          "cantidad": 1,
          "descripcion": "Tarifas de almacenamiento de Logística de Amazon:",
          "valorUnitario": 2.35,
          "importe": 2.35
        }
      ],
      "taxBadges": [],
      "complementos": [],
      "selloVerificado": false,
      "relacionados": [],
      "xml": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<cfdi:Comprobante ...>...</cfdi:Comprobante>",
      "notas": "",
      "pagos": {}
    }
  ],
  "total_count": 8,
  "limit": 500,
  "offset": 0,
  "has_more": false
}
```

## Lógica de Filtros

### Filtro por Año y Mes

- Utiliza el campo `fecha_emision` del `extracted_data`
- Si `extracted_data` no tiene `fecha_emision`, el documento NO será incluido
- Formato esperado: `"2025-09-13T11:01:42"` (ISO 8601)

```sql
WHERE EXTRACT(YEAR FROM TO_TIMESTAMP(s.extracted_data->>'fecha_emision', 'YYYY-MM-DD"T"HH24:MI:SS')) = {year}
```

### Filtro por Tipo

- Utiliza el campo `tipo_comprobante` del `extracted_data`
- Valores válidos: `I` (Ingreso), `E` (Egreso), `T` (Traslado), `N` (Nómina), `P` (Pago)

```sql
WHERE s.extracted_data->>'tipo_comprobante' = {tipo}
```

### Filtro por Estatus SAT

- Utiliza el campo `sat_status` del `extracted_data`
- Valores válidos: `vigente`, `cancelado`, `sustituido`

```sql
WHERE s.extracted_data->>'sat_status' = {estatus}
```

### Filtro de Búsqueda (Search)

Busca en múltiples campos usando ILIKE (case-insensitive):

- UUID
- RFC del emisor
- RFC del receptor
- Nombre del emisor
- Nombre del receptor
- Serie + Folio

```sql
WHERE (
  s.extracted_data->>'uuid' ILIKE '%{search}%'
  OR s.extracted_data->'emisor'->>'rfc' ILIKE '%{search}%'
  OR s.extracted_data->'receptor'->>'rfc' ILIKE '%{search}%'
  OR s.extracted_data->'emisor'->>'nombre' ILIKE '%{search}%'
  OR s.extracted_data->'receptor'->>'nombre' ILIKE '%{search}%'
  OR (s.extracted_data->>'serie' || s.extracted_data->>'folio') ILIKE '%{search}%'
)
```

## Campos Pre-calculados

### impuestosTrasladados

Suma de todos los impuestos trasladados:

```python
impuestos_trasladados = sum(
    imp.get('importe', 0)
    for imp in data.get('impuestos', {}).get('trasladados', [])
)
```

### impuestosRetenidos

Suma de todos los impuestos retenidos:

```python
impuestos_retenidos = sum(
    imp.get('importe', 0)
    for imp in data.get('impuestos', {}).get('retenidos', [])
)
```

### XML Content

Lee el archivo XML desde el disco usando `invoice_file_path`:

```python
if session.get('invoice_file_path') and os.path.exists(session['invoice_file_path']):
    with open(session['invoice_file_path'], 'r', encoding='utf-8') as f:
        xml_content = f.read()
```

## Compatibilidad con Datos Incompletos

El endpoint está diseñado para funcionar **incluso con `extracted_data` incompletos**:

### Campos con Defaults

- `moneda`: "MXN" si no existe
- `subtotal`: 0 si no existe
- `total`: 0 si no existe
- `estatusSAT`: "desconocido" si no existe
- `impuestosTrasladados`: 0 si no hay impuestos
- `impuestosRetenidos`: 0 si no hay impuestos

### Campos Nullable

La mayoría de los campos pueden ser `null` si no están en `extracted_data`:
- `uuid`, `serie`, `folio`
- `fechaEmision`, `fechaTimbrado`
- `tipo`, `tipoCambio`, `descuento`
- `formaPago`, `metodoPago`, `usoCFDI`
- Todos los campos de emisor/receptor

### XML Siempre Disponible

**Ventaja clave:** Incluso si `extracted_data` está vacío o incompleto, el XML completo siempre se lee desde el archivo, permitiendo al visualizador mostrar o parsear el XML directamente.

## Performance

### Optimizaciones Implementadas

1. **Single Query**: Una sola consulta SQL obtiene todos los datos
2. **Índices**: Usa índices existentes en `company_id`, `created_at`, `extraction_status`
3. **Paginación**: Límite default de 500, configurable
4. **Lectura de XML**: Solo lee archivos que existen en disco

### Tiempos Estimados

| Operación | Tiempo |
|-----------|--------|
| Query sin filtros (100 docs) | ~50-100ms |
| Query con filtros (100 docs) | ~100-200ms |
| Lectura de XML (por documento) | ~5-10ms |
| **Total para 100 documentos** | **~500ms - 1.5s** |

## Limitaciones Actuales

1. **Complementos**: Array vacío por ahora (pendiente implementación)
2. **selloVerificado**: Siempre `false` (pendiente verificación SAT)
3. **relacionados**: Array vacío (pendiente implementación de relaciones)
4. **Filtros requieren datos completos**: Los filtros por año/mes/tipo/estatus solo funcionan si `extracted_data` tiene esos campos

## Próximas Mejoras

1. ✅ Endpoint creado con estructura flat
2. ✅ XML content incluido
3. ✅ Filtros básicos implementados
4. ⏳ Extraer complementos del XML
5. ⏳ Implementar verificación de sello SAT
6. ⏳ Agregar relaciones entre CFDIs (sustituidos, cancelados)
7. ⏳ Agregar cache para mejorar performance
8. ⏳ Agregar filtros por rango de fechas
9. ⏳ Agregar ordenamiento configurable

## Uso en Frontend

### React/TypeScript

```typescript
import { useState, useEffect } from 'react';

interface Documento {
  id: string;
  uuid: string | null;
  serie: string | null;
  folio: string | null;
  // ... todos los demás campos
}

interface ViewerProResponse {
  success: boolean;
  documents: Documento[];
  total_count: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

const InvoicesPage = () => {
  const [documents, setDocuments] = useState<Documento[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchInvoices = async (filters?: {
    year?: number;
    month?: number;
    tipo?: string;
    search?: string;
  }) => {
    setLoading(true);

    const params = new URLSearchParams();
    if (filters?.year) params.append('year', filters.year.toString());
    if (filters?.month) params.append('month', filters.month.toString());
    if (filters?.tipo) params.append('tipo', filters.tipo);
    if (filters?.search) params.append('search', filters.search);
    params.append('limit', '100');

    const response = await fetch(
      `http://localhost:8001/universal-invoice/sessions/viewer-pro/carreta_verde?${params}`
    );

    const data: ViewerProResponse = await response.json();
    setDocuments(data.documents);
    setLoading(false);
  };

  useEffect(() => {
    fetchInvoices();
  }, []);

  return (
    <div>
      {/* UI del visualizador */}
    </div>
  );
};
```

## Errores Comunes

### Error: "column s.file_path does not exist"

**Causa**: Usar `file_path` en lugar de `invoice_file_path`

**Solución**: El campo correcto es `invoice_file_path`

### Error: 0 documentos con filtros aplicados

**Causa**: `extracted_data` incompleto no tiene los campos necesarios para filtrar

**Solución**:
1. Reprocesar facturas con endpoint `/sessions/reprocess-failed/`
2. Usar el endpoint sin filtros y filtrar en frontend
3. Verificar que los datos existen: `SELECT extracted_data FROM universal_invoice_sessions LIMIT 1;`

### Error: XML vacío ("")

**Causa**: El archivo en `invoice_file_path` no existe o no es accesible

**Solución**:
1. Verificar que el archivo existe: `SELECT invoice_file_path FROM universal_invoice_sessions LIMIT 1;`
2. Verificar permisos del archivo
3. Re-subir el archivo si es necesario

## Testing

### Verificar que el endpoint funciona

```bash
# 1. Verificar salud del endpoint
curl -s "http://localhost:8001/universal-invoice/sessions/viewer-pro/default?limit=1" | jq '.success'
# Debe devolver: true

# 2. Verificar que devuelve documentos
curl -s "http://localhost:8001/universal-invoice/sessions/viewer-pro/default?limit=5" | jq '.total_count'
# Debe devolver un número > 0

# 3. Verificar que el XML se incluye
curl -s "http://localhost:8001/universal-invoice/sessions/viewer-pro/default?limit=1" | jq '.documents[0].xml' | head -5
# Debe mostrar contenido XML

# 4. Verificar filtros
curl -s "http://localhost:8001/universal-invoice/sessions/viewer-pro/default?year=2025" | jq '.total_count'
```

## Logs

El endpoint genera los siguientes logs:

```
INFO - [universal-invoice] /universal-invoice/sessions/viewer-pro/carreta_verde - tenant_id=carreta_verde, year=2025, month=9
INFO - [universal-invoice] Successfully retrieved 100 sessions for viewer pro
```

En caso de error:

```
ERROR - Error fetching sessions for viewer pro: {error_message}
```

---

**Implementado por:** Claude Code
**Fecha:** 2025-11-10
**Estado:** ✅ Completado y probado
**Versión:** 1.0

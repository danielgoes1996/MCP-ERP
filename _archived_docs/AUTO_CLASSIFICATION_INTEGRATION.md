# Auto-Classification Integration

## Resumen

Se ha integrado la clasificación automática con AI en el `BulkInvoiceProcessor`, unificando los dos flujos de carga de facturas:

- **Flow A (SAT Bulk Download)**: Ahora puede clasificar automáticamente las facturas al descargarlas
- **Flow B (Manual Upload)**: Sigue funcionando igual, clasificación al subir

## Cambios Implementados

### 1. Modificaciones en `BulkInvoiceProcessor`

**Archivo**: `core/expenses/invoices/bulk_invoice_processor.py`

**Nuevos métodos**:

- `_should_auto_classify_invoice()`: Determina si una factura debe clasificarse automáticamente
- `_auto_classify_invoice()`: Ejecuta la clasificación usando `UniversalInvoiceEngineSystem`

**Flujo actualizado**:
```python
1. Insertar factura en expense_invoices (INSERT)
2. ⭐ NUEVO: Auto-clasificar si está habilitado (AI classification)
3. Buscar matching con expense_records existentes
4. Crear placeholder si no hay match (opcional)
```

### 2. Configuración de Auto-Clasificación

La clasificación automática se controla mediante `batch_metadata` al crear el batch:

```python
batch_metadata = {
    # Habilitar auto-clasificación
    'auto_classify_enabled': True,  # Default: False

    # Monto mínimo para clasificar (en MXN)
    'auto_classify_min_amount': 10000,  # Default: 0 (todas)

    # Tipos de comprobante a clasificar
    'auto_classify_types': ['I'],  # Default: ['I'] (solo Ingreso)
                                    # Opciones: 'I', 'E', 'P', 'N', 'T'
}
```

### 3. Criterios de Clasificación

Una factura se clasifica automáticamente SI:

1. ✅ `auto_classify_enabled` = True
2. ✅ `total_amount` >= `auto_classify_min_amount`
3. ✅ `tipo_comprobante` está en `auto_classify_types`

## Ejemplos de Uso

### Ejemplo 1: Clasificar solo facturas grandes (>$10,000 MXN)

```python
from core.expenses.invoices.bulk_invoice_processor import BulkInvoiceProcessor

processor = BulkInvoiceProcessor()

# Crear batch con auto-clasificación para facturas grandes
batch = await processor.create_batch(
    company_id='contaflow',
    invoices=invoices_list,
    batch_metadata={
        'auto_classify_enabled': True,
        'auto_classify_min_amount': 10000,  # Solo facturas >$10k
        'auto_classify_types': ['I']  # Solo tipo Ingreso
    }
)

# Procesar batch
result = await processor.process_batch(batch.batch_id)
```

### Ejemplo 2: Clasificar TODAS las facturas

```python
batch = await processor.create_batch(
    company_id='contaflow',
    invoices=invoices_list,
    batch_metadata={
        'auto_classify_enabled': True,
        'auto_classify_min_amount': 0,  # Todas las facturas
        'auto_classify_types': ['I', 'E']  # Ingreso y Egreso
    }
)
```

### Ejemplo 3: SIN auto-clasificación (comportamiento actual)

```python
# Simplemente omite batch_metadata o pon auto_classify_enabled=False
batch = await processor.create_batch(
    company_id='contaflow',
    invoices=invoices_list,
    batch_metadata={
        'auto_classify_enabled': False  # Deshabilitado
    }
)

# O simplemente:
batch = await processor.create_batch(
    company_id='contaflow',
    invoices=invoices_list
    # Sin batch_metadata = auto-clasificación deshabilitada por default
)
```

## Integración con SAT Descarga API

Para habilitar auto-clasificación en descargas masivas del SAT, modifica el endpoint en `sat_descarga_api.py`:

```python
# En descargar_y_procesar_paquete()
batch = await bulk_processor.create_batch(
    company_id=company_id,
    invoices=invoices,
    batch_metadata={
        'auto_classify_enabled': True,
        'auto_classify_min_amount': 10000,  # Configurar según necesidad
        'auto_classify_types': ['I'],
        'source': 'sat_bulk_download'
    }
)
```

## Logging y Monitoreo

La auto-clasificación genera logs detallados:

```
INFO: 🤖 Auto-classifying invoice ABC123.xml (amount: $15,000.00)
INFO: ✅ Auto-classified ABC123.xml: 601.84.01 (confidence: 87.50%)
DEBUG: ✓ Verified dual-write to expense_invoices for ABC123.xml
```

### Verificar clasificaciones en item.metadata

```python
for item in batch.items:
    if item.metadata and item.metadata.get('auto_classified'):
        print(f"Invoice: {item.filename}")
        print(f"SAT Code: {item.metadata['sat_account_code']}")
        print(f"Confidence: {item.metadata['classification_confidence']:.2%}")
        print(f"Session ID: {item.metadata['classification_session_id']}")
```

## Estructura de Datos

### expense_invoices (después de auto-clasificación)

```sql
SELECT
    id,
    uuid,
    filename,
    total,
    accounting_classification,  -- ⭐ JSONB con clasificación AI
    session_id                  -- ⭐ ID de la sesión de clasificación
FROM expense_invoices
WHERE accounting_classification IS NOT NULL;
```

### accounting_classification JSONB

```json
{
    "sat_account_code": "601.84.01",
    "family_code": "601",
    "confidence_sat": 0.875,
    "confidence_family": 0.95,
    "status": "pending_confirmation",
    "classified_at": "2025-11-13T10:30:00Z",
    "explanation_short": "Gastos de software y licencias",
    "model_version": "claude-3-haiku-20240307"
}
```

## Ventajas de esta Arquitectura

### 1. **Configurabilidad**
- Puedes habilitar/deshabilitar auto-clasificación según caso de uso
- Control granular por monto y tipo de comprobante
- No rompe flujos existentes (default = deshabilitado)

### 2. **Eficiencia de Costos**
- Clasificar solo facturas importantes (>$10k)
- Evita costos de AI en facturas pequeñas o irrelevantes
- Clasificación bajo demanda para el resto (usando backfill script)

### 3. **Dual-Write Automático**
- La clasificación se guarda en ambas tablas:
  - `sat_invoices` (audit trail)
  - `expense_invoices` (single source of truth)
- Consistencia garantizada

### 4. **Flexibilidad**
- Lee XML desde `raw_xml` en BD o desde `file_path`
- Funciona con ambos flujos (SAT bulk download + manual upload)
- Failsafe: Si falla clasificación, no detiene el proceso

## Recomendaciones de Uso

### Para Producción

1. **Fase 1 (Ahora)**: Deshabilitar auto-clasificación
   - Ejecutar backfill manual para facturas históricas importantes
   - Configurar `auto_classify_enabled: False` (default)

2. **Fase 2 (1-2 semanas)**: Habilitar para facturas grandes
   ```python
   batch_metadata={
       'auto_classify_enabled': True,
       'auto_classify_min_amount': 20000,  # Solo >$20k MXN
       'auto_classify_types': ['I']
   }
   ```

3. **Fase 3 (1 mes)**: Evaluar resultados y ajustar threshold
   - Monitorear precisión de clasificación
   - Ajustar `auto_classify_min_amount` según ROI
   - Considerar expandir a tipos 'E' (Egreso)

### Para Desarrollo/Testing

```python
# Clasificar TODO para pruebas
batch_metadata={
    'auto_classify_enabled': True,
    'auto_classify_min_amount': 0,
    'auto_classify_types': ['I', 'E', 'P']
}
```

## Próximos Pasos

1. ✅ **Completado**: Integración de auto-clasificación en BulkInvoiceProcessor
2. 🔄 **Pendiente**: Modificar SAT API para usar esta funcionalidad
3. 🔄 **Pendiente**: Ejecutar backfill para 227 facturas históricas de ContaFlow
4. 🔄 **Pendiente**: Agregar métricas de clasificación al dashboard

## Notas Técnicas

### Performance

- Auto-clasificación agrega ~2-5 segundos por factura
- Para 100 facturas con `auto_classify_min_amount: 10000`:
  - Sin auto-clasificación: ~30 segundos
  - Con auto-clasificación (20 facturas >$10k): ~2 minutos

### Manejo de Errores

- Si falla la clasificación, el proceso continúa
- La factura se inserta en `expense_invoices` sin clasificación
- Puede clasificarse después usando el backfill script

### Compatibilidad

- ✅ Compatible con SQLite y PostgreSQL
- ✅ Compatible con facturas CFDI 3.3 y 4.0
- ✅ No requiere cambios en base de datos
- ✅ Backward compatible (default deshabilitado)

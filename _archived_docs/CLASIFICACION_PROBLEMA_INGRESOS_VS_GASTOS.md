# Problema Crítico: Clasificación Incorrecta de Ingresos vs Gastos

**Fecha**: 2025-11-13
**Status**: PROBLEMA IDENTIFICADO - Solución Propuesta

---

## Problema Detectado

Las facturas recibidas (que son GASTOS para la empresa) están siendo clasificadas incorrectamente como INGRESOS (familia 400).

### Resultados de Pruebas (5 facturas)

| Proveedor | SAT Asignado | Familia | ❌ Debería Ser |
|-----------|--------------|---------|---------------|
| FINKOK | **401.01** (Ingresos) | 401 | 613.xx (Gastos admin) |
| Gasolina | 601.01 (Costo ventas) | 601 | ✅ 601/612 (correcto) |
| Envases | **119.02** (IVA importación) | 119 | 601.xx (Insumos) |
| Amazon | **401.02** (Ingresos) | 401 | 612.xx (Logística) |
| Miel | **119.02** (IVA importación) | 119 | 601.xx (Materia prima) |

**Accuracy**: 1/5 = 20% ❌

---

## Causa Raíz

###1. Catálogo SAT Mexicano - Estructura

```
400-499: INGRESOS (cuando la empresa VENDE)
  401: Ventas y servicios gravados
  402: Ventas y servicios exentos
  ...

600-699: GASTOS/COMPRAS (cuando la empresa COMPRA)
  601: Costo de ventas - Compras
  612: Gastos de operación - Transportes
  613: Gastos de administración - Servicios
  614: Gastos de venta - Marketing
  615: Gastos generales
  616: Gastos financieros
  ...
```

### 2. Confusión en el Contexto

**CFDI tipo "I" (Ingreso)** significa:
- Para el **EMISOR** (FINKOK, Amazon, etc.) → Es un INGRESO que están facturando
- Para el **RECEPTOR** (nosotros/Carreta Verde) → Es un GASTO que estamos recibiendo

**El problema**: El embeddings search NO está filtrando por familia. Está buscando en TODO el catálogo SAT (400s + 600s), y el LLM puede confundirse al ver cuentas de ingresos en los candidatos.

### 3. Evidencia en el Código

**Archivo**: `core/ai_pipeline/classification/classification_service.py:48-56`

```python
# Retrieve SAT account candidates via embeddings
candidates_raw = retrieve_relevant_accounts(
    expense_payload=expense_payload,
    top_k=top_k
    # ❌ PROBLEMA: No se usa family_filter
)
```

**Archivo**: `core/accounting/account_catalog.py:458-475`

```python
def retrieve_relevant_accounts(
    expense_payload: Dict[str, Any],
    top_k: int = 5,
    family_filter: Optional[Sequence[str]] = None,  # ✅ Existe pero no se usa
) -> List[Dict[str, Any]]:
```

El parámetro `family_filter` existe pero nunca se pasa desde el servicio de clasificación.

---

## Solución Propuesta

### Opción 1: Filtrar en Embeddings Search (RECOMENDADA)

Modificar `classification_service.py` para SIEMPRE filtrar por familias de GASTOS al clasificar facturas recibidas:

```python
# En core/ai_pipeline/classification/classification_service.py

# Determine expense families (exclude income families 400-499)
EXPENSE_FAMILIES = ['6']  # All 600-699 families (gastos)

# Retrieve SAT account candidates via embeddings - SOLO GASTOS
candidates_raw = retrieve_relevant_accounts(
    expense_payload=expense_payload,
    top_k=top_k,
    family_filter=EXPENSE_FAMILIES  # ✅ Filtrar solo cuentas de gastos
)
```

**Ventajas**:
- Elimina candidatos irrelevantes desde el embeddings search
- LLM solo ve opciones válidas de GASTOS
- Más eficiente (menos candidatos, menor confusión)
- Fix estructural en el flujo

**Desventajas**:
- Requiere identificar correctamente el tipo de documento (ingreso recibido vs ingreso emitido)

### Opción 2: Aclarar en el Prompt del LLM

Modificar el prompt en `expense_llm_classifier.py` para ser MÁS EXPLÍCITO:

```python
prompt = (
    "A continuación se presentan los datos de una FACTURA RECIBIDA (un GASTO para la empresa). "
    "Esta factura representa un gasto/compra que la empresa está pagando a un proveedor.\n"
    "Debes clasificarla en el catálogo SAT usando CUENTAS DE GASTOS (familias 600-699), "
    "NO cuentas de ingresos (400-499).\n\n"
    "Analiza el proveedor y concepto, y selecciona la cuenta SAT de GASTOS más adecuada.\n\n"
    # ... resto del prompt
)
```

**Ventajas**:
- Fix rápido sin cambiar embeddings
- Puede ayudar con casos edge

**Desventajas**:
- Depende de comprensión del LLM
- Los candidatos incorrectos siguen en la lista
- Menos robusto que Opción 1

### Opción 3: Ambas (MÁS ROBUSTO)

Combinar ambas soluciones:
1. Filtrar embeddings por familia 6xx
2. Aclarar en el prompt que es un gasto

---

## Recomendación

**Implementar Opción 3 (Ambas)**:

1. **Modificar `classification_service.py`** para agregar `family_filter=['6']`
2. **Mejorar el prompt** en `expense_llm_classifier.py` para clarificar:
   - "FACTURA RECIBIDA = GASTO"
   - "Usar SOLO cuentas de gastos (600-699)"
   - "NO usar cuentas de ingresos (400-499)"

Esto garantiza que:
- ✅ Embeddings solo devuelve candidatos de gastos
- ✅ LLM tiene instrucciones claras
- ✅ Defensa en profundidad (múltiples capas de validación)

---

## Impacto Esperado

**Antes**: 20% accuracy (1/5 correctas)
**Después (estimado)**: 80-90% accuracy

**Casos que debería resolver**:
- ✅ FINKOK → 613.xx (servicios admin) en vez de 401.xx
- ✅ Amazon → 612.xx (logística) en vez de 401.xx
- ✅ Envases/Miel → 601.xx (insumos) en vez de 119.xx

**Casos que podrían seguir con problemas**:
- Conceptos muy ambiguos sin contexto suficiente
- Proveedores desconocidos
- Facturas con múltiples conceptos mixtos

---

## Próximos Pasos

1. ✅ Problema identificado y documentado
2. ⏳ Implementar fix en `classification_service.py` (agregar family_filter)
3. ⏳ Mejorar prompt en `expense_llm_classifier.py`
4. ⏳ Re-ejecutar test de 5 facturas
5. ⏳ Validar mejora en accuracy
6. ⏳ Test con 20-30 facturas diversas
7. ⏳ Deploy a producción

---

**Archivos a Modificar**:
1. [core/ai_pipeline/classification/classification_service.py](core/ai_pipeline/classification/classification_service.py) - Línea 48-56
2. [core/ai_pipeline/classification/expense_llm_classifier.py](core/ai_pipeline/classification/expense_llm_classifier.py) - Línea 247-256

**Tests afectados**:
- [test_embeddings_classification.py](test_embeddings_classification.py)
- [test_upload_simple.py](test_upload_simple.py)
- [test_batch_classification.py](test_batch_classification.py)

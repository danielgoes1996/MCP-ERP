# Post-Backfill Action Plan
## Correcciones Críticas Después de Completar el Backfill Actual

**Status**: Backfill en progreso (142/228 clasificadas - 62.28%)
**Fecha creación**: 2025-01-13
**Prioridad**: CRÍTICA antes del siguiente backfill o uso en producción

---

## ✅ Completado (Durante y Post-Backfill)

1. ✅ **Deprecation warning en `cfdi_llm_parser.py`** (2025-01-13)
   - Archivo: `/core/ai_pipeline/parsers/cfdi_llm_parser.py`
   - Docstring con advertencia DEPRECATED
   - Runtime `DeprecationWarning` agregado (líneas 198-212)
   - Logger warning para visibilidad en logs
   - Verificado: No hay imports activos en código de producción

2. ✅ **Helper centralizado: `tenant_utils.py`**
   - Archivo: `/core/shared/tenant_utils.py`
   - Funciones canónicas:
     - `get_tenant_and_company(company_id_str) → (tenant_id, company_id)`
     - `get_company_id_from_tenant(tenant_id) → company_id`
   - Reemplazar TODOS los mapeos manuales con estas funciones

3. ✅ **Helper centralizado: `classification_utils.py`**
   - Archivo: `/core/shared/classification_utils.py`
   - Funciones canónicas:
     - `should_update_classification(existing, new) → bool`
     - `merge_classification(existing, new) → Dict`
   - Enforce priority: corrected > confirmed > pending

---

## 🔴 CRÍTICO - Hacer INMEDIATAMENTE después del backfill

### 1. Eliminar uso de `cfdi_llm_parser` en `UniversalInvoiceEngineSystem`

**Archivo**: `core/expenses/invoices/universal_invoice_engine_system.py`
**Línea aproximada**: 206

**Cambio**:
```python
# ANTES (MAL - usando LLM):
from core.ai_pipeline.parsers.cfdi_llm_parser import extract_cfdi_metadata
parsed_data = extract_cfdi_metadata(xml_content)

# DESPUÉS (BIEN - usando XML parser):
from core.ai_pipeline.parsers.invoice_parser import parse_cfdi_xml
parsed_data = parse_cfdi_xml(xml_content)
```

**IMPORTANTE**: Verificar que el formato de salida de `parse_cfdi_xml` sea compatible con el resto del código:
- Comparar campos retornados vs esperados
- Probar con 2-3 facturas reales antes de aplicar masivamente

**Impacto**:
- Ahorra ~$0.005-0.01 por factura
- Reduce latencia de ~5s a ~0.1s por factura
- Elimina errores de parsing LLM

---

### 2. Refactorizar `_get_company_id_string` en `BulkInvoiceProcessor`

**Archivo**: `core/expenses/invoices/bulk_invoice_processor.py`
**Líneas**: 752-785

**Cambio**:
```python
# ANTES (implementación ad-hoc):
async def _get_company_id_string(self, tenant_id: int) -> str:
    conn = self._get_conn()
    cursor = conn.cursor()
    # ... código manual ...

# DESPUÉS (usar helper centralizado):
from core.shared.tenant_utils import get_company_id_from_tenant

async def _get_company_id_string(self, tenant_id: int) -> str:
    """Wrapper for centralized tenant mapping"""
    return get_company_id_from_tenant(tenant_id)
```

**Buscar TODOS los usos de conversión manual** y reemplazarlos:
```bash
grep -r "SELECT.*company_id.*FROM tenants" core/ --include="*.py"
```

---

### 3. Integrar `merge_classification` en dual-write

**Archivos afectados**:
- `core/expenses/invoices/universal_invoice_engine_system.py` (método `_save_classification_to_invoice`)
- `api/invoice_classification_api.py` (endpoints `/confirm` y `/correct`)

**Cambio en `_save_classification_to_invoice`**:
```python
from core.shared.classification_utils import merge_classification, should_update_classification

# ANTES (sin merge):
cursor.execute("""
    UPDATE expense_invoices
    SET accounting_classification = %s
    WHERE uuid = %s
""", (json.dumps(classification), uuid))

# DESPUÉS (con merge):
# 1. Leer clasificación existente
cursor.execute("""
    SELECT accounting_classification
    FROM expense_invoices
    WHERE uuid = %s
""", (uuid,))
existing = cursor.fetchone()
existing_class = existing['accounting_classification'] if existing else None

# 2. Merge con prioridades
final_classification = merge_classification(existing_class, classification)

# 3. Solo actualizar si cambió
if final_classification != existing_class:
    cursor.execute("""
        UPDATE expense_invoices
        SET accounting_classification = %s
        WHERE uuid = %s
    """, (json.dumps(final_classification), uuid))
```

---

### 4. Test de Regresión

**Crear**: `tests/test_classification_flow.py`

```python
import pytest
from core.shared.tenant_utils import get_tenant_and_company, get_company_id_from_tenant
from core.shared.classification_utils import merge_classification, should_update_classification

def test_tenant_mapping():
    """Verify tenant<->company mapping works"""
    tenant_id, company_id = get_tenant_and_company("contaflow")
    assert tenant_id == 2
    assert company_id == "contaflow"

    reverse = get_company_id_from_tenant(2)
    assert reverse == "contaflow"

def test_classification_priority():
    """Verify classification merge respects priority"""
    confirmed = {'status': 'confirmed', 'sat_account_code': '601.84'}
    pending = {'status': 'pending', 'sat_account_code': '603.12'}

    # Confirmed should win
    result = merge_classification(confirmed, pending)
    assert result['status'] == 'confirmed'
    assert result['sat_account_code'] == '601.84'

    # Pending should upgrade to confirmed
    result = merge_classification(pending, confirmed)
    assert result['status'] == 'confirmed'
```

**Ejecutar antes de desplegar**:
```bash
pytest tests/test_classification_flow.py -v
```

---

## 🟡 IMPORTANTE - Hacer antes del próximo sprint

### 5. Documentar Reglas Canónicas en Código

**Crear**: `core/expenses/invoices/CLASSIFICATION_RULES.md`

```markdown
# Classification Rules (CANON)

## Single Source of Truth
- `expense_invoices.accounting_classification` = CANON
- `sat_invoices.accounting_classification` = AUDIT TRAIL (snapshot)

## Priority Rules
1. corrected > confirmed > pending > None
2. NEVER downgrade status
3. Use `merge_classification()` for ALL updates

## Mapping Rules
- `tenant_id` (INT) for DB performance (FKs, indexes)
- `company_id` (TEXT) for UX/API readability
- Use `tenant_utils.py` for ALL conversions
```

---

### 6. Deprecar o Eliminar `cfdi_llm_parser` completamente

**Opciones**:

**Opción A**: Mover a legacy y eliminar imports
```bash
mkdir core/ai_pipeline/parsers/legacy
mv core/ai_pipeline/parsers/cfdi_llm_parser.py core/ai_pipeline/parsers/legacy/
```

**Opción B**: Añadir warning en runtime
```python
# Al inicio de extract_cfdi_metadata()
import warnings
warnings.warn(
    "cfdi_llm_parser is deprecated. Use parse_cfdi_xml for CFDI XML files.",
    DeprecationWarning,
    stacklevel=2
)
```

**Recomendación**: Opción B primero (warning), luego Opción A después de 1 mes sin usos.

---

## 📊 Métricas de Éxito Post-Corrección

Después de aplicar las correcciones, verificar:

1. **Coste por factura**:
   - ANTES: ~$0.01-0.02 (con LLM parsing)
   - DESPUÉS: ~$0.005-0.01 (solo clasificación LLM)
   - ✅ Target: Reducción de 50%

2. **Tiempo por factura**:
   - ANTES: ~8-12 segundos
   - DESPUÉS: ~3-5 segundos
   - ✅ Target: Reducción de 60%

3. **Errores de parsing**:
   - ANTES: ~3-5% (LLM JSON parse errors)
   - DESPUÉS: ~0% (XML determinístico)
   - ✅ Target: Cero errores de parsing

4. **Inconsistencias tenant/company**:
   - ANTES: Múltiples implementaciones
   - DESPUÉS: 1 función canónica
   - ✅ Target: grep = 0 resultados para conversiones manuales

---

## 🚀 Timeline

| Fase | Acción | Tiempo estimado | Deadline |
|------|--------|-----------------|----------|
| 1 | Esperar fin backfill | ~40 min | Hoy 11:00 AM |
| 2 | Cambiar parser en UniversalEngine | 30 min | Hoy 11:30 AM |
| 3 | Refactorizar tenant mapping | 45 min | Hoy 12:15 PM |
| 4 | Integrar merge_classification | 1 hora | Hoy 1:15 PM |
| 5 | Tests de regresión | 30 min | Hoy 2:00 PM |
| 6 | Probar con 5 facturas reales | 15 min | Hoy 2:15 PM |
| 7 | Deploy a dev | 10 min | Hoy 2:30 PM |

**Total tiempo**: ~3.5 horas
**Deadline recomendado**: Hoy antes de las 3:00 PM

---

## ✅ Checklist Final

Antes de considerar las correcciones completas:

- [ ] `cfdi_llm_parser` marcado como deprecated (HECHO ✅)
- [ ] `tenant_utils.py` creado y testeado (HECHO ✅)
- [ ] `classification_utils.py` creado y testeado (HECHO ✅)
- [ ] Parser LLM eliminado de UniversalEngine
- [ ] Todos los tenant mappings usan helper centralizado
- [ ] Todos los classification updates usan merge_classification
- [ ] Tests de regresión pasan
- [ ] Probado con 5 facturas reales
- [ ] Documentación actualizada
- [ ] Code review por segundo par de ojos

---

## 📝 Notas

**Por qué esperar al fin del backfill**:
- El backfill actual está estable (142/228 done)
- Cambiarlo a mitad de camino puede introducir bugs sutiles
- El coste adicional de 86 facturas (~$0.50) es aceptable vs riesgo

**Por qué hacerlo antes del siguiente uso**:
- El antipatrón (LLM para XML) está identificado y documentado
- Cada día que pase sin corrección es dinero/tiempo desperdiciado
- Riesgo de que alguien más copie el patrón incorrecto

**Autor**: Claude Code
**Reviewer**: [Pendiente]
**Última actualización**: 2025-01-13 10:20 AM

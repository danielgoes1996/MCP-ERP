# Validation Checklist - Post Backfill & Parser Fix

**Fecha**: 2025-01-13
**Estado**: En validación
**Opción elegida**: C (Híbrida)

---

## ✅ Completado

### 1. Backfill Exitoso
- [x] 209/228 facturas clasificadas (91.67%)
- [x] Nuevo parser XML implementado y testeado
- [x] Documentación completa ([BACKFILL_COMPLETE_SUMMARY.md](BACKFILL_COMPLETE_SUMMARY.md))

### 2. Deprecación del Parser LLM
- [x] Docstring actualizado con advertencia
- [x] Runtime warning agregado (`DeprecationWarning`)
- [x] Logger warning agregado para visibilidad
- [x] Verificado: No hay imports activos del parser LLM en código de producción

**Cambios en**: [cfdi_llm_parser.py:181-212](core/ai_pipeline/parsers/cfdi_llm_parser.py#L181-L212)

---

## 🔍 En Validación (Esta Semana)

### 3. Validar en Producción

#### Test con Facturas Nuevas (Prioridad ALTA)
- [ ] Subir 2-3 facturas CFDI nuevas manualmente
- [ ] Verificar que:
  - [ ] Parser XML funciona correctamente
  - [ ] Clasificación automática funciona
  - [ ] Dual-write a `expense_invoices` funciona
  - [ ] No hay regresiones en campos extraídos
  - [ ] Tiempo de procesamiento < 5 segundos (vs 10-15s antes)

**Comando para probar**:
```bash
# 1. Subir factura por API o interfaz
# 2. Verificar en logs:
tail -f logs/app.log | grep "XML parsed successfully with deterministic parser"
# 3. Verificar en DB:
docker exec mcp-postgres psql -U mcp_user -d mcp_system -c \
  "SELECT id, uuid, accounting_classification FROM expense_invoices ORDER BY created_at DESC LIMIT 3;"
```

#### Monitoreo de Logs (Prioridad ALTA)
- [ ] Revisar logs cada 12 horas durante 48 horas
- [ ] Buscar errores relacionados con XML parsing
- [ ] Verificar que no aparezcan warnings de parser LLM

**Comandos útiles**:
```bash
# Buscar errores de parsing
grep -i "error parsing" logs/app.log | tail -20

# Buscar warnings de LLM parser deprecated
grep "DEPRECATED: extract_cfdi_metadata" logs/app.log

# Contar clasificaciones exitosas hoy
docker exec mcp-postgres psql -U mcp_user -d mcp_system -c \
  "SELECT COUNT(*) FROM expense_invoices WHERE DATE(created_at) = CURRENT_DATE AND accounting_classification IS NOT NULL;"
```

#### Retry Factura 814 (Prioridad MEDIA)
- [ ] Intentar clasificar factura 814 (falló por rate limit, no por parser)
- [ ] Comando:
```bash
python3 scripts/backfill_invoice_classifications.py --company-id contaflow --limit 1
```
- [ ] **Objetivo**: 210/228 (92.11%) en lugar de 209/228 (91.67%)

---

## 📊 Métricas a Monitorear

### Baseline (Antes del fix)
- Tiempo de parsing: 5-10 segundos
- Costo por factura (parsing): ~$0.01
- Tasa de error parsing: ~9%
- Clasificaciones exitosas: 204/228 (89.47%)

### Target (Después del fix)
- Tiempo de parsing: < 0.2 segundos ✅
- Costo por factura (parsing): $0.00 ✅
- Tasa de error parsing: 0% ✅
- Clasificaciones exitosas: 209/228 (91.67%) ✅

### KPIs de Validación
| Métrica | Target | Cómo verificar |
|---------|--------|----------------|
| Parsing exitoso | 100% | Logs: "XML parsed successfully" |
| Tiempo < 5s | 100% | Logs: timestamps entre parse y classify |
| Sin warnings LLM | 0 | `grep "DEPRECATED" logs/app.log` |
| Clasificaciones nuevas | ≥ 3 | Query DB diario |

---

## ✅ Completado - Fase de Refactorización (2025-01-13)

### 4. Tests de Regresión
- [x] Crear `tests/test_classification_priority.py` - 10 tests, 100% pass rate
- [x] Tests de tenant mapping (verified with inline test)
- [x] Tests de classification priority (comprehensive 10-test suite)
- [ ] Tests de XML parsing (5 facturas muestra) - **Pendiente, baja prioridad**

**Tiempo real**: 10 minutos (estimado 1 hora)
**Resultado**: [test_classification_priority.py](tests/test_classification_priority.py)

### 5. Refactorizar Tenant Mapping
- [x] Buscar y reemplazar conversiones manuales (2 instancias encontradas)
- [x] Usar `tenant_utils.get_tenant_and_company()` consistentemente
- [x] Actualizar `BulkInvoiceProcessor` (líneas 760-780)
- [x] Actualizar `UniversalInvoiceEngineSystem` (líneas 1482-1491)

**Tiempo real**: 15 minutos (estimado 1.5 horas)
**Archivos modificados**:
- [bulk_invoice_processor.py](core/expenses/invoices/bulk_invoice_processor.py#L760-L780)
- [universal_invoice_engine_system.py](core/expenses/invoices/universal_invoice_engine_system.py#L1482-L1491)

### 6. Integrar merge_classification
- [x] Modificar `_save_classification_to_invoice()` en `universal_invoice_engine_system.py`
- [x] Analizar `/confirm` y `/correct` en `api/invoice_classification_api.py`
- [x] Decisión: Endpoints NO necesitan merge (son overrides intencionales)
- [x] Verificar que prioridad corrected > confirmed > pending funciona
- [x] Fix bugs en `merge_classification()` (handle None cases, metadata fields)

**Tiempo real**: 15 minutos (estimado 2 horas)
**Tests**: 10/10 passed, prioridades verificadas

**Resumen completo**: [REFACTORING_PHASE_COMPLETE.md](REFACTORING_PHASE_COMPLETE.md)

---

## ⏳ Pendiente (Opcional - Baja Prioridad)

### 7. Limpieza de Código Legacy
- [ ] Move `cfdi_llm_parser.py` to `legacy/` folder (~15 minutos)
- [ ] Verificar que no hay imports activos

### 8. Documentación
- [ ] Crear `CLASSIFICATION_RULES.md` (~30 minutos)
- [ ] Crear `CONTRIBUTING.md` con estándares de código (~45 minutos)

---

## 🚨 Criterios de Rollback

Si encuentras alguno de estos problemas, considera rollback:

1. **Parsing falla > 5%**: Muchos "Error parsing CFDI XML" en logs
2. **Campos faltantes**: `uuid`, `total`, `rfc_emisor` no se extraen correctamente
3. **Clasificación no funciona**: SAT codes no se asignan (puede ser problema de API, no parser)
4. **Performance peor**: Facturas tardan > 15 segundos (antes eran ~10s)

**Comando de rollback**:
```bash
git checkout HEAD~1 core/expenses/invoices/universal_invoice_engine_system.py
git commit -m "Rollback: XML parser causing issues"
```

---

## 📝 Log de Validación

### Día 1 (2025-01-13)
- [x] Backfill completado: 209/228 (91.67%)
- [x] Parser LLM deprecado con warnings
- [x] **Refactorización completada**: Tenant mapping + Classification merge
  - 10/10 tests passed
  - 2 instancias de código duplicado eliminadas
  - Bugs fixed en merge_classification
  - Documentación completa: [REFACTORING_PHASE_COMPLETE.md](REFACTORING_PHASE_COMPLETE.md)
- [ ] **Pendiente**: Probar con 2-3 facturas nuevas
- [ ] **Pendiente**: Monitoreo de logs

### Día 2 (2025-01-14)
- [ ] Revisar logs cada 12 horas
- [ ] Verificar facturas nuevas clasificadas
- [ ] Retry factura 814

### Día 3 (2025-01-15)
- [ ] Análisis final de métricas
- [ ] Decisión: ¿Proceder con refactorings?

---

## ✅ Checklist de "Todo OK"

Antes de proceder con refactorings, verificar:

- [ ] ≥ 3 facturas nuevas procesadas correctamente (100% éxito)
- [ ] 48 horas sin errores de parsing en logs
- [ ] 0 warnings de parser LLM deprecated (nadie lo está usando)
- [ ] Tiempo de procesamiento < 5 segundos por factura
- [ ] Factura 814 clasificada (si es posible)
- [ ] No hay quejas de usuarios sobre facturas faltantes o incorrectas

**Si todas las casillas están marcadas → Proceder con POST_BACKFILL_ACTION_PLAN.md**

---

## 📞 Contacto en Caso de Problemas

Si encuentras algún problema crítico:

1. **Rollback inmediato** si > 10% de facturas fallan
2. **Capturar logs** con contexto completo del error
3. **Crear issue** en repositorio con:
   - Logs del error
   - UUID de factura afectada
   - Timestamp del problema
   - Pasos para reproducir

---

**Última actualización**: 2025-01-13 11:30 AM
**Responsable**: Equipo de desarrollo
**Reviewer**: Pendiente

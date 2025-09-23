# 🛡️ CHECKLIST DE ROLLBACK - Integración Sistema Robusto

## ⚠️ INSTRUCCIONES DE EMERGENCIA

Si algo falla después de la integración, sigue estos pasos **EN ORDEN**:

### 🔥 ROLLBACK INMEDIATO (< 5 minutos)

1. **Restaurar main.py original:**
   ```bash
   mv main.py main_enhanced.py  # Backup enhanced
   mv main_original.py main.py  # Restore original
   ```

2. **Reiniciar servidor:**
   ```bash
   pkill -f "python main.py"
   python main.py
   ```

3. **Verificar endpoints básicos:**
   - `curl http://localhost:8000/health`
   - `curl http://localhost:8000/invoicing/tickets`

### 🔧 ROLLBACK PARCIAL (Deshabilitar features)

Si solo algunas features fallan, deshabilitarlas individualmente:

#### Deshabilitar motor robusto:
```python
# En main_enhanced.py o integration_layer.py
ENHANCED_AUTOMATION = False
```

#### Deshabilitar servicios específicos:
```sql
-- Deshabilitar Claude
UPDATE feature_flags SET enabled = 0 WHERE feature_name = 'claude_analysis';

-- Deshabilitar Google Vision
UPDATE feature_flags SET enabled = 0 WHERE feature_name = 'google_vision_ocr';

-- Deshabilitar 2Captcha
UPDATE feature_flags SET enabled = 0 WHERE feature_name = 'captcha_solving';
```

### 📊 ROLLBACK DE BASE DE DATOS

Si hay problemas con nuevas tablas:

```sql
-- 1. Backup actual
.backup backup_before_rollback.db

-- 2. Eliminar tablas nuevas (PELIGROSO - solo en emergencia)
DROP TABLE IF EXISTS feature_flags;
DROP TABLE IF EXISTS tenant_config;
DROP TABLE IF EXISTS automation_batches;
DROP TABLE IF EXISTS automation_metrics;

-- 3. Restaurar desde backup anterior
-- (Requiere backup previo a la migración)
```

## 📋 ARCHIVOS CRÍTICOS A MONITOREAR

### ✅ Archivos seguros (NO tocar en rollback):
- `modules/invoicing_agent/models.py` ← Mantiene compatibilidad
- `modules/invoicing_agent/api.py` ← Solo se añadieron parches
- `expenses.db` ← Se añadieron columnas, datos existentes intactos

### ⚠️ Archivos nuevos (se pueden eliminar si fallan):
- `core/enhanced_api_models.py`
- `core/unified_automation_engine.py`
- `core/google_vision_ocr.py`
- `core/claude_dom_analyzer.py`
- `core/captcha_solver.py`
- `core/security_middleware.py`
- `modules/invoicing_agent/enhanced_api.py`
- `modules/invoicing_agent/integration_layer.py`
- `modules/invoicing_agent/fastapi_integration.py`

### 🔄 Archivos modificados (revisar cambios):
- `modules/invoicing_agent/robust_automation_engine.py` ← OpenAI → Claude
- `main.py` → `main_enhanced.py`

## 🚨 PUNTOS DE FALLO COMUNES

### 1. Import Errors
**Síntoma:** `ImportError: No module named 'core.unified_automation_engine'`
**Solución:**
```python
# En integration_layer.py, línea ~15
try:
    from core.unified_automation_engine import create_unified_engine
    ROBUST_ENGINE_AVAILABLE = True
except ImportError as e:
    ROBUST_ENGINE_AVAILABLE = False  # Fallback automático
```

### 2. Database Errors
**Síntoma:** `no such table: feature_flags`
**Solución:**
```bash
# Aplicar migración manualmente
sqlite3 expenses.db < migrations/010_enhance_automation_20240922.sql
```

### 3. API Key Errors
**Síntoma:** Errores 500 en endpoints v2
**Solución:** Sistema diseñado para funcionar SIN API keys
```python
# Verificar fallbacks funcionan:
analyzer = create_claude_analyzer()
print(analyzer.is_available())  # False → usa heurística
```

### 4. Port/Address Already in Use
**Síntoma:** `Address already in use`
**Solución:**
```bash
# Encontrar y matar proceso
lsof -i :8000
kill -9 [PID]
```

## 🔍 COMANDOS DE DIAGNÓSTICO

### Verificar estado del sistema:
```bash
# 1. Verificar servidor
curl -s http://localhost:8000/health | jq

# 2. Verificar endpoints originales
curl -s http://localhost:8000/invoicing/tickets | head -20

# 3. Verificar endpoints enhanced (opcional)
curl -s http://localhost:8000/invoicing/v2/health | jq

# 4. Verificar base de datos
sqlite3 expenses.db "SELECT name FROM sqlite_master WHERE type='table';"
```

### Verificar logs:
```bash
# Logs de aplicación
tail -f logs/app.log

# Logs de sistema
journalctl -f -u mcp-server  # Si está como servicio
```

## 📞 CONTACTOS DE EMERGENCIA

- **DBA:** Revisar migraciones y rollback DB
- **DevOps:** Rollback infrastructure/containers
- **QA:** Validar funcionalidad básica post-rollback

## 🧪 TESTS DE VALIDACIÓN POST-ROLLBACK

```bash
# 1. Funcionalidad básica
curl -X POST http://localhost:8000/invoicing/tickets \
  -F "text_content=test ticket" \
  -F "company_id=default"

# 2. Automation viewer
curl http://localhost:8000/static/automation-viewer.html

# 3. Advanced dashboard
curl http://localhost:8000/static/advanced-ticket-dashboard.html

# 4. Verificar no hay errores 500
grep -i "error\|exception" logs/app.log | tail -20
```

## 📈 MÉTRICAS A MONITOREAR

Después del rollback, verificar que estas métricas estén normales:

- **Response Times:** < 500ms para endpoints básicos
- **Error Rate:** < 1% en 15 minutos
- **CPU Usage:** < 80%
- **Memory Usage:** < 2GB
- **Database Connections:** < 10 concurrentes

## 🔄 PROCEDIMIENTO DE RE-IMPLEMENTACIÓN

Una vez solucionado el problema:

1. **Aplicar fix específico** en desarrollo
2. **Probar extensivamente** en staging
3. **Rollout gradual:**
   - Habilitar solo para `company_id = "test"`
   - Monitorear 24h
   - Expandir a más tenants
   - Full rollout

## 💾 BACKUPS CRÍTICOS

**Antes de cualquier cambio:**
```bash
# Base de datos
cp expenses.db expenses_backup_$(date +%Y%m%d_%H%M%S).db

# Código
git tag rollback_point_$(date +%Y%m%d_%H%M%S)
git add -A && git commit -m "Pre-rollback checkpoint"

# Screenshots/evidencia
tar -czf screenshots_backup_$(date +%Y%m%d_%H%M%S).tar.gz screenshots/
```

---

## ✅ CHECKLIST DE CONFIRMACIÓN POST-ROLLBACK

- [ ] Servidor responde en puerto correcto
- [ ] Endpoints originales funcionan
- [ ] Base de datos accesible
- [ ] No hay errores en logs recientes
- [ ] UI/frontend carga correctamente
- [ ] Automation viewer accesible (aunque sea básico)
- [ ] Performance normal (response times)
- [ ] No memory leaks visibles

**Rollback exitoso cuando TODOS los items ✅ están marcados.**
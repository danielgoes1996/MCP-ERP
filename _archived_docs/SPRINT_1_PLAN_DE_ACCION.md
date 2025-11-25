# 🎯 Sprint 1: Plan de Acción - Sistema de Placeholders

**Inicio**: 2025-01-29
**Fin**: 2025-02-04 (5 días hábiles)
**Objetivo**: Eliminar deuda técnica crítica antes de Fase 2 (IA)
**Responsable**: Equipo de Desarrollo
**Stakeholder**: PM Técnico

---

## 📊 Estado Actual del Sistema

| Componente | Estado | Cobertura |
|------------|--------|-----------|
| Validación de campos | ✅ 100% | Testeado |
| API endpoints | ✅ 95% | Básico |
| Base de datos | ⚠️ 70% | Índices OK, schema incompleto |
| Testing E2E | ❌ 10% | Solo validación |
| Logging/Métricas | ❌ 20% | No estructurado |
| Seguridad (duplicados) | ❌ 0% | Sin validación |

**Bloqueadores para Producción**: 3 críticos identificados

---

## 🚨 Issues Críticos (Bloqueadores de Producción)

### Issue #1: payment_account_id Faltante en record_internal_expense()
**Prioridad**: 🔴 CRÍTICA
**Impacto**: 67% expenses sin cuenta de pago
**Bloquea**: Integridad contable
**Tiempo estimado**: 2 horas
**Responsable**: Backend Developer
**Due date**: 2025-01-29 EOD

**Descripción**:
La función `record_internal_expense()` no acepta `payment_account_id` como parámetro, causando que 8 de 12 expenses (67%) tengan este campo NULL. Esto genera reportes contables incompletos.

**Criterios de Aceptación**:
- [ ] Agregar parámetro `payment_account_id: Optional[int] = None` a función
- [ ] Actualizar INSERT para incluir el campo
- [ ] Actualizar 8 expenses existentes con cuenta default
- [ ] Test unitario que verifique persistencia
- [ ] Validar que nuevos expenses tienen payment_account_id

**Código esperado**:
```python
# core/internal_db.py línea ~20
def record_internal_expense(
    *,
    description: str,
    amount: float,
    # ... otros parámetros
    payment_account_id: Optional[int] = None,  # ← AGREGAR
    paid_by: str = "company_account",
    # ...
)
```

**Script de migración de datos**:
```sql
-- Actualizar expenses existentes con payment_account_id NULL
UPDATE expense_records
SET payment_account_id = (
    SELECT id FROM user_payment_accounts
    WHERE tenant_id = expense_records.tenant_id
    AND is_default = 1
    LIMIT 1
)
WHERE payment_account_id IS NULL;
```

---

### Issue #2: Validación de Duplicados en /update
**Prioridad**: 🔴 CRÍTICA
**Impacto**: Riesgo de doble contabilización
**Bloquea**: Seguridad de datos
**Tiempo estimado**: 3 horas
**Responsable**: Backend Developer
**Due date**: 2025-01-30 EOD

**Descripción**:
El endpoint `/update` no valida si el RFC o UUID ya existen en otro expense, permitiendo duplicados al completar placeholders.

**Criterios de Aceptación**:
- [ ] Validar RFC duplicado antes de UPDATE
- [ ] Validar UUID duplicado antes de UPDATE
- [ ] Retornar HTTP 409 Conflict con mensaje claro
- [ ] Test unitario de cada validación
- [ ] Test de integración con casos edge

**Código esperado**:
```python
# api/expense_placeholder_completion_api.py:208+
# Antes de UPDATE
if 'rfc_proveedor' in completed_fields:
    cursor.execute("""
    SELECT id FROM expense_records
    WHERE rfc_proveedor = ? AND id != ? AND tenant_id = ?
    """, (completed_fields['rfc_proveedor'], expense_id, tenant_id))

    if cursor.fetchone():
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe un expense con RFC {completed_fields['rfc_proveedor']}"
        )

# Similar para UUID
```

**Tests necesarios**:
```python
def test_update_duplicate_rfc_rejected():
    # Crear expense con RFC "ABC123"
    # Intentar completar placeholder con mismo RFC
    # Esperar: 409 Conflict

def test_update_same_expense_allowed():
    # Completar placeholder con su propio RFC (idempotencia)
    # Esperar: 200 OK
```

---

### Issue #3: Test E2E del Flujo Completo
**Prioridad**: 🔴 CRÍTICA
**Impacto**: Sin tests, no hay garantía de funcionamiento
**Bloquea**: Deployment a producción
**Tiempo estimado**: 4 horas
**Responsable**: QA + Backend Developer
**Due date**: 2025-01-31 EOD

**Descripción**:
Solo 1 de 10 tests funciona. El flujo completo nunca ha sido testeado end-to-end. Sin esto, no podemos garantizar que el sistema funcione en producción.

**Criterios de Aceptación**:
- [ ] Test E2E: CFDI → Placeholder → Completar → Draft
- [ ] Test de duplicados de facturas
- [ ] Test de concurrencia (2 usuarios)
- [ ] Test de fallback de payment account
- [ ] Todos los tests passing en local
- [ ] Coverage > 80% en módulos críticos

**Estructura del test E2E**:
```python
# test_placeholder_full_flow_e2e.py
import pytest
from fastapi.testclient import TestClient

def test_full_placeholder_flow():
    """
    Test completo: Upload CFDI → Placeholder → Complete → Draft
    """
    # PASO 1: Upload factura sin expense existente
    response = client.post("/api/bulk-invoice/process-batch", json={
        "company_id": "default",
        "invoices": [{
            "uuid": "TEST-UUID-123",
            "total": 5000.00,
            "provider_rfc": "TST850301XXX",
            "provider_name": "Test Provider SA",
            "issued_date": "2025-01-28"
        }],
        "create_placeholder_on_no_match": True
    })

    assert response.status_code == 200
    batch = response.json()
    assert batch["linked_count"] == 1

    # PASO 2: Verificar placeholder creado
    expense_id = batch["items"][0]["matched_expense_id"]

    response = client.get(f"/api/expenses/{expense_id}")
    expense = response.json()
    assert expense["workflow_status"] == "requiere_completar"
    assert expense["category"] is None  # Campo faltante

    # PASO 3: Obtener completion prompt
    response = client.get(f"/api/expenses/placeholder-completion/prompt/{expense_id}")
    prompt = response.json()

    assert prompt["needs_completion"] == True
    assert "category" in [f["field_name"] for f in prompt["missing_fields"]]

    # PASO 4: Completar placeholder
    response = client.post("/api/expenses/placeholder-completion/update", json={
        "expense_id": expense_id,
        "completed_fields": {
            "category": "servicios_profesionales"
        }
    })

    assert response.status_code == 200
    result = response.json()
    assert result["workflow_status"] == "draft"
    assert result["is_complete"] == True

    # PASO 5: Verificar estado final
    response = client.get(f"/api/expenses/{expense_id}")
    expense = response.json()
    assert expense["workflow_status"] == "draft"
    assert expense["category"] == "servicios_profesionales"
    assert expense["metadata"]["completed_by_user"] == True
```

---

## 🟡 Issues de Alta Prioridad (No Bloqueantes)

### Issue #4: Logging Estructurado
**Prioridad**: 🟡 ALTA
**Impacto**: Dificulta debugging y auditoría
**Tiempo estimado**: 2 horas
**Responsable**: Backend Developer
**Due date**: 2025-02-01 EOD

**Criterios de Aceptación**:
- [ ] Implementar structlog o logging con JSON
- [ ] Logear eventos: placeholder_created, placeholder_completed
- [ ] Incluir: tenant_id, user_id, expense_id, timestamp
- [ ] Logs a archivo rotativo (logs/placeholders.log)
- [ ] Configuración de niveles (DEBUG, INFO, ERROR)

**Implementación**:
```python
import structlog
import logging.config

# Configuración
logging.config.dictConfig({
    'version': 1,
    'formatters': {
        'json': {
            '()': structlog.stdlib.ProcessorFormatter,
            'processor': structlog.processors.JSONRenderer(),
        },
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/placeholders.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'json',
        },
    },
    'loggers': {
        'placeholder': {
            'handlers': ['file'],
            'level': 'INFO',
        },
    },
})

logger = structlog.get_logger('placeholder')

# Uso
logger.info(
    "placeholder_created",
    expense_id=expense_id,
    invoice_uuid=invoice_uuid,
    tenant_id=tenant_id,
    company_id=company_id,
    missing_fields=missing_fields,
    timestamp=datetime.utcnow().isoformat()
)
```

---

### Issue #5: Endpoint /stats/detailed con KPIs Completos
**Prioridad**: 🟡 ALTA
**Impacto**: No hay métricas para tomar decisiones
**Tiempo estimado**: 3 horas
**Responsable**: Backend Developer
**Due date**: 2025-02-02 EOD

**Criterios de Aceptación**:
- [ ] Endpoint `/stats/detailed` implementado
- [ ] KPI: completion_rate (% completados)
- [ ] KPI: top_missing_fields (top 5 campos faltantes)
- [ ] KPI: avg_completion_time_hours
- [ ] KPI: placeholders by age (< 7 days, 7-30 days, > 30 days)
- [ ] Response model con Pydantic
- [ ] Test unitario de cada query

**Response esperado**:
```json
{
  "period": "last_30_days",
  "total_created": 45,
  "total_completed": 35,
  "completion_rate": 0.78,
  "avg_completion_time_hours": 4.2,
  "top_missing_fields": [
    {"field": "category", "count": 23, "percentage": 51.1},
    {"field": "payment_account_id", "count": 12, "percentage": 26.7},
    {"field": "rfc_proveedor", "count": 8, "percentage": 17.8}
  ],
  "by_age": {
    "fresh_0_7_days": 12,
    "aging_7_30_days": 3,
    "stale_30_plus_days": 0
  },
  "by_category": {
    "servicios_profesionales": 18,
    "sin_clasificar": 17,
    "oficina": 10
  }
}
```

---

### Issue #6: Script de Limpieza de Stale Placeholders
**Prioridad**: 🟡 ALTA
**Impacto**: Placeholders se acumulan indefinidamente
**Tiempo estimado**: 2 horas
**Responsable**: Backend Developer
**Due date**: 2025-02-02 EOD

**Criterios de Aceptación**:
- [ ] Script `cleanup_stale_placeholders.py` creado
- [ ] Marca placeholders > 30 días como 'stale_placeholder'
- [ ] Guarda metadata con stale_marked_at
- [ ] Genera reporte de placeholders marcados
- [ ] Dry-run mode para testing
- [ ] Cron job configurado (diario 9am)

**Implementación**:
```python
# scripts/cleanup_stale_placeholders.py
import asyncio
import sqlite3
from datetime import datetime, timedelta

async def cleanup_stale_placeholders(days_old: int = 30, dry_run: bool = False):
    """
    Marca placeholders antiguos como stale.

    Args:
        days_old: Días sin completar para considerar stale
        dry_run: Si True, solo reporta sin actualizar
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days_old)

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Encontrar placeholders stale
    cursor.execute("""
    SELECT id, descripcion, monto_total, created_at,
           CAST((julianday('now') - julianday(created_at)) AS INT) as days_old
    FROM expense_records
    WHERE workflow_status = 'requiere_completar'
    AND datetime(created_at) < ?
    """, (cutoff_date.isoformat(),))

    stale_placeholders = cursor.fetchall()

    print(f"\n{'='*80}")
    print(f"🧹 Limpieza de Placeholders Antiguos (> {days_old} días)")
    print(f"{'='*80}")
    print(f"Encontrados: {len(stale_placeholders)} placeholders")

    if dry_run:
        print("\n⚠️  DRY RUN MODE - No se actualizará la BD\n")

    for placeholder in stale_placeholders:
        expense_id, desc, amount, created, days = placeholder
        print(f"\nID: {expense_id}")
        print(f"  - Descripción: {desc}")
        print(f"  - Monto: ${amount:,.2f}")
        print(f"  - Creado: {created}")
        print(f"  - Días sin completar: {days}")

        if not dry_run:
            # Actualizar a stale
            cursor.execute("""
            UPDATE expense_records
            SET workflow_status = 'stale_placeholder',
                metadata = json_set(
                    COALESCE(metadata, '{}'),
                    '$.stale_marked_at',
                    ?
                )
            WHERE id = ?
            """, (datetime.utcnow().isoformat(), expense_id))

    if not dry_run:
        conn.commit()
        print(f"\n✅ {len(stale_placeholders)} placeholders marcados como stale")

    conn.close()

    return stale_placeholders

if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    asyncio.run(cleanup_stale_placeholders(days_old=30, dry_run=dry_run))
```

**Cron job**:
```bash
# crontab -e
0 9 * * * cd /path/to/mcp-server && python3 scripts/cleanup_stale_placeholders.py >> logs/cleanup.log 2>&1
```

---

### Issue #7: GitHub Actions CI/CD
**Prioridad**: 🟡 ALTA
**Impacto**: Tests no se ejecutan automáticamente
**Tiempo estimado**: 2 horas
**Responsable**: DevOps + Backend Developer
**Due date**: 2025-02-03 EOD

**Criterios de Aceptación**:
- [ ] Archivo `.github/workflows/tests.yml` creado
- [ ] Pipeline ejecuta pytest en cada push/PR
- [ ] Coverage report generado
- [ ] Badge de build status en README
- [ ] Notificaciones de fallos

**Implementación**:
```yaml
# .github/workflows/tests.yml
name: Tests

on:
  push:
    branches: [ main, feature/* ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio

    - name: Run tests
      run: |
        pytest test_validation_only.py -v
        pytest test_placeholder_full_flow_e2e.py -v
        pytest --cov=core --cov=api --cov-report=xml --cov-report=term

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella

    - name: Comment coverage on PR
      if: github.event_name == 'pull_request'
      uses: py-cov-action/python-coverage-comment-action@v3
```

---

### Issue #8: Validación de Idempotencia en /update
**Prioridad**: 🟢 MEDIA
**Impacto**: Usuario puede completar placeholder múltiples veces
**Tiempo estimado**: 1 hora
**Responsable**: Backend Developer
**Due date**: 2025-02-03 EOD

**Criterios de Aceptación**:
- [ ] Verificar workflow_status antes de UPDATE
- [ ] Si ya es 'draft', retornar 200 con mensaje
- [ ] No actualizar si ya completado
- [ ] Test de idempotencia

**Código esperado**:
```python
# api/expense_placeholder_completion_api.py:208+
cursor.execute("""
SELECT workflow_status FROM expense_records WHERE id = ?
""", (expense_id,))

current_status = cursor.fetchone()
if not current_status:
    raise HTTPException(404, "Expense no encontrado")

if current_status[0] == 'draft':
    return {
        "status": "already_completed",
        "expense_id": expense_id,
        "workflow_status": "draft",
        "message": "Este expense ya fue completado previamente"
    }
```

---

## 🔵 Issues de Baja Prioridad (Post-Sprint 1)

### Issue #9: Optimistic Locking para Concurrencia
**Prioridad**: 🔵 BAJA
**Impacto**: Riesgo bajo (5%) de race condition
**Due date**: Sprint 2

### Issue #10: Tabla pending_invoices para Facturas sin Procesar
**Prioridad**: 🔵 BAJA
**Impacto**: Mejora de auditoría
**Due date**: Sprint 2

### Issue #11: Dashboard de Placeholders Pendientes
**Prioridad**: 🔵 BAJA
**Impacto**: UX
**Due date**: Sprint 3

---

## 📅 Calendario de Ejecución

### Día 1 (Miércoles 29 Enero)
**AM**:
- ✅ Issue #1: payment_account_id (2h)
  - Agregar parámetro a función
  - Migrar datos existentes
  - Test unitario

**PM**:
- ✅ Issue #2: Validación duplicados (3h)
  - Implementar validaciones
  - Tests unitarios
  - Casos edge

---

### Día 2 (Jueves 30 Enero)
**AM**:
- ✅ Issue #3: Test E2E - Parte 1 (2h)
  - Setup de test environment
  - Test CFDI → Placeholder

**PM**:
- ✅ Issue #3: Test E2E - Parte 2 (2h)
  - Test Completar → Draft
  - Test de duplicados

---

### Día 3 (Viernes 31 Enero)
**AM**:
- ✅ Issue #4: Logging estructurado (2h)
  - Configurar structlog
  - Implementar en endpoints críticos

**PM**:
- ✅ Issue #8: Idempotencia (1h)
- ✅ Code review de Issues #1-4 (2h)

---

### Día 4 (Lunes 3 Febrero)
**AM**:
- ✅ Issue #5: /stats/detailed (3h)
  - Queries de KPIs
  - Response model
  - Tests

**PM**:
- ✅ Issue #6: Script limpieza (2h)
  - Script + dry-run
  - Cron job

---

### Día 5 (Martes 4 Febrero)
**AM**:
- ✅ Issue #7: GitHub Actions (2h)
  - Pipeline CI/CD
  - Coverage reports

**PM**:
- ✅ Testing completo de todos los issues (2h)
- ✅ Dry run del flujo completo (1h)
- ✅ Retrospectiva y cierre de Sprint (1h)

---

## 🎯 Dry Run del Flujo Completo

**Objetivo**: Validar experiencia de usuario end-to-end antes de Fase 2

**Checklist de Dry Run**:
```
1. Setup
   [ ] Servidor corriendo en localhost:8000
   [ ] Base de datos limpia (o con datos de test)
   [ ] Postman/Insomnia collection preparada

2. Paso 1: Subir CFDI sin expense
   [ ] POST /api/bulk-invoice/process-batch
   [ ] create_placeholder_on_no_match: true
   [ ] Verificar: batch.linked_count == 1
   [ ] Verificar: item.match_method == "auto_created_placeholder"

3. Paso 2: Verificar placeholder en /pending
   [ ] GET /api/expenses/placeholder-completion/pending
   [ ] Verificar: Lista tiene 1 item
   [ ] Verificar: missing_fields_count > 0

4. Paso 3: Obtener completion prompt
   [ ] GET /api/expenses/placeholder-completion/prompt/{expense_id}
   [ ] Verificar: needs_completion == true
   [ ] Verificar: missing_fields tiene "category"
   [ ] Verificar: prefilled_data tiene descripcion, monto, fecha
   [ ] Verificar: invoice_reference tiene UUID de factura

5. Paso 4: Completar placeholder
   [ ] POST /api/expenses/placeholder-completion/update
   [ ] completed_fields: {"category": "servicios_profesionales"}
   [ ] Verificar: workflow_status == "draft"
   [ ] Verificar: is_complete == true

6. Paso 5: Verificar estado final
   [ ] GET /api/expenses/{expense_id}
   [ ] Verificar: workflow_status == "draft"
   [ ] Verificar: category == "servicios_profesionales"
   [ ] Verificar: payment_account_id IS NOT NULL
   [ ] Verificar: metadata.completed_by_user == true
   [ ] Verificar: metadata.completed_at tiene timestamp

7. Paso 6: Verificar en /pending
   [ ] GET /api/expenses/placeholder-completion/pending
   [ ] Verificar: Lista vacía (placeholder ya completado)

8. Paso 7: Verificar stats
   [ ] GET /api/expenses/placeholder-completion/stats/detailed
   [ ] Verificar: total_created >= 1
   [ ] Verificar: total_completed >= 1
   [ ] Verificar: completion_rate > 0

9. Paso 8: Intentar duplicado (debe fallar)
   [ ] POST /api/bulk-invoice/process-batch (mismo UUID)
   [ ] Verificar: Error UNIQUE constraint
   [ ] Verificar: No se crea expense duplicado

10. Paso 9: Verificar logs
    [ ] Revisar logs/placeholders.log
    [ ] Verificar: evento "placeholder_created"
    [ ] Verificar: evento "placeholder_completed"
    [ ] Verificar: tenant_id, expense_id en logs
```

---

## 📊 Métricas de Éxito del Sprint

### Criterios Obligatorios (Must-Have):
- ✅ Todos los tests E2E passing
- ✅ Coverage > 80% en módulos críticos
- ✅ 0 expenses con payment_account_id NULL
- ✅ Validación de duplicados implementada
- ✅ Índices UNIQUE funcionando

### Criterios Deseables (Nice-to-Have):
- ✅ Logging estructurado en producción
- ✅ /stats/detailed con KPIs
- ✅ Script de limpieza configurado
- ✅ CI/CD pipeline activo

### KPIs a Medir Post-Sprint:
| Métrica | Valor Objetivo |
|---------|----------------|
| Cobertura de tests | > 80% |
| Expenses con payment_account_id | 100% |
| Tests E2E passing | 100% |
| Issues críticos resueltos | 3/3 |
| Pipeline CI/CD | Activo |

---

## 🚀 Definición de Política de Caducidad

**Propuesta de Política**:

### Nivel 1: Fresh (0-7 días)
- **Estado**: Normal
- **Acción**: Ninguna
- **Indicador**: 🟢 Verde en dashboard

### Nivel 2: Aging (7-30 días)
- **Estado**: Requiere atención
- **Acción**: Notificación al usuario (email/app)
- **Frecuencia**: Cada 3 días
- **Indicador**: 🟡 Amarillo en dashboard
- **Mensaje**: "Tienes gastos pendientes de completar hace X días"

### Nivel 3: Stale (> 30 días)
- **Estado**: Crítico
- **Acción**:
  1. Marcar como `workflow_status='stale_placeholder'`
  2. Notificación urgente a usuario
  3. Notificación a supervisor/admin
  4. Aparecer en dashboard de alertas
- **Indicador**: 🔴 Rojo en dashboard
- **Escalación**: Si > 60 días, escalar a Finance team

### Nivel 4: Archived (> 90 días)
- **Estado**: Archivado
- **Acción**:
  1. Mover a tabla `archived_placeholders`
  2. No aparece en /pending
  3. Solo visible en reportes históricos
- **Reversible**: Sí, con aprobación de supervisor

**Configuración en código**:
```python
# config/placeholder_policy.py
PLACEHOLDER_AGING_POLICY = {
    "fresh": {
        "days": 7,
        "status": "requiere_completar",
        "notification": False,
        "color": "green"
    },
    "aging": {
        "days": 30,
        "status": "requiere_completar",
        "notification": True,
        "frequency_days": 3,
        "color": "yellow"
    },
    "stale": {
        "days": 60,
        "status": "stale_placeholder",
        "notification": True,
        "escalate": True,
        "color": "red"
    },
    "archived": {
        "days": 90,
        "status": "archived",
        "notification": False,
        "move_to_archive": True,
        "color": "gray"
    }
}
```

---

## 📝 Retrospectiva (End of Sprint 1)

**Fecha**: 2025-02-04 17:00

**Agenda**:
1. Revisión de issues completados (30 min)
2. Demo del dry run completo (15 min)
3. Métricas del sprint (15 min)
4. ¿Qué salió bien? (15 min)
5. ¿Qué mejorar? (15 min)
6. Planificación de Fase 2 - IA (30 min)

**Output Esperado**:
- ✅ Checklist de 8 issues cerrados
- ✅ Coverage report con > 80%
- ✅ Video/screenshots del dry run exitoso
- ✅ Plan de Fase 2 aprobado

---

## 🎓 Criterios de "Ready for Fase 2 (IA)"

**Checklist de Aprobación**:

### Técnico:
- [ ] Todos los tests E2E passing
- [ ] Coverage > 80%
- [ ] 0 bloqueadores críticos
- [ ] CI/CD pipeline activo
- [ ] Logging estructurado funcionando
- [ ] Dry run exitoso documentado

### Funcional:
- [ ] Usuario puede completar placeholder sin errores
- [ ] Duplicados se bloquean correctamente
- [ ] Stats muestra métricas reales
- [ ] Placeholders stale se marcan automáticamente

### Documentación:
- [ ] README actualizado con flujo
- [ ] API docs con ejemplos de /pending, /update, /stats
- [ ] Runbook para troubleshooting
- [ ] Política de caducidad documentada

### Aprobación:
- [ ] ✅ PM Técnico aprueba
- [ ] ✅ Lead Developer aprueba
- [ ] ✅ QA sign-off
- [ ] ✅ Stakeholders notificados

---

## 📞 Contactos y Responsabilidades

| Rol | Responsable | Email | Slack |
|-----|-------------|-------|-------|
| PM Técnico | [Nombre] | pm@company.com | @pm |
| Backend Lead | [Nombre] | dev@company.com | @dev |
| QA Engineer | [Nombre] | qa@company.com | @qa |
| DevOps | [Nombre] | devops@company.com | @devops |

---

## 🔗 Enlaces Útiles

- **Board de Issues**: [GitHub Projects / Jira]
- **Documentación**: `/docs/placeholder_system.md`
- **Tests**: `/tests/README.md`
- **Logs**: `/logs/placeholders.log`
- **Metrics**: `http://localhost:8000/api/expenses/placeholder-completion/stats/detailed`

---

**Última Actualización**: 2025-01-28
**Próxima Revisión**: 2025-02-01 (mid-sprint check-in)
**Versión**: 1.0

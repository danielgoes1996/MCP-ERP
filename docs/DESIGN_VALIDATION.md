# 🔍 VALIDACIÓN DEL DISEÑO - Sistema Robusto v2

## 📊 REVISIÓN DE 4 TABLAS NUEVAS

### ✅ Casos de Uso Validados por Tabla:

#### 1. `feature_flags`
**Propósito:** Control granular de features por tenant
```sql
-- Caso de uso real: Cliente problemático
UPDATE feature_flags SET enabled=0
WHERE company_id='cliente_dificil' AND feature_name='captcha_solving';

-- Caso de uso real: A/B testing
INSERT INTO feature_flags VALUES
('company_a', 'claude_analysis', 1, '{"model": "claude-3-5-sonnet"}'),
('company_b', 'claude_analysis', 1, '{"model": "claude-3-haiku"}');
```
**Validación equipo:** ✅ PM confirma necesidad control gradual rollout

#### 2. `tenant_config`
**Propósito:** Límites y configuración por empresa
```sql
-- Caso de uso real: Cliente enterprise vs startup
company_enterprise: max_concurrent_jobs=20, max_daily_jobs=1000
company_startup: max_concurrent_jobs=3, max_daily_jobs=100
```
**Validación equipo:** ✅ Sales confirma necesidad tiers diferenciados

#### 3. `automation_batches`
**Propósito:** Operaciones masivas trackeable
```sql
-- Caso de uso real: Cliente sube 500 tickets de fin de mes
batch_id='month_end_2024_09', total_jobs=500, completed=450, failed=50
```
**Validación equipo:** ✅ Ops confirma necesidad batch processing

#### 4. `automation_metrics`
**Propósito:** Analytics y billing
```sql
-- Caso de uso real: Facturación por uso
SELECT SUM(total_cost) FROM automation_metrics
WHERE company_id='cliente_x' AND date BETWEEN '2024-09-01' AND '2024-09-30';
```
**Validación equipo:** ✅ Finance confirma necesidad cost tracking

## 🔗 REVISIÓN DE 12 ENDPOINTS NUEVOS

### Endpoints v1 (MANTIENEN COMPATIBILIDAD):
```yaml
POST   /invoicing/tickets                    # ✅ MISMO contrato
GET    /invoicing/tickets/{id}               # ✅ MISMO contrato
GET    /invoicing/merchants                  # ✅ MISMO contrato
POST   /invoicing/merchants                  # ✅ MISMO contrato
GET    /invoicing/jobs                       # ✅ MISMO contrato
```

### Endpoints v2 (NUEVOS CON FEATURES):
```yaml
POST   /invoicing/v2/tickets                 # Enhanced con captcha_solving, alternative_urls
GET    /invoicing/v2/tickets/{id}            # Con automation_steps, llm_reasoning
POST   /invoicing/v2/jobs                    # Con priority, config avanzado
GET    /invoicing/v2/jobs                    # Con filtros status, pagination
GET    /invoicing/v2/jobs/{id}/stream        # Real-time SSE
POST   /invoicing/v2/bulk                    # Batch operations
GET    /invoicing/v2/health                  # System diagnostics
GET    /invoicing/v2/metrics                 # Usage analytics
```

### Endpoints de Compatibilidad (BRIDGES):
```yaml
GET    /invoicing/tickets/{id}/enhanced      # Bridge: v1 endpoint con v2 data
POST   /invoicing/tickets/{id}/process-robust # Bridge: trigger v2 desde v1
GET    /invoicing/system/status              # Bridge: health check cross-version
GET    /invoicing/automation/latest-data-enhanced # Bridge: viewer data enriquecida
```

## ✅ VALIDACIÓN ANTI-RUPTURA

### Test de Compatibilidad v1:
```python
# Caso 1: Cliente legacy sigue funcionando
response = requests.post("/invoicing/tickets", files={"file": ticket_image})
assert response.status_code == 200
assert "id" in response.json()  # Mismo contrato

# Caso 2: Mismo JSON response schema
ticket = requests.get("/invoicing/tickets/123").json()
assert set(ticket.keys()) >= {"id", "estado", "created_at"}  # Campos mínimos
```

### Test de Enriquecimiento v2:
```python
# Caso 3: v2 añade fields, no quita
enhanced_ticket = requests.get("/invoicing/v2/tickets/123").json()
assert set(enhanced_ticket.keys()) >= set(ticket.keys())  # Superset
assert "automation_status" in enhanced_ticket  # Nuevo field
```

## 📋 CONTRATOS DE API (OpenAPI)

### Schema Base v1 (INMUTABLE):
```yaml
TicketResponse:
  type: object
  required: [id, estado, created_at, updated_at]
  properties:
    id: {type: integer}
    estado: {type: string, enum: [pendiente, procesando, completado, fallido]}
    created_at: {type: string, format: date-time}
    updated_at: {type: string, format: date-time}
    # Otros campos opcionales mantienen compatibilidad
```

### Schema Enhanced v2 (EXTENSIBLE):
```yaml
EnhancedTicketResponse:
  allOf:
    - $ref: '#/components/schemas/TicketResponse'  # Hereda v1
    - type: object
      properties:
        automation_status:
          type: string
          enum: [pendiente, en_cola, procesando, ocr_completado, navegando,
                 resolviendo_captcha, completado, fallido, requiere_intervencion]
        automation_steps:
          type: array
          items: {$ref: '#/components/schemas/AutomationStep'}
        cost_breakdown:
          type: object
          additionalProperties: {type: number}
```

## 🗄️ CONTRATOS DE DB (Migraciones)

### Migración 010 - ROLLBACK EXPLÍCITO:
```sql
-- UP: Añadir campos sin romper existentes
ALTER TABLE automation_jobs ADD COLUMN priority TEXT DEFAULT 'normal';
ALTER TABLE automation_jobs ADD COLUMN cost_breakdown TEXT; -- JSON

-- DOWN: Rollback limpio
ALTER TABLE automation_jobs DROP COLUMN priority;
ALTER TABLE automation_jobs DROP COLUMN cost_breakdown;
-- Las tablas nuevas se DROP completas si es necesario
```

### Validaciones de Integridad:
```sql
-- Constraint: No permitir jobs huérfanos
FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE;

-- Constraint: Estados válidos
CHECK (estado IN ('pendiente', 'en_progreso', 'completado', 'fallido', 'pausado'));

-- Constraint: Prioridades válidas
CHECK (priority IN ('baja', 'normal', 'alta', 'urgente'));
```

## 🧪 SETUP DE ENTORNO DE PRUEBAS

### Rama Feature:
```bash
git checkout -b feature/robust-automation-v2
git push -u origin feature/robust-automation-v2
```

### Base de Datos Staging:
```bash
# 1. Clonar producción (sin datos sensibles)
cp expenses_prod_clean.db expenses_staging.db

# 2. Aplicar migraciones nuevas
sqlite3 expenses_staging.db < migrations/010_enhance_automation_20240922.sql

# 3. Seed con datos de prueba
python scripts/seed_test_data.py --env staging
```

### Test Data Factory:
```python
# scripts/seed_test_data.py
def create_test_merchants():
    return [
        {"nombre": "OXXO Test", "portal_url": "https://oxxo.com", "has_captcha": True},
        {"nombre": "Litro Mil Test", "portal_url": "http://litromil.test", "multiple_urls": True},
        {"nombre": "Simple Portal", "portal_url": "https://simple.test", "basic_form": True}
    ]

def create_test_tickets():
    return [
        {"tipo": "imagen", "raw_data": "base64_ticket_oxxo", "merchant_hint": "OXXO Test"},
        {"tipo": "texto", "raw_data": "RFC: TEST010101000\nTotal: $100", "merchant_hint": "Simple Portal"}
    ]
```

## 🔄 INTEGRACIÓN CONTINUA

### Pipeline CI/CD (.github/workflows/test-v2.yml):
```yaml
name: Test Robust Automation v2
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio

      - name: Setup test database
        run: |
          sqlite3 test.db < migrations/009_automation_engine_20240921.sql
          sqlite3 test.db < migrations/010_enhance_automation_20240922.sql

      - name: Run compatibility tests
        run: pytest tests/test_v1_compatibility.py -v

      - name: Run v2 functionality tests
        run: pytest tests/test_v2_features.py -v

      - name: Run integration tests
        run: pytest tests/test_integration.py -v --cov=modules/invoicing_agent

      - name: Performance benchmarks
        run: pytest tests/test_performance.py -v
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GOOGLE_APPLICATION_CREDENTIALS: ${{ secrets.GOOGLE_CREDS }}
```

### Métricas Básicas:
```python
# tests/test_performance.py
def test_v1_endpoint_latency():
    """v1 endpoints must respond < 500ms"""
    start = time.time()
    response = client.get("/invoicing/tickets/1")
    assert time.time() - start < 0.5
    assert response.status_code == 200

def test_v2_endpoint_acceptable_latency():
    """v2 endpoints acceptable < 2s (includes LLM calls)"""
    start = time.time()
    response = client.get("/invoicing/v2/tickets/1")
    assert time.time() - start < 2.0
    assert response.status_code == 200
```

## 📅 IMPLEMENTACIÓN POR FASES

### 📅 Semana 1: Base + Core Endpoints
**Entregables:**
- [ ] Migración 010 aplicada en staging
- [ ] 4 endpoints v2 core funcionando
- [ ] Tests de compatibilidad v1 pasando
- [ ] OpenAPI docs generadas

**Acceptance Criteria:**
```bash
# Existing functionality unchanged
curl /invoicing/tickets -> 200 OK (same schema)

# New functionality available
curl /invoicing/v2/tickets -> 200 OK (enhanced schema)
```

### 📅 Semana 2: Workers + Seguridad
**Entregables:**
- [ ] Background jobs funcionando
- [ ] RBAC implementado
- [ ] Credenciales cifradas
- [ ] Rate limiting activo

**Acceptance Criteria:**
```bash
# Security working
curl -H "Authorization: Bearer invalid" /invoicing/v2/admin -> 403

# Background processing
POST /invoicing/v2/tickets -> {"status": "queued"}
```

### 📅 Semana 3: Real-time + WebSockets
**Entregables:**
- [ ] SSE streaming funcionando
- [ ] Automation viewer actualizado
- [ ] Notificaciones en tiempo real

**Acceptance Criteria:**
```javascript
// Real-time updates working
const stream = new EventSource('/invoicing/v2/jobs/123/stream');
stream.onmessage = (event) => { /* progress updates */ };
```

### 📅 Semana 4: Observabilidad + Rollout
**Entregables:**
- [ ] Métricas en producción
- [ ] Feature flags per-tenant
- [ ] Rollout gradual funcionando

**Acceptance Criteria:**
```sql
-- Granular control working
SELECT * FROM feature_flags WHERE company_id='pilot_client';
-- pilot_client gets v2, others stay v1
```

## ⚠️ CHECKLIST DE RIESGOS

### 🗄️ Riesgo: Migraciones fallan a la mitad
**Mitigación:**
```sql
-- Transaccional migration
BEGIN TRANSACTION;
  ALTER TABLE automation_jobs ADD COLUMN priority TEXT DEFAULT 'normal';
  -- Verificar que funciona
  SELECT priority FROM automation_jobs LIMIT 1;
  -- Si falla, ROLLBACK automático
COMMIT;
```

**Plan B:** Migración idempotente
```sql
-- Safe to run multiple times
ALTER TABLE automation_jobs ADD COLUMN IF NOT EXISTS priority TEXT DEFAULT 'normal';
```

### ⚙️ Riesgo: Workers se saturan o caen
**Mitigación:**
- Circuit breaker pattern
- Queue con dead letter
- Health checks cada 30s

```python
# Circuit breaker
@circuit_breaker(failure_threshold=5, recovery_timeout=60)
async def process_automation_job(job_id):
    # Si falla 5 veces seguidas, parar 60s
```

### 🔌 Riesgo: WebSockets se cortan
**Mitigación:**
- Auto-reconnect con exponential backoff
- Fallback a polling cada 5s
- Estado persistido en DB

```javascript
// Auto-reconnect SSE
function createSSE() {
    const stream = new EventSource('/stream');
    stream.onerror = () => {
        setTimeout(createSSE, backoff_time);
        backoff_time *= 2; // Exponential backoff
    };
}
```

### 🔐 Riesgo: Rotación de credenciales sin downtime
**Mitigación:**
- Dual-key system (key1 active, key2 standby)
- Blue-green credential rotation
- Zero-downtime key refresh

```python
# Dual key system
def get_active_credential():
    try:
        return decrypt_with_key(primary_key)
    except:
        return decrypt_with_key(fallback_key)  # Seamless fallback
```

## ✅ SIGN-OFF CHECKLIST

### Equipo Técnico:
- [ ] **Backend Lead:** APIs y contratos validados
- [ ] **Frontend Lead:** UI changes compatible
- [ ] **DevOps:** Deployment pipeline ready
- [ ] **QA:** Test strategy approved
- [ ] **DBA:** Migration path validated

### Equipo Negocio:
- [ ] **PM:** Feature scope aligned with roadmap
- [ ] **Sales:** Pricing model for enhanced features
- [ ] **Support:** Runbooks for troubleshooting
- [ ] **Legal:** Security/privacy compliance review

### Go/No-Go Criteria:
- [ ] All v1 compatibility tests pass (100%)
- [ ] Performance regression < 10%
- [ ] Security audit passed
- [ ] Rollback procedure tested successfully
- [ ] Feature flags working per-tenant

**✅ APROBACIÓN FINAL: Equipo completo sign-off antes de merge a main**
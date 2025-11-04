# API Conventions - MCP System

## Estructura de Rutas

### Versionado
```
/api/v1/{resource}      # Rutas versionadas (futuro)
/{resource}             # Rutas legacy (actual)
```

**Decisión**: Mantener rutas sin versión para MVP, agregar `/api/v2` cuando haya breaking changes.

### Naming Patterns

| Tipo | Patrón | Ejemplo |
|------|--------|---------|
| Recursos | `snake_case` | `/employee_advances` |
| Sub-recursos | `/parent/{id}/child` | `/employee_advances/{id}/reimbursements` |
| Acciones | POST con verbo | `/employee_advances/reimburse` |
| Filtros | Query params | `/employee_advances?status=pending` |
| Agregaciones | `/resource/summary` | `/employee_advances/summary/all` |

### Organización por Prefijos

```python
# ✅ Bueno: Agrupación lógica
/bank_reconciliation/splits          # Conciliación manual
/bank_reconciliation/ai/suggestions  # Motor IA
/bank_reconciliation/ai/auto-apply   # Aplicación automática

# ❌ Evitar: Rutas planas sin jerarquía
/reconciliation-splits
/ai-suggestions
/auto-apply
```

## Respuestas HTTP

### Status Codes
```python
200 OK              # GET exitoso, UPDATE exitoso
201 Created         # POST create exitoso
204 No Content      # DELETE exitoso
400 Bad Request     # Validación falló
404 Not Found       # Recurso no existe
409 Conflict        # Duplicado, estado inválido
500 Server Error    # Error interno
```

### Formato de Errores
```json
{
  "detail": "Expense 10244 is already registered as an advance",
  "error_code": "DUPLICATE_ADVANCE",
  "field": "expense_id",
  "value": 10244
}
```

### Paginación
```python
GET /employee_advances?limit=50&offset=0

Response:
{
  "total": 250,
  "limit": 50,
  "offset": 0,
  "data": [...]
}
```

## Tags de Swagger

```python
router = APIRouter(
    prefix="/employee_advances",
    tags=["Employee Advances"]  # Categoría en docs
)
```

Grupos actuales:
- **Employee Advances**: Gestión de anticipos
- **AI Reconciliation**: Motor IA de conciliación
- **Bank Reconciliation**: Conciliación manual
- **Expense Completion**: Autocompletado de gastos
- **Conversational Assistant**: Asistente por voz

## Autenticación (Futuro)

```python
# Header requerido:
Authorization: Bearer <jwt_token>

# Scopes por rol:
employee:read       # Ver propios anticipos
employee:write      # Crear anticipos propios
accountant:read     # Ver todos los anticipos
accountant:write    # Procesar reembolsos
admin:*             # Acceso completo
```

## Ejemplos Completos

### Employee Advances
```
POST   /employee_advances                    # Crear anticipo
GET    /employee_advances                    # Listar (filtrable)
GET    /employee_advances/{id}               # Ver detalle
PATCH  /employee_advances/{id}               # Actualizar
DELETE /employee_advances/{id}               # Cancelar

POST   /employee_advances/reimburse          # Procesar reembolso
GET    /employee_advances/summary/all        # Dashboard global
GET    /employee_advances/employee/{id}/summary  # Por empleado
GET    /employee_advances/pending/all        # Pendientes de pago
```

### AI Reconciliation
```
GET    /bank_reconciliation/ai/suggestions   # Obtener sugerencias
POST   /bank_reconciliation/ai/auto-apply/{index}  # Aplicar sugerencia
GET    /bank_reconciliation/ai/confidence/{id}     # Ver score detallado
```

## Migración a v2 (Propuesta)

Cuando tengamos breaking changes:

```python
# api/v2/employee_advances_api.py
router = APIRouter(prefix="/api/v2/employee-advances", tags=["Employee Advances v2"])

@router.post("/")
async def create_advance_v2(request: CreateAdvanceRequestV2):
    """
    V2 Changes:
    - Required fields: employee_email (no solo ID)
    - Validation: auto-check expense is not reconciled
    - Response: include expense details in advance object
    """
    pass

# Deprecation warning en v1:
@router.post("/")
async def create_advance(request: CreateAdvanceRequest):
    """
    ⚠️ DEPRECATED: Use /api/v2/employee-advances instead
    Will be removed in 2026-01-01
    """
    pass
```

## Testing

Cada endpoint debe tener:
```python
# tests/test_employee_advances_api.py
def test_create_advance_success():
    response = client.post("/employee_advances/", json={...})
    assert response.status_code == 201
    assert "id" in response.json()

def test_create_advance_duplicate():
    response = client.post("/employee_advances/", json={...})
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]
```

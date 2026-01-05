# 🔥 CPG Vertical Refactoring - ANTES vs DESPUÉS

## 📊 Métricas de Reducción

| Métrica | ANTES | DESPUÉS | Reducción |
|---------|-------|---------|-----------|
| **Líneas de código** | 535 | ~400 | 25% |
| **Lógica CRUD manual** | 100% duplicada | 0% (usa DAL) | ✅ Eliminada |
| **Obtención de tenant_id** | 2 lugares | 0 (DAL auto) | ✅ Eliminada |
| **Serialización JSON** | 5 lugares | 0 (DAL auto) | ✅ Eliminada |
| **Validación de estados** | ❌ No existe | ✅ StatusMachine | 🆕 Agregada |
| **Cálculos financieros** | Manual inline | FinancialCalculator | ✅ Centralizado |
| **Logging estructurado** | Ad-hoc | EnhancedVerticalBase | ✅ Estandarizado |

---

## 🔍 Comparación Detallada

### 1. CREATE POS

#### ❌ ANTES (54 líneas)
```python
async def create_pos(self, company_id: str, pos_data: Dict[str, Any]) -> Dict[str, Any]:
    from core.shared.unified_db_adapter import execute_query
    import json

    query = """
        INSERT INTO cpg_pos (
            company_id, tenant_id, codigo, nombre, tipo_comercio,
            direccion, ciudad, estado, codigo_postal, coordenadas,
            contacto_nombre, contacto_telefono, contacto_email,
            payment_mode, credit_days, consignment_percentage,
            status, metadata
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s
        )
        RETURNING *
    """

    # ❌ Obtener tenant_id MANUALMENTE
    tenant_result = execute_query(
        "SELECT tenant_id FROM companies WHERE company_id = %s",
        (company_id,),
        fetch_one=True
    )
    tenant_id = tenant_result['tenant_id'] if tenant_result else None

    # ❌ Serializar JSON MANUALMENTE
    params = (
        company_id,
        tenant_id,
        pos_data.get('codigo'),
        pos_data.get('nombre'),
        pos_data.get('tipo_comercio'),
        pos_data.get('direccion'),
        pos_data.get('ciudad'),
        pos_data.get('estado'),
        pos_data.get('codigo_postal'),
        json.dumps(pos_data.get('coordenadas')) if pos_data.get('coordenadas') else None,  # ❌ Manual
        pos_data.get('contacto_nombre'),
        pos_data.get('contacto_telefono'),
        pos_data.get('contacto_email'),
        pos_data.get('payment_mode', 'cash'),
        pos_data.get('credit_days', 0),
        pos_data.get('consignment_percentage', 0.0),
        pos_data.get('status', 'active'),
        json.dumps(pos_data.get('metadata')) if pos_data.get('metadata') else None  # ❌ Manual
    )

    result = execute_query(query, params, fetch_one=True)
    logger.info(f"Created POS {result['codigo']} for company {company_id}")
    return result
```

#### ✅ DESPUÉS (1 línea)
```python
async def create_pos(self, company_id: str, pos_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    ANTES: 54 líneas (tenant_id manual, JSON manual, INSERT manual)
    DESPUÉS: 1 línea (DAL hace todo automáticamente)
    """
    # ✅ DAL auto-inyecta company_id, tenant_id, serializa JSONB
    return self.pos_dal.create(company_id, pos_data)
```

**Beneficios:**
- ✅ Cero SQL manual
- ✅ Auto-inyección de `company_id` y `tenant_id`
- ✅ Auto-serialización de campos JSONB (`coordenadas`, `metadata`)
- ✅ Logging automático
- ✅ Seguridad: imposible olvidar filtrar por `company_id`

---

### 2. UPDATE POS

#### ❌ ANTES (29 líneas)
```python
async def update_pos(self, company_id: str, pos_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
    from core.shared.unified_db_adapter import execute_query
    import json

    # ❌ Build dynamic update query MANUALMENTE
    set_clauses = []
    params = []

    for field, value in updates.items():
        # ❌ Serializar JSON MANUALMENTE
        if field in ['coordenadas', 'metadata'] and value:
            set_clauses.append(f"{field} = %s")
            params.append(json.dumps(value))
        else:
            set_clauses.append(f"{field} = %s")
            params.append(value)

    params.extend([pos_id, company_id])

    query = f"""
        UPDATE cpg_pos
        SET {', '.join(set_clauses)}, updated_at = NOW()
        WHERE id = %s AND company_id = %s
        RETURNING *
    """

    result = execute_query(query, tuple(params), fetch_one=True)
    logger.info(f"Updated POS {pos_id} for company {company_id}")
    return result
```

#### ✅ DESPUÉS (1 línea)
```python
async def update_pos(self, company_id: str, pos_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    ANTES: 29 líneas (dynamic UPDATE, JSON serialization manual)
    DESPUÉS: 1 línea (DAL hace todo)
    """
    return self.pos_dal.update(company_id, pos_id, updates)
```

**Beneficios:**
- ✅ Cero lógica de construcción de UPDATE
- ✅ Auto-serialización de JSONB
- ✅ Auto-actualización de `updated_at`
- ✅ Logging automático
- ✅ Seguridad: siempre filtra por `company_id`

---

### 3. CREATE CONSIGNMENT

#### ❌ ANTES (61 líneas)
```python
async def create_consignment(
    self,
    company_id: str,
    consignment_data: Dict[str, Any]
) -> Dict[str, Any]:
    from core.shared.unified_db_adapter import execute_query
    import json

    # ❌ Calcular total MANUALMENTE
    productos = consignment_data.get('productos', [])
    monto_total = sum(
        p.get('qty', 0) * p.get('precio', 0)
        for p in productos
    )

    query = """
        INSERT INTO cpg_consignment (
            company_id, tenant_id, pos_id,
            numero_remision, fecha_entrega,
            productos, monto_total, monto_pagado,
            status, notas, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """

    # ❌ Obtener tenant_id MANUALMENTE
    tenant_result = execute_query(
        "SELECT tenant_id FROM companies WHERE company_id = %s",
        (company_id,),
        fetch_one=True
    )
    tenant_id = tenant_result['tenant_id'] if tenant_result else None

    # ❌ Preparar params MANUALMENTE
    params = (
        company_id,
        tenant_id,
        consignment_data.get('pos_id'),
        consignment_data.get('numero_remision'),
        consignment_data.get('fecha_entrega'),
        json.dumps(productos),  # ❌ Manual
        monto_total,
        0.0,
        'pending',
        consignment_data.get('notas'),
        json.dumps(consignment_data.get('metadata')) if consignment_data.get('metadata') else None  # ❌ Manual
    )

    result = execute_query(query, params, fetch_one=True)
    logger.info(f"Created consignment {result['numero_remision']} for POS {consignment_data.get('pos_id')}")
    return result
```

#### ✅ DESPUÉS (15 líneas)
```python
async def create_consignment(
    self,
    company_id: str,
    consignment_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    ANTES: 61 líneas (cálculo manual, tenant_id manual, INSERT manual)
    DESPUÉS: 8 líneas (usa FinancialCalculator + DAL)
    """
    # ✅ Usar FinancialCalculator compartido
    productos = consignment_data.get('productos', [])
    monto_total = self.financial.calculate_total(productos, qty_field='qty', price_field='precio')

    # Preparar datos
    consignment_data['monto_total'] = monto_total
    consignment_data['monto_pagado'] = 0.0
    consignment_data['status'] = 'pending'

    # ✅ DAL auto-inyecta company_id, tenant_id, serializa productos (JSONB)
    result = self.consignment_dal.create(company_id, consignment_data)

    self.log_operation("create", "consignment", result['id'], {
        "numero_remision": result.get('numero_remision'),
        "monto_total": monto_total
    })

    return result
```

**Beneficios:**
- ✅ `FinancialCalculator` centraliza lógica de cálculo
- ✅ Si mañana cambias la fórmula de totales, se arregla en todos los verticales
- ✅ Logging estructurado con `log_operation()`
- ✅ Auto-inyección de `company_id` y `tenant_id`

---

### 4. MARK CONSIGNMENT SOLD

#### ❌ ANTES (24 líneas) - SIN validación de estados
```python
async def mark_consignment_sold(
    self,
    company_id: str,
    consignment_id: int,
    fecha_venta: str
) -> Dict[str, Any]:
    """Mark consignment as sold (waiting for payment)."""
    from core.shared.unified_db_adapter import execute_query

    # ❌ NO valida si la transición pending→sold es válida
    # ❌ Podría pasar de "paid" a "sold" (invalido) y nadie se da cuenta

    result = execute_query(
        """
        UPDATE cpg_consignment
        SET status = 'sold',
            fecha_venta = %s,
            updated_at = NOW()
        WHERE id = %s AND company_id = %s
        RETURNING *
        """,
        (fecha_venta, consignment_id, company_id),
        fetch_one=True
    )

    logger.info(f"Marked consignment {consignment_id} as sold")
    return result
```

#### ✅ DESPUÉS (12 líneas) - CON validación de estados
```python
async def mark_consignment_sold(
    self,
    company_id: str,
    consignment_id: int,
    fecha_venta: str
) -> Dict[str, Any]:
    """
    ANTES: 24 líneas sin validación de transiciones
    DESPUÉS: 12 líneas con StatusMachine que previene errores
    """
    # ✅ Validar transición de estado
    current = self.consignment_dal.get(company_id, consignment_id)
    if not current:
        raise ValueError(f"Consignment {consignment_id} not found")

    # 🛡️ CRITICAL: StatusMachine previene transiciones inválidas
    # Si el estado actual es "paid", esto lanzará excepción
    self.consignment_sm.validate_transition(current['status'], 'sold')

    # ✅ Actualizar con DAL
    result = self.consignment_dal.update(company_id, consignment_id, {
        'status': 'sold',
        'fecha_venta': fecha_venta
    })

    self.log_operation("mark_sold", "consignment", consignment_id)
    return result
```

**Beneficios:**
- 🛡️ **CRÍTICO**: Previene corrupción de datos
- ✅ Si intentas marcar como "sold" un consignment que ya está "paid", el sistema lo bloquea
- ✅ Reglas de negocio centralizadas en StatusMachine
- ✅ Logging estructurado

---

## 🎯 Resumen de Mejoras

### ✅ Código Eliminado (Ya no necesitas escribir esto)

| Lógica Eliminada | Reemplazado Por |
|------------------|-----------------|
| `tenant_result = execute_query(...)` | `VerticalDAL` auto-inyecta |
| `json.dumps(metadata)` | `VerticalDAL` auto-serializa JSONB |
| `INSERT INTO ... VALUES (...)` | `VerticalDAL.create()` |
| `UPDATE ... SET ... WHERE ...` | `VerticalDAL.update()` |
| `SELECT * FROM ... WHERE id = ...` | `VerticalDAL.get()` |
| `sum(p['qty'] * p['precio'] ...)` | `FinancialCalculator.calculate_total()` |
| `logger.info(f"Created ...")` | `EnhancedVerticalBase.log_operation()` |

### 🆕 Funcionalidad Nueva (Gratis)

| Feature | Descripción | Beneficio |
|---------|-------------|-----------|
| **StatusMachine** | Validación de transiciones de estado | Previene datos corruptos |
| **Auto company_id** | Inyección automática en queries | Seguridad anti-IDOR |
| **Auto tenant_id** | Inyección automática en queries | Multi-tenancy sin esfuerzo |
| **Auto JSONB** | Serialización automática | Menos errores JSON |
| **Structured Logging** | `log_operation()` estandarizado | Debugging más fácil |
| **Soft Deletes** | `delete()` solo marca como inactivo | Datos recuperables |

---

## 🚀 Siguiente Paso

Para activar el código refactorizado:

```bash
# 1. Reemplazar el archivo viejo
mv core/verticals/cpg_retail/cpg_vertical.py core/verticals/cpg_retail/cpg_vertical_OLD.py
mv core/verticals/cpg_retail/cpg_vertical_v2.py core/verticals/cpg_retail/cpg_vertical.py

# 2. Probar que funciona
python3 -m pytest tests/test_cpg_vertical.py -v

# 3. Commit
git add core/verticals/cpg_retail/cpg_vertical.py
git commit -m "refactor: CPG vertical using shared_logic (535→400 lines, 25% reduction)"
```

---

## 📈 Impacto a Futuro

**Cuando crees el próximo vertical (Manufacturing, Logistics):**

```python
class ManufacturingVertical(VerticalBase, EnhancedVerticalBase):
    def __init__(self):
        super().__init__()

        # ✅ 3 líneas y tienes CRUD completo
        self.workorder_dal = self.create_dal("mfg_workorders")
        self.bom_dal = self.create_dal("mfg_bom")  # Bill of Materials

        # ✅ State machine para workflow
        self.workorder_sm = self.create_status_machine({
            "draft": ["submitted"],
            "submitted": ["approved", "rejected"],
            "approved": ["in_progress"],
            "in_progress": ["completed", "cancelled"],
            "completed": [],
        })
```

**Sin shared_logic, cada vertical nuevo = 500 líneas de código duplicado.**
**Con shared_logic, cada vertical nuevo = ~150 líneas de lógica de negocio pura.**

---

## 🎉 Conclusión

**ANTES:**
- 535 líneas de código
- Lógica duplicada en 10+ lugares
- Sin validación de transiciones de estado
- Fácil cometer errores de seguridad (olvidar `company_id`)

**DESPUÉS:**
- ~400 líneas de código (25% reducción)
- Lógica compartida, cero duplicación
- StatusMachine previene corrupción de datos
- Imposible olvidar `company_id` (inyección automática)

**Esta es la diferencia entre código que escala y código que se convierte en legado.**

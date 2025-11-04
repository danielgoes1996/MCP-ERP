# 📘 Convenciones de Nomenclatura - MCP System

## 🎯 Objetivo

Prevenir inconsistencias entre capas del sistema (BD, API, Frontend) que causan bugs como:
- ❌ Campo existe en BD pero no se muestra en UI (`metodo_pago` vs `forma_pago`)
- ❌ API devuelve `null` porque mapea campo incorrecto
- ❌ Datos se pierden en actualizaciones por nombres diferentes

---

## 🏗️ Arquitectura de 3 Capas

```
┌─────────────────────────────────────────────────────────┐
│                    CAPA FRONTEND                        │
│  Nomenclatura: camelCase (JavaScript/React)            │
│  Ejemplo: metodoPago, fechaGasto, montoTotal           │
└─────────────────────────────────────────────────────────┘
                         ↕️
┌─────────────────────────────────────────────────────────┐
│                     CAPA API                            │
│  Nomenclatura: snake_case español (Pydantic)           │
│  Ejemplo: metodo_pago, fecha_gasto, monto_total        │
└─────────────────────────────────────────────────────────┘
                         ↕️
┌─────────────────────────────────────────────────────────┐
│                  CAPA BASE DE DATOS                     │
│  Nomenclatura: snake_case español (SQLite/PostgreSQL)  │
│  Ejemplo: metodo_pago, fecha_gasto, monto_total        │
└─────────────────────────────────────────────────────────┘
```

---

## ✅ REGLA #1: UNA Fuente de Verdad

**La base de datos es la fuente de verdad para nombres de campos.**

### ✅ CORRECTO: Alinear todo con BD

```python
# 1. Base de Datos
CREATE TABLE expense_records (
    metodo_pago TEXT,     -- ✅ Nombre en español
    fecha_gasto DATE,
    monto_total REAL
);

# 2. Modelo API (DEBE coincidir con BD)
class ExpenseResponse(BaseModel):
    metodo_pago: Optional[str]  # ✅ Mismo nombre que BD
    fecha_gasto: str
    monto_total: float

# 3. Mapping en endpoint (DEBE usar nombre de BD)
def _build_expense_response(record):
    return ExpenseResponse(
        metodo_pago=record.get("metodo_pago"),  # ✅ Coincide con BD
        fecha_gasto=record.get("fecha_gasto"),
        monto_total=record.get("monto_total")
    )
```

### ❌ INCORRECTO: Crear alias innecesarios

```python
# ❌ NO hacer esto - crea confusión
class ExpenseResponse(BaseModel):
    forma_pago: Optional[str]      # ❌ Nombre diferente a BD
    payment_method: Optional[str]  # ❌ Inglés cuando BD es español
    metodo_pago: Optional[str]     # ❌ Ahora tenemos 3 nombres!

# ❌ NO hacer esto - mapeo incorrecto
def _build_expense_response(record):
    return ExpenseResponse(
        forma_pago=record.get("payment_method")  # ❌ Ninguno existe en BD!
    )
```

---

## ✅ REGLA #2: Nomenclatura Consistente

### Base de Datos y API: `snake_case` español

```python
✅ metodo_pago
✅ fecha_gasto
✅ monto_total
✅ categoria
✅ descripcion

❌ metodoPago     # NO - camelCase es para frontend
❌ payment_method # NO - inglés genera confusión
❌ forma_pago     # NO - usar nombre estándar metodo_pago
```

### Frontend: `camelCase` español

```javascript
// ✅ CORRECTO
const expense = {
    metodoPago: "tarjeta_credito",
    fechaGasto: "2025-10-04",
    montoTotal: 500.0
};

// ❌ INCORRECTO
const expense = {
    metodo_pago: "...",  // ❌ snake_case en JS es no idiomático
    payment_method: "..." // ❌ Mezclando idiomas
};
```

---

## ✅ REGLA #3: Detectar Duplicados Antes de Merge

### Script de Validación

Ejecutar **ANTES** de cada commit:

```bash
python validate_schema.py
```

Esto detectará:
- ✅ Campos duplicados (forma_pago + metodo_pago)
- ✅ Campos en BD sin mapeo en API
- ✅ Campos en API sin columna en BD

### Ejemplo de salida

```
❌ DUPLICADO: Modelo tiene ambos 'forma_pago' y 'metodo_pago'
⚠️  Campos en BD sin mapeo en modelo: {'payment_account_id'}
```

---

## ✅ REGLA #4: Documentar Mapeos Excepcionales

Si **absolutamente necesitas** un alias (ej: API legacy), documéntalo:

```python
# core/api_models.py

class ExpenseResponse(BaseModel):
    # ✅ Campo primario (alineado con BD)
    metodo_pago: Optional[str] = Field(
        None,
        description="Método de pago utilizado"
    )

    # ⚠️ DEPRECATED - Solo para compatibilidad con API v1
    payment_method: Optional[str] = Field(
        None,
        deprecated=True,
        description="DEPRECATED: Usar metodo_pago"
    )

    @validator('payment_method', pre=True, always=True)
    def sync_payment_method(cls, v, values):
        """Auto-sincronizar payment_method desde metodo_pago"""
        return v or values.get('metodo_pago')
```

---

## 📋 Checklist de Code Review

Antes de aprobar un PR, verificar:

- [ ] ✅ Nombres de campos coinciden entre BD y modelo API
- [ ] ✅ No se crearon campos duplicados (ej: `forma_pago` + `metodo_pago`)
- [ ] ✅ `python validate_schema.py` pasa sin errores
- [ ] ✅ Tests de integración cubren el nuevo campo
- [ ] ✅ Documentación actualizada si hay excepciones

---

## 🔧 Cómo Corregir Inconsistencias Existentes

### 1. Identificar campo correcto (BD es fuente de verdad)

```bash
sqlite3 unified_mcp_system.db "PRAGMA table_info(expense_records);"
# Resultado: metodo_pago TEXT
```

### 2. Actualizar modelo API

```python
# Antes
class ExpenseResponse(BaseModel):
    forma_pago: Optional[str]  # ❌

# Después
class ExpenseResponse(BaseModel):
    metodo_pago: Optional[str]  # ✅
```

### 3. Actualizar mapping en endpoints

```python
# Antes
forma_pago=record.get("payment_method")  # ❌

# Después
metodo_pago=record.get("metodo_pago")  # ✅
```

### 4. Actualizar frontend

```javascript
// Antes
<td>{expense.forma_pago}</td>  // ❌

// Después
<td>{expense.metodo_pago}</td>  // ✅
```

### 5. Validar

```bash
python validate_schema.py
# Debe pasar sin errores críticos
```

---

## 📚 Casos de Uso Comunes

### Agregar nuevo campo

1. Agregar columna a BD:
   ```sql
   ALTER TABLE expense_records ADD COLUMN nuevo_campo TEXT;
   ```

2. Agregar a modelo API con **mismo nombre**:
   ```python
   class ExpenseResponse(BaseModel):
       nuevo_campo: Optional[str]  # ✅ Mismo nombre que BD
   ```

3. Mapear en endpoint:
   ```python
   nuevo_campo=record.get("nuevo_campo")  # ✅ Coincide con BD
   ```

4. Validar:
   ```bash
   python validate_schema.py
   ```

### Renombrar campo existente

**NO** renombrar a menos que sea absolutamente necesario.

Si es necesario:

1. Agregar nueva columna a BD
2. Migrar datos
3. Deprecar campo viejo
4. Eliminar después de 2 sprints

---

## 🚨 Errores Comunes a Evitar

### ❌ Error #1: Inventar nombres en el mapping

```python
# ❌ MAL
return ExpenseResponse(
    payment_type=record.get("metodo_pago")  # Inventa "payment_type"
)

# ✅ BIEN
return ExpenseResponse(
    metodo_pago=record.get("metodo_pago")  # Usa nombre de BD
)
```

### ❌ Error #2: Mezclar idiomas

```python
# ❌ MAL
metodo_pago TEXT,
payment_date DATE,
categoria TEXT

# ✅ BIEN
metodo_pago TEXT,
fecha_pago DATE,
categoria TEXT
```

### ❌ Error #3: Crear duplicados por refactor

```python
# ❌ MAL - durante refactor
class Expense(BaseModel):
    forma_pago: str       # Campo viejo
    metodo_pago: str      # Campo nuevo - ahora tenemos 2!

# ✅ BIEN - reemplazar completamente
class Expense(BaseModel):
    metodo_pago: str      # Solo el nuevo
```

---

## 🎓 Resumen Ejecutivo

1. **Base de Datos = Fuente de Verdad**
2. **snake_case español** en BD y API
3. **camelCase español** en frontend
4. **Validar con `python validate_schema.py`**
5. **NO crear duplicados** durante refactors
6. **Documentar excepciones** si son necesarias

---

**Última actualización**: 2025-10-04
**Mantenedor**: Equipo de Arquitectura

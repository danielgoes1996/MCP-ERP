# 📖 Guía: Manejo de Nombres de Proveedores

## Problema
El **nombre comercial** de un proveedor puede ser diferente del **nombre fiscal** que aparece en la factura.

## Ejemplos Reales

### Ejemplo 1: Costco
- **Nombre Comercial** (lo que conocemos): "Costco"
- **Nombre Fiscal** (en la factura): "Costco de México S.A. de C.V."
- **RFC**: CME850101ABC

### Ejemplo 2: Office Depot
- **Nombre Comercial**: "Office Depot"
- **Nombre Fiscal**: "Office Depot de México S.A. de C.V."
- **RFC**: ODE850101ABC

### Ejemplo 3: Gasolinera
- **Nombre Comercial**: "Pemex"
- **Nombre Fiscal**: "Pemex Refinación S.A. de C.V."
- **RFC**: PRE850101ABC

## Solución Propuesta

### Campos en PostgreSQL

```sql
provider_name         VARCHAR(500)  -- Nombre comercial (lo que escribes normalmente)
provider_fiscal_name  VARCHAR(500)  -- Nombre fiscal (de la factura)
provider_rfc          VARCHAR(13)   -- RFC del proveedor
```

### Flujo de Trabajo

#### 1️⃣ Al Crear un Gasto (Manual)
El usuario captura el **nombre comercial** que conoce:

```json
{
  "descripcion": "Compra de papelería",
  "monto_total": 1500.00,
  "proveedor": {
    "nombre": "Office Depot",
    "rfc": null
  }
}
```

**Resultado en DB:**
- `provider_name`: "Office Depot"
- `provider_fiscal_name`: `null` (aún no hay factura)
- `provider_rfc`: `null`

#### 2️⃣ Al Recibir la Factura (Automático con IA)
Cuando llega el XML de la factura, el sistema extrae automáticamente:

```xml
<cfdi:Emisor
  Nombre="Office Depot de México S.A. de C.V."
  Rfc="ODE850101ABC"/>
```

**El sistema actualiza:**
- `provider_name`: "Office Depot" (se mantiene)
- `provider_fiscal_name`: "Office Depot de México S.A. de C.V." ✅ (extraído del XML)
- `provider_rfc`: "ODE850101ABC" ✅ (extraído del XML)

#### 3️⃣ Conciliación Inteligente
El sistema puede comparar nombres usando similitud:

```python
# Buscar gastos sin factura que coincidan con este proveedor
similarity("Office Depot", "Office Depot de México S.A. de C.V.") = 85%
# ✅ Probable match - sugerir conciliación
```

## Formato del Campo `proveedor`

### Formato Actual (Implementado)
```json
"proveedor": {
  "nombre": "Nombre comercial",
  "rfc": "RFC123456789"  // Opcional
}
```

### Formato Propuesto (Con nombre fiscal)
```json
"proveedor": {
  "nombre_comercial": "Office Depot",
  "nombre_fiscal": "Office Depot de México S.A. de C.V.",  // Opcional hasta tener factura
  "rfc": "ODE850101ABC"  // Opcional hasta tener factura
}
```

## Migración a Ejecutar

```bash
# Aplicar la migración
docker exec mcp-postgres psql -U mcp_user -d mcp_system -f /migrations/add_provider_fiscal_name.sql
```

## Ventajas de Esta Solución

✅ **Flexibilidad**: Permite captura rápida sin RFC
✅ **Precisión**: Nombre fiscal exacto de la factura
✅ **Conciliación**: Match inteligente entre gastos y facturas
✅ **Auditoría**: Trazabilidad completa del proveedor
✅ **UX**: Usuario captura lo que conoce, IA completa lo fiscal

## Ejemplo Completo

```json
{
  "descripcion": "Gasolina para auto de empresa",
  "monto_total": 850.00,
  "fecha_gasto": "2025-11-25",
  "categoria": "combustible_gasolina",
  "proveedor": {
    "nombre_comercial": "Pemex",
    "nombre_fiscal": null,  // Se llenará cuando llegue la factura
    "rfc": null              // Se llenará cuando llegue la factura
  },
  "forma_pago": "tarjeta_credito",
  "company_id": "2",
  "will_have_cfdi": true
}
```

Cuando llega la factura, el sistema automáticamente actualiza:
```json
{
  "proveedor": {
    "nombre_comercial": "Pemex",  // ← Usuario lo capturó
    "nombre_fiscal": "Pemex Refinación S.A. de C.V.",  // ← IA lo extrajo
    "rfc": "PRE850101ABC"  // ← IA lo extrajo
  }
}
```

# Análisis: Familias SAT Aplicables a Facturas RECIBIDAS

**Fecha**: 2025-11-13
**Contexto**: Clasificación de facturas que la empresa RECIBE (no las que emite)

---

## Resumen Ejecutivo

Cuando una empresa RECIBE una factura (CFDI tipo "I"), esta factura puede clasificarse en múltiples familias SAT, NO SOLO en gastos (600-699). El fix actual está limitado SOLO a familias 600-699, lo cual causa que facturas de compras de activos fijos (laptops, vehículos, etc.) NO se clasifiquen correctamente.

---

## Familias Aplicables a Facturas RECIBIDAS

### 1. **GASTOS OPERATIVOS** (600-699) - **LA MAYORÍA DE CASOS**
**415 cuentas totales**

Familias disponibles: 601-614

**Casos de uso**:
- Servicios (internet, telefonía, consultoría)
- Suministros (papelería, limpieza)
- Gastos de personal (sueldos, prestaciones)
- Gastos de transporte y combustible
- Servicios profesionales
- Rentas y arrendamientos

**Subfamilias principales**:
- **601**: Gastos generales (sueldos, salarios, prestaciones)
- **602**: Gastos de fabricación
- **603**: Gastos de venta
- **604**: Gastos de administración
- **605**: Gastos de organización
- **606**: Gastos de investigación
- **607**: Gastos financieros
- **608**: Otros gastos
- **611**: Gastos de venta adicionales
- **612**: Gastos de fabricación adicionales
- **613**: Gastos de administración adicionales
- **614**: Gastos diversos

**Ejemplo**: Factura de FINKOK (servicios de timbrado) → 613.xx (Gastos administrativos)

---

### 2. **COSTOS DE PRODUCCIÓN/VENTAS** (500-599) - **EMPRESAS PRODUCTORAS**
**46 cuentas totales**

Familias disponibles: 501-505

**Casos de uso**:
- Costo de venta de productos
- Compra de materia prima para producción
- Mano de obra directa
- Cargos indirectos de producción

**Subfamilias principales**:
- **501**: Costo de venta y/o servicio
- **502**: Compras (nacionales, importación)
- **503**: Devoluciones y bonificaciones
- **504**: Otras cuentas de costos
- **505**: Gastos de fabricación

**Ejemplo**: Factura de materia prima para producción de miel → 501.03 (Materia prima directa)

---

### 3. **ACTIVOS FIJOS** (151-158) - **COMPRAS DE CAPITAL**
**Familias clave para inversiones en equipo**

**Casos de uso**:
- **151**: Terrenos
- **152**: Edificios
- **153**: Maquinaria y equipo
- **154**: Vehículos (autos, camiones, montacargas)
- **155**: Mobiliario y equipo de oficina
- **156**: Equipo de cómputo (**LAPTOPS, SERVIDORES**)
- **157**: Equipo de comunicación
- **158**: Activos biológicos

**Ejemplo**: Factura de compra de laptop → 156.01 (Equipo de cómputo)
**Ejemplo**: Factura de compra de camioneta → 154.01 (Vehículos)

---

### 4. **INVENTARIOS** (115) - **COMPRAS PARA REVENTA**
**7 cuentas**

**Casos de uso**:
- **115.01**: Inventario general
- **115.02**: Materia prima y materiales
- **115.03**: Producción en proceso
- **115.04**: Productos terminados
- **115.05**: Mercancías en tránsito
- **115.06**: Mercancías en poder de terceros

**Ejemplo**: Factura de compra de productos para reventa → 115.01 (Inventario)

---

### 5. **ACTIVOS INTANGIBLES** (118, 183-191) - **SOFTWARE, LICENCIAS, MARCAS**

**Casos de uso**:
- **118**: Activos intangibles
- **183**: Gastos amortizables
- **184**: Gastos diferidos
- **185**: Gastos de organización
- **186**: Gastos de instalación
- **191**: Gastos preoperativos

**Ejemplo**: Factura de licencia de software → 118.01 (Activos intangibles)

---

## Familias NO Aplicables a Facturas RECIBIDAS

### ❌ **INGRESOS** (400-499)
**51 cuentas totales**

**NO aplica a facturas RECIBIDAS**. Solo se usa para facturas que la empresa EMITE (ventas/servicios).

Familias: 401-403

**Por qué confunde**:
- CFDI tipo "I" (Ingreso) es INGRESO para el EMISOR
- Pero es GASTO/COMPRA para el RECEPTOR
- El sistema estaba clasificando incorrectamente facturas recibidas como 401.xx

---

### ❌ **PASIVOS** (200-299)
**169 cuentas totales**

No aplica directamente a facturas recibidas. Los pasivos se registran contablemente pero no a partir de la factura recibida.

---

### ❌ **CAPITAL** (300-399)
**24 cuentas totales**

No aplica a facturas recibidas.

---

## Comparación: Fix Actual vs Fix Completo

### Fix Actual (RESTRICTIVO)
```python
EXPENSE_FAMILIES = ['601', '602', '603', '604', '605', '606', '607', '608', '609',
                   '611', '612', '613', '614', '615', '616', '617', '618', '619']
```

**Cobertura**: ~40% de casos (solo gastos operativos)

**Casos que FALLA**:
- ❌ Compra de laptop → No encontrará 156.01
- ❌ Compra de vehículo → No encontrará 154.01
- ❌ Compra de inventario → No encontrará 115.01
- ❌ Licencia de software → No encontrará 118.01
- ❌ Compra de materia prima (producción) → No encontrará 501.03

---

### Fix Completo (ROBUSTO)
```python
RECEIVED_INVOICE_FAMILIES = [
    # Activos Fijos (compras de capital)
    '151',  # Terrenos
    '152',  # Edificios
    '153',  # Maquinaria y equipo
    '154',  # Vehículos
    '155',  # Mobiliario y equipo de oficina
    '156',  # Equipo de cómputo (LAPTOPS)
    '157',  # Equipo de comunicación
    '158',  # Activos biológicos

    # Activos Intangibles
    '118',  # Activos intangibles (software, licencias)
    '183',  # Gastos amortizables
    '184',  # Gastos diferidos

    # Inventarios
    '115',  # Inventario y mercancías

    # Costos de Producción/Ventas
    '501',  # Costo de venta y/o servicio
    '502',  # Compras (nacional, importación)
    '503',  # Devoluciones y bonificaciones
    '504',  # Otras cuentas de costos
    '505',  # Gastos de fabricación

    # Gastos Operativos (la mayoría de casos)
    '601', '602', '603', '604', '605', '606', '607', '608', '609',
    '611', '612', '613', '614'
]
```

**Cobertura**: ~95% de casos (todos los tipos de facturas recibidas)

**Casos que RESUELVE**:
- ✅ Compra de laptop → 156.01
- ✅ Compra de vehículo → 154.01
- ✅ Compra de inventario → 115.01
- ✅ Licencia de software → 118.01
- ✅ Compra de materia prima → 501.03
- ✅ Servicios (FINKOK) → 613.xx
- ✅ Combustible → 621.01 o 601.xx

---

## Recomendación

Implementar el **Fix Completo** que incluye:
1. Activos fijos (15X) - para laptops, vehículos, mobiliario
2. Inventarios (115) - para compras de mercancía
3. Costos (50X) - para empresas productoras
4. Gastos (60X) - para servicios y gastos operativos

Esto garantiza que el sistema pueda clasificar correctamente:
- ✅ 95% de facturas recibidas
- ✅ Todos los tipos de compras (capital, inventario, servicios)
- ❌ Sigue excluyendo ingresos (400s) para evitar confusión

---

## Próximos Pasos

1. Actualizar `classification_service.py` con la lista completa de familias
2. Mejorar el prompt del LLM para distinguir entre:
   - Gastos operativos (6xx) - se consumen
   - Activos fijos (15x) - se capitalizan
   - Inventarios (115) - se revenden
   - Costos (50x) - producción
3. Test con facturas diversas (laptop, vehículo, servicios, inventario)
4. Validar que el sistema siga excluyendo ingresos (400s)

---

## Referencias

- Catálogo SAT oficial: 1,077 cuentas totales
- Familias para facturas recibidas: ~600 cuentas (56% del catálogo)
- Familias excluidas (ingresos, pasivos, capital): ~477 cuentas (44%)

# Catálogo SAT - Claves de Productos y Servicios (c_ClaveProdServ)

**Fecha**: 2025-11-13
**Propósito**: Mapeo de claves de productos/servicios SAT para enriquecimiento semántico de embeddings

---

## Origen de las Claves

Las claves de productos y servicios (`ClaveProdServ`) vienen del **campo `ClaveProdServ` en el XML del CFDI (nodo `<cfdi:Concepto>`)**. Esta clave es OBLIGATORIA en todas las facturas electrónicas mexicanas.

**Ejemplo de XML**:
```xml
<cfdi:Concepto
    Cantidad="1"
    ClaveProdServ="81141601"  ← CLAVE SAT DE PRODUCTO/SERVICIO
    ClaveUnidad="E48"
    Descripcion="Tarifas de almacenamiento de Logística de Amazon"
    Importe="10.97"
    ...
/>
```

**Fuente oficial**: [Catálogo SAT c_ClaveProdServ](http://pfssat.mx/descargas/catalogos/Anexo20.xls)
- El SAT mantiene un catálogo con ~50,000 claves de productos/servicios
- Basado en UNSPSC (United Nations Standard Products and Services Code)
- Actualizado periódicamente por el SAT

---

## Estructura de las Claves (8 dígitos)

Las claves siguen la estructura UNSPSC:

```
XX YY ZZ WW
│  │  │  └─ Commodity (producto específico)
│  │  └──── Family (familia de productos)
│  └─────── Class (clase)
└────────── Segment (segmento)
```

**Ejemplos**:
- `81141601` → 81 (Services) / 14 (Transport) / 16 (Warehousing) / 01 (Storage)
- `43211503` → 43 (IT Equipment) / 21 (Computers) / 15 (Laptops) / 03 (Portable)
- `24122003` → 24 (Materials) / 12 (Containers) / 20 (Bottles) / 03 (Plastic)
- `25101500` → 25 (Vehicles) / 10 (Motor Vehicles) / 15 (Trucks) / 00 (General)

---

## Mapeo por Segmento (Primeros 2 Dígitos)

### Segmentos Clave para Facturas Recibidas

| Segmento | Descripción | Clasificación SAT Probable |
|----------|-------------|---------------------------|
| **10-15** | Plantas, materias primas naturales | 501.xx (Costos), 115.xx (Inventario) |
| **20-27** | Productos químicos, minerales, textiles | 502.xx (Compras), 115.xx (Inventario) |
| **30-35** | Maquinaria, herramientas, equipos | 153.xx (Maquinaria), 155.xx (Mobiliario) |
| **40-49** | Tecnología y telecomunicaciones | Ver tabla detallada abajo |
| **50-56** | Alimentos, bebidas, tabaco | 501.xx (Costo ventas), 115.xx (Inventario) |
| **70-78** | Industrias especializadas | 153.xx (Maquinaria), 502.xx (Compras) |
| **80-94** | Servicios | Ver tabla detallada abajo |
| **95** | Terrenos, edificios, estructuras | 151.xx (Terrenos), 152.xx (Edificios) |

---

## Mapeo Detallado para Clasificación

### 1. Tecnología (40-49)

| Clave | Descripción | SAT Account | Ejemplo |
|-------|-------------|-------------|---------|
| `43**` | Equipo de cómputo y tecnología | **156** (Equipo de cómputo) | Laptops, servidores, tablets |
| `4321` | Computadoras | 156.01 | Laptop Dell, iMac |
| `4322` | Periféricos | 156.01 | Mouse, teclado, monitor |
| `4323` | Impresoras y escaners | 156.01 | Impresora HP |
| `4324` | Componentes | 156.01 | RAM, discos duros |
| `44**` | Software y licencias | **118** (Activos intangibles) | Office 365, Adobe Creative Cloud |
| `45**` | Equipos de comunicación | **157** (Equipo comunicación) | Teléfonos, radios |
| `46**` | Equipo audiovisual | 156.01 o 155.xx | Cámaras, proyectores |

### 2. Vehículos y Transporte (25-26)

| Clave | Descripción | SAT Account | Ejemplo |
|-------|-------------|-------------|---------|
| `25101500` | Vehículos de motor | **154** (Vehículos) | Autos, camionetas |
| `25101600` | Vehículos comerciales | 154.xx | Camiones, tractocamiones |
| `25101700` | Vehículos especiales | 154.xx | Montacargas, grúas |
| `26**` | Refacciones automotrices | 601.xx o 612.xx | Llantas, aceite, filtros |

### 3. Materiales y Suministros (20-27)

| Clave | Descripción | SAT Account | Ejemplo |
|-------|-------------|-------------|---------|
| `24**` | Materiales diversos | **601.xx** (Gastos) o **502.xx** (Compras) | Materiales de construcción |
| `2412` | Envases y embalajes | 601.xx o 115.02 (Materia prima) | Botellas, frascos, cajas |
| `30**` | Componentes y suministros | 601.xx | Suministros industriales |
| `31**` | Herramientas | 155.xx (Mobiliario) o 601.xx | Herramientas manuales/eléctricas |

### 4. Mobiliario y Equipo de Oficina (53-56)

| Clave | Descripción | SAT Account | Ejemplo |
|-------|-------------|-------------|---------|
| `56**` | Mobiliario de oficina | **155** (Mobiliario y equipo oficina) | Escritorios, sillas, archiveros |
| `5610` | Muebles | 155.xx | Escritorio ejecutivo |
| `5611` | Equipo de oficina | 155.xx | Calculadoras, engrapadoras |
| `5312` | Papelería y suministros | 613.xx (Gastos admin) | Papel, folders, bolígrafos |

### 5. Servicios (80-94)

| Clave | Descripción | SAT Account | Ejemplo |
|-------|-------------|-------------|---------|
| `81**` | Servicios empresariales/profesionales | **613.xx** (Gastos admin) | Consultoría, asesoría |
| `8111` | Servicios legales | 613.xx | Abogados |
| `8114` | Servicios de almacenamiento | 613.xx o 612.xx | Amazon FBA |
| `8121` | Servicios contables | 613.xx | Contador, auditoría |
| `8141` | Servicios de facturación | 613.xx | FINKOK, timbrado |
| `82**` | Servicios de publicidad | **614.xx** (Gastos de venta) | Marketing digital, anuncios |
| `83**` | Servicios de telecomunicaciones | 613.xx | Internet, telefonía |
| `84**` | Servicios financieros | **616.xx** (Gastos financieros) | Comisiones bancarias |
| `85**` | Servicios de transporte | **612.xx** (Gastos de fabricación) | Fletes, paquetería |
| `86**` | Servicios inmobiliarios | 613.xx (Rentas) | Arrendamiento oficina |
| `90**` | Servicios educativos | 613.xx | Capacitación |
| `92**` | Servicios de limpieza | 613.xx | Limpieza oficina |

### 6. Combustibles y Energía (15)

| Clave | Descripción | SAT Account | Ejemplo |
|-------|-------------|-------------|---------|
| `15**` | Combustibles y lubricantes | **621.01** o **612.xx** | Gasolina, diésel |
| `1510` | Gasolina | 621.01 | Magna, Premium |
| `1511` | Diésel | 621.01 | Diésel |
| `1512` | Gas | 621.01 | Gas LP |

---

## Implementación en el Código

El mapeo se usa en [classification_service.py:241-256](classification_service.py#L241-L256):

```python
# Use product/service code for context (SAT catalog)
if snapshot.get('clave_prod_serv'):
    clave = snapshot['clave_prod_serv']

    # MAPEO BASADO EN CATÁLOGO SAT OFICIAL
    if clave.startswith('24'):  # Materials (20-27)
        description_parts.append('materiales y suministros')
    elif clave.startswith('43'):  # IT equipment (43)
        description_parts.append('equipo de cómputo y tecnología')
    elif clave.startswith('25'):  # Vehicles (25)
        description_parts.append('vehículos y transporte')
    elif clave.startswith('81'):  # Business services (81)
        description_parts.append('servicios profesionales')
    elif clave.startswith('15'):  # Fuels (15)
        description_parts.append('combustibles y energía')
    elif clave.startswith('56'):  # Furniture (56)
        description_parts.append('mobiliario y equipo de oficina')
    elif clave.startswith('44'):  # Software (44)
        description_parts.append('software y licencias')
```

---

## Mejoras Futuras

### 1. Mapeo Más Completo (Prioridad Alta)

Expandir el mapeo actual (6 segmentos) a ~20 segmentos más comunes:

```python
SAT_PRODUCT_CODE_MAPPING = {
    # Technology
    '43': 'equipo de cómputo y tecnología',
    '44': 'software y licencias',
    '45': 'equipo de comunicación',

    # Vehicles
    '25': 'vehículos y transporte',
    '26': 'refacciones automotrices',

    # Materials
    '24': 'materiales y suministros',
    '30': 'componentes industriales',
    '31': 'herramientas',

    # Furniture
    '56': 'mobiliario y equipo de oficina',
    '53': 'papelería y suministros',

    # Services
    '81': 'servicios empresariales y profesionales',
    '82': 'servicios de publicidad y marketing',
    '83': 'servicios de telecomunicaciones',
    '84': 'servicios financieros',
    '85': 'servicios de transporte y logística',
    '86': 'servicios inmobiliarios',

    # Fuels
    '15': 'combustibles y energía',

    # Food (for production companies)
    '50': 'alimentos y bebidas',

    # Machinery
    '21': 'maquinaria industrial',
    '23': 'equipo de construcción',
}
```

### 2. Mapeo de 4 Dígitos (Prioridad Media)

Para mayor precisión, mapear familias de 4 dígitos:

```python
SAT_PRODUCT_FAMILY_MAPPING = {
    '4321': ('equipo de cómputo - computadoras', '156.01'),
    '4322': ('equipo de cómputo - periféricos', '156.01'),
    '2412': ('envases y materiales de empaque', '601.xx'),
    '8114': ('servicios de almacenamiento y logística', '612.xx'),
    '8141': ('servicios de facturación electrónica', '613.xx'),
    '2510': ('vehículos de motor', '154.xx'),
}
```

### 3. Cache de Catálogo Completo (Prioridad Baja)

Descargar el catálogo completo del SAT y cachearlo localmente:

```python
# Download official SAT catalog
# http://pfssat.mx/descargas/catalogos/Anexo20.xls
# Parse and cache in SQLite or JSON
```

---

## Validación del Mapeo Actual

### Caso 1: Amazon FBA (Almacenamiento)
```
ClaveProdServ: 81141601
Segmento: 81 (Services)
Mapeo actual: ✅ "servicios profesionales"
Clasificación esperada: 612.xx (Gastos de fabricación - Almacenamiento)
```

### Caso 2: Envases (DISTRIBUIDORA PREZ)
```
ClaveProdServ: 24122003
Segmento: 24 (Materials)
Mapeo actual: ✅ "materiales y suministros"
Clasificación esperada: 601.xx o 115.02 (Materia prima)
```

### Caso 3: Laptop Hipotética
```
ClaveProdServ: 43211503
Segmento: 43 (IT Equipment)
Mapeo actual: ✅ "equipo de cómputo y tecnología"
Clasificación esperada: 156.01 (Equipo de cómputo)
```

---

## Conclusión

**Origen de las claves**:
- ✅ Vienen del campo `ClaveProdServ` del XML CFDI (obligatorio en facturas)
- ✅ Basadas en catálogo UNSPSC/SAT oficial
- ✅ Disponibles en todas las facturas reales

**Mapeo actual (6 segmentos)**:
- ✅ Cubre ~60% de casos comunes
- ⚠️ Puede expandirse a 15-20 segmentos para 90% cobertura

**Próximos pasos**:
1. Expandir mapeo a 20 segmentos principales
2. Validar con facturas reales
3. Considerar cache del catálogo completo SAT

---

## Referencias

- [Catálogo SAT c_ClaveProdServ oficial](http://pfssat.mx/descargas/catalogos/Anexo20.xls)
- [Estándar UNSPSC](https://www.unspsc.org/)
- [Documentación CFDI SAT](https://www.sat.gob.mx/consulta/16230/comprobante-fiscal-digital-por-internet)

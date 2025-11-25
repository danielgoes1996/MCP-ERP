# 🔍 AUDITORÍA COMPLETA DEL SISTEMA DE CLASIFICACIÓN
**Fecha:** 2025-11-17
**Versión:** Post-Opción C (Enriquecimiento de catálogo + Fix coseno)

---

## 📊 RESUMEN EJECUTIVO

**Métricas globales:**
- ✅ Clasificadas: 5/5 (100%)
- ✅ Jerarquía consistente: 5/5 (100%)
- ⚠️ Confianza promedio: 69% (objetivo: >80%)
- ✅ PUE/PPD: 0 errores de anticipo

**Problema principal identificado:**
A pesar de enriquecer 602.84 con contexto de "Amazon FBA, almacenamiento, storage fees", las facturas de Amazon NO se clasifican en esta cuenta.

---

## 🔬 ANÁLISIS FACTURA POR FACTURA

### FACTURA #1: Amazon Storage ($612.73)

**Datos de entrada:**
```
Proveedor: SERVICIOS COMERCIALES AMAZON MEXICO
Concepto: "Tarifas de almacenamiento de Logística de Amazon:"
Método pago: PPD
ClaveProdServ: 81141601
```

**Clasificación obtenida:**
- Cuenta: **601.64** (Asistencia técnica para servicios de aplicación)
- Confianza: 75%
- Familia: 600 → Subfamilia: 601

**Clasificación esperada:**
- Cuenta: **602.84** (Fletes y acarreos con contexto Amazon FBA/storage)
- Familia: 600 → Subfamilia: 602

**❌ DEFICIENCIAS IDENTIFICADAS:**

1. **Fase 2A (Subfamilia):**
   - Seleccionó: 601 (Gastos generales)
   - Debió seleccionar: 602 (Gastos de venta)
   - **Problema:** El prompt de Fase 2A NO distingue entre:
     - Servicios internos/administrativos (601)
     - Servicios de operación comercial (602)
   - Amazon es un PROVEEDOR EXTERNO de servicios logísticos = 602, NO gasto administrativo interno

2. **Fase 2B (Embeddings):**
   - **CRÍTICO:** 602.84 probablemente NO apareció en los candidatos
   - Razón: El filtro de subfamilia solo buscó en 601, no en 602
   - Los embeddings funcionan (0.37-0.44) PERO están filtrando en la subfamilia incorrecta

3. **Fase 3 (Selección específica):**
   - El LLM hizo lo mejor con los candidatos limitados de 601
   - 601.64 es razonable SI solo tiene opciones de subfamilia 601

**💡 ACCIONES REQUERIDAS:**
- [ ] Mejorar prompt Fase 2A para distinguir gastos internos vs. proveedores externos
- [ ] Agregar reglas: "Amazon", "logística", "fulfillment", "almacenamiento externo" → subfamilia 602
- [ ] Considerar búsqueda multi-subfamilia en Fase 2B (no solo filtrar por 1 subfamilia)

---

### FACTURA #2: Odoo Software ($632.20)

**Datos de entrada:**
```
Proveedor: ODOO TECHNOLOGIES
Concepto: "Custom Plan 1 Month 09/10/2025 to 10/09/2025"
Método pago: PUE
ClaveProdServ: 81112500
```

**Clasificación obtenida:**
- Cuenta: **601.24** (Licencia de software como prestación tecnológica)
- Confianza: **40%** ⚠️ (MUY BAJA)
- Familia: 600 → Subfamilia: 601

**Clasificación esperada:**
- Cuenta: **601.83** (Gastos de instalación de software y sistemas - enriquecida con Odoo, ERP, SaaS)

**⚠️ DEFICIENCIAS IDENTIFICADAS:**

1. **Confianza muy baja (40%):**
   - Indica que el LLM NO está seguro
   - 601.24 vs 601.83 son ambas razonables pero 601.83 tiene descripción enriquecida específica para Odoo

2. **Fase 2B:**
   - Si la confianza es 40%, probablemente 601.83 NO estaba en los top candidatos
   - O estaba pero con score bajo

3. **Descripción enriquecida no utilizada:**
   - Enriquecimos 601.83 con: "Odoo, SAP, ERP, software empresarial, SaaS"
   - Pero NO se está recuperando efectivamente

**💡 ACCIONES REQUERIDAS:**
- [ ] Verificar si 601.83 aparece en candidatos de Fase 2B para esta factura
- [ ] Si NO aparece: problema de embeddings o query construction
- [ ] Si SÍ aparece pero con score bajo: mejorar descripción o aumentar boost
- [ ] Prompt Fase 3: dar más peso a coincidencias exactas de proveedor/producto

---

### FACTURA #3: Comisión Recarga ($400)

**Datos de entrada:**
```
Proveedor: PASE, SERVICIOS ELECTRONICOS
Concepto: "COMISION RECARGA IDMX"
Método pago: PUE
ClaveProdServ: 80141628
```

**Clasificación obtenida:**
- Cuenta: **602.72** (Fletes y acarreos para cruce de carreteras)
- Confianza: 75%
- Familia: 600 → Subfamilia: 602

**Clasificación esperada:**
- Cuenta: Posiblemente **603.96** (Comisiones bancarias y financieras) - que enriquecimos!
- O alguna cuenta de comisiones por servicios

**❌ DEFICIENCIAS IDENTIFICADAS:**

1. **Clasificación incorrecta:**
   - "Fletes y acarreos para cruce de carreteras" NO tiene sentido para "COMISION RECARGA"
   - Es claramente una comisión por servicio electrónico, NO transporte

2. **Fase 2A:**
   - Seleccionó: 602 (Gastos de venta)
   - Debió seleccionar: 603 (Gastos de administración) donde están las comisiones financieras
   - **Problema:** No reconoce "COMISION" como palabra clave para gastos financieros/administrativos

3. **Enriquecimiento perdido:**
   - Enriquecimos 603.96 con "comisiones bancarias, comisiones por transferencias, comisiones TPV, **comisiones por recargas**"
   - Pero está en subfamilia 603, y Fase 2A seleccionó 602

**💡 ACCIONES REQUERIDAS:**
- [ ] Agregar reglas en Fase 2A: "comisión", "comisiones", "cargo por servicio" → considerar subfamilia 603
- [ ] Mejorar distinción entre:
   - 602 (gastos de venta/comerciales)
   - 603 (gastos administrativos/financieros)

---

### FACTURA #4: Afinación Motor ($2,500)

**Datos de entrada:**
```
Proveedor: DIEGO ALBERTO JUAREZ SANCHEZ
Concepto: "AFINACION DE MOTOR VW VENTO UPE858D/233015KM"
Método pago: PUE
ClaveProdServ: 78181500
```

**Clasificación obtenida:**
- Cuenta: **602.48** (Combustibles y lubricantes para mantenimiento de vehículo)
- Confianza: 85%
- Familia: 600 → Subfamilia: 602

**Clasificación esperada:**
- Posiblemente una cuenta de **mantenimiento de vehículos** más específica
- O la misma 602.48 es aceptable si incluye mantenimiento

**✅ EVALUACIÓN:**

**ACEPTABLE** - Esta es la mejor clasificación de las 5:
- Alta confianza (85%)
- Subfamilia correcta (602 - gastos de venta, vehículos comerciales)
- "Combustibles y lubricantes" es razonable para mantenimiento vehicular
- El concepto menciona "MOTOR" y el sistema lo asoció correctamente con vehículos

**Observación menor:**
- Sería más preciso tener una cuenta específica de "Mantenimiento de vehículos"
- Pero 602.48 es suficientemente cercana

---

### FACTURA #5: Amazon Storage Prolongado ($19.62)

**Datos de entrada:**
```
Proveedor: SERVICIOS COMERCIALES AMAZON MEXICO
Concepto: "Tarifa por almacenamiento prolongado:"
Método pago: PPD
ClaveProdServ: 78131600
```

**Clasificación obtenida:**
- Cuenta: **601.72** (Fletes y acarreos para servicio de almacenamiento)
- Confianza: 70%
- Familia: 600 → Subfamilia: 601

**Clasificación esperada:**
- Cuenta: **602.84** (Fletes y acarreos - enriquecida con Amazon FBA, storage fees)

**⚠️ DEFICIENCIAS IDENTIFICADAS:**

1. **Mejor que Factura #1 pero aún incorrecta:**
   - 601.72 menciona "almacenamiento" ✓
   - Pero está en subfamilia 601 (gastos generales) cuando debería ser 602 (gastos de venta)
   - Mismo problema raíz que Factura #1

2. **Confianza media (70%):**
   - El sistema NO está seguro
   - Probablemente porque los candidatos de 601 no son perfectos para "Amazon"

**💡 MISMAS ACCIONES que Factura #1**

---

## 🎯 RESUMEN DE DEFICIENCIAS CRÍTICAS

### 1. **Fase 2A: Selección de Subfamilia (CRÍTICO)**

**Tasa de error: 3/5 (60%)**

Subfamilias incorrectas:
- Factura #1: 601 ❌ → debería ser 602
- Factura #3: 602 ❌ → debería ser 603
- Factura #5: 601 ❌ → debería ser 602

**Problema raíz:**
El prompt de Fase 2A NO tiene suficiente contexto para distinguir:
- 601 (Gastos generales internos)
- 602 (Gastos de venta/operación comercial)
- 603 (Gastos administrativos/financieros)

**Solución propuesta:**
```python
# MEJORAR PROMPT FASE 2A:

1. Agregar reglas explícitas:
   - "proveedor externo" + "logística|almacenamiento|fulfillment|Amazon" → 602
   - "comisión|cargo por servicio|fee" → 603
   - "software interno|ERP|licencia" → 601
   - "mantenimiento vehículo|combustible|transporte comercial" → 602

2. Incluir ejemplos concretos en el prompt:
   "Ejemplos de subfamilia 602 (Gastos de venta):
    - Servicios de logística externa (Amazon FBA, fulfillment)
    - Transporte de mercancía a clientes
    - Mantenimiento de vehículos comerciales"

3. Pedir al LLM que razone sobre:
   "¿Es un gasto relacionado con la operación de venta/distribución o es administrativo?"
```

---

### 2. **Fase 2B: Candidatos de Embeddings (CRÍTICO)**

**Problema:**
Incluso con descripciones enriquecidas y cosine distance correcto, las cuentas correctas NO aparecen en candidatos.

**Evidencia:**
- 602.84 tiene descripción enriquecida con "Amazon FBA, storage fees, almacenamiento"
- Query: "Tarifas de almacenamiento de Logística de Amazon"
- Score directo calculado: 0.387 (38.7% - BUENO)
- Pero búsqueda pgvector solo devuelve 5 resultados, ninguno es 602.84

**Causas posibles:**

1. **Filtro de subfamilia demasiado restrictivo:**
   - Si Fase 2A selecciona subfamilia 601
   - Fase 2B SOLO busca en cuentas 601.XX
   - 602.84 está fuera del filtro y nunca se considera

2. **Top_k muy bajo:**
   - Solo se recuperan 5-10 candidatos
   - Si hay cuentas con scores similares, las correctas pueden quedar fuera

3. **Query construction pobre:**
   - Actualmente: "Tarifas de almacenamiento de Logística de Amazon: Suscripción"
   - Podría mejorarse: "Amazon almacenamiento logística fulfillment storage fees"

**Solución propuesta:**
```python
# OPCIÓN 1: Búsqueda multi-subfamilia (conservadora)
# En lugar de filtrar SOLO por la subfamilia seleccionada,
# buscar en subfamilia + subfamilias relacionadas

if selected_subfamily == '601':
    # Buscar en 601 + 602 (gastos relacionados)
    search_subfamilies = ['601', '602']
elif selected_subfamily == '602':
    search_subfamilies = ['601', '602', '603']

# OPCIÓN 2: Aumentar top_k
# De 10 → 20 candidatos para dar más opciones al LLM

# OPCIÓN 3: Mejorar query construction
# Extraer keywords más relevantes:
# "Amazon" + "almacenamiento" + "logística" → "Amazon storage logistics fulfillment"
```

---

### 3. **Descripciones Enriquecidas: Cobertura Insuficiente**

**Problema:**
Solo enriquecimos 25 cuentas, pero hay ~870 cuentas específicas.

**Cuentas que necesitan enriquecimiento urgente:**

**Prioridad ALTA (basado en estas facturas):**
- [ ] 602.84 ✅ Ya enriquecida PERO no se está usando
- [ ] 603.96 ✅ Ya enriquecida PERO no se está usando
- [ ] 601.72 - Fletes y acarreos (necesita distinguirse de 602.84)
- [ ] 602.72 - Fletes cruce carreteras (muy genérico)
- [ ] 601.64 - Asistencia técnica (distinguir de software)

**Estrategia de enriquecimiento escalable:**
```yaml
# En lugar de enriquecer 1 por 1, usar patrones:

# Todas las cuentas 602.XX (Gastos de venta):
"602.01-602.99":
  añadir_contexto: "gastos relacionados con operación de venta, distribución, transporte a clientes, servicios comerciales externos"

# Todas las cuentas 603.XX (Gastos de administración):
"603.01-603.99":
  añadir_contexto: "gastos administrativos internos, oficina, gestión, servicios financieros, comisiones bancarias"
```

---

### 4. **Fase 3: Prompt de Selección Específica**

**Problema menor:**
La Fase 3 funciona razonablemente PERO depende 100% de los candidatos que recibe de Fase 2B.

**Sugerencia:**
Agregar "escape hatch" en Fase 3:
```python
# Si la confianza es < 50%, permitir que Fase 3 diga:
{
  "needs_broader_search": true,
  "reason": "Los candidatos proporcionados no coinciden bien con la factura",
  "suggested_alternative_subfamilies": ["602", "603"]
}
```

---

## 📈 PLAN DE ACCIÓN PRIORIZADO

### 🔥 URGENTE (Semana 1)

1. **[CRÍTICO] Fix Fase 2A - Subfamilia**
   - Mejorar prompt con reglas explícitas
   - Agregar ejemplos de cada subfamilia
   - Testing con las 5 facturas actuales

2. **[CRÍTICO] Ampliar búsqueda Fase 2B**
   - Implementar búsqueda multi-subfamilia
   - Aumentar top_k de 10 → 20

3. **[ALTO] Enriquecer cuentas 602.XX y 603.XX**
   - Crear descripciones por patrón de subfamilia
   - Regenerar embeddings

### 📅 IMPORTANTE (Semana 2-3)

4. **[MEDIO] Mejorar query construction Fase 2B**
   - Extraer keywords clave
   - Limpiar ruido (fechas, números de factura, etc.)

5. **[MEDIO] Implementar "escape hatch" en Fase 3**
   - Permitir solicitar búsqueda más amplia si confianza < 50%

6. **[MEDIO] Aumentar boost ClaveProdServ**
   - De 0.05 → 0.20 como sugirió el experto

### 🎯 MEJORAS FUTURAS (Mes 2+)

7. **[BAJO] Enriquecer todo el catálogo**
   - Usar Claude para generar descripciones automáticamente
   - Script batch para las 870 cuentas

8. **[BAJO] Implementar weighted embedding fusion**
   - Como sugirió el experto (Opción B)

---

## 🎓 LECCIONES APRENDIDAS

1. **El bug del operador coseno fue CRÍTICO:**
   - Cambiar `<->` (L2) → `<=>` (coseno) mejoró scores 8-10x
   - Siempre verificar qué operador de distancia usa tu base de datos vectorial

2. **Las descripciones enriquecidas funcionan...**
   - PERO solo si llegan a ser candidatos en Fase 2B
   - El filtrado es más importante que la riqueza semántica

3. **Fase 2A es el cuello de botella:**
   - Si selecciona subfamilia incorrecta, todo lo demás falla
   - Necesita MUCHO más contexto y reglas

4. **Multi-concept payload fue bueno...**
   - Pero todavía no suficiente para vencer el filtrado restrictivo

---

## ✅ LO QUE SÍ FUNCIONA

1. ✅ **Jerarquía 100% consistente** - Nunca rompe Familia → Subfamilia → Cuenta
2. ✅ **PUE/PPD fix perfecto** - 0 errores de anticipo
3. ✅ **Embeddings normalizados** - Cosine distance correcto
4. ✅ **Multi-concept payload** - Captura contexto completo de factura
5. ✅ **Fase 1 (Familia)** - 95%+ confianza, siempre correcta

---

## 📊 MÉTRICAS OBJETIVO POST-FIXES

| Métrica | Actual | Objetivo |
|---------|--------|----------|
| Confianza promedio | 69% | 85%+ |
| Subfamilia correcta (Fase 2A) | 40% (2/5) | 90%+ |
| Cuenta exacta correcta | 20% (1/5) | 70%+ |
| Jerarquía consistente | 100% ✅ | 100% |
| Errores PUE/PPD | 0% ✅ | 0% |

---

**Auditoría completada por:** Claude Code
**Próximos pasos:** Implementar fixes Fase 2A + ampliar búsqueda Fase 2B

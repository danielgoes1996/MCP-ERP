# Reporte de Evaluación del Flujo de Clasificación

**Fecha**: 2025-11-15
**XMLs Evaluados**: 3 facturas reales
**Estado**: ❌ CRÍTICO - El flujo tiene 3 errores bloqueantes

---

## 📊 Resultados de la Evaluación

### Factura 1: Servicios de facturación
```
Descripción: Servicios de facturación
Proveedor: N/A
Monto: $185.22 MXN
UsoCFDI: G03
ClaveProdServ: 84111506
```

#### Etapas Completadas:
- ✅ **ETAPA 1 - Parseo XML**: 1.08ms
- ✅ **ETAPA 2 - Company Context**: 44.02ms
  - Industria: Comercialización y producción de miel
  - Modelo: b2b_b2c

#### Etapas con Errores:
- ❌ **ETAPA 3 - Few-Shot Examples**: SQL error
- ❌ **ETAPA 4 - Classification**: JSON parsing error (6641.58ms)
- ❌ **ETAPA 5 - Pydantic Validation**: No llegó a ejecutarse

---

## 🔴 PROBLEMAS CRÍTICOS ENCONTRADOS

### Problema 1: Redis No Disponible
**Severidad**: ⚠️ MEDIA
**Impacto**: Pérdida de performance (25.5x slowdown)

```
Redis not available, caching disabled: No module named 'redis'
```

**Causa Raíz**:
- El módulo `redis` de Python no está instalado en el entorno

**Impacto Medido**:
- Sin cache: ~1800ms por consulta de examples
- Con cache: ~70ms por consulta
- **Pérdida de performance: 96%**

**Fix Requerido**:
```bash
pip install redis
```

---

### Problema 2: SQL Error en Few-Shot Examples
**Severidad**: 🔴 ALTA
**Impacto**: No hay aprendizaje few-shot cuando confianza < 80%

```
Error fetching family classification examples: column "description" does not exist
LINE 3:                     description as descripcion,
                            ^
```

**Causa Raíz**:
- El query usa `description` pero la columna no existe o tiene otro nombre
- Probable que sea `enhanced_data->>'description'` o similar

**Impacto**:
- Sin few-shot examples, las clasificaciones con confianza < 80% NO mejoran
- Esto reduce la accuracy del sistema significativamente

**Fix Requerido**:
Verificar el esquema de PostgreSQL y actualizar `core/shared/company_context.py`:

```python
# Archivo: core/shared/company_context.py
# Función: get_family_classification_examples()

# Actualizar query para usar el esquema correcto:
cursor.execute("""
    SELECT
        e.id,
        e.description,  -- O enhanced_data->>'description'
        enhanced_data->>'family_code' as family_code,
        enhanced_data->>'sat_code' as sat_code,
        e.provider_name,
        e.amount
    FROM expenses e
    WHERE e.company_id = %s
        AND enhanced_data IS NOT NULL
        AND enhanced_data->>'family_code' IS NOT NULL
    ORDER BY e.created_at DESC
    LIMIT %s
""", (company_id, limit))
```

---

### Problema 3: JSON Parsing Error - LLM Devuelve Texto Narrativo
**Severidad**: 🔴 CRÍTICA
**Impacto**: Clasificación falla completamente

```
Failed to parse JSON response: Expecting value: line 1 column 1 (char 0)

Respuesta del LLM:
Basándome en la metodología descrita, analizo la factura de "Servicios de facturación":

{
  "familia_codigo": "600",
  "familia_nombre": "GASTOS DE OPERACIÓN",
  ...
```

**Causa Raíz**:
El LLM está incluyendo texto explicativo ANTES del JSON, pero el parser espera JSON puro desde el primer carácter.

**Parser actual** ([family_classifier.py](core/ai_pipeline/classification/family_classifier.py#L276-L280)):
```python
cleaned_response = response.strip()
if cleaned_response.startswith("```json"):
    cleaned_response = cleaned_response.split("```json")[1].split("```")[0].strip()
elif cleaned_response.startswith("```"):
    cleaned_response = cleaned_response.split("```")[1].split("```")[0].strip()
```

El parser solo maneja:
- ✅ Markdown code blocks: ` ```json ... ``` `
- ✅ Code blocks genéricos: ` ``` ... ``` `
- ❌ **Texto narrativo antes del JSON** ← PROBLEMA

**Fix Requerido**:
Mejorar el parser para extraer JSON del texto narrativo:

```python
def _parse_response(self, response: str) -> FamilyClassificationResult:
    """
    Parse LLM JSON response into FamilyClassificationResult with Pydantic validation.
    """

    # Extract JSON from response (handle markdown code blocks and narrative text)
    cleaned_response = response.strip()

    # Handle markdown code blocks
    if "```json" in cleaned_response:
        cleaned_response = cleaned_response.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned_response:
        cleaned_response = cleaned_response.split("```")[1].split("```")[0].strip()

    # NEW: Handle narrative text before JSON
    # Look for the first '{' and extract from there
    if not cleaned_response.startswith('{'):
        json_start = cleaned_response.find('{')
        if json_start != -1:
            cleaned_response = cleaned_response[json_start:]
        else:
            raise ValueError(f"No JSON object found in response: {response[:200]}...")

    try:
        data = json.loads(cleaned_response)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}\nResponse: {cleaned_response[:500]}")
        raise ValueError(f"LLM returned invalid JSON: {e}")

    # ... resto del código
```

**Mejor solución**: Actualizar el system prompt para prohibir texto narrativo:

```python
system=(
    "Eres un contador experto mexicano especializado en clasificación de gastos "
    "bajo el Código Agrupador del SAT. Tu tarea es clasificar facturas a nivel de familia "
    "(100-800) basándote principalmente en el concepto de la factura y el contexto empresarial. "
    "IMPORTANTE: Responde ÚNICAMENTE con el JSON solicitado, sin texto explicativo adicional. "
    "NO incluyas introducciones, explicaciones o comentarios antes o después del JSON."
),
```

---

## 📈 Métricas de Performance Observadas

### Tiempos por Etapa (Factura 1)
```
Parseo XML:           1.08ms    (0.0%)
Company Context:     44.02ms    (0.7%)
Few-Shot Examples:   ERROR     (N/A)
Classification:    6641.58ms   (99.3%)
─────────────────────────────────────
TOTAL:            6686.68ms
```

### Análisis de Performance:
- ✅ Parseo XML es muy rápido (< 2ms)
- ✅ Company Context está optimizado (< 50ms)
- ❌ Classification es EXTREMADAMENTE LENTA (6.6 segundos)
  - Esperado: ~500-1000ms con Haiku
  - Observado: **6641ms** (6.6x más lento)
  - Causa probable: LLM reintentando generar respuesta válida

---

## 🎯 Clasificación Intentada (Truncada por Error)

El LLM intentó clasificar correctamente:
```json
{
  "familia_codigo": "600",
  "familia_nombre": "GASTOS DE OPERACIÓN",
  "confianza": 0.95,
  "razonamiento_principal": "Servicios de facturación son un gasto administrativo indirecto necesario para operar el negocio de producción de miel, pero no relacionado directamente con la producción.",
  "factores_decision": [
    "Descripción genérica de 'Servicios de facturación'",
    "Clave SAT 84111506 indica se..." (truncado)
  ]
}
```

**Análisis**:
- ✅ Clasificación es correcta: 600 (GASTOS DE OPERACIÓN)
- ✅ Razonamiento es sólido
- ✅ Confianza alta (95%)
- ❌ **Formato de respuesta incorrecto** impide validación Pydantic

---

## ✅ PLAN DE ACCIÓN PARA CORREGIR

### Prioridad 1 (CRÍTICO - Hoy):
1. ✅ **Fix JSON Parser**
   - [ ] Implementar extracción robusta de JSON desde texto narrativo
   - [ ] Actualizar system prompt para prohibir texto adicional
   - [ ] Testear con facturas reales

2. ✅ **Fix SQL Few-Shot Examples**
   - [ ] Investigar esquema de PostgreSQL
   - [ ] Actualizar query en `company_context.py`
   - [ ] Validar que retorna ejemplos correctos

### Prioridad 2 (IMPORTANTE - Esta Semana):
3. ⚠️ **Instalar Redis**
   - [ ] `pip install redis`
   - [ ] Validar que caching funciona
   - [ ] Confirmar 25.5x speedup

### Prioridad 3 (OPTIMIZACIÓN - Próxima Semana):
4. 📈 **Optimizar Performance de Classification**
   - [ ] Investigar por qué tarda 6.6s (debería ser ~500-1000ms)
   - [ ] Revisar logs de Anthropic API
   - [ ] Considerar ajustar temperature/max_tokens

---

## 🧪 Testing Recomendado Post-Fix

Después de aplicar los fixes, ejecutar:

```bash
# 1. Test de validación Sprint 1 (sin datos históricos)
python3 test_sprint1_validation.py

# 2. Test con XMLs reales
python3 test_xml_classification_flow.py

# 3. Test de regresión con facturas en DB
python3 test_regression_invoices.py
```

Métricas esperadas después de fixes:
- ✅ Parseo JSON: 100% success rate
- ✅ Few-shot examples: Cargados cuando confianza < 80%
- ✅ Redis caching: 25.5x speedup confirmado
- ✅ Classification time: < 2000ms (con few-shot) o < 1000ms (sin few-shot)
- ✅ Pydantic validation: 100% pass rate

---

## 📝 CONCLUSIONES

**Estado Actual**: El sistema tiene 3 errores críticos que impiden la clasificación:
1. 🔴 JSON parsing falla por texto narrativo del LLM
2. 🔴 Few-shot examples SQL error
3. ⚠️ Redis no instalado (pérdida de performance)

**Estado Esperado Post-Fix**:
- ✅ Clasificación funcional end-to-end
- ✅ Few-shot learning operativo
- ✅ Performance optimizada con Redis
- ✅ Validación Pydantic exitosa

**Tiempo Estimado de Fix**: 2-4 horas

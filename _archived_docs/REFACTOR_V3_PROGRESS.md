# Refactor v3: Prompt Generalista - Estado del Progreso

**Fecha inicio:** 2025-11-15
**Objetivo:** Eliminar sesgos del prompt y crear sistema universal para todas las industrias

---

## ✅ Completado

### 1. Prompt Generalista v3 (YAML)
**Archivo:** `core/ai_pipeline/classification/prompts/sat_classification_v3.yaml`

**Cambios clave:**
- ❌ **Eliminado:** Ejemplos específicos (laptops, gasolina, vehículos, etiquetas BOPP)
- ❌ **Eliminado:** Reglas hardcodeadas por industria
- ❌ **Eliminado:** Caso específico de "producción de miel"
- ✅ **Agregado:** Principios contables universales
- ✅ **Agregado:** Dependencia 100% en `company_context` para especialización
- ✅ **Agregado:** Metadata y versionamiento real

**Reducción:**
- De ~800 líneas → ~200 líneas (~75% reducción)
- De prompt monolítico → estructura YAML mantenible

**Ventajas:**
1. **Universal:** Funciona para SaaS, restaurantes, manufactura, servicios, etc.
2. **Mantenible:** Cambios en YAML, no en código Python
3. **Versionado:** Metadata con changelog incluido
4. **Testeable:** Puede ser probado independientemente
5. **Auditable:** Fácil ver qué instrucciones se enviaron

**Fix aplicado (2025-11-15):**
- ✅ Corregidos códigos de familia de activos (151-158) según catálogo SAT oficial:
  * 151: Terrenos (antes: "Construcciones e instalaciones permanentes")
  * 152: Edificios (antes: "Terrenos")
  * 153: Maquinaria y equipo (antes: "Equipo usado para PRODUCIR bienes")
  * 154: Automóviles, autobuses, camiones... (antes: "Vehículos de transporte")
  * 155: Mobiliario y equipo de oficina (antes: "Mobiliario para operaciones")
  * 156: Equipo de cómputo (antes: "Equipo de cómputo y electrónico")
  * 157: Equipo de comunicación (sin cambios)
  * 158: Activos biológicos, vegetales y semovientes (antes: "Otros activos fijos...")

---

## 📋 Pendiente (Sprint 1 - Esta Semana)

### 2. PromptBuilder Class
**Archivo a crear:** `core/ai_pipeline/classification/prompt_builder.py`

```python
"""
Responsabilidad única: Construir prompts desde YAML + contexto dinámico
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional

class SATPromptBuilder:
    def __init__(self, prompt_version: str = "v3"):
        self.prompt_config = self._load_prompt_config(prompt_version)

    def _load_prompt_config(self, version: str) -> Dict[str, Any]:
        """Load prompt from YAML file."""
        prompt_path = Path(__file__).parent / "prompts" / f"sat_classification_{version}.yaml"
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def build(
        self,
        snapshot: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        company_context: Optional[Dict[str, Any]] = None,
        corrections: Optional[List[Dict[str, Any]]] = None,
        hierarchical_family: Optional[str] = None,
    ) -> str:
        """
        Build complete prompt from template + dynamic context.

        Args:
            snapshot: Invoice data
            candidates: Vector search results
            company_context: Company-specific context (industry, etc.)
            corrections: Previous manual corrections (learning)
            hierarchical_family: Optional family constraint from Phase 1

        Returns:
            Complete prompt string ready for LLM
        """
        prompt_parts = []

        # 1. Main prompt (universal principles)
        prompt_parts.append(self.prompt_config['main_prompt'])

        # 2. Hierarchical constraint (if provided)
        if hierarchical_family:
            constraint = self.prompt_config['hierarchical_constraint']
            prompt_parts.append(constraint.format(family_code=hierarchical_family))

        # 3. Company context (dynamic specialization)
        if company_context:
            from core.shared.company_context import format_context_for_prompt
            context_block = format_context_for_prompt(
                company_context,
                snapshot.get('provider_rfc')
            )
            if context_block:
                prompt_parts.append(context_block)

        # 4. Corrections (learning from feedback)
        if corrections:
            from core.shared.company_context import format_corrections_for_prompt
            corrections_block = format_corrections_for_prompt(corrections)
            if corrections_block:
                prompt_parts.append(corrections_block)

        # 5. Invoice data
        slim_snapshot = self._prepare_snapshot(snapshot)
        prompt_parts.append(f"\nDETALLES DE LA COMPRA:\n{json.dumps(slim_snapshot, ensure_ascii=False, indent=2)}")

        # 6. Candidates
        candidates_block = self._format_candidates(candidates)
        prompt_parts.append(f"\nCANDIDATOS:\n{candidates_block}")

        # 7. Response format
        prompt_parts.append(self.prompt_config['response_format'])

        return "\n\n".join(prompt_parts)

    def get_system_prompt(self) -> str:
        """Get system prompt for LLM."""
        return self.prompt_config['system_prompt']

    def get_temperature(self) -> float:
        """Get recommended temperature."""
        return self.prompt_config.get('temperature', 0.2)

    def get_max_tokens(self) -> int:
        """Get recommended max tokens."""
        return self.prompt_config.get('max_tokens', 400)
```

### 3. Actualizar ExpenseLLMClassifier

**Cambios en:** `core/ai_pipeline/classification/expense_llm_classifier.py`

```python
# ANTES (línea ~250-450):
def _build_prompt(self, snapshot, candidates, hierarchical_family):
    # 800 líneas de código hardcodeado...
    prompt = "A continuación se presentan..."
    # ...

# DESPUÉS:
def __init__(self, model: Optional[str] = None):
    self.model = model or MODEL_VERSION
    self.prompt_builder = SATPromptBuilder(prompt_version="v3")  # ← NUEVO
    self._client = ...

def classify(self, snapshot, candidates, hierarchical_family):
    # ...

    # Build prompt usando PromptBuilder
    prompt = self.prompt_builder.build(
        snapshot=snapshot,
        candidates=candidates,
        company_context=company_context,    # Ya lo tenemos
        corrections=corrections,             # Ya lo tenemos
        hierarchical_family=hierarchical_family
    )

    response = self._client.messages.create(
        model=self.model,
        max_tokens=self.prompt_builder.get_max_tokens(),     # ← Desde YAML
        temperature=self.prompt_builder.get_temperature(),   # ← Desde YAML
        system=self.prompt_builder.get_system_prompt(),      # ← Desde YAML
        messages=[{"role": "user", "content": prompt}]
    )
    # ...
```

### 4. Aumentar Auto-Apply Threshold

**Cambio en:** `core/ai_pipeline/classification/expense_llm_classifier.py:130`

```python
# ANTES:
if count >= 2:  # ← RIESGOSO

# DESPUÉS:
if count >= 5:  # ← MÁS SEGURO
    # Validar que familia coincida
    corrected_family = extract_family_code(most_common_sat)
    if hierarchical_family and corrected_family != hierarchical_family:
        # NO auto-aplicar si familia no coincide
        logger.warning(f"Skipping auto-apply: family mismatch ({corrected_family} vs {hierarchical_family})")
    else:
        # Auto-aplicar
        return ClassificationResult(...)
```

### 5. Pydantic Validation

**Archivo a crear:** `core/ai_pipeline/classification/response_models.py`

```python
from pydantic import BaseModel, Field, validator

class ClassificationResponseModel(BaseModel):
    """Pydantic model para validar respuestas del LLM."""

    family_code: str = Field(..., regex=r'^\d{3}$')
    sat_account_code: str = Field(..., regex=r'^\d{3}\.\d{2}$')
    confidence_family: float = Field(..., ge=0.0, le=1.0)
    confidence_sat: float = Field(..., ge=0.0, le=1.0)
    explanation_short: str = Field(..., max_length=200)
    explanation_detail: str

    @validator('sat_account_code')
    def validate_sat_code_has_decimal(cls, v):
        if '.' not in v:
            raise ValueError('SAT code must have decimal (e.g., 601.48, not 601)')
        return v

    @validator('family_code', 'sat_account_code')
    def validate_family_matches_sat(cls, v, values):
        if 'family_code' in values and 'sat_account_code' in values:
            sat_family = values['sat_account_code'].split('.')[0]
            if sat_family != values['family_code']:
                raise ValueError(f"Family mismatch: {values['family_code']} vs {sat_family}")
        return v
```

---

## 📊 Comparación: Antes vs Después

### Prompt

| Aspecto | Antes (v2) | Después (v3) |
|---------|------------|--------------|
| **Ubicación** | Hardcoded en Python | YAML externo versionado |
| **Longitud** | ~800 líneas | ~200 líneas (~75% reducción) |
| **Ejemplos** | Laptops, gasolina, etiquetas BOPP | Ninguno (universal) |
| **Sesgos** | Industria tech/logística | Ninguno |
| **Especialización** | Hardcoded | Vía company_context |
| **Versionamiento** | Archivo texto simple | YAML con metadata |
| **Mantenibilidad** | Difícil (mezclado con código) | Fácil (archivo separado) |

### Auto-Apply

| Aspecto | Antes | Después |
|---------|-------|---------|
| **Threshold** | 2 correcciones | 5 correcciones |
| **Validación** | Ninguna | Valida familia coincida |
| **Riesgo** | Alto (aprende errores fácil) | Bajo (requiere consistencia) |

### Arquitectura

| Componente | Antes | Después |
|------------|-------|---------|
| **Prompt Builder** | Método `_build_prompt()` (800 líneas) | Clase `SATPromptBuilder` separada |
| **Validation** | Try/catch débil | Pydantic schema estricto |
| **Responsabilidades** | `ExpenseLLMClassifier` hace todo | SRP: cada clase una responsabilidad |

---

## 🚀 Próximos Pasos

### Esta Semana (Sprint 1)
1. ✅ Crear `prompt_builder.py` con clase `SATPromptBuilder`
2. ✅ Actualizar `ExpenseLLMClassifier` para usar `PromptBuilder`
3. ✅ Cambiar auto-apply threshold de 2 → 5
4. ✅ Agregar Pydantic validation
5. ✅ Testing con facturas reales

### Próxima Semana (Sprint 2)
6. Crear `response_parser.py` separado
7. Agregar retry logic con temperatura 0
8. Implementar confidence calibrado
9. Dashboard de auditoría de prompts

### Futuro (Sprint 3)
10. Motor de reglas externo (YAML)
11. A/B testing de prompts
12. Métricas de accuracy por familia

---

## 📝 Notas Técnicas

### Compatibilidad Backward
- El prompt v3 es compatible con el pipeline actual
- `company_context` ya existe y está poblado
- `corrections` ya existe y se usa
- Solo cambia la construcción del prompt

### Migración Gradual
1. Crear `PromptBuilder` con prompt v3
2. Agregar flag `USE_PROMPT_V3=true` en `.env`
3. Probar en paralelo con v2
4. Comparar accuracy
5. Switchear a v3 si accuracy ≥ v2
6. Deprecar v2 después de 2 semanas

### Testing
```python
# Test que prompt NO contiene sesgos
def test_prompt_has_no_industry_bias():
    builder = SATPromptBuilder(prompt_version="v3")
    prompt = builder.build(snapshot, candidates)

    # Asegurar que NO contiene ejemplos específicos
    assert "laptop" not in prompt.lower()
    assert "gasolina" not in prompt.lower()
    assert "BOPP" not in prompt
    assert "etiquetas" not in prompt

# Test que usa company context
def test_prompt_uses_company_context():
    context = {"industry": "food_production"}
    builder = SATPromptBuilder()
    prompt = builder.build(snapshot, candidates, company_context=context)

    assert "food_production" in prompt or "producción de alimentos" in prompt
```

---

## 🎯 Beneficios Esperados

### Técnicos
- ✅ Reducción 75% tamaño prompt
- ✅ Separación de responsabilidades (SRP)
- ✅ Versionamiento real de prompts
- ✅ Testing unitario posible
- ✅ Mantenibilidad mejorada

### Negocio
- ✅ Funciona para TODAS las industrias
- ✅ Menos errores de clasificación
- ✅ Sistema aprende más seguro (threshold 5)
- ✅ Auditoría SAT más fácil
- ✅ Escalable a nuevas empresas sin código

---

**Estado actual:** Prompt v3 creado ✅
**Próximo paso:** Crear `PromptBuilder` class
**ETA Sprint 1:** 2-3 días

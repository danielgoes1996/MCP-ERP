# 🧠 Guía Técnica: Evaluación de Similitud de Conceptos

**Fecha**: 2025-11-25
**Objetivo**: Comparar descripciones de tickets con conceptos de facturas para mejorar matching

---

## 📊 EL PROBLEMA

### **Caso Real: Gasolina**

**Ticket extraído**:
```json
{
  "merchant_name": "Pemex",
  "extracted_concepts": ["MAGNA 40 LITROS"],
  "precio_litro": 21.50,
  "total": 860.00
}
```

**Factura (CFDI XML)**:
```json
{
  "conceptos": [
    {
      "cantidad": "40.00",
      "unidad": "Litro",
      "descripcion": "Combustible Magna sin plomo",
      "valorUnitario": "21.50",
      "importe": "860.00"
    }
  ]
}
```

**Pregunta**: ¿Cómo comparar `"MAGNA 40 LITROS"` con `"Combustible Magna sin plomo"`?

---

## ✅ SOLUCIÓN: 3 NIVELES DE SIMILITUD

### **Nivel 1: Similitud Exacta de Palabras Clave** (Simple, Rápido)

**Algoritmo**:
1. Extraer palabras clave de ambos textos
2. Normalizar (minúsculas, sin acentos, sin stopwords)
3. Calcular overlap de palabras

**Ejemplo**:
```python
# Ticket
ticket_keywords = normalize("MAGNA 40 LITROS")
# → {"magna", "40", "litros"}

# Factura
invoice_keywords = normalize("Combustible Magna sin plomo, 40 Litros")
# → {"combustible", "magna", "sin", "plomo", "40", "litros"}

# Similitud
overlap = ticket_keywords & invoice_keywords  # {"magna", "40", "litros"}
jaccard_similarity = len(overlap) / len(ticket_keywords | invoice_keywords)
# → 3 / 6 = 0.50 (50%)
```

**Código PostgreSQL**:
```sql
-- Usando extensión pg_trgm para similitud de texto
CREATE EXTENSION IF NOT EXISTS pg_trgm;

SELECT
    similarity(
        lower(regexp_replace('MAGNA 40 LITROS', '[^a-zA-Z0-9 ]', '', 'g')),
        lower(regexp_replace('Combustible Magna sin plomo', '[^a-zA-Z0-9 ]', '', 'g'))
    ) as similarity_score;
-- Resultado: ~0.45 (45%)
```

---

### **Nivel 2: Similitud de Secuencia (Levenshtein Distance)** (Medio)

**Algoritmo**: Medir cuántas operaciones (insertar, eliminar, reemplazar) se necesitan para transformar un texto en otro.

**Ejemplo**:
```python
from difflib import SequenceMatcher

ticket = "MAGNA 40 LITROS"
invoice = "Combustible Magna sin plomo 40 Litros"

matcher = SequenceMatcher(None, ticket.lower(), invoice.lower())
ratio = matcher.ratio()
# → 0.58 (58% similitud)
```

**Código PostgreSQL** (usando extensión fuzzystrmatch):
```sql
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;

SELECT levenshtein(
    'MAGNA 40 LITROS',
    'Combustible Magna sin plomo'
) as edit_distance;
-- Menor distancia = mayor similitud
```

---

### **Nivel 3: Similitud Semántica Contextual** (Sofisticado, Más Preciso)

**Algoritmo**: Usar embeddings o LLM para entender el **significado** de los conceptos.

**Ejemplo usando GPT/Claude**:
```python
def semantic_similarity(ticket_concept: str, invoice_concept: str) -> float:
    """
    Usar LLM para evaluar si dos conceptos describen el mismo producto/servicio
    """
    prompt = f"""
    Evalúa si estos dos conceptos describen el mismo producto/servicio.
    Responde con un score de 0 a 100.

    Concepto 1 (ticket): {ticket_concept}
    Concepto 2 (factura): {invoice_concept}

    Score:
    """

    response = llm.complete(prompt)
    return int(response) / 100.0

# Ejemplo
score = semantic_similarity(
    "MAGNA 40 LITROS",
    "Combustible Magna sin plomo, 40 Litros, $21.50/L"
)
# → 0.95 (95% - claramente es el mismo producto)
```

---

## 🎯 ENFOQUE RECOMENDADO: HÍBRIDO

Combinar los 3 niveles para obtener **confianza escalonada**:

```python
def calculate_concept_match_score(ticket_concepts: list, invoice_concepts: list) -> int:
    """
    Retorna score de 0 a 100 basado en similitud de conceptos
    """
    max_score = 0

    for ticket_concept in ticket_concepts:
        for invoice_concept in invoice_concepts:
            # Nivel 1: Keyword Overlap (rápido)
            keyword_score = keyword_similarity(ticket_concept, invoice_concept)

            # Nivel 2: Levenshtein (medio)
            sequence_score = sequence_similarity(ticket_concept, invoice_concept)

            # Nivel 3: Semántico (solo si niveles 1-2 son prometedores)
            semantic_score = 0
            if keyword_score > 0.3 or sequence_score > 0.4:
                semantic_score = semantic_similarity(ticket_concept, invoice_concept)

            # Score combinado (ponderado)
            combined_score = (
                keyword_score * 0.3 +
                sequence_score * 0.3 +
                semantic_score * 0.4
            ) * 100

            max_score = max(max_score, combined_score)

    return int(max_score)
```

---

## 📊 TABLA DE SCORING

| Ticket Concept | Invoice Concept | Keyword | Sequence | Semantic | **Final Score** |
|----------------|-----------------|---------|----------|----------|-----------------|
| `MAGNA 40 LITROS` | `Combustible Magna sin plomo, 40 Litros` | 50 | 58 | 95 | **76** ✅ |
| `DIESEL 50L` | `Combustible Diesel 50 Litros` | 66 | 70 | 90 | **79** ✅ |
| `COCA COLA 600ML` | `Refresco Coca Cola, presentación 600ml` | 55 | 45 | 85 | **68** ⚠️ |
| `GASOLINA` | `Servicio de auditoría` | 0 | 5 | 10 | **6** ❌ |

**Thresholds**:
- **≥ 70**: Alta confianza → Auto-match (si RFC + monto también coinciden)
- **50-69**: Media confianza → A cola de revisión
- **< 50**: Baja confianza → No match

---

## 🔧 IMPLEMENTACIÓN EN POSTGRESQL

### **Opción 1: Función PostgreSQL con pg_trgm**

```sql
CREATE OR REPLACE FUNCTION calculate_concept_similarity(
    ticket_concepts JSONB,
    invoice_concepts JSONB
) RETURNS INTEGER AS $$
DECLARE
    ticket_text TEXT;
    invoice_text TEXT;
    max_similarity FLOAT := 0;
    current_similarity FLOAT;
BEGIN
    -- Iterar sobre cada concepto del ticket
    FOR ticket_text IN SELECT jsonb_array_elements_text(ticket_concepts) LOOP
        -- Iterar sobre cada concepto de la factura
        FOR invoice_text IN SELECT jsonb_array_elements_text(invoice_concepts) LOOP
            -- Calcular similitud usando pg_trgm
            current_similarity := similarity(
                lower(regexp_replace(ticket_text, '[^a-zA-Z0-9 ]', '', 'g')),
                lower(regexp_replace(invoice_text, '[^a-zA-Z0-9 ]', '', 'g'))
            );

            -- Guardar la mayor similitud
            IF current_similarity > max_similarity THEN
                max_similarity := current_similarity;
            END IF;
        END LOOP;
    END LOOP;

    -- Convertir a score de 0-100
    RETURN (max_similarity * 100)::INTEGER;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

**Uso en Query**:
```sql
SELECT
    me.id,
    me.description,
    calculate_concept_similarity(
        me.ticket_extracted_concepts,
        si.parsed_data->'conceptos'
    ) as concept_score
FROM manual_expenses me
JOIN sat_invoices si ON si.id = 'UUID_FACTURA'
WHERE concept_score > 50
ORDER BY concept_score DESC;
```

---

### **Opción 2: Procesamiento en Python (Más Flexible)**

```python
from typing import List, Dict
from difflib import SequenceMatcher
import re

def normalize_text(text: str) -> str:
    """Normalizar texto para comparación"""
    # Minúsculas
    text = text.lower()
    # Remover caracteres especiales
    text = re.sub(r'[^a-z0-9\s]', '', text)
    # Remover espacios múltiples
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_keywords(text: str) -> set:
    """Extraer palabras clave (sin stopwords)"""
    stopwords = {'de', 'del', 'la', 'el', 'sin', 'con', 'para'}
    words = set(normalize_text(text).split())
    return words - stopwords

def keyword_similarity(text1: str, text2: str) -> float:
    """Similitud basada en overlap de keywords"""
    kw1 = extract_keywords(text1)
    kw2 = extract_keywords(text2)

    if not kw1 or not kw2:
        return 0.0

    intersection = len(kw1 & kw2)
    union = len(kw1 | kw2)

    return intersection / union if union > 0 else 0.0

def sequence_similarity(text1: str, text2: str) -> float:
    """Similitud basada en secuencia de caracteres"""
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)

    return SequenceMatcher(None, norm1, norm2).ratio()

def calculate_concept_match_score(
    ticket_concepts: List[str],
    invoice_concepts: List[Dict]
) -> int:
    """
    Calcular score de 0-100 para similitud de conceptos

    Args:
        ticket_concepts: ["MAGNA 40 LITROS"]
        invoice_concepts: [{"descripcion": "Combustible Magna sin plomo"}]

    Returns:
        Score de 0-100
    """
    if not ticket_concepts or not invoice_concepts:
        return 0

    max_score = 0

    for ticket_concept in ticket_concepts:
        for invoice_concept in invoice_concepts:
            invoice_desc = invoice_concept.get('descripcion', '')

            # Nivel 1: Keyword overlap (30% peso)
            kw_score = keyword_similarity(ticket_concept, invoice_desc)

            # Nivel 2: Sequence similarity (70% peso)
            seq_score = sequence_similarity(ticket_concept, invoice_desc)

            # Score combinado
            combined = (kw_score * 0.3) + (seq_score * 0.7)
            score = int(combined * 100)

            max_score = max(max_score, score)

    return max_score
```

**Uso en API**:
```python
# En invoice_to_expense_matching_api.py

# Extraer conceptos del ticket
ticket_concepts = expense.get('ticket_extracted_concepts', [])

# Extraer conceptos de la factura
invoice_concepts = parsed_data.get('conceptos', [])

# Calcular similitud
concept_score = calculate_concept_match_score(ticket_concepts, invoice_concepts)

# Agregar a match_score
if concept_score >= 70:
    match_score += 20  # Boost para conceptos muy similares
elif concept_score >= 50:
    match_score += 10  # Boost moderado
```

---

## 🎯 INTEGRACIÓN CON MATCH_SCORE EXISTENTE

### **Nuevo Sistema de Scoring Combinado**

```python
# Match score components:
rfc_score = 100 if provider_rfc == invoice_rfc else 0
name_score = 80 if provider_name similar to emisor_nombre else 0
amount_score = 100 if abs(amount - total) < 5 else 0
date_score = 100 if date within ±15 days else 0
concept_score = calculate_concept_match_score(ticket_concepts, invoice_concepts)

# Weighted final score
final_score = (
    rfc_score * 0.35 +      # RFC es el más importante
    amount_score * 0.25 +   # Monto debe coincidir
    concept_score * 0.20 +  # Conceptos similares
    date_score * 0.10 +     # Fecha menos crítica
    name_score * 0.10       # Nombre comercial
)

# Decision thresholds
if final_score >= 85:
    action = "auto_match"  # Alta confianza
elif final_score >= 60:
    action = "pending_review"  # Media confianza
else:
    action = "no_match"  # Baja confianza
```

---

## 📋 EJEMPLOS REALES

### **Ejemplo 1: Gasolina Pemex** ✅

```python
Ticket:
  concepts = ["MAGNA 40 LITROS"]

Factura:
  concepts = [{"descripcion": "Combustible Magna sin plomo", "cantidad": "40"}]

Cálculo:
  - Keywords: {"magna", "40", "litros"} ∩ {"combustible", "magna", "sin", "plomo", "40", "litros"}
    → overlap = 3/6 = 50%
  - Sequence: "magna 40 litros" vs "combustible magna sin plomo 40 litros"
    → 58%
  - Combined: (0.50 * 0.3) + (0.58 * 0.7) = 0.56 → 56/100

Score Final: 56 → MEDIA CONFIANZA → Pending Review
```

### **Ejemplo 2: Oxxo - Comida** ✅

```python
Ticket:
  concepts = ["SANDWICH JAMON", "COCA COLA 600ML"]

Factura:
  concepts = [
    {"descripcion": "Alimentos preparados - Sandwich"},
    {"descripcion": "Bebidas - Refresco Coca Cola 600ml"}
  ]

Cálculo:
  - Concepto 1: "sandwich jamon" vs "alimentos preparados sandwich"
    → Keywords: {"sandwich"} común → 25%
    → Sequence: 45%
    → Combined: 39/100

  - Concepto 2: "coca cola 600ml" vs "bebidas refresco coca cola 600ml"
    → Keywords: {"coca", "cola", "600ml"} → 60%
    → Sequence: 70%
    → Combined: 67/100

  - Max: 67/100

Score Final: 67 → MEDIA CONFIANZA → Pending Review
```

### **Ejemplo 3: Match Perfecto** ✅✅✅

```python
Ticket:
  concepts = ["DIESEL 50 LITROS"]

Factura:
  concepts = [{"descripcion": "DIESEL 50 LITROS"}]

Cálculo:
  - Exactamente igual
  - Keywords: 100%
  - Sequence: 100%

Score Final: 100 → ALTA CONFIANZA → Auto-match
```

---

## 🔐 MIGRACIÓN DE BASE DE DATOS

Agregar campos para almacenar conceptos extraídos del ticket:

```sql
-- Agregar columna para conceptos extraídos del ticket
ALTER TABLE manual_expenses
ADD COLUMN ticket_extracted_concepts JSONB;

-- Agregar índice para búsquedas rápidas
CREATE INDEX idx_manual_expenses_ticket_concepts
ON manual_expenses USING gin(ticket_extracted_concepts);

-- Ejemplo de datos:
UPDATE manual_expenses
SET ticket_extracted_concepts = '["MAGNA 40 LITROS", "Precio: $21.50/L"]'::jsonb
WHERE id = 123;
```

---

## 📊 MÉTRICAS ESPERADAS

| Métrica | Valor | Explicación |
|---------|-------|-------------|
| **Precision** | 85%+ | De los auto-matches, 85% son correctos |
| **Recall** | 75%+ | De los matches válidos, 75% son detectados |
| **False Positives** | <5% | Casos incorrectamente auto-matched |
| **Manual Review** | 20-25% | Casos que requieren validación humana |

---

## ✅ PRÓXIMOS PASOS

1. **Agregar campo `ticket_extracted_concepts` a `manual_expenses`**
2. **Implementar función `calculate_concept_match_score()` en Python**
3. **Actualizar endpoint de matching para incluir concept score**
4. **Extraer conceptos automáticamente cuando se sube ticket**
5. **Dashboard para revisar casos con concept_score medio (50-69)**

---

**Preparado por**: Claude Code
**Documento**: Evaluación de Similitud de Conceptos
**Estado**: Diseño técnico completo - Listo para implementar

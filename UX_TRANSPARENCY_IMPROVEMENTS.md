# UX Transparency - Mejoras Propuestas

## Problema
El scoring IA puede percibirse como "caja negra" difícil de auditar.

## Solución: Explicabilidad Multi-Nivel

### Nivel 1: Usuario Casual (Actual) ✅
```
[92% ALTA CONFIANZA]
✓ Monto coincide: $850.50
✓ Fechas cercanas: 15 ene - 17 ene (2 días)
✓ Descripciones similares
```

### Nivel 2: Contable (Propuesto) 🔄
Agregar modal "¿Cómo se calculó esto?"

```javascript
function showAIExplanation(suggestion) {
    const modal = `
        <div class="explanation-modal">
            <h3>Explicación del Score: 92%</h3>

            <div class="factor">
                <h4>🔢 Coincidencia de Monto: 47.5/50 pts (95%)</h4>
                <p>
                    <strong>Movimiento bancario:</strong> -$850.50<br>
                    <strong>Suma de gastos:</strong> $850.50<br>
                    <strong>Diferencia:</strong> $0.00 ✓
                </p>
                <details>
                    <summary>¿Cómo se calcula?</summary>
                    <code>
                    score = max(0, 100 - (|diferencia| / monto * 100))
                          = max(0, 100 - (0 / 850.50 * 100))
                          = 100%
                    peso = 100% * 0.50 = 50 puntos
                    </code>
                </details>
            </div>

            <div class="factor">
                <h4>📅 Proximidad de Fecha: 27/30 pts (90%)</h4>
                <p>
                    <strong>Fecha movimiento:</strong> 17 ene 2025<br>
                    <strong>Fechas gastos:</strong> 15 ene, 15 ene, 16 ene<br>
                    <strong>Promedio diferencia:</strong> 1.7 días ✓
                </p>
                <details>
                    <summary>¿Cómo se calcula?</summary>
                    <code>
                    score = max(0, 30 - (diferencia_días * 3))
                          = max(0, 30 - (1.7 * 3))
                          = 25 puntos
                    </code>
                </details>
            </div>

            <div class="factor">
                <h4>📝 Similitud de Texto: 18/20 pts (90%)</h4>
                <p>
                    <strong>Descripción bancaria:</strong> "GASOLINERA PEMEX INSURGENTES"<br>
                    <strong>Descripciones gastos:</strong><br>
                    - "Gasolina Pemex" (similitud: 85%)<br>
                    - "Gasolina Pemex Sur" (similitud: 92%)<br>
                    - "Combustible Pemex" (similitud: 78%)
                </p>
                <details>
                    <summary>¿Cómo se calcula?</summary>
                    <code>
                    1. Normalizar texto: lowercase, quitar acentos
                    2. Extraer keywords: ["gasolinera", "pemex"]
                    3. Calcular overlap ratio: 2/2 = 100%
                    4. SequenceMatcher promedio: 85%
                    5. Score final: (100% + 85%) / 2 * 0.20 = 18.5 pts
                    </code>
                </details>
            </div>

            <div class="total">
                <strong>Score Total:</strong> 47.5 + 27 + 18 = 92.5 ≈ 92%
            </div>

            <div class="warning">
                ⚠️ <strong>Nota:</strong> Este score es una sugerencia, no una decisión automática.
                Siempre revisa los datos antes de aplicar.
            </div>
        </div>
    `;
}
```

### Nivel 3: Auditor (Propuesto) 🔄
Guardar en BD el cálculo completo

```sql
CREATE TABLE ai_suggestion_audit (
    id INTEGER PRIMARY KEY,
    suggestion_id TEXT,
    confidence_score REAL,

    -- Factores individuales
    amount_score REAL,
    amount_diff REAL,
    amount_calculation TEXT,

    date_score REAL,
    date_diff_avg REAL,
    date_calculation TEXT,

    text_score REAL,
    text_similarity REAL,
    text_calculation TEXT,

    -- Metadata
    algorithm_version TEXT,  -- 'v1.0-greedy'
    calculated_at TIMESTAMP,
    applied BOOLEAN,
    applied_by INTEGER,
    applied_at TIMESTAMP,

    -- Resultado
    movement_ids TEXT,  -- JSON array
    expense_ids TEXT,   -- JSON array
    total_allocated REAL
);
```

### Nivel 4: Desarrollador (Logging) 🔄
```python
logger.info(f"""
AI Suggestion Generated:
  ID: {suggestion_id}
  Type: one_to_many
  Movement: ID {movement_id}, ${movement_amount:.2f}
  Expenses: [{', '.join(str(e['id']) for e in expenses)}]

  Scoring Breakdown:
    Amount:  {amount_score:.2f}/50 (diff: ${amount_diff:.2f})
    Date:    {date_score:.2f}/30 (avg diff: {date_diff_avg:.1f} days)
    Text:    {text_score:.2f}/20 (similarity: {text_similarity:.1f}%)
    TOTAL:   {confidence_score:.2f}%

  Algorithm: greedy_combination_v1
  Execution time: {elapsed_ms}ms
""")
```

## Mejoras UX Adicionales

### 1. Tutorial Interactivo (Primera Vez)
```javascript
if (!localStorage.getItem('ai_suggestions_tutorial_seen')) {
    showTutorial([
        {
            target: '.confidence-badge',
            message: 'Este porcentaje indica qué tan segura está la IA de esta sugerencia. Verde = alta confianza.'
        },
        {
            target: '.breakdown-section',
            message: 'Aquí puedes ver cómo se calculó el score: monto, fecha y texto.'
        },
        {
            target: '.review-button',
            message: 'Siempre revisa la sugerencia antes de aplicarla. Puedes editar los montos.'
        }
    ]);
}
```

### 2. Feedback Loop
```html
<!-- Después de aplicar una sugerencia -->
<div class="feedback-dialog">
    <h4>¿Qué tan útil fue esta sugerencia?</h4>
    <button onclick="rateSuggestion('helpful')">👍 Útil</button>
    <button onclick="rateSuggestion('incorrect')">👎 Incorrecta</button>

    <textarea placeholder="¿Qué mejorarías? (opcional)"></textarea>
</div>
```

### 3. Historial de Sugerencias Aplicadas
```javascript
// En el dashboard
GET /bank_reconciliation/ai/history

Response:
{
    "total_suggestions": 150,
    "applied": 87,
    "rejected": 23,
    "pending": 40,

    "accuracy_by_confidence": {
        "high (≥85%)": { "applied": 65, "correct": 63, "accuracy": "96.9%" },
        "medium (60-84%)": { "applied": 22, "correct": 18, "accuracy": "81.8%" }
    },

    "recent": [
        {
            "date": "2025-01-20",
            "type": "one_to_many",
            "confidence": 92,
            "applied": true,
            "user_rating": "helpful"
        }
    ]
}
```

### 4. Modo "Explicación Simple"
```javascript
// Toggle en UI
<button onclick="toggleSimpleMode()">
    <i class="fas fa-graduation-cap"></i>
    Modo Explicación Simple
</button>

// Cuando está activo:
const simpleExplanation = {
    92: "Esta conciliación es casi perfecta. El monto coincide exactamente y las fechas son muy cercanas.",
    76: "Esta conciliación es probable, pero revisa que los conceptos sean correctos.",
    55: "Esta es solo una posibilidad. Verifica cuidadosamente antes de aplicar."
};
```

## Implementación Recomendada

1. **Fase 1** (1 semana): Modal de explicación detallada
2. **Fase 2** (1 semana): Audit trail en BD
3. **Fase 3** (2 semanas): Tutorial interactivo + feedback loop
4. **Fase 4** (1 mes): Dashboard de accuracy histórico

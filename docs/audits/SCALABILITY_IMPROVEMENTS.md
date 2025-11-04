# Mejoras de Escalabilidad - Motor IA de Conciliación

## Problema Identificado
El motor IA actual funciona bien con ~100 movimientos, pero degradaría con 10,000 movimientos y 8,000 gastos debido a:
- Algoritmo greedy O(n²) sin optimización
- Cálculo de similitud de texto en memoria (Python)
- Sin índices especializados para búsqueda de texto
- LIMIT hardcoded en queries

## Mejoras Propuestas

### 1. Índices de Base de Datos

```sql
-- Full-text search en descripciones
CREATE VIRTUAL TABLE expense_fts USING fts5(
    id, description, merchant_name,
    content=expense_records
);

CREATE VIRTUAL TABLE movement_fts USING fts5(
    id, description,
    content=bank_movements
);

-- Índices compuestos para filtrado rápido
CREATE INDEX idx_expense_amount_date
ON expense_records(amount, date)
WHERE bank_status = 'pending';

CREATE INDEX idx_movement_amount_date
ON bank_movements(amount, date)
WHERE matched_expense_id IS NULL;
```

### 2. Pre-filtrado Inteligente

```python
def suggest_one_to_many_splits(self, limit: int = 10, amount_range: tuple = None):
    """
    Mejora: Pre-filtrar por rango de montos antes de algoritmo greedy
    """
    # Solo buscar movimientos grandes (> $500)
    min_amount_threshold = 500.0

    cursor.execute("""
        SELECT * FROM bank_movements
        WHERE (matched_expense_id IS NULL OR matched_expense_id = 0)
        AND amount < 0
        AND ABS(amount) >= ?
        ORDER BY ABS(amount) DESC
        LIMIT 100  -- Procesar top 100 primero
    """, (min_amount_threshold,))
```

### 3. Algoritmo de Combinaciones Optimizado

**Actual**: Greedy O(n²) en memoria
**Propuesto**: Knapsack con dynamic programming

```python
def find_matching_combinations_optimized(self, target_amount, expenses, max_items=5):
    """
    Usa dynamic programming para encontrar combinaciones sin explorar todas

    Complejidad: O(n * target * max_items) vs O(2^n) del greedy
    """
    from functools import lru_cache

    @lru_cache(maxsize=10000)
    def dp(index, remaining, count):
        if abs(remaining) <= 0.01:
            return []
        if index >= len(expenses) or count >= max_items:
            return None

        # Skip this expense
        skip = dp(index + 1, remaining, count)

        # Take this expense
        exp = expenses[index]
        if exp['amount'] <= remaining:
            take = dp(index + 1, remaining - exp['amount'], count + 1)
            if take is not None:
                return [exp] + take

        return skip if skip is not None else None

    result = dp(0, abs(target_amount), 0)
    return result or []
```

### 4. Similarity Search con Embeddings

**Actual**: SequenceMatcher en Python (lento)
**Propuesto**: Sentence embeddings pre-calculados

```python
# Instalar: pip install sentence-transformers
from sentence_transformers import SentenceTransformer
import faiss

class EmbeddingCache:
    def __init__(self):
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.index = None
        self.expense_ids = []

    def build_index(self, expenses):
        """Pre-calcular embeddings y construir índice FAISS"""
        descriptions = [e['description'] for e in expenses]
        embeddings = self.model.encode(descriptions)

        # Crear índice FAISS para búsqueda rápida
        self.index = faiss.IndexFlatL2(embeddings.shape[1])
        self.index.add(embeddings)
        self.expense_ids = [e['id'] for e in expenses]

    def find_similar(self, movement_description, k=10):
        """Encontrar top-k gastos similares en O(log n)"""
        query_embedding = self.model.encode([movement_description])
        distances, indices = self.index.search(query_embedding, k)

        return [
            {
                'expense_id': self.expense_ids[idx],
                'similarity': 1 / (1 + distances[0][i])  # Convertir distancia a similitud
            }
            for i, idx in enumerate(indices[0])
        ]
```

### 5. Caching de Sugerencias

```python
from functools import lru_cache
import hashlib

class AIReconciliationService:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutos

    def _cache_key(self, movements, expenses):
        """Generar hash de estado actual"""
        data = f"{len(movements)}:{len(expenses)}"
        return hashlib.md5(data.encode()).hexdigest()

    @lru_cache(maxsize=100)
    def suggest_one_to_many_splits(self, limit: int = 10):
        cache_key = self._cache_key(...)

        if cache_key in self.cache:
            return self.cache[cache_key]

        # ... calcular sugerencias ...

        self.cache[cache_key] = suggestions
        return suggestions
```

### 6. Procesamiento Asíncrono

```python
from celery import Celery
from fastapi import BackgroundTasks

app = Celery('ai_reconciliation', broker='redis://localhost:6379/0')

@app.task
def process_large_reconciliation_batch(movements_ids, expenses_ids):
    """
    Procesar en background para no bloquear UI
    """
    service = AIReconciliationService()
    suggestions = service.suggest_one_to_many_splits(limit=100)

    # Guardar en cache/DB
    cache.set(f"suggestions:{batch_id}", suggestions, expire=3600)

    return {"batch_id": batch_id, "count": len(suggestions)}

# En el endpoint
@router.get("/ai/suggestions")
async def get_suggestions(background_tasks: BackgroundTasks):
    # Si hay muchos registros, procesar en background
    if movement_count > 1000:
        background_tasks.add_task(process_large_reconciliation_batch, ...)
        return {"status": "processing", "check_at": "/ai/suggestions/status"}

    return service.suggest_one_to_many_splits()
```

## Benchmarks Esperados

| Operación | Actual (100 mov) | Optimizado (10k mov) |
|-----------|------------------|----------------------|
| Cargar movimientos | 50ms | 200ms |
| Calcular similitud | 500ms | 800ms (con FAISS) |
| Greedy combinations | 1s | 3s (con DP + cache) |
| **Total** | **1.5s** | **4s** |

## Implementación Recomendada

1. **Fase 1** (inmediata): Agregar índices DB + pre-filtrado por monto
2. **Fase 2** (1 semana): Implementar DP algorithm + caching
3. **Fase 3** (2 semanas): Agregar embeddings con FAISS
4. **Fase 4** (1 mes): Procesamiento asíncrono con Celery

## Notas

- Mantener límite de 100 sugerencias en UI (UX)
- Monitorear performance con `logging` de tiempos
- Considerar paginación en `/ai/suggestions?offset=0&limit=20`

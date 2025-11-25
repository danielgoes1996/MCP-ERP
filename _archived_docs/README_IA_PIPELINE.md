# IA Pipeline – Clasificación SAT

Este documento resume la arquitectura cognitiva que estamos implementando para clasificar gastos contra el catálogo SAT, los flujos de orquestación en segundo plano y los pendientes clave para garantizar trazabilidad y escalabilidad.

## Stages (0–3)

| Stage | Módulo | Propósito |
| ----- | ------ | --------- |
| 0 – Snapshot | `core/expense_features.py` | Normaliza descripción, proveedor, monto, estatus y metadatos del gasto en un snapshot reproducible. |
| 1 – (omitido por ahora) | — | Un clasificador ligero por familia se activará cuando superemos ~3 k gastos confirmados; mientras tanto, el LLM resuelve la familia. |
| 2 – Retrieval | `core/account_catalog.py` + `sat_account_embeddings` | Busca candidatos SAT con pgvector, filtrando por `family_hint` cuando hay señales previas. |
| 3 – CoT-lite | `core/expense_llm_classifier.py` | Claude/GPT evalúa snapshot + candidatos y responde JSON con `family_code`, `sat_account_code`, confidencias y explicación. |
| 4 – Feedback & Audit | `core/classification_feedback.py`, `core/classification_trace.py` | Recolecta confirmaciones/rechazos por tenant y guarda trazas completas por gasto. |

## Arquitectura Cognitiva

| Capa | Tecnología | Rol |
| ---- | ---------- | --- |
| Embeddings | PostgreSQL + `pgvector` | Contexto semántico de cuentas SAT (`family_hint`, `tsvector`). |
| LLM | `core/expense_llm_classifier.py` (Claude / GPT) | Razonamiento fiscal, selección y explicación. |
| Feedback | `core/classification_feedback.py` | Aprendizaje supervisado continuo / tenant bias. |
| Tenancy | `core/tenancy_middleware.py` | Aislamiento por empresa y adaptación fiscal. |
| API REST | FastAPI (`main.py`) | Entrada/salida estructurada (gastos, feedback, auditoría). |
| UI React | `dashboard-react/` | Confirmación rápida vs modal de reclasificación. |
| Workers | `core/worker_system.py` + `core/task_dispatcher.py` | Ejecución en background y helpers asíncronos para clasificación masiva y reindexados. |

## Orquestación en segundo plano

- **Event bus interno:** `core/worker_system.py` ya implementa una cola priorizada en memoria (`TaskQueue`) con workers basados en hilos/asyncio. `core/task_dispatcher.py` expone helpers listos para usar, por ejemplo:
  ```python
  from core.task_dispatcher import enqueue_expense_classification

  await enqueue_expense_classification(expense_id=expense_id, tenant_id=tenant_id)
  ```
  El helper arranca el scheduler, registra el handler `expense.classify` y despacha el pipeline completo (`core.fiscal_pipeline.classify_expense_fiscal`) en background.
- **Ejecución recurrente:** jobs semanales (reindex, tenant_bias) deberían registrarse mediante el scheduler de `worker_system` o migrar a Celery/RQ si preferimos multiproceso. El README se actualizará cuando definamos la opción final.
- **Escalado horizontal:** al documentar el patrón `enqueue_task`, aclaramos que se puede correr `python core/worker_system.py --worker` en múltiples instancias detrás de Redis (pendiente migrar la cola a un backend compartido).

## Versionado y trazabilidad

- **Embeddings:** `scripts/build_sat_embeddings_dense.py` ahora recibe `--version-tag` (default `vYYYYMMDD`) y persiste la columna `version_tag` + índice dedicado. El servicio consume la versión activa mediante `SAT_EMBEDDING_VERSION` (o usa la del candidato si viene etiquetada).
- **Explicaciones LLM:** `core/classification_trace.py` crea la tabla `classification_trace` y guarda cada corrida del pipeline con confidencias, snapshot resumido, candidatos evaluados, fallback aplicado y el payload `asdict(result)`. Sirve como bitácora auditable (`SELECT * FROM classification_trace WHERE expense_id = ? ORDER BY created_at DESC`).
- **Feedback loop:** `core/classification_feedback.py` resuelve automáticamente el `classification_trace_id` más reciente al registrar correcciones, vinculando feedback ↔ trace ↔ versión sin intervención manual.
- **APIs de trazabilidad:** nuevos endpoints `GET /expenses/{id}/classification-trace` y `GET /classification-trace/recent` exponen trazas y candidatos para la UI y paneles QA.

## Tenancy y pooling

- Middleware (`core/tenancy_middleware.py`) garantiza aislamiento, pero debemos documentar que:
  - Con Postgres usamos `psycopg2.pool` (pendiente) para pool compartido por proceso.
  - Para SQLite, el adaptador unificado mantiene conexiones por tenant; se documentará un cache LRU de snapshots fiscales y credenciales.
- Incluir sección “Performance y caching” en los docs: latencia objetivo < 200 ms para fetch de snapshots y < 1 s para clasificación.

## Próximos pasos

1. Publicar helper `enqueue_embedding_refresh` y documentar métricas de duración.
2. Migrar la cola a backend compartido (Redis/Celery) o habilitar modo multiproceso con locks distribuidos.
3. Documentar pooling/caching por tenant y preparar métricas (`hit@1`, latencia, confirmaciones).
4. Exponer dashboards QA que combinen `classification_trace` + feedback y permitan filtrar por tenant/version.

Mantendremos este README como blueprint vivo del pipeline y de las decisiones de arquitectura IA.

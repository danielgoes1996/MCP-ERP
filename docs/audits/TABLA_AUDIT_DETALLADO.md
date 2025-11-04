# 📊 AUDITORÍA COMPLETA DE TABLAS - ANÁLISIS DETALLADO

**Sistema:** MCP Multi-Tenant SaaS
**Fecha:** 2025-10-03
**Total Tablas:** 49

---

## 🎯 RESUMEN EJECUTIVO

| Clasificación | Tablas | % |
|---------------|--------|---|
| ACTIVE_MULTI_TENANT | 18 | 37% |
| DEFINED_NO_DATA | 18 | 37% |
| ACTIVE_NO_TENANT | 10 | 20% |
| UNUSED | 2 | 4% |
| LEGACY_DATA | 1 | 2% |

---

## 📋 ANÁLISIS POR TABLA


### 🏷️ ACTIVE_MULTI_TENANT (18 tablas)

#### `automation_jobs`

**Filas:** 117  
**Menciones en código:** 61  
**Archivos que la usan:** 8  
**Queries SQL:** 26 (SELECT: 17, INSERT: 3, UPDATE: 6)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T1=117  
**Rango de fechas:** 2025-09-25 16:44:02 → 2025-09-25 16:44:02  
**Archivos:**  
  - `core/rollback_safety.py`  
  - `modules/invoicing_agent/automation_persistence.py`  
  - `core/idempotent_workers.py`  
  - `core/unified_db_adapter.py`  
  - `core/multi_tenancy_scaling.py`  
  - ... y 3 más  

#### `bank_matching_rules`

**Filas:** 7  
**Menciones en código:** 2  
**Archivos que la usan:** 1  
**Queries SQL:** 0 (SELECT: 0, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T1=7  
**Rango de fechas:** 2025-09-25 22:04:01 → 2025-09-25 22:04:01  
**Archivos:**  
  - `core/unified_db_adapter.py`  

#### `bank_ml_config`

**Filas:** 3  
**Menciones en código:** 1  
**Archivos que la usan:** 1  
**Queries SQL:** 1 (SELECT: 1, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T1=3  
**Rango de fechas:** 2025-09-25 22:04:01 → 2025-09-25 22:04:01  
**Archivos:**  
  - `core/unified_db_adapter.py`  

#### `bank_movements`

**Filas:** 196  
**Menciones en código:** 104  
**Archivos que la usan:** 10  
**Queries SQL:** 60 (SELECT: 44, INSERT: 6, UPDATE: 10)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T3=110, T4=86  
**Rango de fechas:** 2025-09-28 12:57:48.126118 → 2025-10-03 04:09:10  
**Archivos:**  
  - `core/bank_reconciliation.py`  
  - `core/internal_db.py`  
  - `core/bank_statements_models.py`  
  - `core/split_reconciliation_service.py`  
  - `core/db_optimizer.py`  
  - ... y 5 más  

#### `bank_reconciliation_splits`

**Filas:** 3  
**Menciones en código:** 10  
**Archivos que la usan:** 1  
**Queries SQL:** 10 (SELECT: 8, INSERT: 2, UPDATE: 0)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T3=3  
**Rango de fechas:** 2025-10-03 04:16:29 → 2025-10-03 04:16:29  
**Archivos:**  
  - `core/split_reconciliation_service.py`  

#### `bank_statements`

**Filas:** 2  
**Menciones en código:** 39  
**Archivos que la usan:** 9  
**Queries SQL:** 10 (SELECT: 7, INSERT: 1, UPDATE: 2)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T3=1, T4=1  
**Rango de fechas:** 2025-09-29 19:47:46.031149 → 2025-09-30 11:05:43.725174  
**Archivos:**  
  - `api/bank_statements_api.py`  
  - `core/bank_statements_models.py`  
  - `core/enhanced_pdf_parser.py`  
  - `core/unified_db_adapter.py`  
  - `core/llm_pdf_parser.py`  
  - ... y 4 más  

#### `category_prediction_config`

**Filas:** 1  
**Menciones en código:** 2  
**Archivos que la usan:** 1  
**Queries SQL:** 1 (SELECT: 1, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T1=1  
**Rango de fechas:** 2025-09-26 05:21:57 → 2025-09-26 05:21:57  
**Archivos:**  
  - `core/unified_db_adapter.py`  

#### `companies`

**Filas:** 3  
**Menciones en código:** 16  
**Archivos que la usan:** 4  
**Queries SQL:** 1 (SELECT: 1, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T1=1, T2=1, T3=1  
**Rango de fechas:** 2025-09-25 16:44:02 → 2025-09-27 16:25:47  
**Archivos:**  
  - `core/rollback_safety.py`  
  - `api/advanced_invoicing_api.py`  
  - `api/feature_flags_api.py`  
  - `modules/invoicing_agent/api.py`  

#### `custom_categories`

**Filas:** 8  
**Menciones en código:** 10  
**Archivos que la usan:** 3  
**Queries SQL:** 5 (SELECT: 4, INSERT: 0, UPDATE: 1)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T1=8  
**Rango de fechas:** 2025-09-26 05:21:57 → 2025-09-26 05:21:57  
**Archivos:**  
  - `core/api_models.py`  
  - `core/category_learning_system.py`  
  - `core/unified_db_adapter.py`  

#### `duplicate_detection_config`

**Filas:** 1  
**Menciones en código:** 2  
**Archivos que la usan:** 1  
**Queries SQL:** 1 (SELECT: 1, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T1=1  
**Rango de fechas:** 2025-09-26 05:09:34 → 2025-09-26 05:09:34  
**Archivos:**  
  - `core/unified_db_adapter.py`  

#### `employee_advances`

**Filas:** 1  
**Menciones en código:** 23  
**Archivos que la usan:** 3  
**Queries SQL:** 8 (SELECT: 4, INSERT: 1, UPDATE: 3)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T3=1  
**Rango de fechas:** 2025-10-03 04:49:39 → 2025-10-03 04:49:39  
**Archivos:**  
  - `core/employee_advances_service.py`  
  - `api/employee_advances_api.py`  
  - `core/auth_jwt.py`  

#### `error_logs`

**Filas:** 57  
**Menciones en código:** 7  
**Archivos que la usan:** 1  
**Queries SQL:** 5 (SELECT: 4, INSERT: 1, UPDATE: 0)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T1=2, TNone=55  
**Rango de fechas:** 2025-09-25 21:30:29 → 2025-09-30 00:50:23  
**Archivos:**  
  - `core/error_handler.py`  

#### `expense_records`

**Filas:** 26  
**Menciones en código:** 120  
**Archivos que la usan:** 9  
**Queries SQL:** 72 (SELECT: 52, INSERT: 3, UPDATE: 17)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T1=19, T3=4, TNone=3  
**Rango de fechas:** 2025-09-27 05:31:35 → 2025-10-03 04:39:42  
**Archivos:**  
  - `core/category_learning_system.py`  
  - `core/internal_db.py`  
  - `core/split_reconciliation_service.py`  
  - `core/db_optimizer.py`  
  - `core/unified_db_adapter.py`  
  - ... y 4 más  

#### `expense_tags`

**Filas:** 8  
**Menciones en código:** 22  
**Archivos que la usan:** 2  
**Queries SQL:** 6 (SELECT: 4, INSERT: 1, UPDATE: 1)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T1=8  
**Rango de fechas:** 2025-09-25 21:36:27 → 2025-09-25 21:36:27  
**Archivos:**  
  - `core/api_models.py`  
  - `core/unified_db_adapter.py`  

#### `pdf_extraction_audit`

**Filas:** 82  
**Menciones en código:** 11  
**Archivos que la usan:** 1  
**Queries SQL:** 6 (SELECT: 3, INSERT: 1, UPDATE: 2)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T1=12, T3=53, T4=17  
**Rango de fechas:** 2025-09-29 01:04:25 → 2025-09-30 16:42:19  
**Archivos:**  
  - `core/extraction_audit_logger.py`  

#### `user_category_preferences`

**Filas:** 1  
**Menciones en código:** 9  
**Archivos que la usan:** 2  
**Queries SQL:** 7 (SELECT: 5, INSERT: 1, UPDATE: 1)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T1=1  
**Rango de fechas:** 2025-09-26 05:30:29 → 2025-09-26 05:30:29  
**Archivos:**  
  - `core/category_learning_system.py`  
  - `core/unified_db_adapter.py`  

#### `user_payment_accounts`

**Filas:** 14  
**Menciones en código:** 10  
**Archivos que la usan:** 3  
**Queries SQL:** 9 (SELECT: 6, INSERT: 1, UPDATE: 2)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T3=11, T4=3  
**Rango de fechas:** 2025-09-27 17:04:48 → 2025-09-30 17:35:51  
**Archivos:**  
  - `api/payment_accounts_api.py`  
  - `core/payment_accounts_models.py`  
  - `core/bank_statements_models.py`  

#### `users`

**Filas:** 9  
**Menciones en código:** 91  
**Archivos que la usan:** 10  
**Queries SQL:** 42 (SELECT: 30, INSERT: 4, UPDATE: 8)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T1=3, T2=1, T3=1, T4=1, TNone=3  
**Rango de fechas:** 2025-09-25 17:03:55 → 2025-10-03 05:13:24  
**Archivos:**  
  - `core/internal_db.py`  
  - `modules/invoicing_agent/playwright_automation_engine.py`  
  - `core/tenancy_middleware.py`  
  - `modules/invoicing_agent/api.py`  
  - `api/auth_jwt_api.py`  
  - ... y 5 más  


### 🏷️ ACTIVE_NO_TENANT (10 tablas)

#### `access_log`

**Filas:** 3  
**Menciones en código:** 3  
**Archivos que la usan:** 1  
**Queries SQL:** 0 (SELECT: 0, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ❌ No  
**Archivos:**  
  - `core/security_vault.py`  

#### `automation_logs`

**Filas:** 1,259  
**Menciones en código:** 6  
**Archivos que la usan:** 3  
**Queries SQL:** 3 (SELECT: 2, INSERT: 1, UPDATE: 0)  
**Multi-tenant:** ❌ No  
**Archivos:**  
  - `modules/invoicing_agent/automation_persistence.py`  
  - `api/automation_v2.py`  
  - `core/playwright_executor.py`  

#### `banking_institutions`

**Filas:** 30  
**Menciones en código:** 4  
**Archivos que la usan:** 2  
**Queries SQL:** 1 (SELECT: 1, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ❌ No  
**Rango de fechas:** 2025-09-27 23:36:41 → 2025-09-27 23:36:41  
**Archivos:**  
  - `core/payment_accounts_models.py`  
  - `api/payment_accounts_api.py`  

#### `missing_transactions_log`

**Filas:** 31,859  
**Menciones en código:** 5  
**Archivos que la usan:** 1  
**Queries SQL:** 3 (SELECT: 1, INSERT: 1, UPDATE: 1)  
**Multi-tenant:** ❌ No  
**Rango de fechas:** 2025-09-29 01:11:09 → 2025-09-30 16:42:20  
**Archivos:**  
  - `core/extraction_audit_logger.py`  

#### `permissions`

**Filas:** 11  
**Menciones en código:** 27  
**Archivos que la usan:** 8  
**Queries SQL:** 2 (SELECT: 2, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ❌ No  
**Rango de fechas:** 2025-10-03 05:13:24 → 2025-10-03 05:13:24  
**Archivos:**  
  - `core/auth_jwt.py`  
  - `core/unified_auth.py`  
  - `core/whatsapp_integration.py`  
  - `core/web_automation_engine_system.py`  
  - `core/security_middleware.py`  
  - ... y 3 más  

#### `refresh_tokens`

**Filas:** 127  
**Menciones en código:** 3  
**Archivos que la usan:** 1  
**Queries SQL:** 3 (SELECT: 1, INSERT: 1, UPDATE: 1)  
**Multi-tenant:** ❌ No  
**Rango de fechas:** 2025-09-25 21:19:37 → 2025-10-03 05:49:11  
**Archivos:**  
  - `core/unified_auth.py`  

#### `schema_migrations`

**Filas:** 11  
**Menciones en código:** 2  
**Archivos que la usan:** 1  
**Queries SQL:** 0 (SELECT: 0, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ❌ No  
**Archivos:**  
  - `core/internal_db.py`  

#### `schema_versions`

**Filas:** 9  
**Menciones en código:** 6  
**Archivos que la usan:** 2  
**Queries SQL:** 3 (SELECT: 2, INSERT: 1, UPDATE: 0)  
**Multi-tenant:** ❌ No  
**Archivos:**  
  - `core/internal_db.py`  
  - `core/unified_db_adapter.py`  

#### `tenants`

**Filas:** 4  
**Menciones en código:** 36  
**Archivos que la usan:** 6  
**Queries SQL:** 8 (SELECT: 6, INSERT: 2, UPDATE: 0)  
**Multi-tenant:** ❌ No  
**Rango de fechas:** 2025-09-25 16:44:02 → 2025-09-30 03:01:32  
**Archivos:**  
  - `core/unified_auth.py`  
  - `core/unified_db_adapter.py`  
  - `core/multi_tenancy_scaling.py`  
  - `core/auth_system.py`  
  - `modules/invoicing_agent/api.py`  
  - ... y 1 más  

#### `validation_issues_log`

**Filas:** 245  
**Menciones en código:** 3  
**Archivos que la usan:** 1  
**Queries SQL:** 1 (SELECT: 0, INSERT: 1, UPDATE: 0)  
**Multi-tenant:** ❌ No  
**Rango de fechas:** 2025-09-29 01:11:09 → 2025-09-30 16:42:20  
**Archivos:**  
  - `core/extraction_audit_logger.py`  


### 🏷️ DEFINED_NO_DATA (18 tablas)

#### `automation_screenshots`

**Filas:** 0  
**Menciones en código:** 17  
**Archivos que la usan:** 10  
**Queries SQL:** 4 (SELECT: 3, INSERT: 1, UPDATE: 0)  
**Multi-tenant:** ❌ No  
**Archivos:**  
  - `modules/invoicing_agent/automation_persistence.py`  
  - `core/rpa_automation_engine_system.py`  
  - `modules/invoicing_agent/universal_invoice_engine.py`  
  - `modules/invoicing_agent/robust_automation_engine.py`  
  - `modules/invoicing_agent/playwright_simple_engine.py`  
  - ... y 5 más  

#### `automation_sessions`

**Filas:** 0  
**Menciones en código:** 20  
**Archivos que la usan:** 5  
**Queries SQL:** 0 (SELECT: 0, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ❌ No  
**Archivos:**  
  - `core/rpa_automation_engine_system.py`  
  - `api/robust_automation_engine_api.py`  
  - `core/web_automation_engine_system.py`  
  - `core/api_models.py`  
  - `core/robust_automation_engine_system.py`  

#### `bank_reconciliation_feedback`

**Filas:** 0  
**Menciones en código:** 1  
**Archivos que la usan:** 1  
**Queries SQL:** 1 (SELECT: 0, INSERT: 1, UPDATE: 0)  
**Multi-tenant:** ✅ Sí  
**Archivos:**  
  - `core/unified_db_adapter.py`  

#### `category_learning`

**Filas:** 0  
**Menciones en código:** 7  
**Archivos que la usan:** 1  
**Queries SQL:** 6 (SELECT: 4, INSERT: 1, UPDATE: 1)  
**Multi-tenant:** ❌ No  
**Archivos:**  
  - `core/category_learning_system.py`  

#### `category_learning_metrics`

**Filas:** 0  
**Menciones en código:** 6  
**Archivos que la usan:** 1  
**Queries SQL:** 6 (SELECT: 4, INSERT: 1, UPDATE: 1)  
**Multi-tenant:** ✅ Sí  
**Archivos:**  
  - `core/category_learning_system.py`  

#### `category_prediction_history`

**Filas:** 0  
**Menciones en código:** 4  
**Archivos que la usan:** 1  
**Queries SQL:** 4 (SELECT: 2, INSERT: 1, UPDATE: 1)  
**Multi-tenant:** ✅ Sí  
**Archivos:**  
  - `core/unified_db_adapter.py`  

#### `duplicate_detection`

**Filas:** 0  
**Menciones en código:** 7  
**Archivos que la usan:** 1  
**Queries SQL:** 4 (SELECT: 2, INSERT: 1, UPDATE: 1)  
**Multi-tenant:** ❌ No  
**Archivos:**  
  - `core/unified_db_adapter.py`  

#### `duplicate_detections`

**Filas:** 0  
**Menciones en código:** 3  
**Archivos que la usan:** 1  
**Queries SQL:** 3 (SELECT: 1, INSERT: 1, UPDATE: 1)  
**Multi-tenant:** ✅ Sí  
**Archivos:**  
  - `core/unified_db_adapter.py`  

#### `expense_attachments`

**Filas:** 0  
**Menciones en código:** 1  
**Archivos que la usan:** 1  
**Queries SQL:** 0 (SELECT: 0, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ❌ No  
**Archivos:**  
  - `core/api_models.py`  

#### `expense_invoices`

**Filas:** 0  
**Menciones en código:** 25  
**Archivos que la usan:** 3  
**Queries SQL:** 13 (SELECT: 7, INSERT: 4, UPDATE: 2)  
**Multi-tenant:** ✅ Sí  
**Archivos:**  
  - `core/db_optimizer.py`  
  - `core/internal_db.py`  
  - `core/unified_db_adapter.py`  

#### `expense_ml_features`

**Filas:** 0  
**Menciones en código:** 4  
**Archivos que la usan:** 1  
**Queries SQL:** 1 (SELECT: 1, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ✅ Sí  
**Archivos:**  
  - `core/unified_db_adapter.py`  

#### `expense_tag_relations`

**Filas:** 0  
**Menciones en código:** 11  
**Archivos que la usan:** 2  
**Queries SQL:** 9 (SELECT: 8, INSERT: 1, UPDATE: 0)  
**Multi-tenant:** ❌ No  
**Archivos:**  
  - `core/internal_db.py`  
  - `core/unified_db_adapter.py`  

#### `gpt_usage_events`

**Filas:** 0  
**Menciones en código:** 7  
**Archivos que la usan:** 2  
**Queries SQL:** 5 (SELECT: 3, INSERT: 2, UPDATE: 0)  
**Multi-tenant:** ✅ Sí  
**Archivos:**  
  - `core/unified_db_adapter.py`  
  - `core/cost_analytics.py`  

#### `system_health`

**Filas:** 0  
**Menciones en código:** 29  
**Archivos que la usan:** 7  
**Queries SQL:** 0 (SELECT: 0, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ❌ No  
**Archivos:**  
  - `modules/invoicing_agent/services/__init__.py`  
  - `api/robust_automation_engine_api.py`  
  - `modules/invoicing_agent/integration_layer.py`  
  - `modules/invoicing_agent/services/orchestrator.py`  
  - `modules/invoicing_agent/fastapi_integration.py`  
  - ... y 2 más  

#### `tickets`

**Filas:** 0  
**Menciones en código:** 223  
**Archivos que la usan:** 10  
**Queries SQL:** 17 (SELECT: 11, INSERT: 2, UPDATE: 4)  
**Multi-tenant:** ✅ Sí  
**Archivos:**  
  - `modules/invoicing_agent/services/__init__.py`  
  - `core/internal_db.py`  
  - `core/service_stack_config.py`  
  - `modules/invoicing_agent/queue_manager.py`  
  - `api/automation_v2.py`  
  - ... y 5 más  

#### `user_preferences`

**Filas:** 0  
**Menciones en código:** 17  
**Archivos que la usan:** 5  
**Queries SQL:** 0 (SELECT: 0, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ❌ No  
**Archivos:**  
  - `core/category_learning_system.py`  
  - `core/unified_db_adapter.py`  
  - `core/expense_completion_system.py`  
  - `core/api_models.py`  
  - `api/expense_completion_api.py`  

#### `user_sessions`

**Filas:** 0  
**Menciones en código:** 3  
**Archivos que la usan:** 2  
**Queries SQL:** 3 (SELECT: 1, INSERT: 1, UPDATE: 1)  
**Multi-tenant:** ❌ No  
**Archivos:**  
  - `core/auth_jwt.py`  
  - `api/auth_jwt_api.py`  

#### `workers`

**Filas:** 0  
**Menciones en código:** 87  
**Archivos que la usan:** 8  
**Queries SQL:** 0 (SELECT: 0, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ❌ No  
**Archivos:**  
  - `core/bulk_invoice_processor.py`  
  - `core/worker_system.py`  
  - `core/idempotent_workers.py`  
  - `modules/invoicing_agent/queue_manager.py`  
  - `modules/invoicing_agent/services/orchestrator.py`  
  - ... y 3 más  


### 🏷️ LEGACY_DATA (1 tablas)

#### `bank_movements_backup_20250928`

**Filas:** 75  
**Menciones en código:** 0  
**Archivos que la usan:** 0  
**Queries SQL:** 0 (SELECT: 0, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ✅ Sí  
**Distribución por tenant:** T3=75  
**Rango de fechas:** 2025-09-28 18:45:22 → 2025-09-28 18:45:22  


### 🏷️ UNUSED (2 tablas)

#### `analytics_cache`

**Filas:** 0  
**Menciones en código:** 0  
**Archivos que la usan:** 0  
**Queries SQL:** 0 (SELECT: 0, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ❌ No  

#### `invoice_match_history`

**Filas:** 0  
**Menciones en código:** 0  
**Archivos que la usan:** 0  
**Queries SQL:** 0 (SELECT: 0, INSERT: 0, UPDATE: 0)  
**Multi-tenant:** ✅ Sí  


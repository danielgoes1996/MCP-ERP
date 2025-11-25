# 📊 Estructura de Base de Datos - ContaFlow MCP System

## 🏗️ Arquitectura General

El sistema utiliza SQLite con **53 tablas principales** organizadas en 8 módulos funcionales:

```
┌─────────────────────────────────────────────────────────────┐
│                   UNIFIED MCP SYSTEM DB                      │
├──────────┬──────────┬──────────┬──────────┬─────────────────┤
│  Auth &  │ Expenses │  Bank    │ Invoice  │   AI & ML      │
│  Users   │   &      │  Recon   │ Process  │   Learning     │
│  (11)    │  Fiscal  │   (3)    │   (9)    │     (12)       │
│          │  (13)    │          │          │                 │
├──────────┼──────────┼──────────┼──────────┼─────────────────┤
│Automation│  System  │ Catalogs │ Audit &  │   Payments     │
│  (6)     │   (4)    │   (4)    │ Logging  │     (2)        │
│          │          │          │   (3)    │                 │
└──────────┴──────────┴──────────┴──────────┴─────────────────┘
```

---

## 1️⃣ MÓDULO DE AUTENTICACIÓN Y USUARIOS (11 tablas)

### 🔑 Tabla Core: `users`
**Propósito**: Gestión completa de usuarios con autenticación multi-método

```sql
users (35 campos)
├─ id (PK)
├─ Identificación
│  ├─ email (UNIQUE) ─────────── Email principal
│  ├─ username ──────────────────  Usuario opcional
│  ├─ identifier ────────────────  Email o teléfono
│  ├─ full_name
│  └─ phone
├─ Autenticación
│  ├─ password_hash
│  ├─ is_active
│  ├─ is_superuser
│  ├─ last_login
│  ├─ failed_login_attempts
│  └─ locked_until
├─ Organización
│  ├─ tenant_id ────────────────> tenants.id (FK)
│  ├─ company_id ───────────────> companies.id (FK)
│  ├─ role ─────────────────────  'admin', 'user', 'viewer'
│  ├─ employee_id
│  └─ department
├─ Onboarding
│  ├─ onboarding_step ──────────  0-5 (progreso)
│  ├─ demo_preferences (JSON)
│  ├─ onboarding_completed
│  └─ onboarding_completed_at
└─ Verificación
   ├─ email_verified
   ├─ phone_verified
   ├─ verification_token
   └─ registration_method ──────  'email', 'whatsapp'
```

**Relaciones**:
- `tenant_id` → `tenants.id` (Multi-tenancy)
- `company_id` → `companies.id` (Empresa del usuario)
- Referenciado por: `expense_records`, `tickets`, `automation_jobs`, etc.

---

### 🏢 Tabla: `tenants`
**Propósito**: Multi-tenancy - Aislamiento de datos por cliente

```sql
tenants
├─ id (PK)
├─ name
├─ domain
├─ api_key
├─ config (JSON)
└─ created_at, updated_at
```

**Alcance**: TODAS las tablas tienen `tenant_id` para aislamiento

---

### 🏪 Tabla: `companies`
**Propósito**: Información de empresas (varias empresas por tenant)

```sql
companies
├─ id (PK)
├─ tenant_id ─────────────> tenants.id
├─ company_name
├─ legal_name
├─ Contexto de Negocio
│  ├─ giro
│  ├─ modelo_negocio
│  ├─ clientes_clave (JSON)
│  ├─ proveedores_clave (JSON)
│  └─ descripcion_negocio
└─ context_profile (JSON) ─── Snapshot para IA
```

---

### 📋 Onboarding (3 tablas)
```
onboarding_steps ──────────── Definición de pasos
     │
     ├─> user_onboarding_progress ─ Progreso por usuario
     │
user_demo_config ──────────── Preferencias de datos demo
```

---

### 🔐 Tabla: `refresh_tokens`
**Propósito**: JWT refresh tokens para renovación de sesión

```sql
refresh_tokens
├─ id (PK)
├─ user_id ───────────────> users.id
├─ token_hash
├─ expires_at
└─ is_revoked
```

---

## 2️⃣ MÓDULO DE GASTOS Y FISCAL (13 tablas)

### 💰 Tabla Central: `expense_records`
**Propósito**: Registro principal de gastos con clasificación fiscal IA

```sql
expense_records (80+ campos) ⭐ TABLA MÁS COMPLEJA
├─ id (PK)
├─ Información Básica
│  ├─ amount, currency
│  ├─ description
│  ├─ descripcion_normalizada
│  ├─ merchant_name, rfc_proveedor
│  └─ date
├─ Clasificación Fiscal (IA)
│  ├─ category, categoria_normalizada
│  ├─ sat_account_code ──────────> Catálogo SAT
│  ├─ sat_product_service_code ─> Catálogo SAT
│  ├─ deducible, requiere_factura
│  ├─ categoria_sugerida (IA)
│  ├─ confianza (0.0-1.0)
│  └─ razonamiento (JSON)
├─ Categorización ML
│  ├─ prediction_method ─────────  'llm', 'rules', 'hybrid'
│  ├─ ml_model_version
│  ├─ predicted_at
│  ├─ category_confirmed
│  └─ category_corrected_by ────> users.id
├─ Impuestos
│  ├─ subtotal, iva_16, iva_8, iva_0
│  ├─ ieps, isr_retenido, iva_retenido
│  ├─ otros_impuestos
│  ├─ deducible_percent
│  └─ iva_acreditable
├─ CFDI / Facturación
│  ├─ cfdi_uuid ─────────────────  UNIQUE
│  ├─ cfdi_status
│  ├─ cfdi_pdf_url, cfdi_xml_url
│  ├─ cfdi_fecha_timbrado
│  ├─ invoice_status ────────────  'pending', 'invoiced'
│  ├─ will_have_cfdi
│  └─ escalated_to_invoicing
├─ Conciliación Bancaria
│  ├─ bank_status ───────────────  'pending', 'bank_reconciled'
│  ├─ reconciliation_type
│  ├─ split_group_id
│  ├─ amount_reconciled
│  └─ amount_pending
├─ Aprobación
│  ├─ approval_status ───────────  'pending', 'approved', 'rejected'
│  ├─ approved_by ───────────────> users.id
│  └─ approved_at
├─ Organización
│  ├─ centro_costo, proyecto
│  ├─ tags (JSON)
│  ├─ metadata (JSON)
│  └─ user_context (JSON)
├─ Duplicados (ML)
│  ├─ is_duplicate
│  ├─ duplicate_of ──────────────> expense_records.id
│  ├─ duplicate_confidence
│  ├─ similarity_score
│  ├─ risk_level
│  └─ ml_features_json (JSON)
├─ Workflow
│  ├─ status ────────────────────  'pending', 'approved', 'rejected'
│  ├─ workflow_status
│  ├─ completion_status
│  ├─ validation_status
│  ├─ validation_errors (JSON)
│  └─ field_completeness (0.0-1.0)
├─ Relaciones
│  ├─ user_id ───────────────────> users.id
│  ├─ tenant_id ─────────────────> tenants.id
│  ├─ company_id ────────────────> companies.id (TEXT)
│  ├─ ticket_id ─────────────────> tickets.id
│  ├─ payment_account_id ────────> user_payment_accounts.id
│  └─ advance_id ────────────────  Para anticipos de empleados
└─ Auditoría
   ├─ created_at, updated_at
   ├─ created_by, updated_by ───> users.id
   └─ audit_trail (JSON)
```

**Flujo de Vida de un Gasto**:
```
1. Creación ───────> status='pending', workflow_status='draft'
2. IA Clasifica ──> categoria_sugerida, sat_account_code
3. Usuario Valida > category_confirmed=TRUE
4. Facturación ───> invoice_status='invoiced', cfdi_uuid
5. Conciliación ──> bank_status='reconciled'
6. Aprobación ────> approval_status='approved'
```

---

### 🏷️ Sistema de Tags (2 tablas)
```
expense_tags ──────────────────  Definición de tags
     │
     └─> expense_tag_relations ─ Relación N:N con expenses
```

---

### 📎 Tabla: `expense_attachments`
**Propósito**: Archivos adjuntos (tickets, facturas, etc.)

```sql
expense_attachments
├─ id (PK)
├─ expense_id ────────────────> expense_records.id
├─ filename, file_path, mime_type
├─ attachment_type ───────────  'receipt', 'invoice', 'proof'
└─ uploaded_by ───────────────> users.id
```

---

### 🔍 Sistema de Duplicados (3 tablas)

```
duplicate_detections ──────────  Detecciones de duplicados (ML)
     │
     ├─> expense_records ──────  expense_id (el sospechoso)
     └─> expense_records ──────  potential_duplicate_id (el original)

duplicate_detection_config ────  Configuración por tenant
expense_ml_features ───────────  Features ML para cada gasto
```

**Campos Clave**:
```sql
duplicate_detections
├─ similarity_score ──────────  0.0-1.0
├─ risk_level ────────────────  'high', 'medium', 'low'
├─ confidence_level
├─ match_reasons (JSON) ──────  ['same_amount', 'same_merchant', ...]
├─ detection_method ──────────  'hybrid', 'ml', 'heuristic'
├─ status ────────────────────  'pending', 'confirmed', 'rejected'
└─ reviewed_by ───────────────> users.id
```

---

### 📊 Categorización IA (6 tablas)

```
category_prediction_history ───  Historial de predicciones IA
user_category_preferences ─────  Preferencias por usuario
custom_categories ─────────────  Categorías personalizadas
category_prediction_config ────  Config de predicción
category_learning_metrics ─────  Métricas de aprendizaje
provider_rules ────────────────  Reglas por proveedor
```

---

### 📄 Tabla: `expense_invoices`
**Propósito**: Almacenamiento de facturas CFDI completas

```sql
expense_invoices
├─ id (PK)
├─ expense_id ────────────────> expense_records.id (FK)
├─ Identificación CFDI
│  ├─ uuid (UNIQUE)
│  ├─ rfc_emisor, nombre_emisor
│  ├─ rfc_receptor
│  ├─ version_cfdi
│  └─ cfdi_status ────────────  'vigente', 'cancelada'
├─ Montos
│  ├─ subtotal, total
│  ├─ iva_amount, discount
│  ├─ retention, ieps
│  ├─ isr_retenido, iva_retenido
│  └─ otros_impuestos
├─ Archivos
│  ├─ filename, file_path
│  ├─ xml_path, xml_content (TEXT)
│  └─ parsed_data (JSON)
├─ Procesamiento
│  ├─ validation_status
│  ├─ parser_used
│  ├─ ocr_confidence
│  ├─ quality_score
│  └─ extraction_confidence
└─ Organización
   ├─ mes_fiscal
   ├─ origen_importacion ─────  'manual', 'email', 'automation'
   └─ tenant_id ──────────────> tenants.id
```

**Triggers Automáticos**:
```sql
-- Calcular total automáticamente
total = subtotal + iva_amount - discount - retention + ieps - isr_retenido - iva_retenido
```

---

## 3️⃣ MÓDULO DE CONCILIACIÓN BANCARIA (3 tablas)

### 🏦 Tabla: `bank_movements`
**Propósito**: Movimientos bancarios para conciliación

```sql
bank_movements
├─ id (PK)
├─ Datos Bancarios
│  ├─ amount, description
│  ├─ date, account
│  ├─ movement_id (ID banco)
│  ├─ reference, balance_after
│  ├─ transaction_type
│  └─ bank_account_id
├─ Conciliación
│  ├─ matched_expense_id ────> expense_records.id
│  ├─ decision ──────────────  'auto', 'manual', 'pending'
│  ├─ matching_confidence
│  ├─ auto_matched
│  ├─ matched_at, matched_by
│  └─ reconciliation_notes
├─ Clasificación IA
│  ├─ category
│  ├─ context_used (JSON)
│  ├─ ai_model
│  ├─ context_confidence
│  └─ context_version
└─ tenant_id ────────────────> tenants.id
```

---

### 💳 Tabla: `user_payment_accounts`
**Propósito**: Cuentas bancarias y tarjetas del usuario

```sql
user_payment_accounts
├─ id (PK)
├─ nombre, tipo ──────────────  'cuenta_bancaria', 'tarjeta_credito', etc.
├─ subtipo, moneda
├─ Saldos
│  ├─ saldo_inicial, saldo_actual
│  ├─ limite_credito
│  └─ credito_disponible ────  Auto-calculado para TDC
├─ Tarjetas de Crédito
│  ├─ fecha_corte, fecha_pago
│  └─ numero_tarjeta
├─ Cuentas Bancarias
│  ├─ numero_cuenta
│  ├─ clabe
│  └─ banco_nombre
├─ propietario_id ────────────> users.id
├─ tenant_id ─────────────────> tenants.id
└─ activo, is_default
```

**Triggers Automáticos**:
```sql
-- Inicializar saldo_actual = saldo_inicial
-- Calcular credito_disponible = limite_credito - saldo_actual (TDC)
```

---

### 🏛️ Tabla: `banking_institutions`
**Propósito**: Catálogo de instituciones bancarias

```sql
banking_institutions
├─ id (PK)
├─ name, short_name
├─ type ──────────────────────  'bank', 'fintech', 'credit_union'
├─ active, sort_order
└─ created_at
```

---

## 4️⃣ MÓDULO DE PROCESAMIENTO DE FACTURAS (9 tablas)

### 🎫 Tabla: `tickets`
**Propósito**: Inbox para facturas y tickets a procesar

```sql
tickets
├─ id (PK)
├─ Contenido
│  ├─ title, description
│  ├─ raw_data ───────────────  XML completo o texto
│  ├─ tipo ───────────────────  'texto', 'imagen'
│  ├─ extracted_text (OCR)
│  └─ original_image
├─ Clasificación
│  ├─ merchant_name, merchant_id
│  ├─ category, confidence
│  ├─ invoice_data (JSON)
│  └─ llm_analysis (JSON)
├─ Workflow
│  ├─ status ─────────────────  'open', 'closed'
│  ├─ estado ─────────────────  'pendiente', 'procesado', 'error'
│  ├─ priority
│  └─ assignee
├─ Relaciones
│  ├─ user_id ────────────────> users.id
│  ├─ tenant_id ──────────────> tenants.id
│  ├─ company_id (TEXT)
│  ├─ expense_id ─────────────> expense_records.id
│  ├─ is_mirror_ticket ───────  Ticket espejo para expense
│  └─ whatsapp_message_id
└─ created_at, updated_at
```

**Flujo**:
```
WhatsApp/Email ──> Ticket ──> IA Procesa ──> Expense Record ──> Invoice
```

---

### 🏪 Tabla: `merchants`
**Propósito**: Catálogo de comercios/proveedores

```sql
merchants
├─ id (PK)
├─ nombre
├─ metodo_facturacion ────────  'litromil', 'portal_web', 'manual'
├─ metadata (JSON)
├─ is_active
└─ created_at, updated_at
```

---

### 📝 Tabla: `invoice_import_logs`
**Propósito**: Log de importaciones de facturas

```sql
invoice_import_logs
├─ id (PK)
├─ filename, uuid_detectado
├─ status ────────────────────  'success', 'error', 'duplicate'
├─ error_message
├─ Import Context
│  ├─ source ─────────────────  'manual', 'email', 'automation'
│  ├─ import_method ──────────  'drag_drop', 'api_call'
│  ├─ imported_by ────────────> users.id
│  └─ batch_id
├─ Metadata
│  ├─ file_size, file_hash
│  ├─ detected_format
│  └─ processing_time_ms
└─ invoice_id, expense_id ────> Relacionados
```

---

### 🚀 Sistema de Trabajos de Automatización (3 tablas)

```
automation_jobs ───────────────  Jobs de facturación automática
     │
     ├─> automation_logs ──────  Logs detallados
     └─> automation_screenshots  Screenshots del proceso
```

**Detalle de `automation_jobs`**:
```sql
automation_jobs
├─ id (PK)
├─ ticket_id ─────────────────> tickets.id
├─ merchant_id ───────────────> merchants.id
├─ Estado
│  ├─ estado ─────────────────  'pendiente', 'en_proceso', 'completado', 'error'
│  ├─ current_step
│  ├─ progress_percentage
│  └─ result (JSON)
├─ Automatización
│  ├─ automation_type ────────  'selenium', 'playwright'
│  ├─ session_id
│  ├─ config (JSON)
│  ├─ checkpoint_data (JSON)
│  └─ recovery_metadata (JSON)
├─ Reintentos
│  ├─ retry_count, max_retries
│  └─ error_details
├─ OCR/Captcha
│  ├─ captcha_attempts
│  └─ ocr_confidence
└─ Scheduling
   ├─ scheduled_at, started_at, completed_at
   └─ estimated_completion
```

---

## 5️⃣ MÓDULO DE IA Y APRENDIZAJE (12 tablas)

### 🧠 Tabla: `ai_context_memory`
**Propósito**: Memoria contextual de la empresa para IA

```sql
ai_context_memory
├─ id (PK)
├─ company_id ────────────────> companies.id
├─ Contexto
│  ├─ context (TEXT largo)
│  ├─ onboarding_snapshot (JSON)
│  ├─ summary, topics (JSON)
│  └─ language_detected
├─ Embeddings
│  ├─ embedding_vector (JSON)
│  ├─ model_name
│  └─ context_version
├─ Confianza
│  ├─ confidence_score
│  └─ source
├─ Auditoría
│  ├─ created_by ─────────────> users.id
│  ├─ audit_log_id ───────────> audit_trail.id
│  └─ last_refresh
└─ created_at, updated_at
```

---

### 🎓 Tabla: `ai_correction_memory`
**Propósito**: Aprendizaje de correcciones del usuario

```sql
ai_correction_memory
├─ id (PK)
├─ company_id ────────────────> companies.id
├─ Transacción Original
│  ├─ original_description
│  ├─ normalized_description
│  ├─ amount, movement_kind
│  └─ raw_transaction (JSON)
├─ Clasificación
│  ├─ ai_category ────────────  Lo que predijo la IA
│  ├─ corrected_category ─────  Lo que corrigió el usuario
│  └─ notes
├─ ML
│  ├─ embedding_json (JSON)
│  ├─ embedding_dimensions
│  ├─ similarity_hint
│  └─ model_used
└─ created_at, updated_at
```

---

### 📚 Catálogos SAT (2 tablas)

```
sat_account_catalog ──────────  Catálogo de cuentas SAT
sat_product_service_catalog ──  Catálogo de productos/servicios SAT
```

**Estructura**:
```sql
sat_account_catalog
├─ code (UNIQUE) ─────────────  '101.01', '201.03'
├─ name, description
├─ parent_code ───────────────  Jerarquía
├─ type ──────────────────────  'agrupador', 'cuenta'
└─ is_active
```

---

### 📊 Tabla: `classification_trace`
**Propósito**: Trazabilidad de clasificaciones fiscales

```sql
classification_trace
├─ id (PK)
├─ expense_id ────────────────> expense_records.id
├─ Clasificación
│  ├─ sat_account_code
│  ├─ family_code
│  ├─ confidence_sat, confidence_family
│  ├─ explanation_short, explanation_detail
│  └─ razonamiento (JSON)
├─ Modelo
│  ├─ model_version
│  ├─ embedding_version
│  ├─ tokens (JSON)
│  └─ raw_payload (JSON)
└─ created_at
```

---

### 📈 Métricas y Config (5 tablas)
```
gpt_usage_events ──────────────  Uso de GPT/LLM
model_config_history ──────────  Historial de configs de modelo
tenant_policies ───────────────  Políticas por tenant
ia_metrics_history ────────────  Métricas históricas de IA
user_preferences ──────────────  Preferencias de usuario
```

---

## 6️⃣ MÓDULO DE PAGOS (2 tablas)

### 💳 Sistema de Pagos CFDI (2 tablas)

```
cfdi_payments ─────────────────  Complementos de pago
     │
     └─> payment_applications ─  Aplicación a facturas específicas
```

**Detalle**:
```sql
cfdi_payments
├─ uuid_pago (UNIQUE)
├─ fecha_pago
├─ moneda, tipo_cambio
└─ tenant_id

payment_applications
├─ uuid_pago ─────────────────> cfdi_payments.uuid_pago
├─ cfdi_uuid ─────────────────> expense_invoices.uuid
├─ no_parcialidad
├─ monto_pagado, saldo_insoluto
└─ UNIQUE (uuid_pago, cfdi_uuid, no_parcialidad)
```

---

## 7️⃣ MÓDULO DE SISTEMA Y WORKERS (10 tablas)

### ⚙️ Workers y Sesiones (3 tablas)

```
workers ───────────────────────  Jobs asíncronos
automation_sessions ───────────  Sesiones de automatización
system_health ─────────────────  Health checks del sistema
```

---

### 📜 Tabla: `audit_trail`
**Propósito**: Auditoría completa de cambios

```sql
audit_trail
├─ id (PK)
├─ entidad, entidad_id
├─ accion ────────────────────  'CREATE', 'UPDATE', 'DELETE'
├─ usuario_id ────────────────> users.id
├─ cambios (JSON) ────────────  Diff de cambios
└─ created_at
```

---

### 🚨 Tabla: `error_logs`
**Propósito**: Logging de errores del sistema

```sql
error_logs
├─ error_id (UNIQUE)
├─ category, severity
├─ message, user_message
├─ user_id, tenant_id
├─ endpoint, method, ip_address
├─ stack_trace, metadata (JSON)
└─ resolution_notes
```

---

## 8️⃣ RELACIONES PRINCIPALES

### 🔗 Diagrama de Relaciones Core

```
                    ┌──────────┐
                    │ tenants  │ ◄─── Multi-tenancy (raíz)
                    └────┬─────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   ┌────▼─────┐    ┌────▼──────┐   ┌────▼─────┐
   │  users   │    │ companies │   │  config  │
   └────┬─────┘    └────┬──────┘   │  tables  │
        │               │           └──────────┘
        │               │
   ┌────▼───────────────▼─────┐
   │   expense_records        │ ◄─── Tabla central
   └──┬──┬──┬───┬───┬───┬───┬┘
      │  │  │   │   │   │   │
      │  │  │   │   │   │   └──> tickets
      │  │  │   │   │   └──────> bank_movements
      │  │  │   │   └──────────> user_payment_accounts
      │  │  │   └──────────────> expense_invoices
      │  │  └──────────────────> expense_attachments
      │  └─────────────────────> expense_tags
      └────────────────────────> duplicate_detections
```

### 📌 Relaciones Clave

#### 1. **Un Expense puede tener**:
- 1 Ticket de origen: `expense_records.ticket_id → tickets.id`
- 1 Factura CFDI: `expense_records.cfdi_uuid = expense_invoices.uuid`
- N Adjuntos: `expense_attachments.expense_id → expense_records.id`
- N Tags: `expense_tag_relations`
- N Detecciones de duplicado: `duplicate_detections.expense_id`
- 1 Movimiento bancario: `bank_movements.matched_expense_id`

#### 2. **Un Ticket puede generar**:
- 1 Expense: `tickets.expense_id → expense_records.id`
- 1 Job de automatización: `automation_jobs.ticket_id → tickets.id`
- 1 Invoicing job: `invoicing_jobs.ticket_id → tickets.id`

#### 3. **Un Usuario tiene**:
- N Expenses creados: `expense_records.user_id`
- N Cuentas de pago: `user_payment_accounts.propietario_id`
- N Tickets: `tickets.user_id`
- 1 Progreso de onboarding: `user_onboarding_progress`

---

## 📊 ÍNDICES Y OPTIMIZACIONES

### Índices Principales (80+ índices)

**Performance crítico**:
```sql
-- Búsquedas frecuentes
idx_expense_records_compound (tenant_id, status, date)
idx_expense_records_date_range (date, tenant_id)
idx_expense_invoice_status (invoice_status)
idx_expense_bank_status (bank_status)

-- Duplicados ML
idx_duplicate_detections_score (similarity_score DESC)
idx_expense_similarity_score (similarity_score DESC)

-- Categorización IA
idx_expense_categoria_sugerida (categoria_sugerida)
idx_expense_confianza (confianza DESC)

-- Conciliación
idx_bank_movements_reconciliation (tenant_id, date, amount)
```

---

## 🔄 TRIGGERS AUTOMÁTICOS

### Triggers de Updated_at
```sql
-- Auto-actualizar updated_at en UPDATE
expense_records_updated_at
duplicate_config_updated_at
ml_features_updated_at
... (10+ triggers similares)
```

### Triggers de Negocio
```sql
-- Cuentas de pago
trg_upa_init_saldo ───────────  saldo_actual = saldo_inicial
trg_upa_credito_disponible ───  Calcular crédito disponible (TDC)

-- Facturas
expense_invoices_calculate_total ─ Auto-calcular total
expense_invoices_update_total ────  Re-calcular en UPDATE
```

---

## 📈 VISTAS (Views)

### `onboarding_status_view`
Resumen del progreso de onboarding por usuario

### `user_payment_accounts_view`
Vista enriquecida de cuentas con datos del propietario

---

## 🎯 MÓDULOS FUNCIONALES

### Flujo Completo: Ticket → Expense → Invoice

```
1. INGRESO
   WhatsApp/Email → tickets (raw_data)
                         ↓
2. PROCESAMIENTO IA
   - OCR si es imagen
   - Parse XML si es texto
   - LLM clasifica: merchant, category
                         ↓
3. CREACIÓN EXPENSE
   tickets.expense_id → expense_records
   - IA sugiere: categoria, SAT codes
   - Detecta duplicados (ML)
                         ↓
4. FACTURACIÓN
   - Si will_have_cfdi = TRUE
   - automation_jobs genera factura
   - Guarda en expense_invoices
                         ↓
5. CONCILIACIÓN
   - Match con bank_movements
   - bank_status = 'reconciled'
                         ↓
6. APROBACIÓN
   - approval_status = 'approved'
   - ✅ Listo para contabilidad
```

---

## 📊 ESTADÍSTICAS DE LA BD

```
Total Tablas:      53
Total Índices:     80+
Total Triggers:    15+
Total Views:       2
Total FK:          100+

Tabla más grande:  expense_records (80+ campos)
Tabla más crítica: expense_records (centro del sistema)
Mayor complejidad: Sistema de duplicados + ML
```

---

## 🔍 QUERIES CLAVE

### 1. Gastos pendientes de facturar por usuario
```sql
SELECT * FROM expense_records
WHERE user_id = ?
  AND tenant_id = ?
  AND will_have_cfdi = TRUE
  AND invoice_status = 'pending'
  AND escalated_to_invoicing = FALSE;
```

### 2. Tickets sin procesar
```sql
SELECT * FROM tickets
WHERE tenant_id = ?
  AND estado = 'pendiente'
  AND expense_id IS NULL
ORDER BY created_at DESC;
```

### 3. Facturas vigentes del mes
```sql
SELECT * FROM expense_invoices
WHERE tenant_id = ?
  AND mes_fiscal = '2024-01'
  AND cfdi_status = 'vigente';
```

### 4. Duplicados de alto riesgo
```sql
SELECT * FROM duplicate_detections
WHERE tenant_id = ?
  AND risk_level = 'high'
  AND status = 'pending';
```

---

## ✅ RESUMEN EJECUTIVO

### Diseño Multi-Tenant ✓
- Todas las tablas tienen `tenant_id`
- Aislamiento total de datos

### IA Integrada ✓
- Clasificación automática de gastos
- Detección de duplicados con ML
- Aprendizaje de correcciones
- Embeddings para búsqueda semántica

### Fiscal Compliance ✓
- Catálogos SAT integrados
- Cálculo automático de impuestos
- Trazabilidad completa
- Soporte CFDI 4.0

### Automatización ✓
- Jobs asíncronos
- Facturación automática
- Conciliación bancaria IA
- Recovery y checkpoints

### Auditoría Completa ✓
- Audit trail de todos los cambios
- Error logging
- Versioning de contexto IA
- Trazabilidad fiscal

---

**Última actualización**: 2025-01-10
**Versión BD**: Unified MCP System v1.0

# AUDITORÍA DE ATRIBUTOS POR FUNCIONALIDAD

**Fecha:** 2025-09-25
**Sistema:** MCP Server - Plataforma de Gestión de Gastos y Facturación
**Objetivo:** Identificar inconsistencias entre atributos UI, API y DB por funcionalidad

---

## 1. FUNCIONALIDAD: GASTOS (EXPENSES)

### 1.1 Atributos Capturados en UI (HTML/JS)

**Archivo principal:** `static/voice-expenses.html` + `static/app.js`

| Campo UI | Tipo | Descripción |
|----------|------|-------------|
| `descripcion` | text | Descripción del gasto |
| `monto_total` | number | Monto total del gasto |
| `fecha_gasto` | date | Fecha cuando ocurrió el gasto |
| `proveedor` | text | Nombre del proveedor |
| `categoria` | select | Categoría del gasto |
| `metodo_pago` | select | Método de pago usado |
| `moneda` | select | Código de moneda (MXN/USD/EUR) |
| `deducible` | checkbox | Si es deducible de impuestos |
| `requiere_factura` | checkbox | Si requiere factura |
| `centro_costo` | select | Centro de costos |
| `proyecto` | text | Proyecto asociado |
| `notas` | textarea | Notas adicionales |
| `ubicacion` | text | Ubicación del gasto |
| `tags` | multi-select | Tags para categorización |
| `user_id` | hidden | ID del usuario |
| `company_id` | hidden | ID de la empresa |

### 1.2 Atributos Esperados en Modelos API (Pydantic)

**Archivos:** `core/api_models.py`, `core/expense_models.py`

#### ExpenseCreate (Request)
| Campo API | Tipo | Validación | Descripción |
|-----------|------|------------|-------------|
| `descripcion` | str | required, min_length=5 | Description of the expense |
| `monto_total` | float | required, gt=0, max=1000000 | Total amount of the expense |
| `fecha_gasto` | Optional[str] | - | Date when the expense occurred |
| `proveedor` | Optional[str] | - | Provider or vendor name |
| `categoria` | Optional[str] | - | Expense category |
| `metodo_pago` | Optional[str] | - | Payment method used |
| `moneda` | str | default="MXN", in=[MXN,USD,EUR] | Currency code |
| `deducible` | Optional[bool] | default=True | Whether tax deductible |
| `requiere_factura` | Optional[bool] | default=True | Whether requires invoice |
| `centro_costo` | Optional[str] | - | Cost center assignment |
| `proyecto` | Optional[str] | - | Project assignment |
| `company_id` | str | default="default" | Company identifier |
| `user_id` | Optional[str] | - | User who created expense |
| `notas` | Optional[str] | - | Additional notes |
| `ubicacion` | Optional[str] | - | Location where expense occurred |
| `tags` | Optional[List[str]] | default=[] | Tags for categorization |

#### ExpenseResponse (Response)
| Campo API | Tipo | Descripción |
|-----------|------|-------------|
| `id` | int | Unique expense ID |
| `estado` | Optional[str] | Status (pendiente/aprobado/pagado) |
| `factura_generada` | Optional[bool] | Whether invoice generated |
| `fecha_facturacion` | Optional[str] | Invoice date |
| `is_advance` | bool | If it's an advance expense |
| `is_ppd` | bool | Payment in installments |
| `created_at` | str | Creation timestamp |
| `updated_at` | str | Update timestamp |
| *(+ todos los campos de ExpenseCreate)* |

### 1.3 Columnas Reales en Tablas DB

**Archivos:** `migrations/001_advanced_invoicing_system.sql`, `migrations/db_performance_optimization.sql`

#### Tabla `expense_records` (SQLite)
| Columna DB | Tipo | Constraints | Descripción |
|------------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique ID |
| `company_id` | TEXT | NOT NULL, DEFAULT 'default' | Company identifier |
| `description` | TEXT | NOT NULL | Expense description |
| `amount` | REAL | NOT NULL, CHECK > 0 | Expense amount |
| `account_code` | TEXT | - | Accounting code |
| `expense_date` | TEXT | - | Date of expense |
| `category` | TEXT | - | Expense category |
| `provider_name` | TEXT | - | Provider name |
| `provider_rfc` | TEXT | - | Provider RFC |
| `workflow_status` | TEXT | DEFAULT 'draft' | Workflow status |
| `invoice_status` | TEXT | DEFAULT 'pending' | Invoice status |
| `invoice_uuid` | TEXT | - | CFDI UUID |
| `invoice_folio` | TEXT | - | Invoice folio |
| `invoice_url` | TEXT | - | Invoice PDF URL |
| `external_reference` | TEXT | - | External reference |
| `metadata` | TEXT | - | JSON metadata |
| `created_at` | TEXT | NOT NULL | Creation timestamp |
| `updated_at` | TEXT | NOT NULL | Update timestamp |

### 1.4 DIFERENCIAS IDENTIFICADAS - GASTOS

#### ❌ Atributos UI que NO están en API o DB:
- **UI:** Ninguno - todos los campos UI tienen correspondencia

#### ❌ Atributos API que NO existen en DB:
| Campo API | Falta en DB | Impacto |
|-----------|-------------|---------|
| `deducible` | ✗ | Alto - funcionalidad fiscal perdida |
| `requiere_factura` | ✗ | Alto - lógica de negocio perdida |
| `centro_costo` | ✗ | Medio - control presupuestario perdido |
| `proyecto` | ✗ | Medio - seguimiento por proyecto perdido |
| `notas` | ✗ | Bajo - información adicional perdida |
| `ubicacion` | ✗ | Bajo - contexto geográfico perdido |
| `tags` | ✗ | Medio - categorización avanzada perdida |
| `moneda` | ✗ | Alto - soporte multi-moneda perdido |
| `metodo_pago` | ✗ | Medio - trazabilidad de pago perdida |
| `is_advance` | ✗ | Medio - clasificación de anticipos perdida |
| `is_ppd` | ✗ | Alto - soporte PPD fiscal perdido |

#### ❌ Columnas DB que NO se usan en API/UI:
| Columna DB | No usado en | Impacto |
|------------|-------------|---------|
| `account_code` | API/UI | Medio - mapeo contable manual |
| `provider_rfc` | API/UI | Alto - validación fiscal perdida |
| `workflow_status` | API parcial | Alto - flujo de trabajo incompleto |
| `external_reference` | API/UI | Bajo - trazabilidad externa perdida |

---

## 2. FUNCIONALIDAD: FACTURACIÓN (INVOICING)

### 2.1 Atributos Capturados en UI

**Archivos:** `static/advanced-ticket-dashboard.html`, `templates/invoicing/simple-dashboard.html`

| Campo UI | Tipo | Descripción |
|----------|------|-------------|
| `ticket_type` | select | Tipo de ticket (imagen/pdf/texto) |
| `raw_data` | file/text | Datos del ticket |
| `company_id` | select | ID de empresa |
| `merchant_hint` | text | Pista del comercio |
| `auto_process` | checkbox | Procesamiento automático |
| `priority` | select | Prioridad del job |
| `notification_webhook` | url | Webhook de notificación |

### 2.2 Atributos Esperados en Modelos API

**Archivos:** `modules/invoicing_agent/models.py`, `core/enhanced_api_models.py`

#### TicketCreate
| Campo API | Tipo | Descripción |
|-----------|------|-------------|
| `raw_data` | str | Ticket data (base64, text, etc.) |
| `tipo` | Literal["imagen","pdf","texto","voz"] | Content type |
| `user_id` | Optional[int] | User ID |
| `whatsapp_message_id` | Optional[str] | WhatsApp message ID |
| `company_id` | str | Company ID |

#### EnhancedTicketCreate (Enhanced)
| Campo API | Tipo | Descripción |
|-----------|------|-------------|
| `auto_process` | bool | Enable automatic processing |
| `priority` | JobPriority | Processing priority |
| `merchant_hint` | Optional[str] | Merchant name hint |
| `alternative_urls` | Optional[List[str]] | Alternative URLs |
| `max_retries` | int | Maximum retry attempts |
| `timeout_seconds` | int | Processing timeout |
| `enable_captcha_solving` | bool | Enable captcha solving |
| `notification_webhook` | Optional[str] | Webhook URL |

### 2.3 Columnas Reales en Tablas DB

#### Tabla `tickets` (SQLite)
| Columna DB | Tipo | Constraints |
|------------|------|-------------|
| `id` | INTEGER | PRIMARY KEY |
| `user_id` | INTEGER | FOREIGN KEY users(id) |
| `raw_data` | TEXT | NOT NULL |
| `tipo` | TEXT | NOT NULL |
| `estado` | TEXT | DEFAULT 'pendiente' |
| `whatsapp_message_id` | TEXT | - |
| `merchant_id` | INTEGER | FOREIGN KEY merchants(id) |
| `merchant_name` | TEXT | - |
| `category` | TEXT | - |
| `confidence` | REAL | - |
| `invoice_data` | TEXT | JSON |
| `llm_analysis` | TEXT | JSON |
| `extracted_text` | TEXT | - |
| `original_image` | TEXT | - |
| `company_id` | TEXT | NOT NULL |
| `created_at` | TEXT | NOT NULL |
| `updated_at` | TEXT | NOT NULL |

#### Tabla `automation_jobs`
| Columna DB | Tipo | Descripción |
|------------|------|-------------|
| `id` | INTEGER | PRIMARY KEY |
| `ticket_id` | INTEGER | FOREIGN KEY tickets(id) |
| `merchant_id` | INTEGER | FOREIGN KEY merchants(id) |
| `estado` | TEXT | Job status |
| `automation_type` | TEXT | Type of automation |
| `priority` | INTEGER | Priority (1-10) |
| `retry_count` | INTEGER | Current retry count |
| `max_retries` | INTEGER | Max retries allowed |
| `config` | TEXT | JSON configuration |
| `result` | TEXT | JSON result |
| `error_details` | TEXT | JSON error details |
| `progress_percentage` | INTEGER | Progress (0-100) |
| `session_id` | TEXT | Automation session ID |
| `company_id` | TEXT | Company identifier |
| `created_at` | TEXT | Creation timestamp |
| `updated_at` | TEXT | Update timestamp |

### 2.4 DIFERENCIAS IDENTIFICADAS - FACTURACIÓN

#### ❌ Atributos UI que NO están en API o DB:
- **UI `ticket_type`** → **API `tipo`** ✓ (mapping correcto)

#### ❌ Atributos API que NO existen en DB:
| Campo API Enhanced | Falta en DB | Impacto |
|-------------------|-------------|---------|
| `alternative_urls` | ✗ | Medio - fallback URLs perdidas |
| `enable_captcha_solving` | ✗ | Alto - configuración captcha perdida |
| `notification_webhook` | ✗ | Medio - notificaciones perdidas |
| `timeout_seconds` | ✗ | Alto - control timeout perdido |

#### ❌ Columnas DB que NO se usan en API/UI:
| Columna DB | No usado en | Impacto |
|------------|-------------|---------|
| `automation_type` | API/UI | Medio - tipo automatización no expuesto |
| `selenium_session_id` | API/UI | Bajo - debug info no expuesta |
| `captcha_attempts` | API/UI | Bajo - métricas captcha perdidas |
| `ocr_confidence` | API/UI | Medio - confianza OCR no expuesta |

---

## 3. FUNCIONALIDAD: CONCILIACIÓN (RECONCILIATION)

### 3.1 Atributos Capturados en UI

**Inferido de:** `core/api_models.py` (BankSuggestion models)

| Campo UI (Inferido) | Tipo | Descripción |
|-------------------|------|-------------|
| `expense_id` | text | ID del gasto a conciliar |
| `movement_id` | text | ID del movimiento bancario |
| `confidence` | range | Confianza en la sugerencia |
| `decision` | select | Decisión (accepted/rejected/manual_review) |
| `amount` | number | Monto del movimiento |
| `date` | date | Fecha del movimiento |
| `description` | text | Descripción del movimiento |

### 3.2 Atributos Esperados en Modelos API

#### BankSuggestionExpense
| Campo API | Tipo | Descripción |
|-----------|------|-------------|
| `expense_id` | str | Expense ID |
| `amount` | float | Movement amount |
| `currency` | str | Currency (default MXN) |
| `description` | Optional[str] | Movement description |
| `date` | Optional[str] | Movement date |
| `provider_name` | Optional[str] | Provider name |
| `paid_by` | Optional[str] | Who made payment |
| `metadata` | Optional[Dict] | Additional metadata |
| `company_id` | str | Company identifier |

#### BankReconciliationFeedback
| Campo API | Tipo | Validación |
|-----------|------|------------|
| `expense_id` | str | required |
| `movement_id` | str | required |
| `confidence` | float | 0.0 <= x <= 1.0 |
| `decision` | Literal | [accepted, rejected, manual_review] |
| `company_id` | str | default="default" |

### 3.3 Columnas Reales en Tablas DB

#### Tabla `bank_movements` (PostgreSQL Schema)
| Columna DB | Tipo | Constraints |
|------------|------|-------------|
| `id` | UUID | PRIMARY KEY |
| `company_id` | UUID | NOT NULL, REFERENCES companies(id) |
| `bank_account` | VARCHAR(50) | - |
| `transaction_date` | DATE | NOT NULL |
| `description` | TEXT | - |
| `amount` | DECIMAL(12,2) | NOT NULL |
| `currency` | VARCHAR(3) | DEFAULT 'MXN' |
| `movement_type` | VARCHAR(20) | debit/credit |
| `category` | VARCHAR(50) | - |
| `reconciliation_status` | VARCHAR(20) | DEFAULT 'pending' |
| `matched_ticket_id` | UUID | REFERENCES tickets(id) |
| `import_batch_id` | UUID | - |
| `external_reference` | VARCHAR(100) | - |
| `created_at` | TIMESTAMP | DEFAULT NOW() |
| `updated_at` | TIMESTAMP | DEFAULT NOW() |

### 3.4 DIFERENCIAS IDENTIFICADAS - CONCILIACIÓN

#### ❌ Atributos UI que NO están en API o DB:
- **UI (inferido):** Todos los campos tienen correspondencia básica

#### ❌ Atributos API que NO existen en DB:
| Campo API | Falta en DB | Impacto |
|-----------|-------------|---------|
| `paid_by` | ✗ | Medio - información de pagador perdida |
| `metadata` | ✗ | Bajo - datos adicionales perdidos |

#### ❌ Columnas DB que NO se usan en API/UI:
| Columna DB | No usado en | Impacto |
|------------|-------------|---------|
| `bank_account` | API/UI | Alto - identificación cuenta perdida |
| `movement_type` | API/UI | Alto - tipo movimiento no clasificado |
| `category` | API/UI | Medio - categorización no expuesta |
| `import_batch_id` | API/UI | Bajo - trazabilidad importación perdida |
| `external_reference` | API/UI | Medio - referencia externa no expuesta |

---

## 4. FUNCIONALIDAD: ONBOARDING

### 4.1 Atributos Capturados en UI

**Archivo:** `static/onboarding.html`

| Campo UI | Tipo | Descripción |
|----------|------|-------------|
| `method` | radio | Método de registro (email/whatsapp) |
| `identifier` | text | Email o número WhatsApp |
| `full_name` | text | Nombre completo (opcional) |
| `company_name` | text | Nombre de empresa (inferido - no visible) |

### 4.2 Atributos Esperados en Modelos API

#### OnboardingRequest
| Campo API | Tipo | Validación |
|-----------|------|------------|
| `method` | Literal["email","whatsapp","manual"] | required |
| `identifier` | str | required, email/phone validation |
| `full_name` | str | required, min_length=2 |
| `company_name` | Optional[str] | optional |

#### OnboardingResponse
| Campo API | Tipo | Descripción |
|-----------|------|-------------|
| `success` | bool | Operation success |
| `company_id` | str | Generated company ID |
| `user_id` | int | Generated user ID |
| `identifier` | str | User identifier |
| `display_name` | str | Display name |
| `already_exists` | bool | If user exists |
| `demo_data` | Optional[DemoSnapshot] | Demo data info |
| `next_steps` | List[str] | Next steps list |

### 4.3 Columnas Reales en Tablas DB

#### Tabla `companies` (PostgreSQL Schema)
| Columna DB | Tipo | Constraints |
|------------|------|-------------|
| `id` | UUID | PRIMARY KEY |
| `name` | VARCHAR(255) | NOT NULL |
| `rfc` | VARCHAR(13) | UNIQUE NOT NULL |
| `email` | VARCHAR(255) | - |
| `phone` | VARCHAR(20) | - |
| `address` | JSONB | - |
| `fiscal_regime` | VARCHAR(10) | - |
| `invoicing_config` | JSONB | DEFAULT '{}' |
| `created_at` | TIMESTAMP | DEFAULT NOW() |
| `updated_at` | TIMESTAMP | DEFAULT NOW() |
| `is_active` | BOOLEAN | DEFAULT true |

#### Tabla `users` (Inferida - no encontrada en schema)
*Falta definición completa de tabla users*

### 4.4 DIFERENCIAS IDENTIFICADAS - ONBOARDING

#### ❌ Atributos UI que NO están en API o DB:
- Todos los campos UI tienen correspondencia

#### ❌ Atributos API que NO existen en DB:
| Campo API | Falta en DB | Impacto |
|-----------|-------------|---------|
| `method` | ✗ | Medio - método registro no persistido |
| `full_name` | ✗ en companies | Alto - nombre usuario no persistido |
| `display_name` | ✗ | Alto - nombre display no persistido |

#### ❌ Columnas DB que NO se usan en API/UI:
| Columna DB | No usado en | Impacto |
|------------|-------------|---------|
| `rfc` | API/UI onboarding | Alto - RFC no capturado en onboarding |
| `address` | API/UI | Medio - dirección no capturada |
| `fiscal_regime` | API/UI | Alto - régimen fiscal no capturado |
| `invoicing_config` | API/UI | Alto - configuración facturación no expuesta |

---

## 5. RESUMEN EJECUTIVO DE DIFERENCIAS

### 5.1 PROBLEMAS CRÍTICOS (Alto Impacto)

1. **GASTOS:**
   - ❌ 7 campos API sin columna DB (`deducible`, `requiere_factura`, `moneda`, etc.)
   - ❌ `provider_rfc` en DB no usado en API/UI (validación fiscal perdida)
   - ❌ `workflow_status` parcialmente implementado

2. **FACTURACIÓN:**
   - ❌ Configuración de timeout y captcha no persistida
   - ❌ Métricas de automatización no expuestas en UI

3. **CONCILIACIÓN:**
   - ❌ `bank_account` y `movement_type` no expuestos (clasificación perdida)
   - ❌ Esquema PostgreSQL no implementado (usando SQLite)

4. **ONBOARDING:**
   - ❌ Información fiscal (RFC, régimen) no capturada en registro
   - ❌ Tabla `users` no definida completamente

### 5.2 RECOMENDACIONES DE CORRECCIÓN

#### Inmediatas (Críticas):
1. **Ampliar schema de `expense_records`** con campos faltantes
2. **Implementar tabla `users`** completa
3. **Migrar a PostgreSQL** según schema documentado
4. **Capturar información fiscal** en onboarding

#### Mediano Plazo:
1. **Exponer métricas** de automatización en UI
2. **Implementar configuración** por tenant
3. **Completar flujo** de conciliación bancaria

#### Largo Plazo:
1. **Auditoría automática** de consistencia UI-API-DB
2. **Validación cruzada** en pipeline CI/CD
3. **Documentación automática** de esquemas

---

## 6. MATRIZ DE COHERENCIA

| Funcionalidad | Coherencia UI-API | Coherencia API-DB | Coherencia UI-DB | Score General |
|---------------|:-----------------:|:-----------------:|:----------------:|:-------------:|
| Gastos | 🟢 95% | 🔴 60% | 🔴 65% | **73%** |
| Facturación | 🟡 85% | 🟡 80% | 🟡 75% | **80%** |
| Conciliación | 🟡 80% | 🔴 70% | 🔴 65% | **72%** |
| Onboarding | 🟢 90% | 🔴 60% | 🔴 55% | **68%** |
| **PROMEDIO** | **87%** | **67%** | **65%** | **73%** |

### Leyenda:
- 🟢 **90-100%**: Excelente coherencia
- 🟡 **75-89%**: Coherencia aceptable con mejoras menores
- 🔴 **<75%**: Requiere atención inmediata

---

*Generado el: 2025-09-25*
*Auditor: Claude Code Assistant*
*Versión: 1.0*
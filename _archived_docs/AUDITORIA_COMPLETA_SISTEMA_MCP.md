# AUDITORÍA COMPLETA DEL SISTEMA MCP
**Fecha:** 3 de Noviembre, 2025
**Versión del Sistema:** MCP Server v1.0.0
**Ubicación:** `/Users/danielgoes96/Desktop/mcp-server`

---

## 📋 TABLA DE CONTENIDOS

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Endpoints API por Categoría](#endpoints-api-por-categoría)
3. [Páginas HTML y Sus Dependencias](#páginas-html-y-sus-dependencias)
4. [Problemas Identificados](#problemas-identificados)
5. [Recomendaciones](#recomendaciones)
6. [Anexos](#anexos)

---

## 📊 RESUMEN EJECUTIVO

### Estadísticas Generales
- **Total de Endpoints en main.py:** ~102 endpoints directos
- **Total de Routers API Montados:** 20 routers externos
- **Páginas HTML Identificadas:** 23 páginas principales
- **Archivos JavaScript Bundle:** 5 bundles principales
- **Estado General:** ✅ Sistema funcional con áreas de mejora

### Tecnologías Principales
- **Backend:** FastAPI (Python)
- **Frontend:** React 18, Tailwind CSS
- **Base de Datos:** SQLite (unified_mcp_system.db)
- **Autenticación:** JWT (OAuth2)
- **Multi-Tenancy:** Implementado

---

## 🔌 ENDPOINTS API POR CATEGORÍA

### 1. AUTENTICACIÓN (`/auth/*`)

| Método | Ruta | Autenticación | Descripción |
|--------|------|---------------|-------------|
| GET | `/auth/login` | ❌ No | Página de login (HTML) |
| POST | `/auth/login` | ❌ No | Login con JWT (OAuth2 form) |
| POST | `/auth/token` | ❌ No | Obtener token OAuth2 |
| GET | `/auth/register` | ❌ No | Página de registro (HTML) |
| POST | `/auth/register` | ❌ No | Registro de nuevo usuario |
| POST | `/auth/refresh` | ✅ Sí | Renovar access token |
| GET | `/auth/me` | ✅ Sí | Información del usuario actual |
| POST | `/auth/logout` | ✅ Sí | Cerrar sesión (invalidar token) |
| GET | `/auth/logout` | ❌ No | Logout via GET (redirect) |
| GET | `/auth/tenants` | ❌ No | Listar empresas/tenants disponibles |

**Notas:**
- ✅ Implementado con JWT Bearer tokens
- ✅ Multi-tenancy funcional
- ⚠️ Existe conflicto potencial entre `auth_jwt_router` y endpoints directos en main.py

---

### 2. EXPENSES - GESTIÓN DE GASTOS (`/expenses/*`)

| Método | Ruta | Autenticación | Descripción |
|--------|------|---------------|-------------|
| POST | `/simple_expense` | ❌ No | Crear gasto simple (legacy) |
| POST | `/complete_expense` | ❌ No | Completar gasto con workflow |
| POST | `/expenses` | ✅ Sí | Crear nuevo gasto |
| GET | `/expenses` | ✅ Sí | Listar gastos con filtros |
| DELETE | `/expenses` | ✅ Sí | Eliminar todos los gastos de empresa |
| PUT | `/expenses/{expense_id}` | ✅ Sí | Actualizar gasto existente |
| POST | `/expenses/{expense_id}/invoice` | ✅ Sí | Registrar factura para gasto |
| POST | `/expenses/{expense_id}/mark-invoiced` | ✅ Sí | Marcar como facturado |
| POST | `/expenses/{expense_id}/close-no-invoice` | ✅ Sí | Cerrar sin factura |
| POST | `/expenses/check-duplicates` | ✅ Sí | Detectar duplicados |
| POST | `/expenses/predict-category` | ✅ Sí | Predecir categoría con ML |
| GET | `/expenses/category-suggestions` | ✅ Sí | Sugerencias de categorías |
| POST | `/expenses/query` | ✅ Sí | Query en lenguaje natural |
| GET | `/expenses/query-help` | ✅ Sí | Ayuda para queries |
| POST | `/expenses/{expense_id}/mark-non-reconcilable` | ✅ Sí | Marcar como no conciliable |
| GET | `/expenses/non-reconciliation-reasons` | ✅ Sí | Razones de no conciliación |
| GET | `/expenses/{expense_id}/non-reconciliation-status` | ✅ Sí | Estado de no conciliación |
| POST | `/expenses/enhanced` | ✅ Sí | Crear con detección de duplicados |

**Tags (Etiquetas de Gastos):**
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/expense-tags` | Listar tags |
| POST | `/expense-tags` | Crear tag |
| PUT | `/expense-tags/{tag_id}` | Actualizar tag |
| DELETE | `/expense-tags/{tag_id}` | Eliminar tag |
| POST | `/expenses/{expense_id}/tags` | Asignar tags a gasto |
| GET | `/expenses/{expense_id}/tags` | Obtener tags de gasto |
| GET | `/expense-tags/{tag_id}/expenses` | Gastos con tag específico |

---

### 3. BANK RECONCILIATION - CONCILIACIÓN BANCARIA (`/bank*`)

| Método | Ruta | Autenticación | Descripción |
|--------|------|---------------|-------------|
| GET | `/bank_reconciliation/movements` | ✅ Sí | Listar movimientos bancarios |
| POST | `/bank_reconciliation/suggestions` | ✅ Sí | Sugerencias de conciliación |
| POST | `/bank_reconciliation/feedback` | ✅ Sí | Feedback de conciliación |
| POST | `/bank_reconciliation/movements` | ✅ Sí | Crear movimiento bancario |
| GET | `/bank_reconciliation/movements/{movement_id}` | ✅ Sí | Obtener movimiento específico |
| GET | `/bank-movements/account/{account_id}` | ✅ Sí | Movimientos por cuenta |
| POST | `/bank-movements/reparse-with-improved-rules` | ✅ Sí | Re-parsear con nuevas reglas |
| POST | `/bank_reconciliation/ml-suggestions` | ✅ Sí | Sugerencias ML |
| POST | `/bank_reconciliation/auto-reconcile` | ✅ Sí | Auto-conciliación |
| GET | `/bank_reconciliation/matching-rules` | ✅ Sí | Reglas de matching |
| POST | `/bank_reconciliation/matching-rules` | ✅ Sí | Crear regla de matching |

**AI Reconciliation (`/bank_reconciliation/ai/*`):**
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/bank_reconciliation/ai/suggestions` | Sugerencias AI 1:1 |
| GET | `/bank_reconciliation/ai/suggestions/one-to-many` | Sugerencias 1:N |
| GET | `/bank_reconciliation/ai/suggestions/many-to-one` | Sugerencias N:1 |
| POST | `/bank_reconciliation/ai/auto-apply/{suggestion_index}` | Aplicar sugerencia |
| POST | `/bank_reconciliation/ai/auto-apply-batch` | Aplicar lote |
| GET | `/bank_reconciliation/ai/stats` | Estadísticas AI |

**Split Reconciliation (`/bank_reconciliation/split/*`):**
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/bank_reconciliation/split/one-to-many` | Dividir 1:N |
| POST | `/bank_reconciliation/split/many-to-one` | Combinar N:1 |
| GET | `/bank_reconciliation/split/{split_group_id}` | Detalle split |
| GET | `/bank_reconciliation/split/` | Listar splits |
| DELETE | `/bank_reconciliation/split/{split_group_id}` | Eliminar split |
| GET | `/bank_reconciliation/split/summary/stats` | Estadísticas |

---

### 4. INVOICES - GESTIÓN DE FACTURAS (`/invoices/*`)

| Método | Ruta | Autenticación | Descripción |
|--------|------|---------------|-------------|
| POST | `/invoices/parse` | ✅ Sí | Parsear factura (PDF/XML) |
| POST | `/invoices/bulk-match` | ✅ Sí | Matching masivo de facturas |
| GET | `/invoices` | ✅ Sí | Listar facturas |
| POST | `/invoices` | ✅ Sí | Crear factura |
| GET | `/invoices/{invoice_id}` | ✅ Sí | Obtener factura |
| PUT | `/invoices/{invoice_id}` | ✅ Sí | Actualizar factura |
| POST | `/invoices/{invoice_id}/find-matches` | ✅ Sí | Encontrar matches |

**Advanced Invoicing API (`/api/v1/invoicing/*`):**
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/v1/invoicing/tickets/upload` | Upload ticket para procesar |
| POST | `/api/v1/invoicing/tickets/{ticket_id}/automate` | Automatizar descarga factura |
| GET | `/api/v1/invoicing/jobs/{job_id}/status` | Estado de job |
| GET | `/api/v1/invoicing/jobs/{job_id}/logs` | Logs de job |
| GET | `/api/v1/invoicing/jobs/{job_id}/screenshots` | Screenshots de job |
| GET | `/api/v1/invoicing/companies/{company_id}/stats` | Estadísticas |

---

### 5. PAYMENT ACCOUNTS - CUENTAS DE PAGO (`/payment-accounts/*`)

| Método | Ruta | Autenticación | Descripción |
|--------|------|---------------|-------------|
| GET | `/payment-accounts/` | ✅ Sí | Listar cuentas de pago |
| GET | `/payment-accounts/{account_id}` | ✅ Sí | Obtener cuenta específica |
| POST | `/payment-accounts/` | ✅ Sí | Crear cuenta |
| PUT | `/payment-accounts/{account_id}` | ✅ Sí | Actualizar cuenta |
| DELETE | `/payment-accounts/{account_id}` | ✅ Sí | Eliminar cuenta |
| GET | `/payment-accounts/summary/dashboard` | ✅ Sí | Resumen dashboard |
| GET | `/payment-accounts/banking-institutions` | ✅ Sí | Instituciones bancarias |
| GET | `/payment-accounts/types/available` | ✅ Sí | Tipos disponibles |
| GET | `/payment-accounts/health` | ✅ Sí | Health check |

---

### 6. BANK STATEMENTS - ESTADOS DE CUENTA (`/bank-statements/*`)

| Método | Ruta | Autenticación | Descripción |
|--------|------|---------------|-------------|
| POST | `/bank-statements/accounts/{account_id}/upload` | ✅ Sí | Subir estado de cuenta PDF |
| GET | `/bank-statements/accounts/{account_id}` | ✅ Sí | Estados de cuenta |
| GET | `/bank-statements/{statement_id}` | ✅ Sí | Detalle estado de cuenta |
| DELETE | `/bank-statements/{statement_id}` | ✅ Sí | Eliminar estado |
| GET | `/bank-statements/` | ✅ Sí | Listar todos |
| POST | `/bank-statements/{statement_id}/reparse` | ✅ Sí | Re-parsear PDF |

---

### 7. ONBOARDING - REGISTRO E INICIO (`/onboarding/*`)

| Método | Ruta | Autenticación | Descripción |
|--------|------|---------------|-------------|
| POST | `/onboarding/register` | ❌ No | Registro simple (WhatsApp/Email) |
| POST | `/onboarding/enhanced-register` | ❌ No | Registro mejorado |
| PUT | `/onboarding/step` | ✅ Sí | Actualizar paso de onboarding |
| GET | `/onboarding/status/{user_id}` | ✅ Sí | Estado de onboarding |
| POST | `/onboarding/generate-demo` | ✅ Sí | Generar datos demo |

---

### 8. ADMIN - ADMINISTRACIÓN (`/admin/*`)

| Método | Ruta | Autenticación | Descripción |
|--------|------|---------------|-------------|
| GET | `/admin/error-stats` | ✅ Sí (Admin) | Estadísticas de errores |
| POST | `/admin/test-error` | ✅ Sí (Admin) | Probar manejo de errores |

---

### 9. DUPLICATES - DETECCIÓN DE DUPLICADOS (`/duplicates/*`)

| Método | Ruta | Autenticación | Descripción |
|--------|------|---------------|-------------|
| POST | `/duplicates/detect` | ✅ Sí | Detectar duplicados |
| PUT | `/duplicates/review` | ✅ Sí | Revisar duplicado |
| GET | `/duplicates/stats` | ✅ Sí | Estadísticas |
| GET | `/duplicates/config` | ✅ Sí | Configuración |

---

### 10. CATEGORIES - CATEGORIZACIÓN ML (`/categories/*`)

| Método | Ruta | Autenticación | Descripción |
|--------|------|---------------|-------------|
| GET | `/categories/custom` | ✅ Sí | Categorías personalizadas |
| GET | `/categories/config` | ✅ Sí | Configuración |
| POST | `/categories/feedback` | ✅ Sí | Feedback de categorización |
| GET | `/categories/stats` | ✅ Sí | Estadísticas |
| GET | `/categories/learning-insights` | ✅ Sí | Insights de aprendizaje |
| POST | `/categories/optimize` | ✅ Sí | Optimizar predictor |

---

### 11. OCR - PROCESAMIENTO DE IMÁGENES (`/ocr/*`)

| Método | Ruta | Autenticación | Descripción |
|--------|------|---------------|-------------|
| POST | `/ocr/parse` | ✅ Sí | Parsear imagen con OCR |
| POST | `/ocr/intake` | ✅ Sí | Intake de documento |
| GET | `/ocr/stats` | ✅ Sí | Estadísticas OCR |

---

### 12. VOICE - PROCESAMIENTO DE VOZ (`/voice_mcp*`)

| Método | Ruta | Autenticación | Descripción |
|--------|------|---------------|-------------|
| POST | `/voice_mcp` | ❌ No | Procesar audio (básico) |
| POST | `/voice_mcp_enhanced` | ❌ No | Procesar audio (mejorado) |
| GET | `/audio/{filename}` | ❌ No | Servir archivo de audio |

---

### 13. DEMO & UTILITIES - UTILIDADES (`/demo/*`, `/methods`, etc.)

| Método | Ruta | Autenticación | Descripción |
|--------|------|---------------|-------------|
| POST | `/demo/generate-dummy-data` | ✅ Sí | Generar datos dummy |
| GET | `/methods` | ❌ No | Métodos soportados |
| GET | `/api/status` | ❌ No | Estado API |
| GET | `/health` | ❌ No | Health check |
| POST | `/mcp` | ❌ No | Endpoint MCP genérico |

---

### 14. AUDIT & VALIDATION - AUDITORÍA (`/audit/*`, `/validation/*`)

| Método | Ruta | Autenticación | Descripción |
|--------|------|---------------|-------------|
| GET | `/audit/extraction-summary` | ✅ Sí | Resumen extracción |
| GET | `/audit/missing-transactions` | ✅ Sí | Transacciones faltantes |
| POST | `/audit/resolve-missing-transaction/{missing_id}` | ✅ Sí | Resolver faltante |
| POST | `/validate/account-transactions/{account_id}` | ✅ Sí | Validar transacciones |
| GET | `/validation/system-status` | ✅ Sí | Estado sistema validación |

---

### 15. EMPLOYEE ADVANCES - ANTICIPOS (`/employee_advances/*`)

| Método | Ruta | Autenticación | Descripción |
|--------|------|---------------|-------------|
| POST | `/employee_advances/` | ✅ Sí | Crear anticipo |
| POST | `/employee_advances/reimburse` | ✅ Sí | Reembolsar anticipo |
| GET | `/employee_advances/{advance_id}` | ✅ Sí | Obtener anticipo |
| GET | `/employee_advances/` | ✅ Sí | Listar anticipos |
| GET | `/employee_advances/employee/{employee_id}/summary` | ✅ Sí | Resumen por empleado |
| GET | `/employee_advances/summary/all` | ✅ Sí | Resumen general |
| DELETE | `/employee_advances/{advance_id}` | ✅ Sí | Eliminar anticipo |
| GET | `/employee_advances/pending/all` | ✅ Sí | Anticipos pendientes |

---

### 16. ROUTERS API EXTERNOS (Montados vía include_router)

#### A. Non-Reconciliation API (`/api/non-reconciliation/*`)
- POST `/api/non-reconciliation/mark-non-reconcilable`
- GET `/api/non-reconciliation/records`
- PUT `/api/non-reconciliation/records/{record_id}`
- POST `/api/non-reconciliation/escalate`
- GET `/api/non-reconciliation/stats`
- +10 endpoints más

#### B. Bulk Invoice API (`/api/bulk-invoice/*`)
- Endpoints para procesamiento masivo de facturas

#### C. Expense Completion API (`/api/expense-completion/*`)
- POST `/api/expense-completion/suggestions`
- POST `/api/expense-completion/interactions`
- POST `/api/expense-completion/bulk-complete`
- GET `/api/expense-completion/preferences/{user_id}`
- +6 endpoints más

#### D. Conversational Assistant API (`/api/conversational-assistant/*`)
- POST `/api/conversational-assistant/sessions`
- Sistema de chat inteligente

#### E. RPA Automation Engine API (`/api/rpa-automation-engine/*`)
- POST `/api/rpa-automation-engine/sessions`
- POST `/api/rpa-automation-engine/sessions/{session_id}/start`
- GET `/api/rpa-automation-engine/sessions/{session_id}/status`
- +15 endpoints más

#### F. Universal Invoice Engine API (`/universal-invoice/*`)
- POST `/universal-invoice/sessions/`
- POST `/universal-invoice/sessions/upload/`
- POST `/universal-invoice/sessions/{session_id}/process`
- +8 endpoints más

#### G. Client Management API (`/api/v1/clients/*`)
- POST `/api/v1/clients/setup`
- GET `/api/v1/clients/{client_id}`
- PUT `/api/v1/clients/{client_id}/fiscal-data`
- +7 endpoints más

#### H. Financial Intelligence API (`/financial-intelligence/*`)
- GET `/financial-intelligence/financial-insights`
- GET `/financial-intelligence/financial-health-score`

#### I. Category Learning API (`/api/category-learning/*`)
- POST `/api/category-learning/feedback`
- POST `/api/category-learning/predict`
- GET `/api/category-learning/metrics`

#### J. Web Automation Engine (`/api/web-automation-engine/*`)

#### K. Hybrid Processor (`/hybrid-processor/*`)

#### L. Robust Automation Engine (`/robust-automation/*`)

---

### 17. API V1 - ROUTERS NO MONTADOS ⚠️

Los siguientes routers están definidos pero **NO están montados** en main.py:

#### A. Financial Reports API (`/api/v1/reports/*`)
❌ **NO MONTADO** - Router existe pero no está incluido
- POST `/api/v1/reports/iva` - Reporte IVA
- POST `/api/v1/reports/poliza-electronica` - Póliza electrónica
- GET `/api/v1/reports/poliza-electronica/xml` - XML póliza
- GET `/api/v1/reports/gastos-revision` - Gastos en revisión
- GET `/api/v1/reports/resumen-fiscal` - Resumen fiscal
- GET `/api/v1/reports/disponibles` - Reportes disponibles

#### B. Pólizas API (`/api/v1/polizas/*`)
❌ **NO MONTADO** - Router existe pero no está incluido
- POST `/api/v1/polizas/generar_desde_conciliacion`
- GET `/api/v1/polizas/`
- GET `/api/v1/polizas/{poliza_id}`
- GET `/api/v1/polizas/por-movimiento/{movement_id}`

#### C. Companies Context API (`/api/v1/companies/*`)
❌ **NO MONTADO** - Router existe pero no está incluido
- GET `/api/v1/companies/context/status`
- POST `/api/v1/companies/contextual_profile`
- POST `/api/v1/companies/context/questions`
- POST `/api/v1/companies/context/analyze`

#### D. User Context API (`/api/v1/users/*`, `/api/v1/auth/*`)
❌ **NO MONTADO** - Router existe pero no está incluido
- Endpoints de contexto de usuario

#### E. Transactions Review API (`/api/v1/transactions/*`)
❌ **NO MONTADO** - Router existe pero no está incluido
- POST `/api/v1/transactions/{transaction_id}/mark_reviewed`

#### F. AI Retrain API (`/api/v1/ai/*`)
❌ **NO MONTADO** - Router existe pero no está incluido
- POST `/api/v1/ai/retrain`

#### G. V1 Invoicing API (`/api/v1/invoicing/*`)
❌ **NO MONTADO DIRECTAMENTE** - Existe en api/v1/__init__.py pero el v1 router no está montado
- GET `/api/v1/invoicing/tickets`
- POST `/api/v1/invoicing/tickets`
- GET `/api/v1/invoicing/tickets/{ticket_id}`
- GET `/api/v1/invoicing/stats`

---

### 18. PÁGINAS HTML (UI Endpoints)

| Método | Ruta | Archivo Servido |
|--------|------|-----------------|
| GET | `/` | Smart root - redirige según autenticación |
| GET | `/onboarding` | static/onboarding.html |
| GET | `/voice-expenses` | static/voice-expenses.html |
| GET | `/advanced-ticket-dashboard.html` | ⚠️ ARCHIVO ELIMINADO |
| GET | `/client-settings` | static/client-settings.html |
| GET | `/automation-viewer` | static/automation-viewer.html |
| GET | `/bank-reconciliation` | static/bank-reconciliation.html |
| GET | `/auth/login` | static/auth-login.html |
| GET | `/auth/register` | static/auth-register.html |
| GET | `/admin` | static/admin-panel.html |
| GET | `/dashboard` | static/dashboard.html |
| GET | `/payment-accounts.html` | static/payment-accounts.html |
| GET | `/payment-accounts` | static/payment-accounts.html |
| GET | `/employee-advances.html` | static/employee-advances.html |
| GET | `/test-ui-debug.html` | test_ui_debug.html |
| GET | `/auth-login.html` | static/auth-login.html |

---

## 🌐 PÁGINAS HTML Y SUS DEPENDENCIAS

### 1. **auth-login.html** (`/auth/login`)
**Propósito:** Página de inicio de sesión

**Endpoints Llamados:**
- GET `/auth/tenants` - Cargar lista de empresas
- POST `/auth/login` - Autenticación con OAuth2 form

**Funcionalidades:**
- ✅ Multi-tenancy selector
- ✅ Recordar sesión
- ✅ Redirección a `/voice-expenses` después de login
- ✅ Manejo de errores detallado

**Dependencias:**
- Tailwind CSS (CDN)
- Font Awesome 6.4.0
- LocalStorage para tokens

---

### 2. **auth-register.html** (`/auth/register`)
**Propósito:** Registro de nuevos usuarios

**Endpoints Llamados:**
- POST `/auth/register` - Crear cuenta

**Funcionalidades:**
- ✅ Validación de contraseñas
- ✅ Campos: nombre, apellido, email, empresa
- ✅ Redirección a login después de registro

**Dependencias:**
- Tailwind CSS
- Font Awesome

---

### 3. **voice-expenses.html** (`/voice-expenses`)
**Propósito:** Centro de control de gastos con entrada por voz

**Endpoints Llamados:**
- ⚠️ **Usa bundle:** `/static/voice-expenses.entry.js`
- El bundle contiene llamadas a múltiples endpoints

**Funcionalidades:**
- ✅ Grabación de voz
- ✅ Procesamiento de gastos
- ✅ React 18
- ✅ Componentes modulares

**Dependencias:**
- React 18 (CDN)
- ReactDOM 18
- `/static/components/components.js`
- `/static/voice-expenses.entry.js` (bundle)
- `/static/components/global-header.html`

---

### 4. **dashboard.html** (`/dashboard`)
**Propósito:** Dashboard principal del sistema

**Endpoints Llamados:**
- GET `/payment-accounts/?company_id={companyId}` - Cuentas activas
- GET `/bank_reconciliation/movements?company_id={companyId}&limit=1000` - Movimientos bancarios

**Funcionalidades:**
- ✅ Vista rápida de estadísticas
- ✅ Enlaces a módulos principales:
  - Conciliación Bancaria
  - Cuentas de Banco/Efectivo
  - Gastos por Voz
  - Automatización
  - Configuración
- ✅ Cálculo de saldos en tiempo real

**Dependencias:**
- Tailwind CSS
- `/static/components/global-header.html`
- `/static/js/mcp-header.js`

---

### 5. **bank-reconciliation.html** (`/bank-reconciliation`)
**Propósito:** Interface de conciliación bancaria

**Endpoints Llamados:**
- ⚠️ **Usa bundle:** `/static/bank-reconciliation.entry.js`

**Funcionalidades:**
- ✅ React app completa
- ✅ Conciliación de movimientos
- ✅ Matching automático

**Dependencias:**
- React 18
- `/static/bank-reconciliation.entry.js` (bundle)
- `/static/components/global-header.html`

---

### 6. **automation-viewer.html** (`/automation-viewer`)
**Propósito:** Visualizador de automatizaciones RPA

**Endpoints Llamados:**
- GET `/invoicing/tickets?limit=50` - ⚠️ **ENDPOINT NO EXISTE**
- GET `/invoicing/tickets/{ticketId}/automation-data` - ⚠️ **ENDPOINT NO EXISTE**

**Funcionalidades:**
- 📸 Visualización de screenshots
- 📊 Timeline de ejecución
- 📝 Logs de automatización

**Estado:** ⚠️ **PROBLEMAS** - Llama a endpoints que no existen

**Dependencias:**
- CSS custom (inline)
- JavaScript vanilla

---

### 7. **client-settings.html** (`/client-settings`)
**Propósito:** Configuración de datos fiscales y credenciales

**Endpoints Llamados:**
- ⚠️ Endpoints comentados en código
- No hay llamadas API activas

**Funcionalidades:**
- 📝 Formulario datos fiscales
- 🔑 Credenciales de portales
- ⚠️ **NO FUNCIONAL** - Endpoints deshabilitados

**Estado:** ⚠️ Implementación incompleta

---

### 8. **admin-panel.html** (`/admin`)
**Propósito:** Panel de administración del sistema

**Endpoints Llamados:**
- GET `/admin/error-stats` - Estadísticas de errores
- POST `/admin/test-error` - Probar errores
- POST `/demo/generate-dummy-data` - Generar datos demo
- GET `/health` - Health check
- GET `/static/components/global-header.html` - Header

**Funcionalidades:**
- ✅ Monitoreo de salud del sistema
- ✅ Estadísticas de errores
- ✅ Generación de datos demo
- ✅ Gráficas con Chart.js

**Dependencias:**
- Chart.js
- Tailwind CSS
- `/static/components/global-header.html`

---

### 9. **onboarding.html** (`/onboarding`)
**Propósito:** Proceso de onboarding y registro

**Endpoints Llamados:**
- POST `/onboarding/register` - Registro con WhatsApp/Email

**Funcionalidades:**
- ✅ Registro con WhatsApp o Email
- ✅ Sistema de misiones (gamificación)
- ✅ Generación de datos demo
- ✅ Progress tracking

**Dependencias:**
- Tailwind CSS
- Font Awesome 6.5.1

---

### 10. **payment-accounts.html** (`/payment-accounts`)
**Propósito:** Gestión de cuentas bancarias y de efectivo

**Endpoints Llamados:**
- GET `/public/banking-institutions` - Instituciones bancarias
- POST `/payment-accounts/` - Crear cuenta
- DELETE `/payment-accounts/{accountId}` - Eliminar cuenta
- GET `/bank-movements/account/{accountId}` - Movimientos
- POST `/api/v1/transactions/{transactionId}/mark_reviewed` - Marcar revisado
- POST `/bank-movements/{id}/reclassify` - Reclasificar
- POST `/bank-statements/accounts/{accountId}/upload` - Subir estado de cuenta

**Funcionalidades:**
- ✅ CRUD completo de cuentas
- ✅ Soporte multi-tipo: Banco, Efectivo, Tarjeta, Terminal
- ✅ Upload de estados de cuenta
- ✅ Visualización de transacciones
- ✅ Reclasificación de movimientos

**Dependencias:**
- Tailwind CSS
- Font Awesome

---

### 11. **employee-advances.html** (`/employee-advances`)
**Propósito:** Gestión de anticipos a empleados

**Endpoints Llamados:**
- GET `/employee_advances/summary/all` - Resumen general
- GET `/employee_advances/?...` - Listar anticipos
- POST `/employee_advances/` - Crear anticipo
- POST `/employee_advances/reimburse` - Reembolsar
- DELETE `/employee_advances/{id}` - Eliminar

**Funcionalidades:**
- ✅ CRUD completo de anticipos
- ✅ Tracking de reembolsos
- ✅ Resúmenes por empleado

---

### 12. **sat-accounts.html** (No tiene ruta en main.py)
**Propósito:** Gestión de cuentas SAT

**Endpoints Llamados:**
- GET `/sat-accounts?{params}` - ⚠️ **ENDPOINT NO EXISTE EN MAIN.PY**

**Estado:** ⚠️ Página huérfana - sin ruta de acceso

---

### 13. **polizas-dashboard.html** (No tiene ruta en main.py)
**Propósito:** Dashboard de pólizas contables

**Endpoints Llamados:**
- GET `/api/v1/polizas/?limit=100` - ⚠️ **ROUTER NO MONTADO**

**Estado:** ⚠️ Router existe pero no está montado en main.py

---

### 14. **financial-reports-dashboard.html** (No tiene ruta en main.py)
**Propósito:** Dashboard de reportes financieros

**Endpoints Llamados:**
- Múltiples endpoints de `/api/v1/reports/*` - ⚠️ **ROUTER NO MONTADO**

**Estado:** ⚠️ Router existe pero no está montado en main.py

---

### 15. **expenses-viewer-enhanced.html** (No tiene ruta en main.py)
**Propósito:** Visor mejorado de gastos

**Endpoints Llamados:**
- GET `/expenses?company_id=default`
- GET `/sat-accounts?{params}` - ⚠️ Endpoint no existe
- PUT `/expenses/{expenseId}`
- POST `/expenses/{id}/classification-feedback`

**Estado:** ⚠️ Página funcional pero sin ruta de acceso directa

---

### 16. **complete-expenses.html** (No tiene ruta en main.py)
**Propósito:** Completar gastos pendientes

**Estado:** ⚠️ Página antigua, posiblemente reemplazada por voice-expenses

---

### 17. **landing.html** (No tiene ruta en main.py)
**Propósito:** Página de inicio/landing

**Dependencias:**
- `/static/landing.bundle.js`

**Estado:** ⚠️ Sin ruta de acceso

---

### 18. **index.html** (No tiene ruta en main.py)
**Propósito:** Posible página de inicio

**Estado:** ⚠️ Sin ruta de acceso

---

## ⚠️ PROBLEMAS IDENTIFICADOS

### 🔴 CRÍTICOS

#### 1. **Routers API V1 No Montados**
**Severidad:** Alta
**Impacto:** Funcionalidades completas inaccesibles

**Routers Afectados:**
- ❌ `/api/v1/polizas/*` - Sistema de pólizas contables
- ❌ `/api/v1/reports/*` - Reportes financieros (IVA, resumen fiscal, etc.)
- ❌ `/api/v1/companies/*` - Contexto de empresas
- ❌ `/api/v1/users/*` - Contexto de usuarios
- ❌ `/api/v1/transactions/*` - Revisión de transacciones
- ❌ `/api/v1/ai/*` - Re-entrenamiento de IA
- ❌ `/api/v1/invoicing/*` - API de invoicing V1

**Solución:**
```python
# Agregar en main.py después de línea 433
from api.financial_reports_api import router as financial_reports_router
app.include_router(financial_reports_router)

from api.v1.polizas_api import router as polizas_router
app.include_router(polizas_router)

from api.v1.companies_context import router as companies_context_router
app.include_router(companies_context_router)

from api.v1.transactions_review_api import router as transactions_review_router
app.include_router(transactions_review_router)

from api.v1.ai_retrain import router as ai_retrain_router
app.include_router(ai_retrain_router)

from api.v1.user_context import auth_router, users_router
app.include_router(auth_router)
app.include_router(users_router)

# Montar el router V1 principal
from api.v1 import router as v1_router
app.include_router(v1_router)
```

---

#### 2. **Páginas HTML Sin Ruta de Acceso**
**Severidad:** Media
**Impacto:** Contenido inaccesible

**Páginas Afectadas:**
- `sat-accounts.html` - No hay GET `/sat-accounts`
- `polizas-dashboard.html` - No hay GET `/polizas-dashboard`
- `financial-reports-dashboard.html` - No hay GET `/financial-reports`
- `expenses-viewer-enhanced.html` - No hay GET `/expenses-viewer`
- `complete-expenses.html` - No hay GET `/complete-expenses`
- `landing.html` - No hay GET `/landing`
- `index.html` - No hay ruta específica
- `onboarding-context.html` - No hay ruta

**Solución:**
```python
# Agregar en main.py
@app.get("/sat-accounts")
async def sat_accounts_page():
    return FileResponse("static/sat-accounts.html")

@app.get("/polizas-dashboard")
async def polizas_dashboard_page():
    return FileResponse("static/polizas-dashboard.html")

@app.get("/financial-reports")
async def financial_reports_page():
    return FileResponse("static/financial-reports-dashboard.html")

@app.get("/expenses-viewer")
async def expenses_viewer_page():
    return FileResponse("static/expenses-viewer-enhanced.html")
```

---

#### 3. **Endpoints Llamados que No Existen**
**Severidad:** Alta
**Impacto:** Páginas rotas

**Casos Detectados:**

| Archivo HTML | Endpoint Llamado | Estado |
|--------------|------------------|--------|
| `automation-viewer.html` | GET `/invoicing/tickets` | ❌ No existe (debería ser `/api/v1/invoicing/tickets`) |
| `automation-viewer.html` | GET `/invoicing/tickets/{id}/automation-data` | ❌ No existe |
| `sat-accounts.html` | GET `/sat-accounts` | ❌ No existe |
| `polizas-dashboard.html` | GET `/api/v1/polizas/` | ⚠️ Router no montado |
| `financial-reports-dashboard.html` | Varios `/api/v1/reports/*` | ⚠️ Router no montado |
| `payment-accounts.html` | POST `/api/v1/transactions/{id}/mark_reviewed` | ⚠️ Router no montado |

**Solución:**
1. Montar los routers faltantes
2. Actualizar las llamadas en los HTML a las rutas correctas
3. Crear endpoints faltantes o deprecar páginas

---

#### 4. **Archivo Eliminado Pero Ruta Existe**
**Severidad:** Alta
**Impacato:** Endpoint 404

**Caso:**
- Ruta: GET `/advanced-ticket-dashboard.html`
- Estado archivo: `D static/advanced-ticket-dashboard.html` (DELETED en git)

**Solución:**
```python
# ELIMINAR de main.py línea 775-787:
@app.get("/advanced-ticket-dashboard.html")
async def advanced_ticket_dashboard():
    ...
```

---

### 🟡 ADVERTENCIAS

#### 5. **Potencial Conflicto de Routers de Auth**
**Severidad:** Media
**Descripción:**
- `auth_jwt_router` montado en `/auth`
- Endpoints directos en main.py también en `/auth`

**Posible Conflicto:**
- ¿Qué endpoints tiene prioridad?
- Posibles rutas duplicadas

**Recomendación:** Auditar y consolidar en un solo router

---

#### 6. **SAT Accounts Endpoint Indefinido**
**Severidad:** Media

**Problema:**
- `sat-accounts.html` llama a GET `/sat-accounts?{params}`
- No existe endpoint en main.py
- Posiblemente debería estar en un router API

**Solución:**
- Crear endpoint o usar router existente
- Documentar si es legacy

---

#### 7. **Endpoints Comentados en client-settings.html**
**Severidad:** Baja

**Problema:**
```javascript
// const response = await fetch(`${API_BASE}/setup`, {...});
```
Endpoints comentados, funcionalidad no operativa

**Impacto:** Configuración de cliente no funciona completamente

---

#### 8. **Bundles JavaScript Sin Código Fuente Visible**
**Severidad:** Media

**Archivos:**
- `voice-expenses.bundle.js` - Código minificado
- `bank-reconciliation.bundle.js` - Código minificado
- `landing.bundle.js` - Código minificado

**Problema:**
- Difícil auditar qué endpoints llaman
- Código fuente está en `.jsx` que se compila

**Recomendación:**
- Documentar proceso de build
- Incluir source maps

---

### 🔵 MEJORAS SUGERIDAS

#### 9. **Falta Endpoint GET `/sat-accounts`**
**Tipo:** Feature missing

**Propuesta:**
```python
@app.get("/sat-accounts")
async def list_sat_accounts(
    company_id: str = "default",
    current_user: User = Depends(get_current_active_user)
):
    """List SAT chart of accounts"""
    # Implementation
    pass
```

---

#### 10. **Documentación de Endpoints**
**Tipo:** Documentation

**Faltante:**
- Muchos endpoints carecen de docstrings detallados
- Parámetros no documentados
- Responses no tipados

**Recomendación:**
- Agregar docstrings completos
- Usar response_model en todos los endpoints
- Generar OpenAPI docs completo

---

#### 11. **Versioning API Inconsistente**
**Tipo:** Architecture

**Problema:**
- Algunos endpoints en `/api/v1/*`
- Otros en raíz `/expenses`, `/invoices`, etc.
- Sin estrategia clara de versionado

**Recomendación:**
- Definir estándar de versionado
- Migrar gradualmente a `/api/v2/*`

---

#### 12. **Testing de Endpoints**
**Tipo:** Quality

**Faltante:**
- No se observan tests en el análisis
- Endpoints críticos sin cobertura

**Recomendación:**
- Implementar pytest con coverage
- Tests de integración para flujos críticos

---

## 📈 RECOMENDACIONES

### 🎯 PRIORIDAD ALTA (Implementar Inmediatamente)

#### 1. **Montar Routers V1 Faltantes**
**Acción:** Agregar includes de routers en main.py
**Archivos:** main.py
**Líneas de código:** ~20 líneas
**Tiempo estimado:** 30 minutos

```python
# Después de línea 433 en main.py
try:
    from api.financial_reports_api import router as financial_reports_router
    app.include_router(financial_reports_router)
    logger.info("Financial reports API loaded successfully")
except ImportError as e:
    logger.warning(f"Financial reports API not available: {e}")

try:
    from api.v1.polizas_api import router as polizas_router
    app.include_router(polizas_router)
    logger.info("Polizas API loaded successfully")
except ImportError as e:
    logger.warning(f"Polizas API not available: {e}")

try:
    from api.v1.companies_context import router as companies_context_router
    app.include_router(companies_context_router)
    logger.info("Companies context API loaded successfully")
except ImportError as e:
    logger.warning(f"Companies context API not available: {e}")

try:
    from api.v1.transactions_review_api import router as transactions_review_router
    app.include_router(transactions_review_router)
    logger.info("Transactions review API loaded successfully")
except ImportError as e:
    logger.warning(f"Transactions review API not available: {e}")

try:
    from api.v1.user_context import auth_router as user_auth_router, users_router
    app.include_router(user_auth_router)
    app.include_router(users_router)
    logger.info("User context API loaded successfully")
except ImportError as e:
    logger.warning(f"User context API not available: {e}")

try:
    from api.v1.ai_retrain import router as ai_retrain_router
    app.include_router(ai_retrain_router)
    logger.info("AI retrain API loaded successfully")
except ImportError as e:
    logger.warning(f"AI retrain API not available: {e}")
```

---

#### 2. **Eliminar Ruta de advanced-ticket-dashboard.html**
**Acción:** Comentar o eliminar endpoint
**Archivos:** main.py (líneas 775-787)

```python
# ELIMINAR O COMENTAR:
# @app.get("/advanced-ticket-dashboard.html")
# async def advanced_ticket_dashboard():
#     ...
```

---

#### 3. **Crear Rutas para Páginas HTML Huérfanas**
**Acción:** Agregar endpoints GET para servir HTML
**Tiempo:** 15 minutos

```python
@app.get("/sat-accounts")
async def sat_accounts_page():
    return FileResponse("static/sat-accounts.html")

@app.get("/polizas-dashboard")
async def polizas_dashboard_page():
    return FileResponse("static/polizas-dashboard.html")

@app.get("/financial-reports")
async def financial_reports_page():
    return FileResponse("static/financial-reports-dashboard.html")
```

---

#### 4. **Actualizar Llamadas en automation-viewer.html**
**Acción:** Cambiar rutas de endpoints
**Archivos:** static/automation-viewer.html

```javascript
// CAMBIAR:
// const response = await fetch('/invoicing/tickets?limit=50');

// POR:
const response = await fetch('/api/v1/invoicing/tickets?limit=50');
```

---

### 🎯 PRIORIDAD MEDIA (Implementar en Sprint Próximo)

#### 5. **Consolidar Autenticación**
**Acción:** Revisar y consolidar auth_jwt_router vs endpoints directos
**Tiempo:** 2-3 horas

**Pasos:**
1. Listar todos los endpoints de auth en ambos lugares
2. Identificar duplicados
3. Decidir fuente única de verdad (preferiblemente router)
4. Migrar o deprecar

---

#### 6. **Implementar GET `/sat-accounts` Endpoint**
**Acción:** Crear endpoint funcional para SAT chart of accounts
**Tiempo:** 1-2 horas

```python
@app.get("/sat-accounts")
async def list_sat_accounts(
    codigo: Optional[str] = None,
    nivel: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    tenancy: TenancyContext = Depends(get_tenancy_context)
):
    """
    List SAT chart of accounts with optional filters
    """
    try:
        from core.accounting_catalog import get_sat_accounts
        accounts = get_sat_accounts(
            tenant_id=tenancy.tenant_id,
            codigo=codigo,
            nivel=nivel
        )
        return accounts
    except Exception as e:
        logger.exception("Error listing SAT accounts")
        raise HTTPException(status_code=500, detail=str(e))
```

---

#### 7. **Documentar Bundles JavaScript**
**Acción:** Crear README.md explicando build process
**Archivos:** static/README.md o docs/frontend-build.md

**Contenido:**
- Qué archivos `.jsx` generan cada bundle
- Comando para rebuild
- Dependencias necesarias
- Proceso de desarrollo

---

### 🎯 PRIORIDAD BAJA (Backlog)

#### 8. **Versionado API Consistente**
**Acción:** Migrar endpoints a `/api/v2/*`
**Tiempo:** Sprint completo

---

#### 9. **Tests de Integración**
**Acción:** Implementar test suite con pytest
**Cobertura objetivo:** 70%

---

#### 10. **Deprecar Páginas Legacy**
**Acción:** Identificar y marcar páginas obsoletas
**Candidatos:**
- complete-expenses.html (reemplazado por voice-expenses)
- Dashboards antiguos en old_dashboards/

---

## 📚 ANEXOS

### ANEXO A: Mapa de Archivos Clave

```
/Users/danielgoes96/Desktop/mcp-server/
├── main.py                          # ⭐ Punto de entrada principal
├── config/
│   ├── config.py                    # Configuración global
│   └── llm_config.py               # Config LLM
├── api/                            # 🔌 Routers API
│   ├── auth_jwt_api.py            # ✅ Montado
│   ├── payment_accounts_api.py    # ✅ Montado
│   ├── bank_statements_api.py     # ✅ Montado
│   ├── employee_advances_api.py   # ✅ Montado
│   ├── financial_reports_api.py   # ❌ NO montado
│   └── v1/
│       ├── polizas_api.py         # ❌ NO montado
│       ├── companies_context.py   # ❌ NO montado
│       ├── transactions_review_api.py # ❌ NO montado
│       └── ai_retrain.py          # ❌ NO montado
├── static/                        # 🌐 Frontend
│   ├── auth-login.html            # ✅ Ruta: /auth/login
│   ├── dashboard.html             # ✅ Ruta: /dashboard
│   ├── voice-expenses.html        # ✅ Ruta: /voice-expenses
│   ├── bank-reconciliation.html   # ✅ Ruta: /bank-reconciliation
│   ├── payment-accounts.html      # ✅ Ruta: /payment-accounts
│   ├── admin-panel.html           # ✅ Ruta: /admin
│   ├── sat-accounts.html          # ⚠️ Sin ruta
│   ├── polizas-dashboard.html     # ⚠️ Sin ruta
│   └── financial-reports-dashboard.html # ⚠️ Sin ruta
└── core/                          # 🧠 Lógica de negocio
    ├── api_models.py              # Modelos Pydantic
    ├── auth_jwt.py                # JWT authentication
    ├── internal_db.py             # Database layer
    └── unified_db_adapter.py      # Unified DB adapter
```

---

### ANEXO B: Endpoints por Autenticación

#### Endpoints Públicos (No requieren auth)
```
GET  /                              - Root (smart redirect)
GET  /auth/login                    - Página login
POST /auth/login                    - Login API
GET  /auth/register                 - Página registro
POST /auth/register                 - Registro API
GET  /auth/tenants                  - Listar tenants
GET  /public/banking-institutions   - Instituciones bancarias
GET  /health                        - Health check
GET  /api/status                    - API status
GET  /methods                       - Métodos soportados
POST /voice_mcp                     - Voz (legacy)
POST /voice_mcp_enhanced            - Voz mejorado
GET  /audio/{filename}              - Servir audio
POST /onboarding/register           - Registro onboarding
POST /mcp                           - MCP genérico
```

#### Endpoints Autenticados (Requieren JWT)
```
Todos los demás endpoints requieren autenticación JWT
via header: Authorization: Bearer {access_token}
```

---

### ANEXO C: Tecnologías y Versiones

| Tecnología | Versión | Uso |
|------------|---------|-----|
| Python | 3.9+ | Backend |
| FastAPI | Latest | Framework API |
| Pydantic | v2 | Validación datos |
| SQLite | 3 | Base de datos |
| React | 18 | Frontend componentes |
| Tailwind CSS | Latest (CDN) | Estilos |
| Font Awesome | 6.4.0 | Iconos |
| Chart.js | Latest | Gráficas |
| JWT | PyJWT | Autenticación |

---

### ANEXO D: Comandos Útiles

#### Iniciar Servidor
```bash
cd /Users/danielgoes96/Desktop/mcp-server
python main.py
# O con uvicorn:
uvicorn main:app --reload --host localhost --port 8002
```

#### Acceder a Documentación
```
http://localhost:8002/docs       # Swagger UI
http://localhost:8002/redoc      # ReDoc
```

#### Verificar Base de Datos
```bash
sqlite3 unified_mcp_system.db
.tables
.schema expenses
```

---

### ANEXO E: Flujos Principales del Usuario

#### Flujo 1: Login
```
1. Usuario → /auth/login (GET) → Página login
2. Usuario ingresa credenciales
3. Cliente → POST /auth/login → JWT token
4. Cliente guarda token en localStorage
5. Redirect → /voice-expenses
```

#### Flujo 2: Crear Gasto
```
1. Usuario en /voice-expenses
2. Graba voz o escribe descripción
3. Cliente → POST /simple_expense o /complete_expense
4. Backend procesa → Claude AI
5. Response con gasto estructurado
6. Cliente muestra resultado
```

#### Flujo 3: Conciliación Bancaria
```
1. Usuario → /bank-reconciliation
2. Upload PDF estado de cuenta
3. Cliente → POST /bank-statements/accounts/{id}/upload
4. Backend parsea PDF → movimientos
5. Cliente → POST /bank_reconciliation/suggestions
6. Backend → ML matching
7. Usuario revisa y acepta
8. Cliente → POST /bank_reconciliation/feedback
```

---

### ANEXO F: Checklist de Correcciones

#### Para Implementar Inmediatamente
- [ ] Montar `financial_reports_router`
- [ ] Montar `polizas_router`
- [ ] Montar `companies_context_router`
- [ ] Montar `transactions_review_router`
- [ ] Montar `ai_retrain_router`
- [ ] Montar `user_context` routers
- [ ] Eliminar ruta `/advanced-ticket-dashboard.html`
- [ ] Crear GET `/sat-accounts` (página)
- [ ] Crear GET `/polizas-dashboard`
- [ ] Crear GET `/financial-reports`
- [ ] Actualizar automation-viewer.html endpoints

#### Para Sprint Próximo
- [ ] Consolidar autenticación (un solo router)
- [ ] Implementar GET `/sat-accounts` API
- [ ] Documentar bundles JavaScript
- [ ] Crear README de frontend build
- [ ] Agregar docstrings a endpoints
- [ ] Implementar response_model en todos los endpoints

#### Backlog
- [ ] Migrar a `/api/v2/*` versionado
- [ ] Implementar test suite (pytest)
- [ ] Deprecar páginas legacy
- [ ] Source maps para bundles
- [ ] Documentación OpenAPI completa

---

## 🎬 CONCLUSIÓN

### Estado General
✅ **Sistema Funcional:** El core del sistema está operativo
⚠️ **Mejoras Necesarias:** Routers no montados y páginas huérfanas
🚀 **Potencial Alto:** Arquitectura sólida con FastAPI + React

### Próximos Pasos Recomendados
1. ✅ Implementar correcciones de PRIORIDAD ALTA (30-60 min)
2. ✅ Validar que páginas funcionan después de montar routers
3. ✅ Documentar cambios realizados
4. ✅ Planificar sprint para PRIORIDAD MEDIA

### Contacto
Para dudas sobre esta auditoría, referirse a:
- **Archivo:** `AUDITORIA_COMPLETA_SISTEMA_MCP.md`
- **Fecha:** 3 de Noviembre, 2025
- **Sistema:** MCP Server v1.0.0

---

**Fin del Reporte** 🎯

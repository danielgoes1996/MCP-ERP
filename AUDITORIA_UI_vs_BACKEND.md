# 🔍 AUDITORÍA: UI vs Backend/Database

**Fecha**: 9 de noviembre de 2025
**Objetivo**: Evaluar qué tan bien el UI refleja la arquitectura completa de BD, modelos y endpoints

---

## 📊 RESUMEN EJECUTIVO

### Cobertura General
```
Backend Endpoints:    10 routers, ~100+ endpoints
Base de Datos:        53 tablas, 8 módulos funcionales
UI Implementado:      6 páginas funcionales (excluyendo auth)

Cobertura UI: ~15% ❌
```

### Veredicto
**El UI NO refleja adecuadamente la arquitectura del backend**. Hay una brecha enorme entre:
- Lo que la BD puede almacenar (80+ campos por expense, ML, IA)
- Lo que el backend expone (APIs completas)
- Lo que el UI muestra (vistas básicas)

---

## 📦 INVENTARIO ACTUAL

### ✅ UI Implementado (6 páginas)

1. **`/dashboard`** - Dashboard básico
2. **`/expenses`** - Lista de gastos
3. **`/invoice-classifier`** - Clasificador de facturas (FASE 1 ✅)
4. **`/tickets`** - Lista de tickets
5. **`/tickets/[id]`** - Detalle de ticket
6. **`/reconciliation`** - Conciliación bancaria

### 🔧 Backend Routers (10 routers)

1. **`auth_router.py`** - Autenticación, registro, JWT
2. **`finance_router.py`** - Reportes financieros, métricas
3. **`bank_router.py`** - Cuentas bancarias, transacciones
4. **`reconciliation_router.py`** - Conciliación automática IA
5. **`invoicing_router.py`** - Tickets, facturas, automatización
6. **`automation_router.py`** - Jobs de automatización
7. **`ai_router.py`** - Clasificación IA, aprendizaje
8. **`config_router.py`** - Configuración, feature flags
9. **`debug_router.py`** - Debugging, health checks
10. **`mcp_router.py`** - MCP tools (probablemente en main.py)

---

## 🚨 BRECHAS CRÍTICAS

### Módulo 1: Gastos y Fiscal (13 tablas) - **Cobertura: 20%**

#### ✅ Implementado
- Lista básica de gastos (`/expenses`)
- Detalle de gasto (parcial)

#### ❌ FALTA (80% del módulo)

**Funcionalidad de `expense_records` (80+ campos) NO expuesta**:

1. **Clasificación Fiscal IA**:
   - ❌ No se muestra `sat_account_code` sugerido
   - ❌ No se muestra `categoria_sugerida` con confianza
   - ❌ No se permite confirmar/corregir categoría IA
   - ❌ No se muestra `razonamiento` (JSON) de la IA
   - ❌ No se muestra si es `deducible` o `requiere_factura`

2. **Impuestos Detallados**:
   - ❌ No se muestra desglose: `subtotal`, `iva_16`, `ieps`, `isr_retenido`
   - ❌ No se calcula `deducible_percent`
   - ❌ No se muestra `iva_acreditable`

3. **Workflow de Aprobación**:
   - ❌ No hay UI para `approval_status`
   - ❌ No se puede aprobar/rechazar gastos
   - ❌ No se muestra quién aprobó (`approved_by`)

4. **Sistema de Tags**:
   - ❌ No se pueden agregar/editar tags
   - ❌ No se pueden filtrar por tags
   - **BD**: `expense_tags`, `expense_tag_relations`

5. **Attachments**:
   - ❌ No se pueden subir múltiples adjuntos por gasto
   - ❌ No se categorizan ('receipt', 'invoice', 'proof')
   - **BD**: `expense_attachments`

6. **Detección de Duplicados ML**:
   - ❌ No se muestra alerta de duplicados
   - ❌ No se muestra `similarity_score`, `risk_level`
   - ❌ No se puede confirmar/rechazar duplicado
   - **BD**: `duplicate_detections`, `duplicate_detection_config`

7. **Completion Status**:
   - ❌ No se muestra `field_completeness` (0.0-1.0)
   - ❌ No se resaltan campos faltantes
   - ❌ No se muestra `validation_errors` (JSON)

8. **Organización**:
   - ❌ No se puede asignar `centro_costo`, `proyecto`
   - ❌ No se edita `metadata` (JSON)

---

### Módulo 2: Conciliación Bancaria (3 tablas) - **Cobertura: 30%**

#### ✅ Implementado
- Vista básica de conciliación (`/reconciliation`)

#### ❌ FALTA (70% del módulo)

1. **Cuentas de Pago**:
   - ❌ No se pueden crear/editar cuentas (`user_payment_accounts`)
   - ❌ No se muestra `saldo_actual`, `credito_disponible` (TDC)
   - ❌ No se configuran `fecha_corte`, `fecha_pago`
   - ❌ No hay selector de cuenta por defecto

2. **Movimientos Bancarios**:
   - ❌ No se importan estados de cuenta
   - ❌ No se muestra `matching_confidence` de la IA
   - ❌ No se puede hacer match manual
   - ❌ No se muestran sugerencias IA (`context_confidence`)

3. **Auto-Match IA**:
   - ❌ No se ejecuta auto-match desde UI
   - ❌ No se muestra `decision` ('auto', 'manual', 'pending')
   - ❌ No se muestra `reconciliation_notes`

---

### Módulo 3: Facturas e Invoicing (9 tablas) - **Cobertura: 40%**

#### ✅ Implementado
- Visor de facturas XML (`/invoice-classifier`) ✅ FASE 1
- Lista de tickets (`/tickets`)
- Detalle de ticket (`/tickets/[id]`)

#### ❌ FALTA (60% del módulo)

1. **Facturas CFDI Completas**:
   - ❌ No se muestra desglose completo (`expense_invoices`)
   - ❌ No se valida contra SAT
   - ❌ No se muestra `cfdi_status` ('vigente', 'cancelada')
   - ❌ No se parsea XML completo (conceptos, impuestos)

2. **Automatización de Facturación**:
   - ❌ No se muestra estado de `automation_jobs`
   - ❌ No se ve progreso (`progress_percentage`, `current_step`)
   - ❌ No se muestran screenshots (`automation_screenshots`)
   - ❌ No se pueden reintentar jobs fallidos

3. **Merchants**:
   - ❌ No hay catálogo de merchants
   - ❌ No se puede configurar `metodo_facturacion` ('litromil', 'portal_web')
   - ❌ No se edita `metadata` (JSON)

4. **Import Logs**:
   - ❌ No se muestra historial de importaciones
   - ❌ No se detectan duplicados en import
   - ❌ No se muestra `processing_time_ms`, `file_hash`

---

### Módulo 4: IA y Aprendizaje (12 tablas) - **Cobertura: 5%**

#### ✅ Implementado
- Se muestra categoría IA en invoice-classifier (nuevo en FASE 1)

#### ❌ FALTA (95% del módulo)

1. **Contexto de Empresa**:
   - ❌ No se edita/visualiza `ai_context_memory`
   - ❌ No se muestra `onboarding_snapshot`
   - ❌ No se actualiza contexto manualmente

2. **Aprendizaje de Correcciones**:
   - ❌ No se registran correcciones automáticamente
   - ❌ No se muestra historial de `ai_correction_memory`
   - ❌ No se visualizan embeddings

3. **Catálogos SAT**:
   - ❌ No hay búsqueda en `sat_account_catalog`
   - ❌ No se autocompletasugiere códigos SAT
   - ❌ No se muestra jerarquía (parent_code)

4. **Trazabilidad de Clasificación**:
   - ❌ No se muestra `classification_trace`
   - ❌ No se explica por qué la IA eligió cierta categoría
   - ❌ No se muestra `razonamiento` (JSON)

5. **Métricas de IA**:
   - ❌ No se muestran métricas de modelo
   - ❌ No se ve uso de GPT (`gpt_usage_events`)
   - ❌ No se comparan versiones de modelo

---

### Módulo 5: Reportes Financieros - **Cobertura: 0%**

#### ❌ COMPLETAMENTE AUSENTE

1. **Dashboard Financiero**:
   - ❌ No hay `/reports` funcional
   - ❌ No se generan reportes fiscales
   - ❌ No se muestran gráficas de gastos por categoría
   - ❌ No hay P&L, Balance Sheet

2. **Exportaciones**:
   - ✅ Export Excel básico (FASE 1)
   - ❌ Export a contabilidad (COI, XML SAT)
   - ❌ Reportes programados

---

### Módulo 6: Pagos CFDI - **Cobertura: 0%**

#### ❌ COMPLETAMENTE AUSENTE

1. **Complementos de Pago**:
   - ❌ No se manejan `cfdi_payments`
   - ❌ No se aplican pagos a facturas (`payment_applications`)
   - ❌ No se calcula `saldo_insoluto`

---

### Módulo 7: Auditoría y Compliance - **Cobertura: 0%**

#### ❌ COMPLETAMENTE AUSENTE

1. **Audit Trail**:
   - ❌ No se muestra historial de cambios
   - ❌ No se ve quién modificó qué
   - ❌ No se pueden revertir cambios

2. **Error Logs**:
   - ❌ No hay visor de errores del sistema
   - ❌ No se categorizan por severidad
   - ❌ No se asignan para resolución

---

## 📋 COMPONENTES FALTANTES CRÍTICOS

### 1. Sistema de Formularios
**Problema**: No hay formularios complejos para editar expenses con 80+ campos

**Necesario**:
- Form wizard multi-paso
- Validación en tiempo real
- Autocompletado (SAT codes, merchants)
- Preview de cambios antes de guardar

### 2. Sistema de Workflows
**Problema**: No se refleja el flujo de estado de los gastos

**Necesario**:
- Visualización de workflow actual
- Acciones disponibles según estado
- Timeline de cambios de estado
- Notificaciones de cambios

### 3. Sistema de Inteligencia Artificial
**Problema**: IA trabaja en background pero usuario no ve nada

**Necesario**:
- Panel de sugerencias IA
- Explicaciones de decisiones ("Por qué la IA clasificó esto así")
- Feedback loop (confirmar/corregir)
- Métricas de confianza visibles

### 4. Sistema de Búsqueda Avanzada
**Problema**: Solo hay búsqueda básica por texto

**Necesario**:
- Filtros multi-campo
- Búsqueda por rango de fechas/montos
- Filtros por estado (approval, invoice, bank)
- Búsqueda semántica (embeddings)

### 5. Sistema de Duplicados
**Problema**: ML detecta duplicados pero usuario no ve alertas

**Necesario**:
- Alertas visuales de duplicados potenciales
- Comparación lado a lado
- Acción: marcar como duplicado / descartar
- Historial de detecciones

---

## 🎯 RECOMENDACIÓN: UI MODERNIZADO

### Propuesta de Reinicio del UI

Dado que solo ~15% del backend está expuesto, recomiendo **reiniciar el UI** con arquitectura moderna:

#### Stack Recomendado (manteniendo Next.js 14)

```typescript
// Arquitectura propuesta
frontend/
├── src/
│   ├── app/                    # Next.js 14 App Router
│   │   ├── (auth)/            # Auth layout group
│   │   ├── (dashboard)/       # Main app layout
│   │   ├── expenses/          # Gestión de gastos COMPLETA
│   │   ├── invoices/          # Facturación COMPLETA
│   │   ├── banking/           # Cuentas y conciliación
│   │   ├── reports/           # Reportes financieros
│   │   ├── ai/                # Panel de IA y aprendizaje
│   │   └── settings/          # Configuración
│   │
│   ├── components/
│   │   ├── forms/             # Form components reutilizables
│   │   │   ├── ExpenseForm/   # Form wizard multi-paso
│   │   │   ├── InvoiceForm/
│   │   │   └── BankForm/
│   │   ├── ai/                # Componentes IA
│   │   │   ├── AISuggestion/
│   │   │   ├── ConfidenceBadge/
│   │   │   └── ExplanationPanel/
│   │   ├── workflow/          # Visualización de workflows
│   │   │   ├── StatusTimeline/
│   │   │   ├── ActionButtons/
│   │   │   └── ApprovalFlow/
│   │   └── data/              # Tablas, listas, filtros
│   │       ├── DataTable/     # Tabla avanzada
│   │       ├── AdvancedFilters/
│   │       └── SearchBar/
│   │
│   ├── features/              # Feature modules
│   │   ├── expenses/
│   │   │   ├── hooks/
│   │   │   ├── services/
│   │   │   ├── schemas/       # Zod schemas
│   │   │   └── types/
│   │   ├── invoices/
│   │   ├── banking/
│   │   └── ai/
│   │
│   └── lib/
│       ├── api/               # API client mejorado
│       ├── schemas/           # Zod validation
│       └── utils/
```

#### Librerías Nuevas Recomendadas

```json
{
  "dependencies": {
    // Formularios
    "react-hook-form": "^7.50.0",      // Mejor manejo de forms
    "zod": "^3.22.0",                   // Validación tipo-segura
    "@hookform/resolvers": "^3.3.0",   // Integración RHF + Zod

    // Tablas avanzadas
    "@tanstack/react-table": "^8.11.0", // Tabla potente (sorting, filtering, pagination)

    // UI Components
    "shadcn/ui": "latest",              // Componentes base modernos
    "recharts": "^2.10.0",              // Gráficas
    "react-hot-toast": "^2.4.0",        // Toast mejorado (reemplaza sonner)

    // Date handling
    "date-fns": "^3.0.0",               // Ya lo tienes ✅

    // IA/ML Visualizations
    "react-markdown": "^9.0.0",         // Renderizar razonamiento IA
    "react-syntax-highlighter": "^15.5.0" // Para JSON previews
  }
}
```

---

## 📝 PLAN DE ACCIÓN PROPUESTO

### Fase 1: Gastos Completos (2-3 semanas)
- [ ] Form wizard multi-paso para crear/editar expense
- [ ] Mostrar todas las sugerencias IA (categoría, SAT codes, confianza)
- [ ] Sistema de aprobación (aprobar/rechazar)
- [ ] Tags system completo
- [ ] Adjuntos múltiples
- [ ] Alertas de duplicados

### Fase 2: Inteligencia Artificial (1-2 semanas)
- [ ] Panel de explicaciones IA
- [ ] Feedback loop (confirmar/corregir clasificación)
- [ ] Visualización de contexto de empresa
- [ ] Métricas de IA y GPT usage

### Fase 3: Banking & Conciliación (2 semanas)
- [ ] CRUD completo de cuentas de pago
- [ ] Import de estados de cuenta
- [ ] Auto-match IA con visualización
- [ ] Match manual mejorado

### Fase 4: Facturación Avanzada (2 semanas)
- [ ] Viewer CFDI completo (todos los campos)
- [ ] Monitor de automation jobs
- [ ] Catálogo de merchants
- [ ] Validación SAT en tiempo real

### Fase 5: Reportes (1-2 semanas)
- [ ] Dashboard financiero con gráficas
- [ ] Reportes por categoría/período
- [ ] Export a formatos contables
- [ ] P&L, Balance Sheet básico

### Fase 6: Auditoría & Compliance (1 semana)
- [ ] Audit trail viewer
- [ ] Error logs dashboard
- [ ] Compliance checks

---

## 🎨 MOCKUPS CONCEPTUALES

### Expense Detail - ANTES vs DESPUÉS

#### ❌ ANTES (Actual)
```
┌─────────────────────────────┐
│ Gasto #123                  │
├─────────────────────────────┤
│ Monto: $500                 │
│ Descripción: Taxi           │
│ Fecha: 2024-01-10           │
│                             │
│ [Editar] [Eliminar]         │
└─────────────────────────────┘
```

#### ✅ DESPUÉS (Propuesto)
```
┌────────────────────────────────────────────────────────┐
│ 💰 Gasto #123                    Estado: ⏳ Pendiente  │
├────────────────────────────────────────────────────────┤
│ Timeline: ●━━○━━○━━○                                   │
│          Creado → Clasif. → Factura → Aprobado        │
├────────────────────────────────────────────────────────┤
│ 📋 Información Básica                                  │
│   Monto: $500.00 MXN        Fecha: 10/01/2024        │
│   Descripción: Taxi aeropuerto                        │
│   Merchant: Uber México                               │
│                                                        │
│ 🤖 Clasificación IA (Confianza: 95%)                  │
│   Categoría: Transporte Terrestre                    │
│   SAT Code: 601.84.01 - Transporte                   │
│   Deducible: ✅ Sí (100%)                            │
│   Requiere Factura: ✅ Sí                            │
│                                                        │
│   💡 Razonamiento IA:                                 │
│   "Gasto de transporte terrestre identificado por    │
│    el merchant 'Uber' y la descripción. Deducible    │
│    al 100% según políticas fiscales vigentes."       │
│                                                        │
│   [✓ Confirmar] [✎ Corregir Categoría]               │
│                                                        │
│ 💳 Impuestos                                          │
│   Subtotal: $431.03                                   │
│   IVA 16%: $68.97                                     │
│   Total: $500.00                                      │
│                                                        │
│ 🏷️ Tags: [transporte] [cliente-abc] [+Agregar]      │
│                                                        │
│ 📎 Adjuntos (2)                                       │
│   [📄] ticket.pdf (Recibo)                           │
│   [📄] factura.xml (Factura)                         │
│   [+ Subir Archivo]                                   │
│                                                        │
│ ⚠️ Duplicado Potencial Detectado                      │
│   Gasto similar: #115 ($500, Uber, 09/01/2024)      │
│   Similitud: 87% | Riesgo: Alto                      │
│   [Ver Comparación] [Marcar Duplicado] [Descartar]   │
│                                                        │
│ 📊 Workflow                                           │
│   ● Creado por: Juan Pérez (05/01/2024 10:30)       │
│   ● Clasificado: IA Modelo v2.3 (05/01/2024 10:31)  │
│   ○ Pendiente: Facturación                          │
│   ○ Pendiente: Aprobación de gerente                │
│                                                        │
│ [✓ Aprobar] [✗ Rechazar] [📝 Editar] [💬 Comentar]  │
└────────────────────────────────────────────────────────┘
```

---

## 🚀 DECISIÓN FINAL

### ¿Reiniciar UI?

**SÍ**, definitivamente recomiendo reiniciar el UI porque:

1. **Brecha Arquitectural**: Solo 15% del backend está expuesto
2. **Complejidad Subestimada**: `expense_records` tiene 80+ campos, el UI actual solo muestra 5
3. **IA Invisible**: Toda la inteligencia artificial trabaja pero el usuario no lo ve
4. **Workflows No Implementados**: Estados, aprobaciones, conciliación no están en UI
5. **UX Pobre**: No hay formularios avanzados, validaciones, feedback visual

### Mantener del UI Actual

✅ **CONSERVAR**:
- Login/Register (funcionan bien)
- Header/Layout base
- Sistema de auth (Zustand + JWT)
- Invoice classifier base (mejorarlo pero no reiniciar)

❌ **REINICIAR**:
- `/expenses` - Muy básico
- `/dashboard` - No refleja data real
- `/reconciliation` - Incompleto
- `/tickets` - Falta mucha funcionalidad

---

## 📊 MÉTRICAS DE ÉXITO

Si reiniciamos el UI correctamente, deberíamos alcanzar:

```
Cobertura Backend:     15% → 80%
Campos Expense:        5 → 60+
Features IA Visibles:  1 → 10+
Workflows:             0 → 5
User Satisfaction:     ⭐⭐ → ⭐⭐⭐⭐⭐
```

---

## ✅ CONCLUSIÓN

**Tu intuición es correcta**: El UI actual NO refleja la arquitectura de BD/Backend.

**Recomendación**: Reiniciar el UI (excluyendo auth) con:
- Arquitectura moderna basada en features
- Formularios complejos (react-hook-form + zod)
- Tablas avanzadas (TanStack Table)
- Visualización completa de IA
- Sistema de workflows

**Prioridad #1**: Módulo de Gastos completo, porque es el 70% del valor del sistema.

---

**Siguiente Paso Sugerido**: ¿Quieres que diseñe la nueva arquitectura del UI con código base?

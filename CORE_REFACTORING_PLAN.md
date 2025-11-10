# 🏗️ Core Refactoring Plan - Fase 2.4

## 📊 Situación Actual

**Archivos en core/**: 138 archivos Python + 1 subdirectorio (ai/)
**Problema**: Estructura plana dificulta navegación y mantenimiento

---

## 🎯 Nueva Estructura Propuesta

```
core/
├── __init__.py
│
├── auth/                           # Sistema de Autenticación
│   ├── __init__.py
│   ├── jwt_auth.py                 # auth_jwt.py
│   ├── unified_auth.py             # unified_auth.py
│   ├── auth_system.py              # auth_system.py
│   └── models.py                   # Modelos de auth
│
├── ai_pipeline/                    # Inteligencia Artificial y ML
│   ├── __init__.py
│   ├── categorization/
│   │   ├── __init__.py
│   │   ├── predictor.py            # category_predictor.py
│   │   ├── learning_system.py      # category_learning_system.py
│   │   ├── mappings.py             # category_mappings.py
│   │   └── llm_classifier.py       # expense_llm_classifier.py
│   ├── ocr/
│   │   ├── __init__.py
│   │   ├── advanced_service.py     # advanced_ocr_service.py
│   │   └── ticket_ocr.py           # ticket_ocr.py
│   ├── nlp/
│   │   ├── __init__.py
│   │   ├── context_memory.py       # ai_context_memory.py
│   │   └── correction_memory.py    # ai_correction_memory.py
│   ├── features/
│   │   ├── __init__.py
│   │   └── expense_features.py     # expense_features.py
│   └── models/
│       ├── __init__.py
│       └── api_models.py           # api_models.py (parte AI)
│
├── reconciliation/                 # Conciliación Bancaria
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── bank_reconciliation.py  # bank_reconciliation.py
│   │   ├── ai_service.py           # ai_reconciliation_service.py
│   │   └── split_models.py         # split_reconciliation_models.py
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── bank_file_parser.py     # bank_file_parser.py
│   │   ├── cargos_abonos.py        # cargos_abonos_parser.py
│   │   └── statement_parser.py     # bank_statement_parser.py
│   ├── detectors/
│   │   ├── __init__.py
│   │   └── bank_detector.py        # bank_detector.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── statements.py           # bank_statements_models.py
│   │   └── transactions.py         # bank_transactions_models.py
│   └── rules/
│       ├── __init__.py
│       └── loader.py               # bank_rules_loader.py
│
├── expenses/                       # Gestión de Gastos
│   ├── __init__.py
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── validator.py            # expense_validation.py
│   │   └── duplicate_detector.py   # duplicate_detection.py
│   ├── classification/
│   │   ├── __init__.py
│   │   ├── trace.py                # classification_trace.py
│   │   └── feedback.py             # classification_feedback.py
│   ├── escalation/
│   │   ├── __init__.py
│   │   ├── system.py               # expense_escalation_system.py
│   │   └── hooks.py                # expense_escalation_hooks.py
│   ├── advances/
│   │   ├── __init__.py
│   │   └── models.py               # employee_advances_models.py
│   └── models/
│       ├── __init__.py
│       └── expense_models.py       # Modelos de expense
│
├── invoicing/                      # Sistema de Facturación
│   ├── __init__.py
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── invoice_parser.py       # invoice_parser.py
│   │   └── cfdi_parser.py          # cfdi_parser.py
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── bulk_processor.py       # bulk_invoice_processor.py
│   │   └── ocr_processor.py        # invoice_ocr_processor.py
│   ├── automation/
│   │   ├── __init__.py
│   │   ├── ticket_analyzer.py      # ticket_analyzer.py
│   │   └── merchant_automation.py  # merchant_automation.py
│   └── models/
│       ├── __init__.py
│       └── invoice_models.py
│
├── automation/                     # RPA y Automatización
│   ├── __init__.py
│   ├── rpa/
│   │   ├── __init__.py
│   │   ├── planner.py              # ai_rpa_planner.py
│   │   ├── executor.py             # web_automation_executor.py
│   │   └── persistence.py          # automation_persistence_system.py
│   ├── captcha/
│   │   ├── __init__.py
│   │   └── solver.py               # captcha_solver.py
│   └── models/
│       ├── __init__.py
│       └── automation_models.py    # automation_models.py
│
├── accounting/                     # Contabilidad y SAT
│   ├── __init__.py
│   ├── catalogs/
│   │   ├── __init__.py
│   │   ├── account_catalog.py      # account_catalog.py
│   │   └── sat_utils.py            # sat_utils.py
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── accounting_rules.py     # accounting_rules.py
│   │   └── mappings.yaml           # accounting_mappings.yaml
│   ├── models/
│   │   ├── __init__.py
│   │   └── accounting_models.py    # accounting_models.py
│   └── fiscal/
│       ├── __init__.py
│       └── pipeline.py             # fiscal_pipeline.py
│
├── integrations/                   # Integraciones Externas
│   ├── __init__.py
│   ├── whatsapp/
│   │   ├── __init__.py
│   │   └── integration.py          # whatsapp_integration.py
│   ├── email/
│   │   ├── __init__.py
│   │   └── integration.py          # email_integration.py
│   ├── odoo/
│   │   ├── __init__.py
│   │   └── sync.py                 # odoo_sync.py
│   └── erp/
│       ├── __init__.py
│       └── connector.py            # erp_connector.py
│
├── database/                       # Database Layer
│   ├── __init__.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   └── unified_adapter.py      # unified_db_adapter.py
│   ├── internal/
│   │   ├── __init__.py
│   │   └── internal_db.py          # internal_db.py
│   └── handlers/
│       ├── __init__.py
│       └── mcp_handler.py          # mcp_handler.py
│
├── tenancy/                        # Multi-tenancy
│   ├── __init__.py
│   ├── policies.py                 # tenant_policies.py
│   ├── context.py                  # tenant_context.py
│   └── isolation.py                # tenant_isolation.py
│
└── common/                         # Utilidades Comunes
    ├── __init__.py
    ├── logging/
    │   ├── __init__.py
    │   └── structured_logger.py    # structured_logger.py
    ├── tasks/
    │   ├── __init__.py
    │   └── dispatcher.py           # task_dispatcher.py
    ├── credentials/
    │   ├── __init__.py
    │   └── manager.py              # client_credential_manager.py
    ├── optimization/
    │   ├── __init__.py
    │   └── batch_optimizer.py      # batch_performance_optimizer.py
    ├── versioning/
    │   ├── __init__.py
    │   └── api_version_manager.py  # api_version_manager.py
    └── utils/
        ├── __init__.py
        └── helpers.py
```

---

## 📊 Distribución de Archivos

| Módulo | Archivos | % Total |
|--------|----------|---------|
| ai_pipeline/ | 25 | 18% |
| reconciliation/ | 15 | 11% |
| expenses/ | 18 | 13% |
| invoicing/ | 20 | 14% |
| automation/ | 12 | 9% |
| accounting/ | 15 | 11% |
| integrations/ | 10 | 7% |
| database/ | 8 | 6% |
| auth/ | 5 | 4% |
| tenancy/ | 4 | 3% |
| common/ | 6 | 4% |

---

## ✅ Beneficios

### 1. **Navegabilidad**
- ✅ Estructura lógica por dominio
- ✅ Fácil encontrar archivos relacionados
- ✅ Clara separación de responsabilidades

### 2. **Mantenibilidad**
- ✅ Cambios localizados a módulos específicos
- ✅ Menor acoplamiento entre módulos
- ✅ Testing más fácil por módulo

### 3. **Escalabilidad**
- ✅ Fácil agregar nuevas features por módulo
- ✅ Equipos pueden trabajar en módulos independientes
- ✅ Despliegue modular posible

### 4. **Onboarding**
- ✅ Nuevos devs encuentran código rápidamente
- ✅ Documentación por módulo
- ✅ Patrones consistentes

---

## 🚀 Plan de Ejecución

### Fase 1: Crear Estructura (5 min)
```bash
mkdir -p core/{auth,ai_pipeline,reconciliation,expenses,invoicing}
mkdir -p core/{automation,accounting,integrations,database,tenancy,common}
# ... subdirectorios
```

### Fase 2: Mover Archivos (15 min)
- Mover archivos a nuevas ubicaciones
- Preservar git history con `git mv`

### Fase 3: Actualizar Imports (30 min)
- Buscar y reemplazar imports en todo el proyecto
- Actualizar `from core.x import y` → `from core.module.x import y`

### Fase 4: Crear __init__.py (10 min)
- Exportar APIs públicas de cada módulo
- Facilitar imports

### Fase 5: Testing (15 min)
- Ejecutar tests completos
- Validar que todo funciona

### Fase 6: Documentación (10 min)
- README por módulo
- Actualizar ARCHITECTURE.md

---

## ⚠️ Riesgos y Mitigaciones

| Riesgo | Probabilidad | Mitigación |
|--------|--------------|------------|
| Imports rotos | Alta | Script automático de búsqueda/reemplazo |
| Tests fallan | Media | Ejecutar tests después de cada cambio |
| Git history perdido | Baja | Usar `git mv` en lugar de `mv` |
| Circular imports | Media | Revisar dependencias, usar imports tardíos |

---

## 🔄 Rollback Plan

Si algo falla:
```bash
# Revertir todos los cambios
git reset --hard HEAD

# O revertir commit específico
git revert <commit-hash>
```

---

## 📝 Notas Importantes

1. **Usar `git mv`** para preservar history
2. **Commits atómicos** por módulo
3. **Tests después de cada módulo** migrado
4. **No cambiar lógica**, solo organización
5. **Documentar** cada módulo con README

---

## ✅ Checklist de Ejecución

- [ ] Crear estructura de directorios
- [ ] Mover archivos de `auth/`
- [ ] Mover archivos de `ai_pipeline/`
- [ ] Mover archivos de `reconciliation/`
- [ ] Mover archivos de `expenses/`
- [ ] Mover archivos de `invoicing/`
- [ ] Mover archivos de `automation/`
- [ ] Mover archivos de `accounting/`
- [ ] Mover archivos de `integrations/`
- [ ] Mover archivos de `database/`
- [ ] Mover archivos de `tenancy/`
- [ ] Mover archivos de `common/`
- [ ] Actualizar todos los imports
- [ ] Crear __init__.py
- [ ] Ejecutar tests
- [ ] Documentar
- [ ] Commit

---

**Tiempo Total Estimado**: 1.5 - 2 horas
**Complejidad**: Media
**Impacto**: Alto (mejora significativa en mantenibilidad)

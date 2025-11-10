#!/usr/bin/env python3
"""
Script para reorganizar la estructura de core/ en dominios lógicos.
Fase 2.4 - Refactor Estructural
"""

import os
import shutil
from pathlib import Path

# Mapeo de archivos a sus nuevas ubicaciones
MIGRATION_MAP = {
    # AI Pipeline - Parsers
    "core/gemini_parser.py": "core/ai_pipeline/parsers/gemini_parser.py",
    "core/gemini_complete_parser.py": "core/ai_pipeline/parsers/gemini_complete_parser.py",
    "core/gemini_native_parser.py": "core/ai_pipeline/parsers/gemini_native_parser.py",
    "core/cfdi_llm_parser.py": "core/ai_pipeline/parsers/cfdi_llm_parser.py",
    "core/robust_pdf_parser.py": "core/ai_pipeline/parsers/robust_pdf_parser.py",
    "core/enhanced_pdf_parser.py": "core/ai_pipeline/parsers/enhanced_pdf_parser.py",
    "core/invoice_parser.py": "core/ai_pipeline/parsers/invoice_parser.py",

    # AI Pipeline - OCR
    "core/advanced_ocr_service.py": "core/ai_pipeline/ocr/advanced_ocr_service.py",
    "core/hybrid_vision_service.py": "core/ai_pipeline/ocr/hybrid_vision_service.py",

    # AI Pipeline - Classification
    "core/category_predictor.py": "core/ai_pipeline/classification/category_predictor.py",
    "core/category_learning_system.py": "core/ai_pipeline/classification/category_learning_system.py",
    "core/enhanced_categorization_engine.py": "core/ai_pipeline/classification/enhanced_categorization_engine.py",
    "core/expense_classifier.py": "core/ai_pipeline/classification/expense_classifier.py",
    "core/expense_llm_classifier.py": "core/ai_pipeline/classification/expense_llm_classifier.py",
    "core/classification_feedback.py": "core/ai_pipeline/classification/classification_feedback.py",
    "core/classification_trace.py": "core/ai_pipeline/classification/classification_trace.py",
    "core/category_mappings.py": "core/ai_pipeline/classification/category_mappings.py",

    # AI Pipeline - Automation
    "core/ai_rpa_planner.py": "core/ai_pipeline/automation/ai_rpa_planner.py",
    "core/claude_dom_analyzer.py": "core/ai_pipeline/automation/claude_dom_analyzer.py",
    "core/captcha_solver.py": "core/ai_pipeline/automation/captcha_solver.py",

    # Reconciliation - Bank
    "core/bank_detector.py": "core/reconciliation/bank/bank_detector.py",
    "core/bank_file_parser.py": "core/reconciliation/bank/bank_file_parser.py",
    "core/bank_rules_loader.py": "core/reconciliation/bank/bank_rules_loader.py",
    "core/universal_bank_patterns.py": "core/reconciliation/bank/universal_bank_patterns.py",
    "core/cargos_abonos_parser.py": "core/reconciliation/bank/cargos_abonos_parser.py",
    "core/bank_statements_models.py": "core/reconciliation/bank/bank_statements_models.py",
    "core/bank_transactions_models.py": "core/reconciliation/bank/bank_transactions_models.py",

    # Reconciliation - Matching
    "core/ai_reconciliation_service.py": "core/reconciliation/matching/ai_reconciliation_service.py",
    "core/bank_reconciliation.py": "core/reconciliation/matching/bank_reconciliation.py",
    "core/smart_reconciliation_engine.py": "core/reconciliation/matching/smart_reconciliation_engine.py",
    "core/claude_transaction_processor.py": "core/reconciliation/matching/claude_transaction_processor.py",
    "core/transaction_enrichment.py": "core/reconciliation/matching/transaction_enrichment.py",

    # Reconciliation - Validation
    "core/duplicate_detector.py": "core/reconciliation/validation/duplicate_detector.py",
    "core/duplicate_prevention.py": "core/reconciliation/validation/duplicate_prevention.py",
    "core/optimized_duplicate_detector.py": "core/reconciliation/validation/optimized_duplicate_detector.py",

    # Expenses - Invoices
    "core/invoice_manager.py": "core/expenses/invoices/invoice_manager.py",
    "core/bulk_invoice_processor.py": "core/expenses/invoices/bulk_invoice_processor.py",
    "core/universal_invoice_engine_system.py": "core/expenses/invoices/universal_invoice_engine_system.py",
    "core/universal_invoice_processor.py": "core/expenses/invoices/universal_invoice_processor.py",

    # Expenses - Completion
    "core/expense_completion_system.py": "core/expenses/completion/expense_completion_system.py",
    "core/expense_enhancer.py": "core/expenses/completion/expense_enhancer.py",
    "core/expense_enrichment.py": "core/expenses/completion/expense_enrichment.py",
    "core/intelligent_field_validator.py": "core/expenses/completion/intelligent_field_validator.py",

    # Expenses - Validation
    "core/expense_validator.py": "core/expenses/validation/expense_validator.py",
    "core/expense_validation.py": "core/expenses/validation/expense_validation.py",
    "core/expense_field_validator.py": "core/expenses/validation/expense_field_validator.py",
    "core/expense_features.py": "core/expenses/validation/expense_features.py",

    # Expenses - Workflow
    "core/expense_escalation_system.py": "core/expenses/workflow/expense_escalation_system.py",
    "core/expense_escalation_hooks.py": "core/expenses/workflow/expense_escalation_hooks.py",
    "core/expense_rollback_system.py": "core/expenses/workflow/expense_rollback_system.py",
    "core/expense_notification_system.py": "core/expenses/workflow/expense_notification_system.py",

    # Expenses - Audit
    "core/expense_audit_system.py": "core/expenses/audit/expense_audit_system.py",
    "core/compliance_audit_trail.py": "core/expenses/audit/compliance_audit_trail.py",

    # Expenses - Models
    "core/expense_models.py": "core/expenses/models.py",
    "core/enhanced_api_models.py": "core/expenses/enhanced_api_models.py",
    "core/employee_advances_models.py": "core/expenses/employee_advances_models.py",
    "core/employee_advances_service.py": "core/expenses/employee_advances_service.py",
    "core/automation_models.py": "core/expenses/automation_models.py",

    # Reports
    "core/financial_reports_engine.py": "core/reports/financial_reports_engine.py",
    "core/financial_reports_generator_simple.py": "core/reports/financial_reports_generator_simple.py",
    "core/cost_analytics.py": "core/reports/cost_analytics.py",
    "core/stp_reports_service.py": "core/reports/stp_reports_service.py",

    # Shared
    "core/text_normalizer.py": "core/shared/text_normalizer.py",
    "core/mcp_handler.py": "core/shared/mcp_handler.py",
    "core/observability_system.py": "core/shared/observability_system.py",
    "core/task_dispatcher.py": "core/shared/task_dispatcher.py",
    "core/robust_fallback_system.py": "core/shared/robust_fallback_system.py",
    "core/unified_db_adapter.py": "core/shared/unified_db_adapter.py",
    "core/db_optimizer.py": "core/shared/db_optimizer.py",
    "core/batch_performance_optimizer.py": "core/shared/batch_performance_optimizer.py",
    "core/data_consistency_manager.py": "core/shared/data_consistency_manager.py",

    # Config
    "core/company_settings.py": "core/config/company_settings.py",
    "core/service_stack_config.py": "core/config/service_stack_config.py",
    "core/feature_flags.py": "core/config/feature_flags.py",
    "core/api_version_manager.py": "core/config/api_version_manager.py",

    # Accounting
    "core/account_catalog.py": "core/accounting/account_catalog.py",
    "core/accounting_catalog.py": "core/accounting/accounting_catalog.py",
    "core/accounting_models.py": "core/accounting/accounting_models.py",
    "core/accounting_rules.py": "core/accounting/accounting_rules.py",
    "core/polizas_service.py": "core/accounting/polizas_service.py",
}

def move_file(src: str, dst: str, dry_run: bool = True):
    """Mueve un archivo manteniendo el historial git"""
    src_path = Path(src)
    dst_path = Path(dst)

    if not src_path.exists():
        print(f"⚠️  SKIP: {src} no existe")
        return False

    if dst_path.exists():
        print(f"⚠️  SKIP: {dst} ya existe")
        return False

    # Crear directorio destino si no existe
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    if dry_run:
        print(f"🔄 WOULD MOVE: {src} → {dst}")
        return True
    else:
        try:
            # Usar git mv para mantener historial
            os.system(f'git mv "{src}" "{dst}"')
            print(f"✅ MOVED: {src} → {dst}")
            return True
        except Exception as e:
            print(f"❌ ERROR moving {src}: {e}")
            return False

def create_init_files(dry_run: bool = True):
    """Crea archivos __init__.py en todas las carpetas"""
    directories = [
        "core/ai_pipeline",
        "core/ai_pipeline/parsers",
        "core/ai_pipeline/ocr",
        "core/ai_pipeline/classification",
        "core/ai_pipeline/automation",
        "core/reconciliation",
        "core/reconciliation/bank",
        "core/reconciliation/matching",
        "core/reconciliation/validation",
        "core/expenses",
        "core/expenses/invoices",
        "core/expenses/completion",
        "core/expenses/validation",
        "core/expenses/workflow",
        "core/expenses/audit",
        "core/reports",
        "core/shared",
        "core/config",
        "core/accounting",
        "api/reconciliation",
        "api/expenses",
        "api/automation",
        "api/reports",
    ]

    for directory in directories:
        init_file = Path(directory) / "__init__.py"
        if not init_file.exists():
            if dry_run:
                print(f"🆕 WOULD CREATE: {init_file}")
            else:
                init_file.write_text("# Auto-generated __init__.py\n")
                print(f"✅ CREATED: {init_file}")

def main():
    import sys

    dry_run = "--execute" not in sys.argv

    if dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No se realizarán cambios reales")
        print("Ejecuta con --execute para aplicar los cambios")
        print("=" * 60)
        print()

    print("📦 Fase 2.4 - Refactor Estructural")
    print()

    # 1. Crear archivos __init__.py
    print("📝 Creando archivos __init__.py...")
    create_init_files(dry_run)
    print()

    # 2. Mover archivos
    print("🚚 Moviendo archivos...")
    moved = 0
    skipped = 0

    for src, dst in MIGRATION_MAP.items():
        if move_file(src, dst, dry_run):
            moved += 1
        else:
            skipped += 1

    print()
    print("=" * 60)
    print(f"✅ Archivos movidos: {moved}")
    print(f"⚠️  Archivos omitidos: {skipped}")
    print("=" * 60)

    if dry_run:
        print()
        print("Para ejecutar los cambios reales:")
        print("  python scripts/refactor_structure.py --execute")

if __name__ == "__main__":
    main()

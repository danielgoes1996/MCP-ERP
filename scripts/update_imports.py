#!/usr/bin/env python3
"""
Script para actualizar imports después del refactor estructural.
Fase 2.4 - Refactor Estructural
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple

# Mapeo de imports antiguos a nuevos
IMPORT_MAP = {
    # AI Pipeline - Parsers
    "from core.ai_pipeline.parsers.gemini_complete_parser": "from core.ai_pipeline.parsers.gemini_complete_parser",
    "from core.ai_pipeline.parsers.gemini_native_parser": "from core.ai_pipeline.parsers.gemini_native_parser",
    "from core.ai_pipeline.parsers.cfdi_llm_parser": "from core.ai_pipeline.parsers.cfdi_llm_parser",
    "from core.ai_pipeline.parsers.robust_pdf_parser": "from core.ai_pipeline.parsers.robust_pdf_parser",
    "from core.ai_pipeline.parsers.enhanced_pdf_parser": "from core.ai_pipeline.parsers.enhanced_pdf_parser",
    "from core.ai_pipeline.parsers.invoice_parser": "from core.ai_pipeline.parsers.invoice_parser",
    "import core.ai_pipeline.parsers.gemini_complete_parser": "import core.ai_pipeline.parsers.gemini_complete_parser",

    # AI Pipeline - OCR
    "from core.ai_pipeline.ocr.advanced_ocr_service": "from core.ai_pipeline.ocr.advanced_ocr_service",
    "from core.ai_pipeline.ocr.hybrid_vision_service": "from core.ai_pipeline.ocr.hybrid_vision_service",

    # AI Pipeline - Classification
    "from core.ai_pipeline.classification.category_predictor": "from core.ai_pipeline.classification.category_predictor",
    "from core.ai_pipeline.classification.category_learning_system": "from core.ai_pipeline.classification.category_learning_system",
    "from core.ai_pipeline.classification.enhanced_categorization_engine": "from core.ai_pipeline.classification.enhanced_categorization_engine",
    "from core.ai_pipeline.classification.expense_classifier": "from core.ai_pipeline.classification.expense_classifier",
    "from core.ai_pipeline.classification.expense_llm_classifier": "from core.ai_pipeline.classification.expense_llm_classifier",
    "from core.ai_pipeline.classification.classification_feedback": "from core.ai_pipeline.classification.classification_feedback",
    "from core.ai_pipeline.classification.classification_trace": "from core.ai_pipeline.classification.classification_trace",
    "from core.ai_pipeline.classification.category_mappings": "from core.ai_pipeline.classification.category_mappings",

    # AI Pipeline - Automation
    "from core.ai_pipeline.automation.ai_rpa_planner": "from core.ai_pipeline.automation.ai_rpa_planner",
    "from core.ai_pipeline.automation.claude_dom_analyzer": "from core.ai_pipeline.automation.claude_dom_analyzer",
    "from core.ai_pipeline.automation.captcha_solver": "from core.ai_pipeline.automation.captcha_solver",

    # Reconciliation - Bank
    "from core.reconciliation.bank.bank_detector": "from core.reconciliation.bank.bank_detector",
    "from core.reconciliation.bank.bank_file_parser": "from core.reconciliation.bank.bank_file_parser",
    "from core.reconciliation.bank.bank_rules_loader": "from core.reconciliation.bank.bank_rules_loader",
    "from core.reconciliation.bank.universal_bank_patterns": "from core.reconciliation.bank.universal_bank_patterns",
    "from core.reconciliation.bank.cargos_abonos_parser": "from core.reconciliation.bank.cargos_abonos_parser",
    "from core.reconciliation.bank.bank_statements_models": "from core.reconciliation.bank.bank_statements_models",
    "from core.reconciliation.bank.bank_transactions_models": "from core.reconciliation.bank.bank_transactions_models",

    # Reconciliation - Matching
    "from core.reconciliation.matching.ai_reconciliation_service": "from core.reconciliation.matching.ai_reconciliation_service",
    "from core.reconciliation.matching.bank_reconciliation": "from core.reconciliation.matching.bank_reconciliation",
    "from core.reconciliation.matching.claude_transaction_processor": "from core.reconciliation.matching.claude_transaction_processor",

    # Reconciliation - Validation
    "from core.reconciliation.validation.duplicate_detector": "from core.reconciliation.validation.duplicate_detector",
    "from core.reconciliation.validation.duplicate_prevention": "from core.reconciliation.validation.duplicate_prevention",
    "from core.reconciliation.validation.optimized_duplicate_detector": "from core.reconciliation.validation.optimized_duplicate_detector",

    # Expenses - Invoices
    "from core.expenses.invoices.invoice_manager": "from core.expenses.invoices.invoice_manager",
    "from core.expenses.invoices.bulk_invoice_processor": "from core.expenses.invoices.bulk_invoice_processor",
    "from core.expenses.invoices.universal_invoice_engine_system": "from core.expenses.invoices.universal_invoice_engine_system",

    # Expenses - Completion
    "from core.expenses.completion.expense_completion_system": "from core.expenses.completion.expense_completion_system",
    "from core.expenses.completion.expense_enhancer": "from core.expenses.completion.expense_enhancer",
    "from core.expenses.completion.expense_enrichment": "from core.expenses.completion.expense_enrichment",
    "from core.expenses.completion.intelligent_field_validator": "from core.expenses.completion.intelligent_field_validator",

    # Expenses - Validation
    "from core.expenses.validation.expense_validator": "from core.expenses.validation.expense_validator",
    "from core.expenses.validation.expense_validation": "from core.expenses.validation.expense_validation",
    "from core.expenses.validation.expense_field_validator": "from core.expenses.validation.expense_field_validator",
    "from core.expenses.validation.expense_features": "from core.expenses.validation.expense_features",

    # Expenses - Workflow
    "from core.expenses.workflow.expense_escalation_system": "from core.expenses.workflow.expense_escalation_system",
    "from core.expenses.workflow.expense_escalation_hooks": "from core.expenses.workflow.expense_escalation_hooks",
    "from core.expenses.workflow.expense_rollback_system": "from core.expenses.workflow.expense_rollback_system",
    "from core.expenses.workflow.expense_notification_system": "from core.expenses.workflow.expense_notification_system",

    # Expenses - Audit
    "from core.expenses.audit.expense_audit_system": "from core.expenses.audit.expense_audit_system",
    "from core.expenses.audit.compliance_audit_trail": "from core.expenses.audit.compliance_audit_trail",

    # Expenses - Models
    "from core.expenses.models": "from core.expenses.models",
    "from core.expenses.enhanced_api_models": "from core.expenses.enhanced_api_models",
    "from core.expenses.employee_advances_models": "from core.expenses.employee_advances_models",
    "from core.expenses.employee_advances_service": "from core.expenses.employee_advances_service",
    "from core.expenses.automation_models": "from core.expenses.automation_models",

    # Reports
    "from core.reports.financial_reports_engine": "from core.reports.financial_reports_engine",
    "from core.reports.financial_reports_generator_simple": "from core.reports.financial_reports_generator_simple",
    "from core.reports.cost_analytics": "from core.reports.cost_analytics",

    # Shared
    "from core.shared.text_normalizer": "from core.shared.text_normalizer",
    "from core.shared.mcp_handler": "from core.shared.mcp_handler",
    "from core.shared.observability_system": "from core.shared.observability_system",
    "from core.shared.task_dispatcher": "from core.shared.task_dispatcher",
    "from core.shared.robust_fallback_system": "from core.shared.robust_fallback_system",
    "from core.shared.unified_db_adapter": "from core.shared.unified_db_adapter",
    "from core.shared.db_optimizer": "from core.shared.db_optimizer",
    "from core.shared.batch_performance_optimizer": "from core.shared.batch_performance_optimizer",
    "from core.shared.data_consistency_manager": "from core.shared.data_consistency_manager",

    # Config
    "from core.config.company_settings": "from core.config.company_settings",
    "from core.config.service_stack_config": "from core.config.service_stack_config",
    "from core.config.feature_flags": "from core.config.feature_flags",
    "from core.config.api_version_manager": "from core.config.api_version_manager",

    # Accounting
    "from core.accounting.account_catalog": "from core.accounting.account_catalog",
    "from core.accounting.accounting_catalog": "from core.accounting.accounting_catalog",
    "from core.accounting.accounting_models": "from core.accounting.accounting_models",
    "from core.accounting.accounting_rules": "from core.accounting.accounting_rules",
    "from core.accounting.polizas_service": "from core.accounting.polizas_service",
}

def update_file_imports(file_path: Path, dry_run: bool = True) -> Tuple[bool, int]:
    """
    Actualiza los imports en un archivo.
    Retorna (changed, num_replacements)
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        replacements = 0

        for old_import, new_import in IMPORT_MAP.items():
            if old_import in content:
                content = content.replace(old_import, new_import)
                count = original_content.count(old_import)
                replacements += count
                if not dry_run and count > 0:
                    try:
                        rel_path = file_path.relative_to(Path.cwd())
                    except ValueError:
                        rel_path = file_path
                    print(f"  ✏️  {rel_path}: {old_import} → {new_import} ({count}x)")

        if content != original_content:
            if not dry_run:
                file_path.write_text(content, encoding='utf-8')
            return True, replacements

        return False, 0

    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return False, 0

def find_python_files() -> List[Path]:
    """Encuentra todos los archivos Python en el proyecto"""
    python_files = []
    base_path = Path.cwd()

    # Buscar en directorios principales
    for directory in ['api', 'core', 'app', 'tests', 'scripts']:
        path = base_path / directory
        if path.exists():
            python_files.extend(path.rglob('*.py'))

    # Incluir main.py
    main_py = base_path / 'main.py'
    if main_py.exists():
        python_files.append(main_py)

    return python_files

def main():
    import sys

    dry_run = "--execute" not in sys.argv

    if dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No se realizarán cambios reales")
        print("Ejecuta con --execute para aplicar los cambios")
        print("=" * 60)
        print()

    print("📝 Fase 2.4 - Actualización de Imports")
    print()

    python_files = find_python_files()
    print(f"Encontrados {len(python_files)} archivos Python")
    print()

    files_changed = 0
    total_replacements = 0

    base_path = Path.cwd()
    for file_path in python_files:
        changed, replacements = update_file_imports(file_path, dry_run)
        if changed:
            files_changed += 1
            total_replacements += replacements
            if dry_run:
                try:
                    rel_path = file_path.relative_to(base_path)
                except ValueError:
                    rel_path = file_path
                print(f"🔄 {rel_path}: {replacements} imports a actualizar")

    print()
    print("=" * 60)
    print(f"✅ Archivos con cambios: {files_changed}")
    print(f"📝 Total de imports actualizados: {total_replacements}")
    print("=" * 60)

    if dry_run:
        print()
        print("Para ejecutar los cambios reales:")
        print("  python scripts/update_imports.py --execute")

if __name__ == "__main__":
    main()

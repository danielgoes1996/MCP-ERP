# FastAPI Endpointss


```json
{
  "api/advanced_invoicing_api.py": [
    {
      "method": "GET",hace
      "path": "/companies/{company_id}/stats",
      "handler": "get_company_stats()",
      "router": "router",
      "desc": "Obtener estadísticas de facturación de una empresa"
    },
    {
      "method": "GET",
      "path": "/jobs/{job_id}/download/{file_name}",
      "handler": "download_job_file()",
      "router": "router",
      "desc": "Descargar archivo generado por un job (CFDI, PDF, etc.)"
    },
    {
      "method": "GET",
      "path": "/jobs/{job_id}/logs",
      "handler": "get_job_logs()",
      "router": "router",
      "desc": "Obtener logs detallados de un job",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/jobs/{job_id}/screenshots",
      "handler": "get_job_screenshots()",
      "router": "router",
      "desc": "Obtener capturas de pantalla de un job",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/jobs/{job_id}/status",
      "handler": "get_job_status()",
      "router": "router",
      "desc": "Obtener estado de un job de automatización"
    },
    {
      "method": "GET",
      "path": "/merchants/{merchant_id}/analytics",
      "handler": "get_merchant_analytics()",
      "router": "router",
      "desc": "Obtener analíticas de un merchant específico"
    },
    {
      "method": "POST",
      "path": "/merchants/{merchant_id}/credentials",
      "handler": "update_merchant_credentials()",
      "router": "router",
      "desc": "Actualizar credenciales de un merchant"
    },
    {
      "method": "GET",
      "path": "/merchants/{merchant_id}/test-portal",
      "handler": "test_merchant_portal()",
      "router": "router",
      "desc": "Probar conectividad con el portal de un merchant"
    },
    {
      "method": "POST",
      "path": "/tickets/upload",
      "handler": "upload_and_process_ticket()",
      "router": "router",
      "desc": "Subir y procesar ticket para facturación automática."
    },
    {
      "method": "POST",
      "path": "/tickets/{ticket_id}/automate",
      "handler": "start_invoice_automation()",
      "router": "router",
      "desc": "Iniciar automatización de facturación para un ticket."
    }
  ],
  "api/ai_reconciliation_api.py": [
    {
      "method": "POST",
      "path": "/auto-apply-batch",
      "handler": "auto_apply_batch()",
      "router": "router",
      "desc": "Auto-apply multiple high-confidence suggestions in batch"
    },
    {
      "method": "POST",
      "path": "/auto-apply/{suggestion_index}",
      "handler": "auto_apply_suggestion()",
      "router": "router",
      "desc": "Automatically apply a suggestion if confidence is high enough"
    },
    {
      "method": "GET",
      "path": "/stats",
      "handler": "get_ai_stats()",
      "router": "router",
      "desc": "Get statistics about AI suggestions",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/suggestions",
      "handler": "get_reconciliation_suggestions()",
      "router": "router",
      "desc": "Get AI-powered reconciliation suggestions"
    },
    {
      "method": "GET",
      "path": "/suggestions/many-to-one",
      "handler": "get_many_to_one_suggestions()",
      "router": "router",
      "desc": "Get many-to-one split suggestions (N movements → 1 expense)"
    },
    {
      "method": "GET",
      "path": "/suggestions/one-to-many",
      "handler": "get_one_to_many_suggestions()",
      "router": "router",
      "desc": "Get one-to-many split suggestions (1 movement → N expenses)"
    }
  ],
  "api/auth_api.py": [
    {
      "method": "POST",
      "path": "/change-password",
      "handler": "change_password()",
      "router": "router",
      "desc": "Cambiar contraseña del usuario autenticado"
    },
    {
      "method": "GET",
      "path": "/health",
      "handler": "auth_health()",
      "router": "router",
      "desc": "Health check del sistema de autenticación",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/info",
      "handler": "auth_info()",
      "router": "router",
      "desc": "Información del sistema de autenticación (público)"
    },
    {
      "method": "POST",
      "path": "/login",
      "handler": "login()",
      "router": "router",
      "desc": "Login de usuario con email y contraseña",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/logout",
      "handler": "logout()",
      "router": "router",
      "desc": "Logout del usuario (invalidar token)",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/profile",
      "handler": "get_user_profile()",
      "router": "router",
      "desc": "Obtener perfil del usuario autenticado"
    },
    {
      "method": "POST",
      "path": "/refresh",
      "handler": "refresh_token()",
      "router": "router",
      "desc": "Renovar access token usando refresh token"
    },
    {
      "method": "POST",
      "path": "/register",
      "handler": "register()",
      "router": "router",
      "desc": "Registro de nuevo usuario"
    },
    {
      "method": "GET",
      "path": "/users",
      "handler": "list_users()",
      "router": "router",
      "desc": "Listar usuarios (solo admin)"
    },
    {
      "method": "GET",
      "path": "/verify",
      "handler": "verify_token()",
      "router": "router",
      "desc": "Verificar validez del token"
    }
  ],
  "api/auth_jwt_api.py": [
    {
      "method": "POST",
      "path": "/login",
      "handler": "login()",
      "router": "router",
      "desc": "Login with username, password, and tenant selection",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/logout",
      "handler": "logout()",
      "router": "router",
      "desc": "Logout current user",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/me",
      "handler": "get_current_user_profile()",
      "router": "router",
      "desc": "Get current authenticated user profile",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/tenants",
      "handler": "get_available_tenants()",
      "router": "router",
      "desc": "Get list of available tenants for login selection."
    }
  ],
  "api/automation_v2.py": [
    {
      "method": "GET",
      "path": "/config",
      "handler": "get_automation_config()",
      "router": "router",
      "desc": "Get automation configuration entries.",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/feature-status",
      "handler": "get_automation_feature_status()",
      "router": "router",
      "desc": "Check if automation engine v2 is enabled."
    },
    {
      "method": "GET",
      "path": "/health",
      "handler": "get_automation_health()",
      "router": "router",
      "desc": "Get automation system health status.",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/jobs",
      "handler": "get_automation_jobs()",
      "router": "router",
      "desc": "Get paginated list of automation jobs.",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/jobs/{job_id}",
      "handler": "get_automation_job()",
      "router": "router",
      "desc": "Get specific automation job by ID.",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/jobs/{job_id}/logs",
      "handler": "get_automation_job_logs()",
      "router": "router",
      "desc": "Get logs for a specific automation job.",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/jobs/{job_id}/screenshots",
      "handler": "get_automation_job_screenshots()",
      "router": "router",
      "desc": "Get screenshots for a specific automation job.",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/metrics",
      "handler": "get_automation_metrics()",
      "router": "router",
      "desc": "Get automation system metrics.",
      "duplicated": true
    }
  ],
  "api/bank_statements_api.py": [
    {
      "method": "GET",
      "path": "/",
      "handler": "get_user_statements()",
      "router": "router",
      "desc": "Obtener todos los estados de cuenta del usuario",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/accounts/{account_id}",
      "handler": "get_account_statements()",
      "router": "router",
      "desc": "Obtener todos los estados de cuenta de una cuenta específica"
    },
    {
      "method": "POST",
      "path": "/accounts/{account_id}/upload",
      "handler": "upload_bank_statement()",
      "router": "router",
      "desc": "Subir estado de cuenta para una cuenta específica"
    },
    {
      "method": "GET",
      "path": "/health/check",
      "handler": "bank_statements_health()",
      "router": "router",
      "desc": "Health check del sistema de estados de cuenta"
    },
    {
      "method": "DELETE",
      "path": "/{statement_id}",
      "handler": "delete_statement()",
      "router": "router",
      "desc": "Eliminar estado de cuenta y sus transacciones"
    },
    {
      "method": "GET",
      "path": "/{statement_id}",
      "handler": "get_statement_details()",
      "router": "router",
      "desc": "Obtener detalles completos de un estado de cuenta"
    },
    {
      "method": "POST",
      "path": "/{statement_id}/reparse",
      "handler": "reparse_statement()",
      "router": "router",
      "desc": "Re-parsear un estado de cuenta existente"
    }
  ],
  "api/bulk_invoice_api.py": [
    {
      "method": "POST",
      "path": "/analytics",
      "handler": "get_bulk_processing_analytics()",
      "router": "router",
      "desc": "Get detailed analytics for bulk invoice processing",
      "duplicated": true
    },
    {
      "method": "DELETE",
      "path": "/batch/{batch_id}",
      "handler": "cancel_batch()",
      "router": "router",
      "desc": "Cancel a running batch processing operation"
    },
    {
      "method": "GET",
      "path": "/batch/{batch_id}/results",
      "handler": "get_batch_results()",
      "router": "router",
      "desc": "Get detailed results of a completed batch processing operation"
    },
    {
      "method": "GET",
      "path": "/batch/{batch_id}/status",
      "handler": "get_batch_status()",
      "router": "router",
      "desc": "Get current status of a batch processing operation"
    },
    {
      "method": "GET",
      "path": "/batches",
      "handler": "list_batches()",
      "router": "router",
      "desc": "List batch processing operations with filtering"
    },
    {
      "method": "GET",
      "path": "/health",
      "handler": "health_check()",
      "router": "router",
      "desc": "Health check endpoint for bulk invoice processing system",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/performance-summary",
      "handler": "get_performance_summary()",
      "router": "router",
      "desc": "Get performance summary for bulk processing operations"
    },
    {
      "method": "POST",
      "path": "/process-batch",
      "handler": "process_invoice_batch()",
      "router": "router",
      "desc": "Process a batch of invoices with enterprise-grade tracking and metrics"
    },
    {
      "method": "GET",
      "path": "/rules",
      "handler": "list_processing_rules()",
      "router": "router",
      "desc": "List bulk processing rules"
    },
    {
      "method": "POST",
      "path": "/rules",
      "handler": "create_processing_rule()",
      "router": "router",
      "desc": "Create a new bulk processing rule",
      "duplicated": true
    }
  ],
  "api/category_learning_api.py": [
    {
      "method": "POST",
      "path": "/feedback",
      "handler": "submit_category_feedback()",
      "router": "router",
      "desc": "Enviar feedback sobre categorización para mejorar el sistema ML",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/history/{expense_id}",
      "handler": "get_prediction_history()",
      "router": "router",
      "desc": "Obtener historial de predicciones para un gasto"
    },
    {
      "method": "GET",
      "path": "/metrics",
      "handler": "get_category_metrics()",
      "router": "router",
      "desc": "Obtener métricas de categorización ML",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/predict",
      "handler": "predict_category()",
      "router": "router",
      "desc": "Predecir categoría para un gasto usando ML"
    },
    {
      "method": "GET",
      "path": "/stats",
      "handler": "get_learning_stats()",
      "router": "router",
      "desc": "Obtener estadísticas generales del sistema de aprendizaje",
      "duplicated": true
    }
  ],
  "api/client_management_api.py": [
    {
      "method": "GET",
      "path": "/",
      "handler": "list_all_clients()",
      "router": "router",
      "desc": "Lista todos los clientes configurados (para desarrollo)",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/batch-setup",
      "handler": "batch_setup_clients()",
      "router": "router",
      "desc": "Configura múltiples clientes de forma masiva"
    },
    {
      "method": "GET",
      "path": "/health",
      "handler": "health_check()",
      "router": "router",
      "desc": "Verifica el estado del sistema de gestión de clientes",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/setup",
      "handler": "setup_client()",
      "router": "router",
      "desc": "Configura un nuevo cliente con sus datos fiscales"
    },
    {
      "method": "GET",
      "path": "/{client_id}",
      "handler": "get_client_info()",
      "router": "router",
      "desc": "Obtiene información completa de un cliente"
    },
    {
      "method": "PUT",
      "path": "/{client_id}/fiscal-data",
      "handler": "update_client_fiscal_data()",
      "router": "router",
      "desc": "Actualiza los datos fiscales de un cliente"
    },
    {
      "method": "POST",
      "path": "/{client_id}/invoice",
      "handler": "create_invoice_with_context()",
      "router": "router",
      "desc": "Crea una factura automáticamente usando el contexto completo del cliente."
    },
    {
      "method": "GET",
      "path": "/{client_id}/portals",
      "handler": "list_client_portals()",
      "router": "router",
      "desc": "Lista todos los portales configurados para un cliente"
    },
    {
      "method": "POST",
      "path": "/{client_id}/portals/{merchant_name}/credentials",
      "handler": "setup_portal_credentials()",
      "router": "router",
      "desc": "Configura credenciales de un cliente para un portal específico"
    },
    {
      "method": "GET",
      "path": "/{client_id}/portals/{merchant_name}/status",
      "handler": "check_portal_status()",
      "router": "router",
      "desc": "Verifica el estado de configuración de un portal"
    }
  ],
  "api/conversational_assistant_api.py": [
    {
      "method": "GET",
      "path": "/analytics/{user_id}",
      "handler": "get_user_analytics()",
      "router": "router",
      "desc": "Obtener analytics de uso del asistente conversacional",
      "duplicated": true
    },
    {
      "method": "DELETE",
      "path": "/cache",
      "handler": "clear_cache()",
      "router": "router",
      "desc": "Limpiar cache de respuestas LLM"
    },
    {
      "method": "GET",
      "path": "/cache/stats",
      "handler": "get_cache_statistics()",
      "router": "router",
      "desc": "Obtener estadísticas del cache de respuestas LLM"
    },
    {
      "method": "POST",
      "path": "/feedback",
      "handler": "record_user_feedback()",
      "router": "router",
      "desc": "Registrar feedback del usuario sobre respuestas del asistente",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/health",
      "handler": "health_check()",
      "router": "router",
      "desc": "Health check del sistema de asistente conversacional",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/models",
      "handler": "list_llm_models()",
      "router": "router",
      "desc": "Listar todos los modelos LLM configurados"
    },
    {
      "method": "POST",
      "path": "/models/config",
      "handler": "configure_llm_model()",
      "router": "router",
      "desc": "Configurar un nuevo modelo LLM o actualizar configuración existente"
    },
    {
      "method": "POST",
      "path": "/query",
      "handler": "process_user_query()",
      "router": "router",
      "desc": "Procesar consulta del usuario con el asistente conversacional"
    },
    {
      "method": "POST",
      "path": "/sessions",
      "handler": "create_conversation_session()",
      "router": "router",
      "desc": "Crear nueva sesión de conversación con el asistente",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/history",
      "handler": "get_conversation_history()",
      "router": "router",
      "desc": "Obtener historial de conversación de una sesión"
    }
  ],
  "api/employee_advances_api.py": [
    {
      "method": "GET",
      "path": "/",
      "handler": "list_advances()",
      "router": "router",
      "desc": "List employee advances with optional filters",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/",
      "handler": "create_advance()",
      "router": "router",
      "desc": "Create a new employee advance",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/employee/{employee_id}/summary",
      "handler": "get_employee_summary()",
      "router": "router",
      "desc": "Get summary of advances for a specific employee"
    },
    {
      "method": "GET",
      "path": "/pending/all",
      "handler": "get_pending_reimbursements()",
      "router": "router",
      "desc": "Get all pending reimbursements (status = pending or partial)"
    },
    {
      "method": "POST",
      "path": "/reimburse",
      "handler": "reimburse_advance()",
      "router": "router",
      "desc": "Reimburse an employee advance (partial or full)"
    },
    {
      "method": "GET",
      "path": "/summary/all",
      "handler": "get_advances_summary()",
      "router": "router",
      "desc": "Get summary of all employee advances"
    },
    {
      "method": "DELETE",
      "path": "/{advance_id}",
      "handler": "cancel_advance()",
      "router": "router",
      "desc": "Cancel an advance"
    },
    {
      "method": "GET",
      "path": "/{advance_id}",
      "handler": "get_advance()",
      "router": "router",
      "desc": "Get advance by ID"
    },
    {
      "method": "PATCH",
      "path": "/{advance_id}",
      "handler": "update_advance()",
      "router": "router",
      "desc": "Update an advance"
    }
  ],
  "api/expense_completion_api.py": [
    {
      "method": "GET",
      "path": "/analytics/{user_id}",
      "handler": "get_completion_analytics()",
      "router": "router",
      "desc": "Get completion analytics for user",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/bulk-complete",
      "handler": "bulk_complete_expenses()",
      "router": "router",
      "desc": "Perform bulk completion of multiple expenses"
    },
    {
      "method": "POST",
      "path": "/interactions",
      "handler": "record_completion_interaction()",
      "router": "router",
      "desc": "Record user interaction with completion suggestions for learning"
    },
    {
      "method": "GET",
      "path": "/patterns/{user_id}",
      "handler": "get_learned_patterns()",
      "router": "router",
      "desc": "Get learned completion patterns for user"
    },
    {
      "method": "GET",
      "path": "/preferences/{user_id}",
      "handler": "get_user_preferences()",
      "router": "router",
      "desc": "Get user completion preferences"
    },
    {
      "method": "PUT",
      "path": "/preferences/{user_id}",
      "handler": "update_user_preferences()",
      "router": "router",
      "desc": "Update user completion preferences"
    },
    {
      "method": "POST",
      "path": "/rules",
      "handler": "create_completion_rule()",
      "router": "router",
      "desc": "Create a new completion rule",
      "duplicated": true
    },
    {
      "method": "DELETE",
      "path": "/rules/{rule_id}",
      "handler": "delete_completion_rule()",
      "router": "router",
      "desc": "Delete a completion rule"
    },
    {
      "method": "GET",
      "path": "/rules/{user_id}",
      "handler": "get_completion_rules()",
      "router": "router",
      "desc": "Get all completion rules for user"
    },
    {
      "method": "POST",
      "path": "/suggestions",
      "handler": "get_completion_suggestions()",
      "router": "router",
      "desc": "Get field completion suggestions for an expense"
    },
    {
      "method": "POST",
      "path": "/validate-completeness",
      "handler": "validate_expense_completeness()",
      "router": "router",
      "desc": "Validate completeness of expense data"
    }
  ],
  "api/feature_flags_api.py": [
    {
      "method": "GET",
      "path": "/audit/{flag_key}",
      "handler": "get_feature_flag_audit()",
      "router": "router",
      "desc": "Get audit trail for a feature flag."
    },
    {
      "method": "GET",
      "path": "/automation/check",
      "handler": "check_automation_status()",
      "router": "router",
      "desc": "Check automation engine status for a company/user."
    },
    {
      "method": "POST",
      "path": "/automation/disable-global",
      "handler": "disable_automation_globally_endpoint()",
      "router": "router",
      "desc": "Disable automation globally (emergency stop)."
    },
    {
      "method": "POST",
      "path": "/automation/enable-company",
      "handler": "enable_automation_for_company_endpoint()",
      "router": "router",
      "desc": "Enable automation for a specific company."
    },
    {
      "method": "POST",
      "path": "/automation/set-rollout",
      "handler": "set_automation_rollout_endpoint()",
      "router": "router",
      "desc": "Configure automation rollout percentage."
    },
    {
      "method": "GET",
      "path": "/check/{flag_key}",
      "handler": "check_feature_flag()",
      "router": "router",
      "desc": "Check if a specific feature flag is enabled."
    },
    {
      "method": "GET",
      "path": "/status",
      "handler": "get_all_feature_flags()",
      "router": "router",
      "desc": "Get status of all feature flags for a company."
    },
    {
      "method": "POST",
      "path": "/update",
      "handler": "update_feature_flag()",
      "router": "router",
      "desc": "Update a feature flag value."
    }
  ],
  "api/financial_intelligence_api.py": [
    {
      "method": "GET",
      "path": "/cash-flow-analysis",
      "handler": "get_cash_flow_analysis()",
      "router": "router",
      "desc": "Obtiene análisis de flujo de efectivo"
    },
    {
      "method": "GET",
      "path": "/comprehensive-report",
      "handler": "get_comprehensive_financial_report()",
      "router": "router",
      "desc": "Obtiene reporte financiero comprensivo con todos los análisis"
    },
    {
      "method": "GET",
      "path": "/expense-breakdown",
      "handler": "get_expense_breakdown()",
      "router": "router",
      "desc": "Obtiene desglose detallado de gastos por período"
    },
    {
      "method": "GET",
      "path": "/financial-health-score",
      "handler": "get_financial_health_score()",
      "router": "router",
      "desc": "Calcula un score de salud financiera basado en múltiples factores"
    },
    {
      "method": "GET",
      "path": "/financial-insights",
      "handler": "get_financial_insights()",
      "router": "router",
      "desc": "Obtiene insights financieros y anomalías detectadas"
    },
    {
      "method": "GET",
      "path": "/optimization-suggestions",
      "handler": "get_optimization_suggestions()",
      "router": "router",
      "desc": "Obtiene sugerencias de optimización de gastos"
    },
    {
      "method": "GET",
      "path": "/tax-deductibility-report",
      "handler": "get_tax_deductibility_report()",
      "router": "router",
      "desc": "Obtiene reporte de deducibilidad fiscal automático"
    }
  ],
  "api/financial_reports_api.py": [
    {
      "method": "GET",
      "path": "/categorias-sat/resumen",
      "handler": "get_categorias_sat_summary()",
      "router": "router",
      "desc": "Obtiene resumen de gastos agrupados por categorías SAT."
    },
    {
      "method": "GET",
      "path": "/disponibles",
      "handler": "get_available_reports()",
      "router": "router",
      "desc": "Lista los tipos de reportes disponibles."
    },
    {
      "method": "GET",
      "path": "/gastos-revision",
      "handler": "get_gastos_revision()",
      "router": "router",
      "desc": "Obtiene gastos marcados para revisión fiscal."
    },
    {
      "method": "GET",
      "path": "/health",
      "handler": "health_check()",
      "router": "router",
      "desc": "Verifica el estado del servicio de reportes.",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/iva",
      "handler": "generate_iva_report()",
      "router": "router",
      "desc": "Genera reporte de IVA acreditable y no acreditable."
    },
    {
      "method": "POST",
      "path": "/poliza-electronica",
      "handler": "generate_poliza_electronica()",
      "router": "router",
      "desc": "Genera póliza electrónica en formato Anexo 24 del SAT."
    },
    {
      "method": "GET",
      "path": "/poliza-electronica/xml",
      "handler": "download_poliza_xml()",
      "router": "router",
      "desc": "Descarga póliza electrónica en formato XML."
    },
    {
      "method": "GET",
      "path": "/resumen-fiscal",
      "handler": "get_resumen_fiscal()",
      "router": "router",
      "desc": "Genera resumen fiscal completo del periodo."
    }
  ],
  "api/hybrid_processor_api.py": [
    {
      "method": "GET",
      "path": "/metrics/{company_id}",
      "handler": "get_company_hybrid_metrics()",
      "router": "router",
      "desc": "Obtiene métricas agregadas de procesamiento híbrido para una empresa"
    },
    {
      "method": "GET",
      "path": "/processors/",
      "handler": "list_available_processors()",
      "router": "router",
      "desc": "Lista todos los procesadores disponibles con sus métricas"
    },
    {
      "method": "POST",
      "path": "/processors/health-check",
      "handler": "run_processors_health_check()",
      "router": "router",
      "desc": "Ejecuta health check en todos los procesadores"
    },
    {
      "method": "POST",
      "path": "/sessions/",
      "handler": "create_hybrid_processing_session()",
      "router": "router",
      "desc": "Crea una nueva sesión de procesamiento híbrido multi-modal",
      "duplicated": true
    },
    {
      "method": "DELETE",
      "path": "/sessions/{session_id}",
      "handler": "cancel_hybrid_session()",
      "router": "router",
      "desc": "Cancela una sesión de procesamiento híbrido",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/metrics",
      "handler": "get_session_processing_metrics()",
      "router": "router",
      "desc": "Obtiene métricas detalladas de procesamiento de una sesión"
    },
    {
      "method": "POST",
      "path": "/sessions/{session_id}/process",
      "handler": "process_hybrid_session()",
      "router": "router",
      "desc": "Inicia el procesamiento de una sesión híbrida",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/results",
      "handler": "get_hybrid_session_results()",
      "router": "router",
      "desc": "Obtiene los resultados finales de procesamiento híbrido"
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/status",
      "handler": "get_hybrid_session_status()",
      "router": "router",
      "desc": "Obtiene el estado actual de una sesión con processing_metrics detallados",
      "duplicated": true
    }
  ],
  "api/non_reconciliation_api.py": [
    {
      "method": "POST",
      "path": "/analytics",
      "handler": "get_non_reconciliation_analytics()",
      "router": "router",
      "desc": "Get detailed analytics for non-reconciliation data",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/bulk-actions",
      "handler": "bulk_non_reconciliation_actions()",
      "router": "router",
      "desc": "Perform bulk actions on multiple non-reconciliation records"
    },
    {
      "method": "GET",
      "path": "/dashboard-summary",
      "handler": "get_dashboard_summary()",
      "router": "router",
      "desc": "Get dashboard summary data for non-reconciliation management"
    },
    {
      "method": "POST",
      "path": "/escalate",
      "handler": "escalate_non_reconciliation()",
      "router": "router",
      "desc": "Escalate a non-reconciliation record to higher level"
    },
    {
      "method": "GET",
      "path": "/escalation-rules",
      "handler": "get_escalation_rules()",
      "router": "router",
      "desc": "Get escalation rules for company"
    },
    {
      "method": "POST",
      "path": "/escalation-rules",
      "handler": "create_escalation_rule()",
      "router": "router",
      "desc": "Create new escalation rule"
    },
    {
      "method": "GET",
      "path": "/health",
      "handler": "health_check()",
      "router": "router",
      "desc": "Health check endpoint for non-reconciliation system",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/mark-non-reconcilable",
      "handler": "mark_expense_non_reconcilable()",
      "router": "router",
      "desc": "Mark an expense as non-reconcilable with specified reason"
    },
    {
      "method": "POST",
      "path": "/notifications/schedule",
      "handler": "schedule_notification()",
      "router": "router",
      "desc": "Schedule a notification for a non-reconciliation record"
    },
    {
      "method": "GET",
      "path": "/reason-codes",
      "handler": "get_reason_codes()",
      "router": "router",
      "desc": "Get available non-reconciliation reason codes"
    },
    {
      "method": "GET",
      "path": "/records",
      "handler": "get_non_reconciliation_records()",
      "router": "router",
      "desc": "Retrieve non-reconciliation records with filtering"
    },
    {
      "method": "GET",
      "path": "/records/{record_id}",
      "handler": "get_non_reconciliation_record()",
      "router": "router",
      "desc": "Get specific non-reconciliation record by ID"
    },
    {
      "method": "PUT",
      "path": "/records/{record_id}",
      "handler": "update_non_reconciliation_record()",
      "router": "router",
      "desc": "Update non-reconciliation record"
    },
    {
      "method": "GET",
      "path": "/records/{record_id}/history",
      "handler": "get_record_history()",
      "router": "router",
      "desc": "Get history of actions for a non-reconciliation record"
    },
    {
      "method": "GET",
      "path": "/stats",
      "handler": "get_non_reconciliation_stats()",
      "router": "router",
      "desc": "Get non-reconciliation statistics for company",
      "duplicated": true
    }
  ],
  "api/payment_accounts_api.py": [
    {
      "method": "GET",
      "path": "/",
      "handler": "get_user_payment_accounts()",
      "router": "router",
      "desc": "Obtener todas las cuentas de pago del usuario autenticado",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/",
      "handler": "create_payment_account()",
      "router": "router",
      "desc": "Crear nueva cuenta de pago",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/banking-institutions",
      "handler": "get_banking_institutions()",
      "router": "router",
      "desc": "Obtener lista de instituciones bancarias disponibles"
    },
    {
      "method": "GET",
      "path": "/health",
      "handler": "payment_accounts_health()",
      "router": "router",
      "desc": "Health check del sistema de cuentas de pago",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/summary/dashboard",
      "handler": "get_accounts_summary()",
      "router": "router",
      "desc": "Obtener resumen de cuentas para dashboard"
    },
    {
      "method": "GET",
      "path": "/types/available",
      "handler": "get_available_account_types()",
      "router": "router",
      "desc": "Obtener tipos y subtipos de cuenta disponibles"
    },
    {
      "method": "DELETE",
      "path": "/{account_id}",
      "handler": "delete_payment_account()",
      "router": "router",
      "desc": "Desactivar cuenta de pago (soft delete)"
    },
    {
      "method": "GET",
      "path": "/{account_id}",
      "handler": "get_payment_account()",
      "router": "router",
      "desc": "Obtener una cuenta de pago específica"
    },
    {
      "method": "PUT",
      "path": "/{account_id}",
      "handler": "update_payment_account()",
      "router": "router",
      "desc": "Actualizar cuenta de pago existente"
    }
  ],
  "api/robust_automation_engine_api.py": [
    {
      "method": "GET",
      "path": "/health/system",
      "handler": "get_system_health()",
      "router": "router",
      "desc": "Obtiene estado de salud del sistema completo"
    },
    {
      "method": "POST",
      "path": "/sessions/",
      "handler": "create_robust_automation_session()",
      "router": "router",
      "desc": "Crea una nueva sesión de automatización robusta con risk assessment",
      "duplicated": true
    },
    {
      "method": "DELETE",
      "path": "/sessions/{session_id}",
      "handler": "cancel_robust_automation()",
      "router": "router",
      "desc": "Cancela una sesión de automatización robusta",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/sessions/{session_id}/execute",
      "handler": "execute_robust_automation()",
      "router": "router",
      "desc": "Ejecuta automatización robusta con monitoreo completo"
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/health",
      "handler": "get_session_health_status()",
      "router": "router",
      "desc": "Obtiene estado de salud detallado de la automatización"
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/performance",
      "handler": "get_session_performance_metrics()",
      "router": "router",
      "desc": "Obtiene métricas detalladas de performance para una sesión"
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/recovery",
      "handler": "get_session_recovery_actions()",
      "router": "router",
      "desc": "Obtiene acciones de recuperación ejecutadas para una sesión"
    },
    {
      "method": "POST",
      "path": "/sessions/{session_id}/recovery/trigger",
      "handler": "trigger_manual_recovery()",
      "router": "router",
      "desc": "Dispara recuperación manual para una sesión"
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/status",
      "handler": "get_robust_automation_status()",
      "router": "router",
      "desc": "Obtiene estado completo con performance_metrics, recovery_actions y automation_health",
      "duplicated": true
    }
  ],
  "api/rpa_automation_engine_api.py": [
    {
      "method": "GET",
      "path": "/analytics/{user_id}",
      "handler": "get_rpa_analytics()",
      "router": "router",
      "desc": "Obtener analytics de automatización RPA para usuario",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/health",
      "handler": "health_check()",
      "router": "router",
      "desc": "Health check del sistema de automatización RPA",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/performance",
      "handler": "get_performance_metrics()",
      "router": "router",
      "desc": "Obtener métricas de performance del sistema RPA",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/sessions",
      "handler": "create_rpa_session()",
      "router": "router",
      "desc": "Crear nueva sesión de automatización RPA con Playwright",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/sessions/{session_id}/cancel",
      "handler": "cancel_rpa_session()",
      "router": "router",
      "desc": "Cancelar sesión RPA",
      "duplicated": true
    },
    {
      "method": "DELETE",
      "path": "/sessions/{session_id}/cleanup",
      "handler": "cleanup_session_resources()",
      "router": "router",
      "desc": "Limpiar recursos de sesión (screenshots, logs temporales)"
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/logs",
      "handler": "get_session_logs()",
      "router": "router",
      "desc": "Obtener logs detallados de ejecución de sesión"
    },
    {
      "method": "POST",
      "path": "/sessions/{session_id}/pause",
      "handler": "pause_rpa_session()",
      "router": "router",
      "desc": "Pausar sesión RPA en ejecución",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/sessions/{session_id}/resume",
      "handler": "resume_rpa_session()",
      "router": "router",
      "desc": "Reanudar sesión RPA pausada",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/sessions/{session_id}/screenshot",
      "handler": "capture_manual_screenshot()",
      "router": "router",
      "desc": "Capturar screenshot manual durante la ejecución"
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/screenshots",
      "handler": "get_session_screenshots()",
      "router": "router",
      "desc": "Obtener screenshots capturados durante la automatización"
    },
    {
      "method": "POST",
      "path": "/sessions/{session_id}/start",
      "handler": "start_rpa_session()",
      "router": "router",
      "desc": "Iniciar ejecución de sesión RPA",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/status",
      "handler": "get_session_status()",
      "router": "router",
      "desc": "Obtener estado actual de sesión RPA con progreso detallado",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/templates",
      "handler": "list_portal_templates()",
      "router": "router",
      "desc": "Listar plantillas de portales disponibles"
    },
    {
      "method": "POST",
      "path": "/templates",
      "handler": "create_portal_template()",
      "router": "router",
      "desc": "Crear plantilla reutilizable para automatización de portal"
    }
  ],
  "api/split_reconciliation_api.py": [
    {
      "method": "GET",
      "path": "/",
      "handler": "list_splits_endpoint()",
      "router": "router",
      "desc": "List all split reconciliations with optional filters.",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/many-to-one",
      "handler": "create_many_to_one_split_endpoint()",
      "router": "router",
      "desc": "Create a many-to-one split reconciliation (partial payments)."
    },
    {
      "method": "POST",
      "path": "/one-to-many",
      "handler": "create_one_to_many_split_endpoint()",
      "router": "router",
      "desc": "Create a one-to-many split reconciliation."
    },
    {
      "method": "GET",
      "path": "/summary/stats",
      "handler": "get_split_summary_endpoint()",
      "router": "router",
      "desc": "Get summary statistics for all split reconciliations."
    },
    {
      "method": "DELETE",
      "path": "/{split_group_id}",
      "handler": "undo_split_endpoint()",
      "router": "router",
      "desc": "Undo a split reconciliation (unlink all records)."
    },
    {
      "method": "GET",
      "path": "/{split_group_id}",
      "handler": "get_split_details_endpoint()",
      "router": "router",
      "desc": "Get detailed information about a specific split reconciliation."
    }
  ],
  "api/universal_invoice_engine_api.py": [
    {
      "method": "GET",
      "path": "/formats/{company_id}",
      "handler": "list_company_formats()",
      "router": "router",
      "desc": "Lista formatos configurados para una empresa"
    },
    {
      "method": "POST",
      "path": "/formats/{company_id}",
      "handler": "create_company_format()",
      "router": "router",
      "desc": "Crea nuevo formato con template patterns y validation rules"
    },
    {
      "method": "GET",
      "path": "/parsers/",
      "handler": "list_available_parsers()",
      "router": "router",
      "desc": "Lista parsers disponibles con sus capacidades"
    },
    {
      "method": "POST",
      "path": "/sessions/",
      "handler": "create_invoice_processing_session()",
      "router": "router",
      "desc": "Crea una nueva sesión de procesamiento universal de facturas",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/sessions/upload/",
      "handler": "upload_and_create_session()",
      "router": "router",
      "desc": "Sube archivo y crea sesión de procesamiento"
    },
    {
      "method": "DELETE",
      "path": "/sessions/{session_id}",
      "handler": "cancel_invoice_processing()",
      "router": "router",
      "desc": "Cancela procesamiento de factura",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/extracted-data",
      "handler": "get_extracted_data()",
      "router": "router",
      "desc": "Obtiene datos extraídos y normalizados"
    },
    {
      "method": "POST",
      "path": "/sessions/{session_id}/process",
      "handler": "process_universal_invoice()",
      "router": "router",
      "desc": "Procesa factura con template matching y validation rules completas",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/status",
      "handler": "get_invoice_processing_status()",
      "router": "router",
      "desc": "Obtiene estado completo con template_match y validation_rules",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/template-match",
      "handler": "get_session_template_match()",
      "router": "router",
      "desc": "Obtiene detalles de template matching para una sesión"
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/validation",
      "handler": "get_session_validation_results()",
      "router": "router",
      "desc": "Obtiene resultados detallados de validación"
    }
  ],
  "api/v1/ai_retrain.py": [
    {
      "method": "POST",
      "path": "/retrain",
      "handler": "retrain_from_corrections()",
      "router": "router",
      "desc": "Persist manual corrections so future parses reuse the feedback."
    }
  ],
  "api/v1/companies_context.py": [
    {
      "method": "POST",
      "path": "/context/analyze",
      "handler": "analyze_company_context()",
      "router": "router",
      "desc": "Analyze company context using Claude and persist the results."
    },
    {
      "method": "POST",
      "path": "/context/questions",
      "handler": "generate_company_context_questions()",
      "router": "router",
      "desc": "Generate conversational onboarding questions tailored to the company context."
    },
    {
      "method": "GET",
      "path": "/context/status",
      "handler": "get_company_context_status()",
      "router": "router",
      "desc": "Return the latest stored context summary for the current user's primary company."
    },
    {
      "method": "POST",
      "path": "/contextual_profile",
      "handler": "create_company_contextual_profile()",
      "router": "router",
      "desc": "Create or update the contextual profile for a company using text or audio input."
    }
  ],
  "api/v1/debug.py": [
    {
      "method": "GET",
      "path": "/config",
      "handler": "get_debug_config()",
      "router": "router",
      "desc": "Get current debugging configuration",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/health",
      "handler": "debug_health_check()",
      "router": "router",
      "desc": "Debug API health check",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/sessions",
      "handler": "get_debug_sessions()",
      "router": "router",
      "desc": "Get all debugging sessions"
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/checkpoints",
      "handler": "get_session_checkpoints()",
      "router": "router",
      "desc": "Get checkpoints for a specific debug session"
    }
  ],
  "api/v1/invoicing.py": [
    {
      "method": "GET",
      "path": "/health",
      "handler": "health_check()",
      "router": "router",
      "desc": "API health check endpoint",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/merchants",
      "handler": "list_merchants()",
      "router": "router",
      "desc": "List all supported merchants",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/stats",
      "handler": "get_processing_stats()",
      "router": "router",
      "desc": "Get processing statistics",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/tickets",
      "handler": "list_tickets()",
      "router": "router",
      "desc": "List tickets with pagination and filtering",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/tickets",
      "handler": "create_ticket()",
      "router": "router",
      "desc": "Create a new ticket from uploaded image",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/tickets/{ticket_id}",
      "handler": "get_ticket()",
      "router": "router",
      "desc": "Get ticket details by ID",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/tickets/{ticket_id}/process",
      "handler": "process_ticket()",
      "router": "router",
      "desc": "Manually trigger ticket processing"
    }
  ],
  "api/v1/polizas_api.py": [
    {
      "method": "GET",
      "path": "/",
      "handler": "listar_polizas()",
      "router": "router",
      "desc": "Listar polizas",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/generar_desde_conciliacion",
      "handler": "generar_poliza_desde_conciliacion()",
      "router": "router",
      "desc": "Generar poliza desde conciliacion"
    },
    {
      "method": "GET",
      "path": "/por-movimiento/{movement_id}",
      "handler": "obtener_poliza_por_movimiento()",
      "router": "router",
      "desc": "Obtener poliza por movimiento"
    },
    {
      "method": "GET",
      "path": "/{poliza_id}",
      "handler": "obtener_poliza()",
      "router": "router",
      "desc": "Obtener poliza"
    }
  ],
  "api/v1/transactions_review_api.py": [
    {
      "method": "POST",
      "path": "/{transaction_id}/mark_reviewed",
      "handler": "mark_transaction_reviewed()",
      "router": "router",
      "desc": "Mark a bank transaction as reviewed by the current user."
    }
  ],
  "api/v1/user_context.py": [
    {
      "method": "GET",
      "path": "/context-status",
      "handler": "get_context_status()",
      "router": "users_router",
      "desc": "Return onboarding flag and latest context summary for the current user."
    },
    {
      "method": "GET",
      "path": "/context/full",
      "handler": "get_full_user_context()",
      "router": "auth_router",
      "desc": "Get full user context"
    },
    {
      "method": "POST",
      "path": "/mark_onboarding",
      "handler": "mark_onboarding_completed()",
      "router": "users_router",
      "desc": "Mark the current user as having completed the onboarding flow."
    },
    {
      "method": "GET",
      "path": "/me",
      "handler": "get_auth_status()",
      "router": "auth_router",
      "desc": "Return authenticated user information with onboarding and context metadata.",
      "duplicated": true
    }
  ],
  "api/web_automation_engine_api.py": [
    {
      "method": "GET",
      "path": "/analytics/{user_id}",
      "handler": "get_web_analytics()",
      "router": "router",
      "desc": "Obtener analytics completas de automatización web",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/engines",
      "handler": "list_web_engines()",
      "router": "router",
      "desc": "Listar engines de automatización web disponibles"
    },
    {
      "method": "POST",
      "path": "/engines/config",
      "handler": "configure_web_engine()",
      "router": "router",
      "desc": "Configurar engine de automatización web"
    },
    {
      "method": "GET",
      "path": "/health",
      "handler": "health_check()",
      "router": "router",
      "desc": "Health check del sistema de automatización web",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/performance",
      "handler": "get_web_performance_metrics()",
      "router": "router",
      "desc": "Obtener métricas de performance del sistema de automatización web",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/sessions",
      "handler": "create_web_automation_session()",
      "router": "router",
      "desc": "Crear nueva sesión de automatización web multi-engine",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/sessions/{session_id}/anti-detection/enable",
      "handler": "enable_anti_detection()",
      "router": "router",
      "desc": "Activar medidas anti-detection avanzadas"
    },
    {
      "method": "POST",
      "path": "/sessions/{session_id}/cancel",
      "handler": "cancel_web_session()",
      "router": "router",
      "desc": "Cancelar sesión de automatización web",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/captcha-solutions",
      "handler": "get_session_captcha_solutions()",
      "router": "router",
      "desc": "Obtener historial de soluciones de CAPTCHA de la sesión"
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/dom-analysis",
      "handler": "get_session_dom_analysis()",
      "router": "router",
      "desc": "Obtener análisis de DOM realizados durante la sesión"
    },
    {
      "method": "POST",
      "path": "/sessions/{session_id}/fingerprint/rotate",
      "handler": "rotate_browser_fingerprint()",
      "router": "router",
      "desc": "Rotar browser fingerprint para evasión avanzada"
    },
    {
      "method": "POST",
      "path": "/sessions/{session_id}/pause",
      "handler": "pause_web_session()",
      "router": "router",
      "desc": "Pausar sesión de automatización web",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/sessions/{session_id}/resume",
      "handler": "resume_web_session()",
      "router": "router",
      "desc": "Reanudar sesión de automatización web pausada",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/sessions/{session_id}/start",
      "handler": "start_web_automation_session()",
      "router": "router",
      "desc": "Iniciar ejecución de sesión de automatización web",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/sessions/{session_id}/status",
      "handler": "get_web_session_status()",
      "router": "router",
      "desc": "Obtener estado detallado de sesión web con métricas de performance",
      "duplicated": true
    }
  ],
  "modules/invoicing_agent/api.py": [
    {
      "method": "GET",
      "path": "/attachments/{attachment_id}/download",
      "handler": "download_attachment()",
      "router": "router",
      "desc": "Descargar archivo adjunto por ID"
    },
    {
      "method": "GET",
      "path": "/automation-viewer",
      "handler": "automation_viewer()",
      "router": "router",
      "desc": "Dashboard visual para ver capturas de automatización y decisiones del LLM"
    },
    {
      "method": "GET",
      "path": "/automation/latest-data",
      "handler": "get_latest_automation_data()",
      "router": "router",
      "desc": "Obtener datos de automatización del job más reciente (para testing y demo)"
    },
    {
      "method": "POST",
      "path": "/bulk-match",
      "handler": "bulk_ticket_upload()",
      "router": "router",
      "desc": "Carga masiva de tickets para procesamiento en lote."
    },
    {
      "method": "GET",
      "path": "/dashboard",
      "handler": "invoicing_dashboard()",
      "router": "router",
      "desc": "Redirige al dashboard simple unificado."
    },
    {
      "method": "POST",
      "path": "/dev/seed-merchants",
      "handler": "seed_merchants()",
      "router": "router",
      "desc": "Crear merchants de prueba para desarrollo."
    },
    {
      "method": "POST",
      "path": "/extract-urls",
      "handler": "extract_urls_from_text()",
      "router": "router",
      "desc": "Extraer URLs de facturación de texto usando el paradigma URL-driven para LATAM."
    },
    {
      "method": "GET",
      "path": "/jobs",
      "handler": "list_jobs_endpoint()",
      "router": "router",
      "desc": "Listar jobs de facturación pendientes y completados.",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/jobs/{job_id}/process",
      "handler": "process_job_manually()",
      "router": "router",
      "desc": "Procesar un job específico manualmente."
    },
    {
      "method": "POST",
      "path": "/maintenance/fix-inconsistencies",
      "handler": "fix_data_inconsistencies()",
      "router": "router",
      "desc": "Buscar y corregir inconsistencias en toda la base de datos."
    },
    {
      "method": "GET",
      "path": "/merchants",
      "handler": "list_merchants_endpoint()",
      "router": "router",
      "desc": "Listar merchants disponibles para facturación.",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/merchants",
      "handler": "create_merchant_endpoint()",
      "router": "router",
      "desc": "Crear un nuevo merchant para facturación."
    },
    {
      "method": "GET",
      "path": "/merchants/{merchant_id}",
      "handler": "get_merchant_endpoint()",
      "router": "router",
      "desc": "Obtener detalles de un merchant específico."
    },
    {
      "method": "GET",
      "path": "/screenshots/{filename}",
      "handler": "serve_screenshot()",
      "router": "router",
      "desc": "Servir archivos de screenshots para el automation viewer"
    },
    {
      "method": "GET",
      "path": "/simple",
      "handler": "simple_dashboard()",
      "router": "router",
      "desc": "Dashboard simple sin dependencias de Jinja2."
    },
    {
      "method": "GET",
      "path": "/stats",
      "handler": "get_dashboard_stats()",
      "router": "router",
      "desc": "Obtener estadísticas reales del dashboard.",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/test-intelligent-agent/{ticket_id}",
      "handler": "test_intelligent_agent()",
      "router": "router",
      "desc": "Endpoint para probar el agente de decisión inteligente con un ticket real."
    },
    {
      "method": "POST",
      "path": "/test-state-machine/{ticket_id}",
      "handler": "test_state_machine_agent()",
      "router": "router",
      "desc": "Endpoint para probar el nuevo agente con State Machine"
    },
    {
      "method": "GET",
      "path": "/tickets",
      "handler": "list_tickets_endpoint()",
      "router": "router",
      "desc": "Listar tickets con filtros opcionales.",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/tickets",
      "handler": "upload_ticket()",
      "router": "router",
      "desc": "Subir un ticket de compra para procesamiento automático.",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/tickets/{ticket_id}",
      "handler": "get_ticket_status()",
      "router": "router",
      "desc": "Obtener el estado y detalles de un ticket específico.",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/tickets/{ticket_id}/automation-data",
      "handler": "get_ticket_automation_data()",
      "router": "router",
      "desc": "Obtener datos completos de automatización para un ticket específico."
    },
    {
      "method": "POST",
      "path": "/tickets/{ticket_id}/create-expense",
      "handler": "create_expense_from_ticket_endpoint()",
      "router": "router",
      "desc": "Crear un expense record a partir de un ticket procesado."
    },
    {
      "method": "POST",
      "path": "/tickets/{ticket_id}/extract-urls",
      "handler": "extract_urls_from_ticket()",
      "router": "router",
      "desc": "Endpoint específico para extraer URLs de un ticket por ID."
    },
    {
      "method": "GET",
      "path": "/tickets/{ticket_id}/image",
      "handler": "get_ticket_image()",
      "router": "router",
      "desc": "Obtener la imagen original del ticket para visualización en el dashboard"
    },
    {
      "method": "GET",
      "path": "/tickets/{ticket_id}/invoice-status",
      "handler": "get_ticket_invoice_status()",
      "router": "router",
      "desc": "Obtener el estado de factura y adjuntos de un ticket"
    },
    {
      "method": "POST",
      "path": "/tickets/{ticket_id}/navigate-urls",
      "handler": "navigate_to_extracted_urls()",
      "router": "router",
      "desc": "Navegar automáticamente a las URLs de facturación extraídas de un ticket."
    },
    {
      "method": "GET",
      "path": "/tickets/{ticket_id}/ocr-text",
      "handler": "get_ticket_ocr_text()",
      "router": "router",
      "desc": "Obtener el texto OCR extraído de un ticket"
    },
    {
      "method": "POST",
      "path": "/tickets/{ticket_id}/reanalyze",
      "handler": "reanalyze_ticket_with_ocr()",
      "router": "router",
      "desc": "Reanalizar un ticket después de que Google Cloud Vision OCR haya terminado correctamente."
    },
    {
      "method": "POST",
      "path": "/tickets/{ticket_id}/upload-invoice",
      "handler": "upload_invoice_file()",
      "router": "router",
      "desc": "Subir archivo de factura (PDF o XML) para un ticket"
    },
    {
      "method": "GET",
      "path": "/tickets/{ticket_id}/validate-consistency",
      "handler": "validate_ticket_consistency()",
      "router": "router",
      "desc": "Validate ticket consistency",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/tickets/{ticket_id}/validate-consistency",
      "handler": "validate_ticket_consistency()",
      "router": "router",
      "desc": "Validar que un ticket tenga datos consistentes entre todos sus campos.",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/url-extraction/health",
      "handler": "get_url_extraction_health()",
      "router": "router",
      "desc": "Verificar estado de salud del sistema de extracción de URLs."
    },
    {
      "method": "GET",
      "path": "/v2/queue/metrics",
      "handler": "get_queue_metrics()",
      "router": "router",
      "desc": "Obtener métricas detalladas del sistema de colas."
    },
    {
      "method": "GET",
      "path": "/v2/system/health",
      "handler": "get_system_health_v2()",
      "router": "router",
      "desc": "Obtener estado de salud completo del sistema escalable."
    },
    {
      "method": "POST",
      "path": "/v2/system/initialize",
      "handler": "initialize_system_v2()",
      "router": "router",
      "desc": "Inicializar servicios escalables."
    },
    {
      "method": "POST",
      "path": "/v2/tickets/batch-process",
      "handler": "batch_process_tickets()",
      "router": "router",
      "desc": "Procesar múltiples tickets en paralelo usando arquitectura escalable."
    },
    {
      "method": "POST",
      "path": "/v2/tickets/process",
      "handler": "process_ticket_v2()",
      "router": "router",
      "desc": "Procesar ticket usando la nueva arquitectura escalable."
    },
    {
      "method": "GET",
      "path": "/v2/tickets/{ticket_id}/status",
      "handler": "get_ticket_processing_status()",
      "router": "router",
      "desc": "Obtener estado detallado del procesamiento de un ticket."
    },
    {
      "method": "POST",
      "path": "/v2/workers/start",
      "handler": "start_workers()",
      "router": "router",
      "desc": "Iniciar workers para procesamiento automático."
    },
    {
      "method": "POST",
      "path": "/webhooks/whatsapp",
      "handler": "whatsapp_webhook()",
      "router": "router",
      "desc": "Webhook para recibir mensajes entrantes de WhatsApp."
    }
  ],
  "modules/invoicing_agent/enhanced_api.py": [
    {
      "method": "POST",
      "path": "/bulk",
      "handler": "create_bulk_automation()",
      "router": "enhanced_router",
      "desc": "Process multiple tickets in batch."
    },
    {
      "method": "GET",
      "path": "/health",
      "handler": "get_system_health()",
      "router": "enhanced_router",
      "desc": "Get system health status.",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/jobs",
      "handler": "list_automation_jobs()",
      "router": "enhanced_router",
      "desc": "List automation jobs with filtering.",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/jobs",
      "handler": "create_automation_job()",
      "router": "enhanced_router",
      "desc": "Create standalone automation job."
    },
    {
      "method": "GET",
      "path": "/jobs/{job_id}",
      "handler": "get_automation_job()",
      "router": "enhanced_router",
      "desc": "Get automation job details.",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/jobs/{job_id}/cancel",
      "handler": "cancel_automation_job()",
      "router": "enhanced_router",
      "desc": "Cancel running automation job."
    },
    {
      "method": "GET",
      "path": "/jobs/{job_id}/stream",
      "handler": "stream_job_progress()",
      "router": "enhanced_router",
      "desc": "Stream real-time job progress via SSE."
    },
    {
      "method": "GET",
      "path": "/metrics",
      "handler": "get_automation_metrics()",
      "router": "enhanced_router",
      "desc": "Get automation metrics.",
      "duplicated": true
    },
    {
      "method": "POST",
      "path": "/tickets",
      "handler": "create_enhanced_ticket()",
      "router": "enhanced_router",
      "desc": "Create ticket with enhanced automation capabilities.",
      "duplicated": true
    },
    {
      "method": "GET",
      "path": "/tickets/{ticket_id}",
      "handler": "get_enhanced_ticket()",
      "router": "enhanced_router",
      "desc": "Get ticket with full automation details.",
      "duplicated": true
    }
  ]
}
```

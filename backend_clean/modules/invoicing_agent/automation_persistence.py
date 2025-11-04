"""
Módulo de Persistencia para Automatización Robusta

Maneja la persistencia de logs, screenshots y datos de automatización
en las tablas automation_jobs, automation_logs y automation_screenshots.
"""

import sqlite3
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class AutomationPersistence:
    """Clase para manejar persistencia de datos de automatización"""

    def __init__(self, db_path: str = "expenses.db"):
        self.db_path = db_path

    def get_connection(self):
        """Obtener conexión a la base de datos"""
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def create_automation_job(self, ticket_id: int, job_data: Dict[str, Any]) -> int:
        """Crear un job de automatización y retornar el ID"""

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                now = datetime.now().isoformat()
                cursor.execute("""
                    INSERT INTO automation_jobs (
                        ticket_id, merchant_id, user_id,
                        automation_type, estado, priority,
                        started_at, config, company_id,
                        session_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticket_id,
                    job_data.get('merchant_id'),
                    job_data.get('user_id'),
                    'selenium',  # Tipo de automatización
                    'en_progreso',   # Estado inicial (usar valor válido)
                    5,  # Priority como integer
                    now,
                    json.dumps(job_data.get('config', {})),
                    job_data.get('company_id', 'default'),
                    f"session_{ticket_id}_{int(datetime.now().timestamp())}",
                    now,
                    now
                ))

                job_id = cursor.lastrowid
                conn.commit()

                logger.info(f"✅ Automation job {job_id} creado para ticket {ticket_id}")
                return job_id

        except Exception as e:
            logger.error(f"Error creando automation job: {e}")
            raise

    def save_automation_step(self, job_id: int, session_id: str, step_data: Dict[str, Any]) -> int:
        """Guardar un paso de automatización como log"""

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Mapear tipos de step a categorías
                category_mapping = {
                    "search_elements": "navigation",
                    "click_header": "navigation",
                    "click_hero": "navigation",
                    "click_footer": "navigation",
                    "validate_visibility": "validation",
                    "handle_tab": "navigation",
                    "wait_dynamic": "navigation",
                    "llm_decision": "validation",
                    "fallback": "navigation",
                    "screenshot": "validation"
                }

                action_type = step_data.get('action_type', 'unknown')
                category = category_mapping.get(action_type, 'navigation')

                # Mapear resultado a nivel de log
                result_status = step_data.get('result', 'unknown')
                level_mapping = {
                    "success": "info",
                    "failed": "warning",
                    "not_visible": "warning",
                    "not_found": "warning",
                    "error": "error",
                    "partial": "warning",
                    "timeout": "error",
                    "requires_intervention": "critical"
                }
                level = level_mapping.get(result_status, 'info')

                cursor.execute("""
                    INSERT INTO automation_logs (
                        job_id, session_id, level, category, message,
                        url, element_selector, execution_time_ms,
                        data, timestamp, company_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_id,
                    session_id,
                    level,
                    category,
                    step_data.get('description', ''),
                    step_data.get('url', ''),
                    step_data.get('selector', ''),
                    step_data.get('timing_ms', 0),
                    json.dumps({
                        'step_number': step_data.get('step_number'),
                        'action_type': action_type,
                        'result': result_status,
                        'error_message': step_data.get('error_message'),
                        'llm_reasoning': step_data.get('llm_reasoning'),
                        'fallback_used': step_data.get('fallback_used', False)
                    }),
                    step_data.get('timestamp', datetime.now().isoformat()),
                    step_data.get('company_id', 'default')
                ))

                log_id = cursor.lastrowid
                conn.commit()

                return log_id

        except Exception as e:
            logger.error(f"Error guardando step de automatización: {e}")
            raise

    def save_screenshot(self, job_id: int, session_id: str, screenshot_data: Dict[str, Any]) -> int:
        """Guardar datos de screenshot"""

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Determinar tipo de screenshot
                step_result = screenshot_data.get('step_result', 'success')
                screenshot_type_mapping = {
                    'success': 'step',
                    'error': 'error',
                    'failed': 'error',
                    'requires_intervention': 'manual'
                }
                screenshot_type = screenshot_type_mapping.get(step_result, 'step')

                # Obtener tamaño de archivo si existe
                file_path = screenshot_data.get('screenshot_path', '')
                file_size = 0
                if file_path and os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)

                cursor.execute("""
                    INSERT INTO automation_screenshots (
                        job_id, session_id, step_name, screenshot_type,
                        file_path, file_size, url, window_title,
                        detected_elements, created_at, company_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_id,
                    session_id,
                    screenshot_data.get('step_name', f"step_{screenshot_data.get('step_number', 0)}"),
                    screenshot_type,
                    file_path,
                    file_size,
                    screenshot_data.get('url', ''),
                    screenshot_data.get('window_title', ''),
                    json.dumps(screenshot_data.get('detected_elements', [])),
                    datetime.now().isoformat(),
                    screenshot_data.get('company_id', 'default')
                ))

                screenshot_id = cursor.lastrowid
                conn.commit()

                return screenshot_id

        except Exception as e:
            logger.error(f"Error guardando screenshot: {e}")
            raise

    def update_automation_job_status(self, job_id: int, status: str, result_data: Dict[str, Any] = None):
        """Actualizar estado de job de automatización"""

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Mapear estados usando valores válidos de la tabla
                status_mapping = {
                    'success': 'completado',
                    'failed': 'fallido',
                    'error': 'fallido',
                    'requires_intervention': 'pausado'
                }

                db_status = status_mapping.get(status, status)
                now = datetime.now().isoformat()

                update_fields = [
                    "estado = ?",
                    "completed_at = ?",
                    "updated_at = ?"
                ]
                update_values = [db_status, now, now]

                if result_data:
                    update_fields.append("result = ?")
                    update_values.append(json.dumps(result_data))

                    # Actualizar métricas disponibles en la tabla
                    # La tabla migration no tiene total_execution_time_ms o final_url
                    # Solo actualizar campos que existen

                update_values.append(job_id)  # Para WHERE clause

                cursor.execute(f"""
                    UPDATE automation_jobs
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                """, update_values)

                conn.commit()

                logger.info(f"✅ Job {job_id} actualizado a estado: {db_status}")

        except Exception as e:
            logger.error(f"Error actualizando job status: {e}")
            raise

    def get_automation_data(self, ticket_id: int) -> Dict[str, Any]:
        """Obtener datos completos de automatización para un ticket"""

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Obtener job más reciente para el ticket
                cursor.execute("""
                    SELECT * FROM automation_jobs
                    WHERE ticket_id = ?
                    ORDER BY started_at DESC
                    LIMIT 1
                """, (ticket_id,))

                job_row = cursor.fetchone()
                if not job_row:
                    return {"error": "No automation job found for ticket"}

                # Convertir row a dict
                job_columns = [desc[0] for desc in cursor.description]
                job_data = dict(zip(job_columns, job_row))
                job_id = job_data['id']

                # Obtener logs
                cursor.execute("""
                    SELECT * FROM automation_logs
                    WHERE job_id = ?
                    ORDER BY timestamp ASC
                """, (job_id,))

                log_rows = cursor.fetchall()
                log_columns = [desc[0] for desc in cursor.description]
                logs = [dict(zip(log_columns, row)) for row in log_rows]

                # Obtener screenshots
                cursor.execute("""
                    SELECT * FROM automation_screenshots
                    WHERE job_id = ?
                    ORDER BY created_at ASC
                """, (job_id,))

                screenshot_rows = cursor.fetchall()
                screenshot_columns = [desc[0] for desc in cursor.description]
                screenshots = [dict(zip(screenshot_columns, row)) for row in screenshot_rows]

                # Construir respuesta
                automation_data = {
                    "ticket_id": ticket_id,
                    "job_data": job_data,
                    "logs": logs,
                    "screenshots": screenshots,
                    "summary": {
                        "total_steps": len(logs),
                        "screenshots_count": len(screenshots),
                        "status": job_data.get('estado', 'unknown'),
                        "duration_ms": 0,  # Migration table no tiene este campo
                        "final_url": "",   # Migration table no tiene este campo
                        "success_rate": self._calculate_success_rate(logs)
                    }
                }

                return automation_data

        except Exception as e:
            logger.error(f"Error obteniendo automation data: {e}")
            return {"error": str(e)}

    def _calculate_success_rate(self, logs: List[Dict]) -> float:
        """Calcular tasa de éxito basada en logs"""
        if not logs:
            return 0.0

        success_logs = len([log for log in logs if log.get('level') == 'info'])
        return success_logs / len(logs) if logs else 0.0

    def cleanup_old_data(self, days_old: int = 30):
        """Limpiar datos antiguos de automatización"""

        try:
            cutoff_date = datetime.now().replace(day=datetime.now().day - days_old).isoformat()

            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Eliminar screenshots antiguos (archivos)
                cursor.execute("""
                    SELECT file_path FROM automation_screenshots
                    WHERE created_at < ?
                """, (cutoff_date,))

                screenshot_files = cursor.fetchall()
                for (file_path,) in screenshot_files:
                    if file_path and os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            logger.warning(f"No se pudo eliminar screenshot {file_path}: {e}")

                # Eliminar registros antiguos (cascada automática por FK)
                cursor.execute("""
                    DELETE FROM automation_jobs
                    WHERE started_at < ?
                """, (cutoff_date,))

                deleted_jobs = cursor.rowcount
                conn.commit()

                logger.info(f"🧹 Limpieza completada: {deleted_jobs} jobs antiguos eliminados")

        except Exception as e:
            logger.error(f"Error en limpieza de datos: {e}")


# Función helper para usar desde el motor robusto
def create_automation_persistence() -> AutomationPersistence:
    """Factory para crear instancia de persistencia"""
    return AutomationPersistence()

# Funciones de conveniencia
async def save_automation_session(ticket_id: int, automation_summary: Dict[str, Any],
                                session_id: str = None) -> int:
    """Guardar sesión completa de automatización"""

    if not session_id:
        session_id = f"session_{ticket_id}_{int(datetime.now().timestamp())}"

    persistence = create_automation_persistence()

    try:
        # Crear job
        job_data = {
            'config': automation_summary.get('config', {}),
            'company_id': 'default'
        }
        job_id = persistence.create_automation_job(ticket_id, job_data)

        # Guardar steps como logs
        steps = automation_summary.get('steps', [])
        for step in steps:
            if isinstance(step, dict):
                step['company_id'] = 'default'
                persistence.save_automation_step(job_id, session_id, step)

        # Guardar screenshots
        screenshots = automation_summary.get('screenshots', [])
        for i, screenshot_path in enumerate(screenshots):
            if screenshot_path:
                screenshot_data = {
                    'step_number': i + 1,
                    'screenshot_path': screenshot_path,
                    'step_result': 'success',
                    'company_id': 'default'
                }
                persistence.save_screenshot(job_id, session_id, screenshot_data)

        # Actualizar estado final
        final_status = 'success' if automation_summary.get('success_rate', 0) > 0.5 else 'failed'
        persistence.update_automation_job_status(job_id, final_status, automation_summary)

        logger.info(f"💾 Sesión de automatización guardada: job_id={job_id}, session_id={session_id}")
        return job_id

    except Exception as e:
        logger.error(f"Error guardando sesión de automatización: {e}")
        raise
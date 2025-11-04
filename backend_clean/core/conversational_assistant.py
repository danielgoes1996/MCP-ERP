"""
Conversational Assistant - AI-powered natural language interface for expense queries
"""

import os
import logging
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


@dataclass
class QueryResponse:
    """Representa una respuesta del asistente conversacional"""
    answer: str
    data: Optional[Dict[str, Any]]
    query_type: str
    confidence: float
    sql_executed: Optional[str] = None


class ConversationalAssistant:
    """
    Asistente conversacional para consultas de gastos en lenguaje natural
    """

    def __init__(self, db_path: str = "empresa.db"):
        self.db_path = db_path

        if not OpenAI:
            logger.warning("OpenAI library not available, conversational assistant will be limited")
            self.client = None
        else:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                logger.warning("OPENAI_API_KEY not configured, conversational assistant will be limited")
                self.client = None
            else:
                self.client = OpenAI(api_key=api_key)

        # Tipos de consultas que puede manejar
        self.QUERY_TYPES = {
            'expense_summary': {
                'keywords': ['total', 'cuanto', 'suma', 'gastado', 'resumen', 'gastos'],
                'description': 'Resúmenes y totales de gastos'
            },
            'expense_search': {
                'keywords': ['buscar', 'encontrar', 'mostrar', 'listar', 'ver'],
                'description': 'Búsqueda de gastos específicos'
            },
            'category_analysis': {
                'keywords': ['categoria', 'clasificacion', 'tipo', 'breakdown'],
                'description': 'Análisis por categorías'
            },
            'time_analysis': {
                'keywords': ['mes', 'semana', 'dia', 'periodo', 'fecha', 'cuando'],
                'description': 'Análisis temporal'
            },
            'provider_analysis': {
                'keywords': ['proveedor', 'empresa', 'comercio', 'donde'],
                'description': 'Análisis por proveedores'
            },
            'duplicate_check': {
                'keywords': ['duplicado', 'repetido', 'similar'],
                'description': 'Verificación de duplicados'
            }
        }

    def process_query(self, user_query: str) -> QueryResponse:
        """
        Procesa una consulta en lenguaje natural y devuelve una respuesta

        Args:
            user_query: Consulta del usuario en lenguaje natural

        Returns:
            QueryResponse con la respuesta del asistente
        """

        if self.client:
            return self._process_with_llm(user_query)
        else:
            return self._process_with_rules(user_query)

    def _process_with_llm(self, user_query: str) -> QueryResponse:
        """Procesa la consulta usando LLM con contexto de base de datos"""

        try:
            # Obtener esquema de la base de datos
            db_schema = self._get_database_schema()

            # Obtener estadísticas básicas
            basic_stats = self._get_basic_stats()

            # Crear prompt estructurado
            prompt = self._create_query_prompt(user_query, db_schema, basic_stats)

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un asistente especializado en análisis de gastos empresariales. Puedes generar SQL y analizar datos de gastos."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=800
            )

            result_text = response.choices[0].message.content.strip()

            # Parsear respuesta del LLM
            return self._parse_llm_query_response(result_text, user_query)

        except Exception as e:
            logger.error(f"Error in LLM query processing: {e}")
            # Fallback a reglas básicas
            return self._process_with_rules(user_query)

    def _create_query_prompt(self, user_query: str, db_schema: Dict, basic_stats: Dict) -> str:
        """Crea el prompt estructurado para el LLM"""

        prompt = f"""
ASISTENTE DE CONSULTAS DE GASTOS EMPRESARIALES

CONSULTA DEL USUARIO: "{user_query}"

ESQUEMA DE BASE DE DATOS:
Tabla: expense_records
Columnas:
- id (INTEGER): ID único del gasto
- descripcion (TEXT): Descripción del gasto
- monto_total (REAL): Monto total del gasto
- categoria (TEXT): Categoría del gasto (combustible, alimentos, transporte, etc.)
- fecha_gasto (TEXT): Fecha del gasto en formato YYYY-MM-DD
- metadata (JSON): Datos adicionales incluyendo proveedor

ESTADÍSTICAS ACTUALES:
- Total de gastos registrados: {basic_stats.get('total_expenses', 0)}
- Suma total gastada: ${basic_stats.get('total_amount', 0):.2f}
- Categorías disponibles: {', '.join(basic_stats.get('categories', []))}
- Rango de fechas: {basic_stats.get('date_range', 'N/A')}

INSTRUCCIONES:
1. Analiza la consulta del usuario y determina qué información necesita
2. Si requiere datos específicos, genera una consulta SQL apropiada
3. Proporciona una respuesta clara y útil
4. Si no puedes responder con los datos disponibles, explica por qué

TIPOS DE CONSULTAS QUE PUEDES MANEJAR:
- Resúmenes de gastos ("¿cuánto gasté este mes?")
- Búsquedas específicas ("mostrar gastos de combustible")
- Análisis por categorías ("breakdown por categoría")
- Análisis temporal ("gastos de la semana pasada")
- Análisis por proveedores ("gastos en Pemex")

RESPUESTA EN FORMATO JSON:
{{
    "query_type": "tipo_de_consulta",
    "sql_query": "SELECT ... (si aplica)",
    "answer": "respuesta clara y útil para el usuario",
    "confidence": 0.85,
    "needs_data": true/false
}}
"""

        return prompt

    def _parse_llm_query_response(self, response_text: str, original_query: str) -> QueryResponse:
        """Parsea la respuesta JSON del LLM y ejecuta SQL si es necesario"""

        try:
            # Extraer JSON de la respuesta
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())

                query_type = result.get('query_type', 'general')
                sql_query = result.get('sql_query')
                answer = result.get('answer', 'No se pudo procesar la consulta')
                confidence = result.get('confidence', 0.5)
                needs_data = result.get('needs_data', False)

                # Ejecutar SQL si es necesario
                data = None
                if needs_data and sql_query:
                    data = self._execute_sql_query(sql_query)

                    # Mejorar respuesta con datos reales
                    if data:
                        answer = self._enhance_answer_with_data(answer, data, original_query)

                return QueryResponse(
                    answer=answer,
                    data=data,
                    query_type=query_type,
                    confidence=confidence,
                    sql_executed=sql_query
                )
            else:
                raise ValueError("No JSON found in response")

        except Exception as e:
            logger.error(f"Error parsing LLM query response: {e}")
            return QueryResponse(
                answer="Hubo un error procesando tu consulta. ¿Podrías reformularla?",
                data=None,
                query_type="error",
                confidence=0.1
            )

    def _process_with_rules(self, user_query: str) -> QueryResponse:
        """Procesa la consulta usando reglas básicas como fallback"""

        query_lower = user_query.lower()

        # Detectar tipo de consulta
        detected_type = None
        for query_type, info in self.QUERY_TYPES.items():
            if any(keyword in query_lower for keyword in info['keywords']):
                detected_type = query_type
                break

        if not detected_type:
            return QueryResponse(
                answer="No entendí tu consulta. Puedes preguntarme sobre totales de gastos, búsquedas por categoría, análisis por fechas o proveedores.",
                data=None,
                query_type="unknown",
                confidence=0.2
            )

        # Procesar según el tipo detectado
        if detected_type == 'expense_summary':
            return self._handle_expense_summary(query_lower)
        elif detected_type == 'expense_search':
            return self._handle_expense_search(query_lower)
        elif detected_type == 'category_analysis':
            return self._handle_category_analysis(query_lower)
        elif detected_type == 'time_analysis':
            return self._handle_time_analysis(query_lower)
        elif detected_type == 'provider_analysis':
            return self._handle_provider_analysis(query_lower)
        else:
            return QueryResponse(
                answer=f"Detecté que quieres hacer un análisis de tipo '{detected_type}', pero esta función aún está en desarrollo.",
                data=None,
                query_type=detected_type,
                confidence=0.4
            )

    def _handle_expense_summary(self, query: str) -> QueryResponse:
        """Maneja consultas de resumen de gastos"""

        sql = "SELECT COUNT(*) as total_expenses, SUM(monto_total) as total_amount FROM expense_records"
        data = self._execute_sql_query(sql)

        if data and len(data) > 0:
            total_expenses = data[0]['total_expenses']
            total_amount = data[0]['total_amount'] or 0

            answer = f"📊 **Resumen de Gastos**\n\n"
            answer += f"• Total de gastos registrados: {total_expenses}\n"
            answer += f"• Suma total gastada: ${total_amount:,.2f}\n"

            return QueryResponse(
                answer=answer,
                data={'total_expenses': total_expenses, 'total_amount': total_amount},
                query_type='expense_summary',
                confidence=0.9,
                sql_executed=sql
            )
        else:
            return QueryResponse(
                answer="No se encontraron gastos registrados en la base de datos.",
                data=None,
                query_type='expense_summary',
                confidence=0.8
            )

    def _handle_expense_search(self, query: str) -> QueryResponse:
        """Maneja búsquedas específicas de gastos"""

        # Buscar términos específicos en la consulta
        search_terms = []
        for word in query.split():
            if len(word) > 3 and word not in ['buscar', 'mostrar', 'listar', 'gastos', 'todos']:
                search_terms.append(word)

        if not search_terms:
            sql = "SELECT * FROM expense_records ORDER BY fecha_gasto DESC LIMIT 10"
            data = self._execute_sql_query(sql)

            answer = "📋 **Últimos 10 gastos registrados:**\n\n"
            if data:
                for expense in data:
                    answer += f"• {expense['descripcion']} - ${expense['monto_total']:.2f} ({expense['fecha_gasto']})\n"
            else:
                answer = "No se encontraron gastos."

        else:
            # Buscar por términos específicos
            search_term = search_terms[0]
            sql = f"""
            SELECT * FROM expense_records
            WHERE descripcion LIKE '%{search_term}%'
            OR categoria LIKE '%{search_term}%'
            ORDER BY fecha_gasto DESC LIMIT 20
            """
            data = self._execute_sql_query(sql)

            if data:
                answer = f"🔍 **Gastos encontrados para '{search_term}':**\n\n"
                for expense in data:
                    answer += f"• {expense['descripcion']} - ${expense['monto_total']:.2f} ({expense['categoria']}) - {expense['fecha_gasto']}\n"
            else:
                answer = f"No se encontraron gastos relacionados con '{search_term}'."

        return QueryResponse(
            answer=answer,
            data=data,
            query_type='expense_search',
            confidence=0.8,
            sql_executed=sql
        )

    def _handle_category_analysis(self, query: str) -> QueryResponse:
        """Maneja análisis por categorías"""

        sql = """
        SELECT categoria, COUNT(*) as count, SUM(monto_total) as total_amount
        FROM expense_records
        GROUP BY categoria
        ORDER BY total_amount DESC
        """
        data = self._execute_sql_query(sql)

        if data:
            answer = "📊 **Análisis por Categorías:**\n\n"
            total_general = sum(row['total_amount'] or 0 for row in data)

            for row in data:
                category = row['categoria'] or 'Sin categoría'
                count = row['count']
                amount = row['total_amount'] or 0
                percentage = (amount / total_general * 100) if total_general > 0 else 0

                answer += f"• **{category.title()}**: {count} gastos - ${amount:,.2f} ({percentage:.1f}%)\n"

            return QueryResponse(
                answer=answer,
                data=data,
                query_type='category_analysis',
                confidence=0.9,
                sql_executed=sql
            )
        else:
            return QueryResponse(
                answer="No se encontraron datos de categorías.",
                data=None,
                query_type='category_analysis',
                confidence=0.5
            )

    def _handle_time_analysis(self, query: str) -> QueryResponse:
        """Maneja análisis temporal"""

        # Detectar período de tiempo
        today = datetime.now()

        if 'mes' in query:
            start_date = today.replace(day=1).strftime('%Y-%m-%d')
            period = "este mes"
        elif 'semana' in query:
            start_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')
            period = "esta semana"
        elif 'dia' in query or 'hoy' in query:
            start_date = today.strftime('%Y-%m-%d')
            period = "hoy"
        else:
            start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
            period = "últimos 30 días"

        sql = f"""
        SELECT COUNT(*) as count, SUM(monto_total) as total_amount
        FROM expense_records
        WHERE fecha_gasto >= '{start_date}'
        """
        data = self._execute_sql_query(sql)

        if data and len(data) > 0:
            count = data[0]['count']
            amount = data[0]['total_amount'] or 0

            answer = f"📅 **Gastos de {period}:**\n\n"
            answer += f"• Número de gastos: {count}\n"
            answer += f"• Total gastado: ${amount:,.2f}\n"

            return QueryResponse(
                answer=answer,
                data={'period': period, 'count': count, 'amount': amount},
                query_type='time_analysis',
                confidence=0.8,
                sql_executed=sql
            )
        else:
            return QueryResponse(
                answer=f"No se encontraron gastos para {period}.",
                data=None,
                query_type='time_analysis',
                confidence=0.6
            )

    def _handle_provider_analysis(self, query: str) -> QueryResponse:
        """Maneja análisis por proveedores"""

        sql = """
        SELECT
            json_extract(metadata, '$.proveedor.nombre') as proveedor,
            COUNT(*) as count,
            SUM(monto_total) as total_amount
        FROM expense_records
        WHERE json_extract(metadata, '$.proveedor.nombre') IS NOT NULL
        GROUP BY proveedor
        ORDER BY total_amount DESC
        LIMIT 10
        """
        data = self._execute_sql_query(sql)

        if data:
            answer = "🏢 **Top Proveedores:**\n\n"
            for row in data:
                proveedor = row['proveedor'] or 'Desconocido'
                count = row['count']
                amount = row['total_amount'] or 0

                answer += f"• **{proveedor}**: {count} gastos - ${amount:,.2f}\n"

            return QueryResponse(
                answer=answer,
                data=data,
                query_type='provider_analysis',
                confidence=0.8,
                sql_executed=sql
            )
        else:
            return QueryResponse(
                answer="No se encontraron datos de proveedores.",
                data=None,
                query_type='provider_analysis',
                confidence=0.5
            )

    def _get_database_schema(self) -> Dict[str, Any]:
        """Obtiene el esquema de la base de datos"""

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Obtener información de las tablas
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            schema = {}
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                schema[table] = [{"name": col[1], "type": col[2]} for col in columns]

            conn.close()
            return schema

        except Exception as e:
            logger.error(f"Error getting database schema: {e}")
            return {}

    def _get_basic_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas básicas de la base de datos"""

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Total de gastos y suma
            cursor.execute("SELECT COUNT(*) as total, SUM(monto_total) as sum FROM expense_records")
            totals = cursor.fetchone()

            # Categorías disponibles
            cursor.execute("SELECT DISTINCT categoria FROM expense_records WHERE categoria IS NOT NULL")
            categories = [row[0] for row in cursor.fetchall()]

            # Rango de fechas
            cursor.execute("SELECT MIN(fecha_gasto) as min_date, MAX(fecha_gasto) as max_date FROM expense_records")
            date_range = cursor.fetchone()

            conn.close()

            return {
                'total_expenses': totals[0] if totals else 0,
                'total_amount': totals[1] if totals else 0.0,
                'categories': categories,
                'date_range': f"{date_range[0]} to {date_range[1]}" if date_range[0] else "N/A"
            }

        except Exception as e:
            logger.error(f"Error getting basic stats: {e}")
            return {'total_expenses': 0, 'total_amount': 0.0, 'categories': [], 'date_range': 'N/A'}

    def _execute_sql_query(self, sql: str) -> Optional[List[Dict[str, Any]]]:
        """Ejecuta una consulta SQL y devuelve los resultados"""

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(sql)
            rows = cursor.fetchall()

            conn.close()

            # Convertir a lista de diccionarios
            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error executing SQL query '{sql}': {e}")
            return None

    def _enhance_answer_with_data(self, base_answer: str, data: List[Dict], original_query: str) -> str:
        """Mejora la respuesta base con datos reales obtenidos de la consulta"""

        if not data:
            return base_answer + "\n\n(No se encontraron datos)"

        # Agregar contexto de datos
        enhanced = base_answer + "\n\n📊 **Datos encontrados:**\n"

        # Mostrar los primeros resultados
        for i, row in enumerate(data[:5]):
            enhanced += f"• {row}\n"

        if len(data) > 5:
            enhanced += f"... y {len(data) - 5} resultados más.\n"

        return enhanced


# Instancia global del asistente
_conversational_assistant = None

def get_conversational_assistant() -> ConversationalAssistant:
    """Obtener instancia global del asistente conversacional"""
    global _conversational_assistant
    if _conversational_assistant is None:
        _conversational_assistant = ConversationalAssistant()
    return _conversational_assistant


def process_natural_language_query(user_query: str) -> Dict[str, Any]:
    """
    Función helper para procesar consultas en lenguaje natural

    Args:
        user_query: Consulta del usuario en lenguaje natural

    Returns:
        Diccionario con la respuesta del asistente
    """
    assistant = get_conversational_assistant()
    response = assistant.process_query(user_query)

    return {
        'answer': response.answer,
        'data': response.data,
        'query_type': response.query_type,
        'confidence': response.confidence,
        'sql_executed': response.sql_executed,
        'has_llm': assistant.client is not None
    }
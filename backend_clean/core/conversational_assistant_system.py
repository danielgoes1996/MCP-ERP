import hashlib
import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum
import sqlite3
from contextlib import asynccontextmanager
import openai
from anthropic import Anthropic

logger = logging.getLogger(__name__)

class QueryType(Enum):
    SELECT = "SELECT"
    COUNT = "COUNT"
    SUM = "SUM"
    GROUP_BY = "GROUP_BY"
    JOIN = "JOIN"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"

class InteractionType(Enum):
    QUERY = "query"
    COMMAND = "command"
    CLARIFICATION = "clarification"

class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    AZURE = "azure"
    HUGGINGFACE = "huggingface"

class ConversationalAssistantSystem:
    """
    Sistema de Asistente Conversacional con LLM integrado

    Características:
    - Cache inteligente de respuestas LLM
    - Sanitización de input y SQL injection prevention
    - Múltiples providers de LLM (OpenAI, Anthropic, etc.)
    - Query logging y analytics completos
    - Sistema de sesiones persistentes
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        self.db_path = "unified_mcp_system.db"

        # Configuración de LLM providers
        self.llm_clients = {
            "openai": None,
            "anthropic": None
        }

        # Cache en memoria para respuestas frecuentes
        self.memory_cache = {}
        self.cache_ttl = 3600  # 1 hora

        # SQL safety patterns
        self.safe_sql_patterns = [
            r'^SELECT\s+.*\s+FROM\s+\w+',
            r'^SELECT\s+COUNT\(',
            r'^SELECT\s+SUM\(',
            r'^SELECT\s+AVG\(',
            r'^SELECT\s+MAX\(',
            r'^SELECT\s+MIN\('
        ]

        self.dangerous_sql_patterns = [
            r'DROP\s+TABLE',
            r'DELETE\s+FROM',
            r'INSERT\s+INTO',
            r'UPDATE\s+SET',
            r'ALTER\s+TABLE',
            r'CREATE\s+TABLE',
            r'EXEC\s*\(',
            r'xp_cmdshell',
            r'sp_executesql'
        ]

        self._setup_llm_clients()

    def _setup_llm_clients(self):
        """Configurar clientes LLM"""
        try:
            # Configurar OpenAI
            import os
            openai_key = os.getenv('OPENAI_API_KEY')
            if openai_key:
                self.llm_clients["openai"] = openai.OpenAI(api_key=openai_key)
                logger.info("✅ OpenAI client configured")

            # Configurar Anthropic
            anthropic_key = os.getenv('ANTHROPIC_API_KEY')
            if anthropic_key:
                self.llm_clients["anthropic"] = Anthropic(api_key=anthropic_key)
                logger.info("✅ Anthropic client configured")

        except Exception as e:
            logger.warning(f"LLM client setup warning: {e}")

    @asynccontextmanager
    async def get_db_connection(self):
        """Context manager para conexión segura a base de datos"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    async def create_conversation_session(self, user_id: str, company_id: str,
                                        session_name: str = None) -> str:
        """Crear nueva sesión de conversación"""
        try:
            session_id = f"conv_{int(time.time())}_{user_id[:8]}"

            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO conversational_sessions (
                        session_id, user_id, company_id, session_name,
                        context_data, created_at, last_activity
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, user_id, company_id,
                    session_name or f"Conversación {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    json.dumps({}), datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat()
                ))
                conn.commit()

                logger.info(f"Created conversation session {session_id} for user {user_id}")
                return session_id

        except Exception as e:
            logger.error(f"Error creating conversation session: {e}")
            raise

    async def process_user_query(self, session_id: str, user_id: str,
                                user_query: str, context: Dict = None) -> Dict[str, Any]:
        """
        Procesar query del usuario con LLM

        Returns:
            Dict con respuesta, SQL ejecutado, modelo usado, etc.
        """
        try:
            start_time = time.time()

            # Validar y sanitizar input
            if not self._is_safe_input(user_query):
                return {
                    "status": "error",
                    "message": "Query contiene contenido potencialmente peligroso",
                    "confidence": 0.0
                }

            # Buscar en cache primero
            cache_key = self._generate_cache_key(user_query, context or {})
            cached_response = await self._get_cached_response(cache_key)

            if cached_response:
                logger.info(f"Cache hit for query: {user_query[:50]}...")

                # Registrar interacción desde cache
                await self._record_interaction(
                    session_id, user_id, user_query,
                    cached_response["response"],
                    cached_response["sql_executed"],
                    cached_response["llm_model_used"],
                    InteractionType.QUERY,
                    confidence=cached_response.get("confidence", 0.9),
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    from_cache=True
                )

                return {
                    "status": "success",
                    "response": cached_response["response"],
                    "sql_executed": cached_response["sql_executed"],
                    "llm_model_used": cached_response["llm_model_used"],
                    "confidence": cached_response.get("confidence", 0.9),
                    "from_cache": True,
                    "processing_time_ms": int((time.time() - start_time) * 1000)
                }

            # Procesar con LLM
            llm_response = await self._process_with_llm(user_query, context or {})

            if llm_response["status"] != "success":
                return llm_response

            # Ejecutar SQL si se generó
            sql_result = None
            sql_executed = llm_response.get("sql_query")

            if sql_executed:
                sql_result = await self._execute_safe_sql(sql_executed, user_id)

            # Generar respuesta final
            final_response = await self._generate_final_response(
                user_query, llm_response, sql_result
            )

            processing_time_ms = int((time.time() - start_time) * 1000)

            # Registrar interacción completa
            await self._record_interaction(
                session_id, user_id, user_query,
                final_response["response"],
                sql_executed,
                llm_response["model_used"],
                InteractionType.QUERY,
                confidence=llm_response.get("confidence", 0.8),
                processing_time_ms=processing_time_ms,
                query_intent=llm_response.get("intent")
            )

            # Guardar en cache si es exitoso
            if final_response["status"] == "success":
                await self._cache_response(
                    cache_key, final_response["response"],
                    sql_executed, llm_response["model_used"],
                    llm_response.get("confidence", 0.8)
                )

            return {
                "status": final_response["status"],
                "response": final_response["response"],
                "sql_executed": sql_executed,
                "llm_model_used": llm_response["model_used"],
                "confidence": llm_response.get("confidence", 0.8),
                "query_intent": llm_response.get("intent"),
                "processing_time_ms": processing_time_ms,
                "sql_result_rows": sql_result.get("row_count", 0) if sql_result else 0
            }

        except Exception as e:
            logger.error(f"Error processing user query: {e}")
            return {
                "status": "error",
                "message": f"Error procesando consulta: {str(e)}",
                "confidence": 0.0
            }

    async def _process_with_llm(self, user_query: str, context: Dict) -> Dict[str, Any]:
        """Procesar query con el modelo LLM más apropiado"""
        try:
            # Determinar mejor modelo para la query
            model_config = await self._select_best_model(user_query, context)

            if not model_config:
                return {
                    "status": "error",
                    "message": "No hay modelos LLM disponibles"
                }

            # Construir prompt optimizado
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(user_query, context)

            # Llamar al modelo
            if model_config["provider"] == "openai":
                response = await self._call_openai(
                    model_config["model_name"], system_prompt, user_prompt
                )
            elif model_config["provider"] == "anthropic":
                response = await self._call_anthropic(
                    model_config["model_name"], system_prompt, user_prompt
                )
            else:
                return {
                    "status": "error",
                    "message": f"Provider {model_config['provider']} no soportado"
                }

            # Parsear respuesta
            parsed_response = self._parse_llm_response(response)
            parsed_response["model_used"] = model_config["model_name"]

            return parsed_response

        except Exception as e:
            logger.error(f"Error processing with LLM: {e}")
            return {
                "status": "error",
                "message": f"Error en procesamiento LLM: {str(e)}"
            }

    async def _call_openai(self, model: str, system_prompt: str, user_prompt: str) -> str:
        """Llamar a OpenAI API"""
        try:
            if not self.llm_clients["openai"]:
                raise Exception("Cliente OpenAI no configurado")

            response = self.llm_clients["openai"].chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=4000
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    async def _call_anthropic(self, model: str, system_prompt: str, user_prompt: str) -> str:
        """Llamar a Anthropic API"""
        try:
            if not self.llm_clients["anthropic"]:
                raise Exception("Cliente Anthropic no configurado")

            response = self.llm_clients["anthropic"].messages.create(
                model=model,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=4000,
                temperature=0.7
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    def _build_system_prompt(self) -> str:
        """Construir prompt de sistema optimizado"""
        return """Eres un asistente inteligente para un sistema de gestión de gastos empresariales.

Tu trabajo es:
1. Analizar consultas de usuarios sobre gastos, facturas, conciliación bancaria
2. Generar consultas SQL seguras cuando sea necesario
3. Proporcionar respuestas claras y útiles

REGLAS IMPORTANTES:
- SOLO genera consultas SELECT, nunca INSERT/UPDATE/DELETE
- Usa siempre WHERE user_id = ? para filtrar por usuario
- Incluye LIMIT en consultas que pueden devolver muchos resultados
- Si no puedes generar SQL seguro, di "NO_SQL_NEEDED"

ESQUEMA DE BASE DE DATOS:
- expenses: id, descripcion, monto_total, fecha_gasto, categoria, user_id
- invoices: id, uuid, rfc_emisor, total, fecha_emision, user_id
- bank_movements: id, amount, description, date, user_id

Responde en formato JSON:
{
  "intent": "categoria_de_consulta",
  "confidence": 0.8,
  "sql_query": "SELECT ... o NO_SQL_NEEDED",
  "explanation": "Explicación de lo que harás",
  "response_template": "Template para respuesta"
}"""

    def _build_user_prompt(self, query: str, context: Dict) -> str:
        """Construir prompt de usuario con contexto"""
        prompt = f"Consulta del usuario: {query}\n\n"

        if context:
            prompt += f"Contexto adicional: {json.dumps(context, ensure_ascii=False)}\n\n"

        prompt += "Por favor, analiza la consulta y genera la respuesta en formato JSON."

        return prompt

    def _parse_llm_response(self, llm_response: str) -> Dict[str, Any]:
        """Parsear respuesta JSON del LLM"""
        try:
            # Buscar JSON en la respuesta
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                response_data = json.loads(json_match.group(0))
            else:
                # Fallback si no hay JSON válido
                response_data = {
                    "intent": "unknown",
                    "confidence": 0.5,
                    "sql_query": "NO_SQL_NEEDED",
                    "explanation": llm_response[:200],
                    "response_template": llm_response
                }

            return {
                "status": "success",
                "intent": response_data.get("intent", "unknown"),
                "confidence": float(response_data.get("confidence", 0.8)),
                "sql_query": response_data.get("sql_query"),
                "explanation": response_data.get("explanation", ""),
                "response_template": response_data.get("response_template", "")
            }

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM JSON response: {e}")
            return {
                "status": "partial_success",
                "intent": "unknown",
                "confidence": 0.5,
                "sql_query": "NO_SQL_NEEDED",
                "explanation": "Respuesta procesada sin estructura JSON",
                "response_template": llm_response
            }

    async def _execute_safe_sql(self, sql_query: str, user_id: str) -> Dict[str, Any]:
        """Ejecutar SQL de forma segura"""
        try:
            # Validar que es SQL seguro
            if not self._is_safe_sql(sql_query):
                return {
                    "status": "error",
                    "message": "SQL query no es segura",
                    "row_count": 0
                }

            # Asegurar filtro de usuario
            if "user_id" not in sql_query.lower():
                return {
                    "status": "error",
                    "message": "Query debe incluir filtro user_id",
                    "row_count": 0
                }

            async with self.get_db_connection() as conn:
                cursor = conn.cursor()

                # Ejecutar query con parámetro seguro
                safe_query = sql_query.replace("?", f"'{user_id}'")
                cursor.execute(safe_query)

                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                # Convertir resultados a formato serializable
                result_data = []
                for row in results:
                    result_data.append(dict(zip(columns, row)))

                return {
                    "status": "success",
                    "result_data": result_data,
                    "row_count": len(result_data),
                    "columns": columns
                }

        except Exception as e:
            logger.error(f"Error executing SQL: {e}")
            return {
                "status": "error",
                "message": f"Error ejecutando consulta: {str(e)}",
                "row_count": 0
            }

    async def _generate_final_response(self, original_query: str,
                                     llm_response: Dict, sql_result: Dict) -> Dict[str, Any]:
        """Generar respuesta final combinando LLM y resultados SQL"""
        try:
            if sql_result and sql_result["status"] == "success":
                # Combinar template con datos reales
                template = llm_response.get("response_template", "")
                data = sql_result["result_data"]

                if data:
                    # Formatear respuesta con datos
                    response = self._format_response_with_data(template, data)
                else:
                    response = "No encontré información que coincida con tu consulta."
            else:
                # Usar respuesta directa del LLM
                response = llm_response.get("response_template", llm_response.get("explanation", ""))

            return {
                "status": "success",
                "response": response
            }

        except Exception as e:
            logger.error(f"Error generating final response: {e}")
            return {
                "status": "error",
                "response": f"Error generando respuesta: {str(e)}"
            }

    def _format_response_with_data(self, template: str, data: List[Dict]) -> str:
        """Formatear template con datos SQL"""
        try:
            if not data:
                return "No se encontraron resultados."

            # Casos comunes de formateo
            if len(data) == 1:
                # Un solo resultado
                result = data[0]
                if "total" in result:
                    return f"El total es ${result['total']:,.2f}"
                elif "count" in result:
                    return f"Encontré {result['count']} registros"
                else:
                    return f"Resultado: {json.dumps(result, ensure_ascii=False, indent=2)}"

            elif len(data) <= 5:
                # Pocos resultados, mostrar detalles
                response = f"Encontré {len(data)} resultados:\n\n"
                for i, item in enumerate(data, 1):
                    response += f"{i}. "
                    if "descripcion" in item and "monto_total" in item:
                        response += f"{item['descripcion']} - ${item['monto_total']:,.2f}\n"
                    else:
                        response += f"{json.dumps(item, ensure_ascii=False)}\n"
                return response

            else:
                # Muchos resultados, mostrar resumen
                return f"Encontré {len(data)} resultados. Aquí están los primeros 5:\n\n" + \
                       self._format_response_with_data(template, data[:5])

        except Exception as e:
            logger.error(f"Error formatting response: {e}")
            return f"Datos encontrados: {len(data)} registros"

    def _is_safe_input(self, user_input: str) -> bool:
        """Validar que el input del usuario es seguro"""
        try:
            # Longitud máxima
            if len(user_input) > 10000:
                return False

            # Patrones peligrosos básicos
            dangerous_patterns = [
                r'<script',
                r'javascript:',
                r'eval\(',
                r'exec\(',
                r'\.\./.*\.\.',  # Path traversal
            ]

            for pattern in dangerous_patterns:
                if re.search(pattern, user_input, re.IGNORECASE):
                    return False

            return True

        except Exception as e:
            logger.warning(f"Error validating input safety: {e}")
            return False

    def _is_safe_sql(self, sql_query: str) -> bool:
        """Validar que la query SQL es segura"""
        try:
            sql_upper = sql_query.upper().strip()

            # Debe comenzar con SELECT
            if not sql_upper.startswith('SELECT'):
                return False

            # Verificar patrones peligrosos
            for pattern in self.dangerous_sql_patterns:
                if re.search(pattern, sql_upper):
                    return False

            # Verificar patrones seguros
            is_safe = any(re.search(pattern, sql_upper) for pattern in self.safe_sql_patterns)

            return is_safe

        except Exception as e:
            logger.warning(f"Error validating SQL safety: {e}")
            return False

    def _generate_cache_key(self, query: str, context: Dict) -> str:
        """Generar clave de cache única"""
        cache_data = {
            "query": query.lower().strip(),
            "context": json.dumps(context, sort_keys=True)
        }
        return hashlib.sha256(json.dumps(cache_data).encode()).hexdigest()[:16]

    async def _get_cached_response(self, cache_key: str) -> Optional[Dict]:
        """Obtener respuesta del cache"""
        try:
            # Verificar cache en memoria primero
            if cache_key in self.memory_cache:
                cached = self.memory_cache[cache_key]
                if time.time() - cached["timestamp"] < self.cache_ttl:
                    return cached["data"]
                else:
                    del self.memory_cache[cache_key]

            # Verificar cache en base de datos
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT llm_response, model_used, confidence_score, hit_count
                    FROM llm_response_cache
                    WHERE cache_key = ? AND is_expired = FALSE
                """, (cache_key,))

                result = cursor.fetchone()
                if result:
                    # Actualizar hit count
                    cursor.execute("""
                        UPDATE llm_response_cache
                        SET hit_count = hit_count + 1,
                            last_accessed = ?
                        WHERE cache_key = ?
                    """, (datetime.utcnow().isoformat(), cache_key))
                    conn.commit()

                    return {
                        "response": result[0],
                        "llm_model_used": result[1],
                        "confidence": result[2],
                        "sql_executed": None  # Cache simple por ahora
                    }

            return None

        except Exception as e:
            logger.warning(f"Error getting cached response: {e}")
            return None

    async def _cache_response(self, cache_key: str, response: str,
                            sql_executed: str, model_used: str, confidence: float):
        """Guardar respuesta en cache"""
        try:
            # Cache en memoria
            self.memory_cache[cache_key] = {
                "data": {
                    "response": response,
                    "sql_executed": sql_executed,
                    "llm_model_used": model_used,
                    "confidence": confidence
                },
                "timestamp": time.time()
            }

            # Cache en base de datos
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()

                expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat()

                cursor.execute("""
                    INSERT OR REPLACE INTO llm_response_cache (
                        cache_key, user_query, llm_response, model_used,
                        confidence_score, expires_at, created_at, last_accessed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cache_key, response[:100], response, model_used,
                    confidence, expires_at,
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat()
                ))
                conn.commit()

        except Exception as e:
            logger.warning(f"Error caching response: {e}")

    async def _record_interaction(self, session_id: str, user_id: str, user_query: str,
                                assistant_response: str, sql_executed: str,
                                llm_model_used: str, interaction_type: InteractionType,
                                confidence: float = 0.0, processing_time_ms: int = 0,
                                query_intent: str = None, from_cache: bool = False):
        """Registrar interacción completa en base de datos"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO conversational_interactions (
                        session_id, user_id, interaction_type, user_query,
                        assistant_response, sql_executed, llm_model_used,
                        query_intent, confidence_score, processing_time_ms,
                        status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, user_id, interaction_type.value, user_query,
                    assistant_response, sql_executed, llm_model_used,
                    query_intent, confidence, processing_time_ms,
                    "completed", datetime.utcnow().isoformat()
                ))

                interaction_id = cursor.lastrowid

                # Registrar resultado de SQL si existe
                if sql_executed and sql_executed != "NO_SQL_NEEDED":
                    cursor.execute("""
                        INSERT INTO query_execution_results (
                            interaction_id, sql_query, execution_status,
                            created_at
                        ) VALUES (?, ?, ?, ?)
                    """, (
                        interaction_id, sql_executed, "completed",
                        datetime.utcnow().isoformat()
                    ))

                conn.commit()

        except Exception as e:
            logger.error(f"Error recording interaction: {e}")

    async def _select_best_model(self, query: str, context: Dict) -> Optional[Dict]:
        """Seleccionar el mejor modelo LLM para la query"""
        try:
            # Por ahora, lógica simple de selección
            query_lower = query.lower()

            # Queries complejas -> modelo más potente
            if any(word in query_lower for word in ["análisis", "tendencia", "predicción", "comparar"]):
                preferred_models = ["gpt-4o", "claude-3-5-sonnet"]
            else:
                preferred_models = ["gpt-4o-mini", "claude-3-haiku", "gpt-4o"]

            # Buscar modelo disponible
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()

                for model in preferred_models:
                    cursor.execute("""
                        SELECT model_name, provider, model_config
                        FROM llm_model_configs
                        WHERE model_name = ? AND is_active = TRUE
                    """, (model,))

                    result = cursor.fetchone()
                    if result:
                        return {
                            "model_name": result[0],
                            "provider": result[1],
                            "config": json.loads(result[2]) if result[2] else {}
                        }

            # Fallback a cualquier modelo activo
            cursor.execute("""
                SELECT model_name, provider, model_config
                FROM llm_model_configs
                WHERE is_active = TRUE
                ORDER BY total_requests DESC
                LIMIT 1
            """)

            result = cursor.fetchone()
            if result:
                return {
                    "model_name": result[0],
                    "provider": result[1],
                    "config": json.loads(result[2]) if result[2] else {}
                }

            return None

        except Exception as e:
            logger.error(f"Error selecting best model: {e}")
            return None

    async def get_conversation_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        """Obtener historial de conversación"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT user_query, assistant_response, llm_model_used,
                           confidence_score, processing_time_ms, created_at
                    FROM conversational_interactions
                    WHERE session_id = ? AND status = 'completed'
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (session_id, limit))

                results = cursor.fetchall()

                return [
                    {
                        "user_query": row[0],
                        "assistant_response": row[1],
                        "llm_model_used": row[2],
                        "confidence_score": row[3],
                        "processing_time_ms": row[4],
                        "created_at": row[5]
                    }
                    for row in results
                ]

        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []

    async def get_analytics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Obtener analytics de uso del asistente"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()

                # Métricas básicas
                cursor.execute("""
                    SELECT COUNT(*) as total_interactions,
                           AVG(confidence_score) as avg_confidence,
                           AVG(processing_time_ms) as avg_processing_time,
                           COUNT(CASE WHEN sql_executed IS NOT NULL THEN 1 END) as sql_queries
                    FROM conversational_interactions
                    WHERE user_id = ? AND created_at >= date('now', '-{} days')
                """.format(days), (user_id,))

                basic_metrics = cursor.fetchone()

                # Distribución de modelos
                cursor.execute("""
                    SELECT llm_model_used, COUNT(*) as usage_count
                    FROM conversational_interactions
                    WHERE user_id = ? AND created_at >= date('now', '-{} days')
                    GROUP BY llm_model_used
                    ORDER BY usage_count DESC
                """.format(days), (user_id,))

                model_distribution = dict(cursor.fetchall())

                return {
                    "user_id": user_id,
                    "period_days": days,
                    "total_interactions": basic_metrics[0] if basic_metrics else 0,
                    "average_confidence": round(basic_metrics[1], 3) if basic_metrics and basic_metrics[1] else 0.0,
                    "average_processing_time_ms": round(basic_metrics[2], 1) if basic_metrics and basic_metrics[2] else 0.0,
                    "sql_queries_executed": basic_metrics[3] if basic_metrics else 0,
                    "model_distribution": model_distribution,
                    "generated_at": datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(f"Error getting analytics: {e}")
            return {
                "user_id": user_id,
                "error": str(e)
            }